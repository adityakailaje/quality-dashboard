import csv
import json
import sys
import time
from pathlib import Path
import mssql_python

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import RAW_PATH, OFFSET_PATH, POLL_SECONDS, SQL_CONNECTION

HEADERS = [
    "part_id", "timestamp", "shift", "machine_id", "supplier",
    "production_order_id", "lot_id", "product_family", "material_grade",
    "material_thickness_mm", "operator_id", "cut_edge_width_mm",
    "defect_type", "defect_count", "defect_opportunities", "scrap_flag",
    "rework_flag", "rework_minutes", "cycle_time_sec", "ideal_cycle_time_sec",
    "unit_cost_inr", "scrap_cost_inr", "rework_cost_inr", "energy_kwh",
]
LEGACY_HEADERS = [
    "part_id", "timestamp", "shift", "machine_id", "supplier",
    "cut_edge_width_mm", "defect_type", "scrap_flag",
]
INSERT_SQL = """
INSERT INTO dbo.RawInspection
(
    part_id, timestamp, shift, machine_id, supplier,
    production_order_id, lot_id, product_family, material_grade,
    material_thickness_mm, operator_id, cut_edge_width_mm,
    defect_type, defect_count, defect_opportunities, scrap_flag,
    rework_flag, rework_minutes, cycle_time_sec, ideal_cycle_time_sec,
    unit_cost_inr, scrap_cost_inr, rework_cost_inr, energy_kwh
)
SELECT
    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
WHERE NOT EXISTS
(
 SELECT 1 FROM dbo.RawInspection WHERE part_id = ?
)
"""
def load_offset():
    if not Path(OFFSET_PATH).exists() or Path(OFFSET_PATH).stat().st_size == 0:
        return 0
    try:
        offset = int(json.loads(Path(OFFSET_PATH).read_text(encoding="utf-8")).get("offset", 0))
    except (json.JSONDecodeError, TypeError, ValueError):
        return 0
    return max(offset, 0)


def save_offset(offset):
    Path(OFFSET_PATH).write_text(
        json.dumps({"offset": offset}),
        encoding="utf-8"
    )


def connect():
    return mssql_python.connect(**SQL_CONNECTION)


def reset_offset_if_table_empty(conn, offset):
    if offset == 0:
        return 0
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM dbo.RawInspection")
    if int(cur.fetchone()[0]) == 0:
        print("RawInspection is empty; replaying the source CSV from the beginning")
        return 0
    return offset


def as_float(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_int(value):
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return int(parsed) if parsed.is_integer() else None


def coerce(row):
    return (
        row["part_id"], row["timestamp"], row["shift"],
        row["machine_id"], row["supplier"],
        row.get("production_order_id") or None,
        row.get("lot_id") or None,
        row.get("product_family") or None,
        row.get("material_grade") or None,
        as_float(row.get("material_thickness_mm")),
        row.get("operator_id") or None,
        as_float(row.get("cut_edge_width_mm")),
        row.get("defect_type") or None,
        as_int(row.get("defect_count")),
        as_int(row.get("defect_opportunities")),
        as_int(row.get("scrap_flag")),
        as_int(row.get("rework_flag")),
        as_float(row.get("rework_minutes")),
        as_float(row.get("cycle_time_sec")),
        as_float(row.get("ideal_cycle_time_sec")),
        as_float(row.get("unit_cost_inr")),
        as_float(row.get("scrap_cost_inr")),
        as_float(row.get("rework_cost_inr")),
        as_float(row.get("energy_kwh")),
        row["part_id"],
    )


def run_once(conn, offset):
    if not Path(RAW_PATH).exists():
        return offset

    # Reset if the source file was deleted/recreated.
    if Path(RAW_PATH).stat().st_size < offset:
        offset = 0

    rows = []
    with open(RAW_PATH, "rb") as f:
        f.seek(offset)
        if offset == 0:
            header_line = f.readline()
            if not header_line:
                return 0
            header = next(csv.reader([header_line.decode("utf-8-sig")]), None)
            if header not in (HEADERS, LEGACY_HEADERS):
                raise ValueError(f"Unexpected CSV header: {header}")
            offset = f.tell()

        new_offset = offset
        while True:
            line = f.readline()
            if not line:
                break
            if not line.endswith(b"\n"):
                break
            new_offset = f.tell()
            values = next(csv.reader([line.decode("utf-8")]), None)
            if values is None or not any(values):
                continue
            if len(values) == len(HEADERS):
                row = dict(zip(HEADERS, values))
            elif len(values) == len(LEGACY_HEADERS):
                row = dict(zip(LEGACY_HEADERS, values))
                row.update({column: "" for column in HEADERS if column not in row})
            else:
                raise ValueError(f"Malformed CSV row at byte offset {new_offset}")
            if row["part_id"]:
                rows.append(coerce(row))

    if rows:
        cur = conn.cursor()
        for params in rows:
            cur.execute(INSERT_SQL, params)
        conn.commit()
    if new_offset != load_offset():
        save_offset(new_offset)
    if rows:
        print(f"Processed {len(rows)} CSV records through byte offset {new_offset}")
    return new_offset


def main():
    offset = load_offset()
    conn = connect()
    offset = reset_offset_if_table_empty(conn, offset)
    print("CSV ingestion worker started")
    try:
        while True:
            try:
                offset = run_once(conn, offset)
            except Exception as exc:
                conn.rollback()
                print(f"[ingest error] {exc}")
                time.sleep(2)
            time.sleep(POLL_SECONDS)
    finally:
        conn.close()


if __name__ == "__main__":
    main()