import csv
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import RAW_PATH, PART_INTERVAL_SECONDS, DRIFT_START_LASER03, DRIFT_SLOPE
rng = np.random.default_rng(42)
SHIFTS = ["Shift A", "Shift B", "Shift C"]
MACHINES = ["Laser-01", "Laser-02", "Laser-03", "Laser-04"]
SUPPLIERS = ["SteelCo", "MetalWorks", "AlloyPlus"]
OPERATORS = ["OP-101", "OP-102", "OP-103", "OP-104", "OP-105", "OP-106"]
PRODUCTS = {
 "Bracket": 2.40,
 "Panel": 3.10,
 "Housing": 4.20,
 "Cover": 2.80,
}
MATERIAL_GRADES = ["CRCA", "GI", "SS304"]
THICKNESSES_MM = [1.0, 1.5, 2.0, 3.0]
# Original project's primary CTQ specification is preserved.
USL = 10.15
LSL = 9.85
TARGET = 10.00
# DPMO convention for this demo: four defect opportunities per unit.
DEFECT_OPPORTUNITIES = 4
REWORK_RATE_INR_PER_MIN = 18.0
FIELDNAMES = [
 "part_id",
 "timestamp",
 "shift",
 "machine_id",
 "supplier",
 "production_order_id",
 "lot_id",
 "product_family",
 "material_grade",
 "material_thickness_mm",
 "operator_id",
 "cut_edge_width_mm",
 "defect_type",
 "defect_count",
 "defect_opportunities",
 "scrap_flag",
 "rework_flag",
 "rework_minutes",
 "cycle_time_sec",
 "ideal_cycle_time_sec",
 "unit_cost_inr",
 "scrap_cost_inr",
 "rework_cost_inr",
 "energy_kwh",
]
def next_part_number(path: Path) -> int:
    """Read only the tail of the append-only CSV once at startup."""
    if not path.exists() or path.stat().st_size == 0:
        return 100000
    with open(path, "rb") as f:
        f.seek(max(0, path.stat().st_size - 8192))
        chunk = f.read().decode("utf-8", errors="ignore")
    lines = [line for line in chunk.splitlines() if line.strip()]
    if len(lines) < 2:
        return 100000
    last = lines[-1].split(",", 1)[0].strip()
    match = re.fullmatch(r"P(\d+)", last)
    return int(match.group(1)) + 1 if match else 100000


def choose_shift():
    return str(rng.choice(SHIFTS, p=[0.34, 0.33, 0.33]))


def choose_material():
    grade = str(rng.choice(MATERIAL_GRADES, p=[0.55, 0.25, 0.20]))
    thickness = float(rng.choice(THICKNESSES_MM, p=[0.30, 0.35, 0.25, 0.10]))
    return grade, thickness


def choose_product():
    names = list(PRODUCTS)
    product = str(rng.choice(names, p=[0.32, 0.25, 0.20, 0.23]))
    return product, float(PRODUCTS[product])


def defect_choice(width: float, machine: str, material_grade: str, machine_count: int) -> str:
    # Preserve the original project's defect vocabulary/probability structure,
    # then add modest process-risk effects for a richer demo.
    oos = width < LSL or width > USL
    base = np.array([0.90, 0.04, 0.03, 0.01, 0.01, 0.01], dtype=float)
    oos_base = np.array([0.55, 0.18, 0.14, 0.05, 0.04, 0.04], dtype=float)
    risk = 0.0
    if machine == "Laser-03" and machine_count > DRIFT_START_LASER03:
        risk += min(0.08, 0.002 * (machine_count - DRIFT_START_LASER03))
    if material_grade == "SS304":
        risk += 0.015
    probs = oos_base.copy() if oos else base.copy()
    probs[0] -= risk
    probs[1:] += risk / (len(probs) - 1)
    probs = probs / probs.sum()
    return str(rng.choice(
        ["None", "Burr", "Dross", "Edge Crack", "Warping", "Dim. Out of Tol."],
        p=probs,
    ))


def build_row(part_no: int, machine_counts: dict[str, int]) -> dict:
    machine = str(rng.choice(MACHINES))
    machine_counts[machine] += 1
    m_count = machine_counts[machine]
    shift = choose_shift()
    supplier = str(rng.choice(SUPPLIERS, p=[0.50, 0.30, 0.20]))
    product_family, ideal_cycle = choose_product()
    material_grade, thickness = choose_material()
    operator_id = str(rng.choice(OPERATORS))
    # Traceability identifiers make the stream useful for order/lot drill-down.
    order_no = (part_no - 100000) // 60
    lot_no = (part_no - 100000) // 120
    production_order_id = f"MO{1000 + order_no:05d}"
    lot_id = f"LOT{5000 + lot_no:05d}"
    # CTQ: preserve the 10.00 mm target and 9.85-10.15 mm specification limits.
    width = float(rng.normal(TARGET, 0.035))
    if machine == "Laser-03" and m_count > DRIFT_START_LASER03:
        wear_cycles = m_count - DRIFT_START_LASER03
        width += wear_cycles * DRIFT_SLOPE
    width = round(width, 4)
    defect_type = defect_choice(width, machine, material_grade, m_count)
    if defect_type == "None":
        defect_count = 0
    else:
        defect_count = 1
        if rng.random() < 0.12:
            defect_count += 1
        if rng.random() < 0.03:
            defect_count += 1
    defect_count = min(defect_count, DEFECT_OPPORTUNITIES)
    oos = width < LSL or width > USL
    severe = defect_type == "Edge Crack"
    scrap = int(
        defect_count > 0
        and (
            (oos and rng.random() < 0.72)
            or defect_count >= 3
            or (severe and rng.random() < 0.65)
        )
    )
    rework = int(defect_count > 0 and scrap == 0 and rng.random() < 0.75)
    rework_minutes = round(float(rng.uniform(2.0, 8.0)) if rework else 0.0, 2)
    # Cycle time is affected by product, thickness, material and machine behavior.
    material_factor = {"CRCA": 1.00, "GI": 1.05, "SS304": 1.12}[material_grade]
    thickness_factor = 1.0 + 0.055 * (thickness - 1.0)
    machine_factor = {"Laser-01": 1.00, "Laser-02": 1.03, "Laser-03": 1.04, "Laser-04": 1.01}[machine]
    cycle = ideal_cycle * material_factor * thickness_factor * machine_factor
    if machine == "Laser-03" and m_count > DRIFT_START_LASER03:
        cycle += 0.012 * (m_count - DRIFT_START_LASER03)
    cycle += float(rng.normal(0.0, 0.10))
    cycle = round(max(ideal_cycle * 0.70, cycle), 3)
    material_premium = {"CRCA": 0.0, "GI": 18.0, "SS304": 65.0}[material_grade]
    product_premium = {"Bracket": 0.0, "Panel": 35.0, "Housing": 70.0, "Cover": 25.0}[product_family]
    unit_cost = round(150.0 + 34.0 * thickness + material_premium + product_premium, 2)
    scrap_cost = round(unit_cost if scrap else 0.0, 2)
    rework_cost = round(rework_minutes * REWORK_RATE_INR_PER_MIN if rework else 0.0, 2)
    # Approximate machine energy per part for an energy-intensity KPI.
    power_kw = {"Laser-01": 7.5, "Laser-02": 8.0, "Laser-03": 8.4, "Laser-04": 7.8}[machine]
    energy_kwh = round(power_kw * cycle / 3600.0 + 0.0015, 5)
    return {
        "part_id": f"P{part_no}",
        "timestamp": datetime.now().isoformat(timespec="milliseconds"),
        "shift": shift,
        "machine_id": machine,
        "supplier": supplier,
        "production_order_id": production_order_id,
        "lot_id": lot_id,
        "product_family": product_family,
        "material_grade": material_grade,
        "material_thickness_mm": thickness,
        "operator_id": operator_id,
        "cut_edge_width_mm": width,
        "defect_type": defect_type,
        "defect_count": defect_count,
        "defect_opportunities": DEFECT_OPPORTUNITIES,
        "scrap_flag": scrap,
        "rework_flag": rework,
        "rework_minutes": rework_minutes,
        "cycle_time_sec": cycle,
        "ideal_cycle_time_sec": round(ideal_cycle, 3),
        "unit_cost_inr": unit_cost,
        "scrap_cost_inr": scrap_cost,
        "rework_cost_inr": rework_cost,
        "energy_kwh": energy_kwh,
    }


def main():
    path = Path(RAW_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    part_no = next_part_number(path)
    machine_counts = {m: 0 for m in MACHINES}
    max_parts = int(os.getenv("MAX_PARTS", "0"))
    emitted = 0
    if not path.exists() or path.stat().st_size == 0:
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=FIELDNAMES).writeheader()
    print(f"Streaming extended quality data to {path}")
    print(f"One part every {PART_INTERVAL_SECONDS} seconds; MAX_PARTS={max_parts or 'unlimited'}")
    while max_parts == 0 or emitted < max_parts:
        row = build_row(part_no, machine_counts)
        with open(path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writerow(row)
            f.flush()
        print(row)
        part_no += 1
        emitted += 1
        time.sleep(PART_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()