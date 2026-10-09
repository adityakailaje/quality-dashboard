import sys
import time
from datetime import timedelta
from pathlib import Path
import numpy as np
import pandas as pd
import mssql_python

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import (
    SQL_CONNECTION, USL, LSL, EXPECTED_GAP_SECONDS,
    GAP_TOLERANCE_SECONDS, BASELINE_SAMPLES_PER_MACHINE, BATCH_SIZE,
    POLL_SECONDS
)

VALID_SHIFTS = {"Shift A", "Shift B", "Shift C"}
VALID_MACHINES = {"Laser-01", "Laser-02", "Laser-03", "Laser-04"}
VALID_SUPPLIERS = {"SteelCo", "MetalWorks", "AlloyPlus"}

def conn_open():
    return mssql_python.connect(**SQL_CONNECTION)

def fetch_unprocessed(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT TOP (?)
            RawID, part_id, timestamp, shift, machine_id, supplier,
            cut_edge_width_mm, defect_type, scrap_flag,
            production_order_id, lot_id, product_family, material_grade,
            material_thickness_mm, operator_id, defect_count,
            defect_opportunities, rework_flag, rework_minutes,
            cycle_time_sec, ideal_cycle_time_sec, unit_cost_inr,
            scrap_cost_inr, rework_cost_inr, energy_kwh
        FROM dbo.RawInspection
        WHERE processed = 0
        ORDER BY RawID
    """, (BATCH_SIZE,))
    cols = [d[0] for d in cur.description]
    return pd.DataFrame(cur.fetchall(), columns=cols)



def clean(df):
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["bad_timestamp"] = df["timestamp"].isna()
    
    for col in ["shift", "machine_id", "supplier", "defect_type"]:
        df[col] = (
            df[col].astype(str)
            .str.strip()
            .str.replace(r"\s+", " ", regex=True)
        )
    df["shift"] = df["shift"].str.title()
    df["machine_id"] = df["machine_id"].str.upper().str.replace("LASER", "Laser", regex=False)
    df["supplier"] = df["supplier"].str.title().replace({
        "Alloyplus":"AlloyPlus",
        "Metalworks":"MetalWorks",
        "Steelco":"SteelCo"
    })

    df["invalid_shift"] = ~df["shift"].isin(VALID_SHIFTS)
    df["invalid_machine"] = ~df["machine_id"].isin(VALID_MACHINES)
    df["invalid_supplier"] = ~df["supplier"].isin(VALID_SUPPLIERS)

    x = df["cut_edge_width_mm"]
    df["null_measurement"] = x.isna()
    df["out_of_range_measurement"] = x.notna() & ((x < LSL*0.8) | (x > USL*1.2))
    df["out_of_spec"] = x.notna() & ((x < LSL) | (x > USL))

    extension_columns = [
        "production_order_id", "lot_id", "product_family", "material_grade",
        "material_thickness_mm", "operator_id", "defect_count",
        "defect_opportunities", "rework_flag", "rework_minutes",
        "cycle_time_sec", "ideal_cycle_time_sec", "unit_cost_inr",
        "scrap_cost_inr", "rework_cost_inr", "energy_kwh",
    ]
    df["legacy_fields_missing"] = df[extension_columns].isna().any(axis=1)

    numeric_columns = [
        "material_thickness_mm", "defect_count", "defect_opportunities",
        "rework_minutes", "cycle_time_sec", "ideal_cycle_time_sec",
        "unit_cost_inr", "scrap_cost_inr", "rework_cost_inr", "energy_kwh",
    ]
    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    legacy_defect_count = df["defect_count"].isna()
    df.loc[legacy_defect_count, "defect_count"] = (
        df.loc[legacy_defect_count, "defect_type"].ne("None").astype(int)
    )

    df["bad_new_numeric"] = (
        df["material_thickness_mm"].isna()
        | (df["material_thickness_mm"] <= 0)
        | df["defect_count"].isna()
        | (df["defect_count"] < 0)
        | df["defect_opportunities"].isna()
        | (df["defect_opportunities"] < 1)
        | (df["defect_count"] > df["defect_opportunities"])
        | df["rework_minutes"].isna()
        | (df["rework_minutes"] < 0)
        | df["cycle_time_sec"].isna()
        | (df["cycle_time_sec"] <= 0)
        | df["ideal_cycle_time_sec"].isna()
        | (df["ideal_cycle_time_sec"] <= 0)
        | df["unit_cost_inr"].isna()
        | (df["unit_cost_inr"] < 0)
        | df["scrap_cost_inr"].isna()
        | (df["scrap_cost_inr"] < 0)
        | df["rework_cost_inr"].isna()
        | (df["rework_cost_inr"] < 0)
        | df["energy_kwh"].isna()
        | (df["energy_kwh"] < 0)
    )
    df["first_pass_flag"] = (
        df["defect_count"].fillna(0).eq(0)
        & df["scrap_flag"].fillna(0).eq(0)
        & df["rework_flag"].fillna(0).eq(0)
        & ~df["bad_new_numeric"]
        & ~df["legacy_fields_missing"]
    )

    # Date key. Bad timestamps stay null and are not silently repaired.
    df["DateKey"] = pd.to_datetime(df["timestamp"], errors="coerce").dt.strftime("%Y%m%d")
    df["DateKey"] = pd.to_numeric(df["DateKey"], errors="coerce").astype("Int64")
    return df


def ensure_date_dimension(conn, start_date, end_date):
    cur = conn.cursor()
    cur.execute("SELECT MIN([Date]), MAX([Date]) FROM dbo.DimDate")
    existing_start, existing_end = cur.fetchone()

    if start_date is None or end_date is None:
        if existing_start is None:
            return
        start_date = existing_start
        end_date = existing_end
    elif existing_start is not None:
        start_date = min(start_date, existing_start)
        end_date = max(end_date, existing_end)

    current_date = start_date
    while current_date <= end_date:
        date_key = int(current_date.strftime("%Y%m%d"))
        cur.execute("""
            IF NOT EXISTS (SELECT 1 FROM dbo.DimDate WHERE DateKey = ?)
            BEGIN
                INSERT INTO dbo.DimDate
                    (DateKey, [Date], [Year], [Quarter], [Month], MonthName,
                     [Day], WeekdayName, IsWeekend)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            END
        """, (
            date_key,
            date_key, current_date, current_date.year,
            (current_date.month - 1) // 3 + 1, current_date.month,
            current_date.strftime("%B"), current_date.day,
            current_date.strftime("%A"), current_date.weekday() >= 5
        ))
        current_date += timedelta(days=1)
    conn.commit()


def ensure_calendar_for_facts(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT MIN(CAST([timestamp] AS date)), MAX(CAST([timestamp] AS date))
        FROM dbo.FactInspection
    """)
    start_date, end_date = cur.fetchone()
    ensure_date_dimension(conn, start_date, end_date)

def previous_machine_value(conn, machine):
    cur = conn.cursor()
    cur.execute("""
        SELECT TOP (1) timestamp, cut_edge_width_mm
        FROM dbo.FactInspection
        WHERE machine_id = ?
            AND cut_edge_width_mm IS NOT NULL
        ORDER BY timestamp DESC, InspectionKey DESC
    """, (machine,))
    row = cur.fetchone()
    return row if row else None

def active_limit(conn, machine):
    cur = conn.cursor()
    cur.execute("""
        SELECT TOP (1) CenterLine, UCL, LCL, MRBar, SigmaHat
        FROM dbo.SPCLimits
        WHERE MachineID = ? AND Active = 1
        ORDER BY SPCLimitID DESC
    """, (machine,))
    row = cur.fetchone()
    return row

def machine_recent_values(conn, machine, n):
    cur = conn.cursor()
    cur.execute("""
        SELECT TOP (?) cut_edge_width_mm
        FROM dbo.FactInspection
        WHERE machine_id = ? AND cut_edge_width_mm IS NOT NULL
        ORDER BY timestamp DESC, InspectionKey DESC
    """, (n, machine))
    vals = [float(r[0]) for r in cur.fetchall()]
    return list(reversed(vals))


def build_limits_if_ready(conn):
    cur = conn.cursor()
    cur.execute("SELECT MachineID FROM dbo.DimMachine ORDER BY MachineID")
    machines = [r[0] for r in cur.fetchall()]
    for machine in machines:
        cur.execute("SELECT COUNT(*) FROM dbo.FactInspection WHERE machine_id=?", (machine,))
        n = int(cur.fetchone()[0])
        cur.execute("SELECT COUNT(*) FROM dbo.SPCLimits WHERE MachineID=? AND Active=1", (machine,))
        active = int(cur.fetchone()[0])

        if n < BASELINE_SAMPLES_PER_MACHINE or active:
            continue

        cur.execute("""
            SELECT TOP (?) timestamp, cut_edge_width_mm
            FROM dbo.FactInspection
            WHERE machine_id=? AND cut_edge_width_mm IS NOT NULL
            ORDER BY timestamp ASC, InspectionKey ASC
        """, (BASELINE_SAMPLES_PER_MACHINE, machine))
        
        arr = np.array([float(r[1]) for r in cur.fetchall()], dtype=float)
        mr = np.abs(np.diff(arr))
        mr_bar = float(mr.mean())
        xbar = float(arr.mean())
        ucl = xbar + 2.66*mr_bar
        lcl = xbar - 2.66*mr_bar
        sigma = mr_bar/1.128
        
        cur.execute("""
            INSERT INTO dbo.SPCLimits
            (MachineID, CenterLine, UCL, LCL, MRBar, SigmaHat,
            BaselineSamples, Active)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        """, (machine, xbar, ucl, lcl, mr_bar, sigma, len(arr)))
        # Mark the baseline records.
        cur.execute("""
            UPDATE dbo.FactInspection
            SET IsBaseline=1
            WHERE InspectionKey IN
            (
                SELECT TOP (?) InspectionKey
                FROM dbo.FactInspection
                WHERE machine_id=?
                ORDER BY timestamp ASC, InspectionKey ASC
            )
        """, (BASELINE_SAMPLES_PER_MACHINE, machine))

        conn.commit()
        print(f"[SPC] baseline locked for {machine}: CL={xbar:.5f}, UCL={ucl:.5f}, LCL={lcl:.5f}")


def rule_signals(conn, machine, current):
    limit = active_limit(conn, machine)
    if not limit:
        return False, False, False, None
    
    cl, ucl, lcl, _, _ = limit
    rule1 = current > ucl or current < lcl
    
    vals8 = machine_recent_values(conn, machine, 7) + [current]
    vals6 = machine_recent_values(conn, machine, 5) + [current]
    
    rule2 = len(vals8) == 8 and (all(v > cl for v in vals8) or all(v < cl for v in vals8))
    rule3 = False
    
    if len(vals6) == 6:
        inc = all(vals6[i] < vals6[i+1] for i in range(5))
        dec = all(vals6[i] > vals6[i+1] for i in range(5))
        rule3 = inc or dec
    return rule1, rule2, rule3, limit



def process_batch(conn, df):
    if df.empty:
        return 0
    
    df = clean(df)
    valid_dates = df["timestamp"].dropna().dt.date
    if not valid_dates.empty:
        ensure_date_dimension(conn, valid_dates.min(), valid_dates.max())
    cur = conn.cursor()
    processed_ids = []
    
    for _, r in df.sort_values("RawID").iterrows():
        raw_id = int(r["RawID"])
        part_id = str(r["part_id"])
        machine = str(r["machine_id"])
        ts = r["timestamp"]
        x = None if pd.isna(r["cut_edge_width_mm"]) else float(r["cut_edge_width_mm"])
        
        if pd.isna(ts):
            # Preserve bad raw data in ETL log and mark raw row processed.
            cur.execute("""
                INSERT INTO dbo.ETL_Log(Component, Severity, Message)
                VALUES ('clean_transform_spc','ERROR',?)
            """, (f"Bad timestamp for part {part_id}",))
            cur.execute("UPDATE dbo.RawInspection SET processed=1, processing_error=? WHERE RawID=?",
                ("Unparseable timestamp", raw_id))
            continue

        # Duplicate handling: fact table keeps one row per part.
        cur.execute("SELECT COUNT(*) FROM dbo.FactInspection WHERE part_id=?", (part_id,))
        duplicate = int(cur.fetchone()[0]) > 0
        if duplicate:
            cur.execute("""
                UPDATE dbo.RawInspection
                SET processed=1, processing_error=?
                WHERE RawID=?
            """, ("Duplicate part_id; fact row already exists", raw_id))
            cur.execute("""
                INSERT INTO dbo.ETL_Log(Component, Severity, Message)
                VALUES ('clean_transform_spc','WARN',?)
            """, (f"Duplicate part_id {part_id}",))
            continue

        prev = previous_machine_value(conn, machine)
        mr = None if (prev is None or x is None) else abs(x - float(prev[1]))
        
        limit = active_limit(conn, machine)
        rule1=rule2=rule3=False
        status='BASELINE'
        ucl=cl=lcl=None
        
        if limit and x is not None:
            rule1, rule2, rule3, _ = rule_signals(conn, machine, x)
            cl,ucl,lcl,_,_ = limit
            status = 'OOC' if (rule1 or rule2 or rule3) else 'IN_CONTROL'
        
        # Live cadence check against the globally last processed inspection.
        cur.execute("SELECT TOP(1) timestamp FROM dbo.FactInspection ORDER BY timestamp DESC, InspectionKey DESC")
        last_ts = cur.fetchone()
        gap_flag=False
        if last_ts:
            dt=(pd.Timestamp(ts)-pd.Timestamp(last_ts[0])).total_seconds()
            gap_flag = dt > (EXPECTED_GAP_SECONDS + GAP_TOLERANCE_SECONDS)

        data_quality_issue_count = sum(
            int(bool(r[column]))
            for column in (
                "invalid_shift", "invalid_machine", "invalid_supplier",
                "null_measurement", "out_of_range_measurement", "bad_new_numeric",
                "legacy_fields_missing",
            )
        ) + int(gap_flag)

        cur.execute("""
            INSERT INTO dbo.FactInspection
            (part_id,timestamp,shift,machine_id,supplier,cut_edge_width_mm,
            defect_type,scrap_flag,null_measurement,out_of_range_measurement,
            out_of_spec,duplicate_part_id,timestamp_gap_flag,DateKey,
            MovingRange,SPC_Status,Rule1_OOC,Rule2_Shift,Rule3_Trend,IsBaseline,
            production_order_id,lot_id,product_family,material_grade,
            material_thickness_mm,operator_id,defect_count,defect_opportunities,
            rework_flag,rework_minutes,cycle_time_sec,ideal_cycle_time_sec,
            unit_cost_inr,scrap_cost_inr,rework_cost_inr,energy_kwh,
            first_pass_flag,data_quality_issue_count)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            part_id, pd.Timestamp(ts).to_pydatetime(), str(r["shift"]), machine,
            str(r["supplier"]), x, str(r["defect_type"]), int(r["scrap_flag"]),
            bool(r["null_measurement"]), bool(r["out_of_range_measurement"]),
            bool(r["out_of_spec"]), False, gap_flag,
            None if pd.isna(r["DateKey"]) else int(r["DateKey"]),
            mr, status, rule1, rule2, rule3, False,
            None if pd.isna(r["production_order_id"]) else str(r["production_order_id"]),
            None if pd.isna(r["lot_id"]) else str(r["lot_id"]),
            None if pd.isna(r["product_family"]) else str(r["product_family"]),
            None if pd.isna(r["material_grade"]) else str(r["material_grade"]),
            None if pd.isna(r["material_thickness_mm"]) else float(r["material_thickness_mm"]),
            None if pd.isna(r["operator_id"]) else str(r["operator_id"]),
            0 if pd.isna(r["defect_count"]) else int(r["defect_count"]),
            4 if pd.isna(r["defect_opportunities"]) else int(r["defect_opportunities"]),
            0 if pd.isna(r["rework_flag"]) else int(r["rework_flag"]),
            0.0 if pd.isna(r["rework_minutes"]) else float(r["rework_minutes"]),
            None if pd.isna(r["cycle_time_sec"]) else float(r["cycle_time_sec"]),
            None if pd.isna(r["ideal_cycle_time_sec"]) else float(r["ideal_cycle_time_sec"]),
            None if pd.isna(r["unit_cost_inr"]) else float(r["unit_cost_inr"]),
            None if pd.isna(r["scrap_cost_inr"]) else float(r["scrap_cost_inr"]),
            None if pd.isna(r["rework_cost_inr"]) else float(r["rework_cost_inr"]),
            None if pd.isna(r["energy_kwh"]) else float(r["energy_kwh"]),
            bool(r["first_pass_flag"]), data_quality_issue_count,
        ))

        if status == 'OOC':
            event_rules=[]
            if rule1: event_rules.append((1,'INDIVIDUAL_OOC'))
            if rule2: event_rules.append((2,'SHIFT_RULE'))
            if rule3: event_rules.append((3,'TREND_RULE'))
            for rule_no,event_type in event_rules:
                cur.execute("""
                    INSERT INTO dbo.SPCEvents
                    (part_id,machine_id,timestamp,event_type,rule_number,measurement,UCL,CL,LCL,status)
                    VALUES (?,?,?,?,?,?,?,?,?, 'OPEN')
            """, (part_id,machine,pd.Timestamp(ts).to_pydatetime(),event_type,rule_no,x,ucl,cl,lcl))
        
        
        cur.execute("UPDATE dbo.RawInspection SET processed=1, processing_error=NULL WHERE RawID=?", (raw_id,))
        processed_ids.append(raw_id)
        
    conn.commit()
    return len(processed_ids)


def main():
    conn = conn_open()
    print('Incremental cleaning + SPC worker started')
    try:
        ensure_calendar_for_facts(conn)
        while True:
            build_limits_if_ready(conn)
            batch = fetch_unprocessed(conn)
            if not batch.empty:
                n = process_batch(conn, batch)
                print(f'[ETL] processed {n} new facts')
            time.sleep(POLL_SECONDS)
    finally:
        conn.close()

if __name__ == '__main__':
    main()