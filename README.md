# Real-Time Laser-Cut Quality Monitoring & SPC Dashboard

A manufacturing-quality analytics project that demonstrates a near-real-time pipeline for simulated laser-cut inspections. Python generates and processes inspection records, SQL Server stores them in a dimensional model and evaluates statistical process control (SPC) signals, and a five-page Power BI DirectQuery report is designed to expose quality loss, process stability, traceability, capability, and cost of poor quality (COPQ).

> **Synthetic-data demo:** all inspection records, costs, and reported metrics are simulated. They are for demonstrating the workflow and are not production data, financial records, or benchmarks for a real process.

## Project at a glance

- **Process:** laser cutting, monitored across Laser-01 through Laser-04.
- **Critical-to-quality characteristic:** cut edge width, in millimetres.
- **Specification:** 10.00 mm target; 9.85 mm lower and 10.15 mm upper specification limits.
- **Pipeline:** simulated inspection feed → CSV staging → SQL Server raw table → validation, transformation and SPC → SQL Server fact/dimension tables → Power BI DirectQuery.
- **Refresh behaviour:** Power BI queries SQL Server when visuals are loaded or requeried; new records appear in fact-based visuals after ingestion and ETL complete.

## Architecture

```text
01_generate_realtime_data_v2.py
             │ one simulated inspection every 2 seconds
             ▼
raw/laser_cut_inspection_stream.csv
             │
             ▼
02_ingest_csv_to_sql_v2.py ──► dbo.RawInspection
                                      │
                                      ▼
                         03_clean_transform_spc.py
                                      │
                                      ▼
      dbo.FactInspection, dimensions, dbo.SPCLimits, dbo.SPCEvents
                                      │ DirectQuery
                                      ▼
                          Power BI report design
```

The generator writes one row every two seconds by default. The ingestion worker resumes from a saved CSV byte offset and avoids inserting part IDs already present in the raw table. The ETL worker processes unprocessed rows in batches, validates and normalizes data, creates date keys, avoids duplicate fact rows, and logs invalid records. Per-machine SPC baselines are calculated after the configured minimum number of samples; subsequent rule violations can be recorded as SPC events.

## Dashboard design

The report is organized as a drill-down from current status to causes, affected production, and business impact:

1. **Executive Overview & Real-Time Status** — headline quality KPIs, machine status, SPC alerts, recent quality trends, throughput, and data freshness.
2. **Quality Loss & Pareto Analysis** — defect frequency and cost Pareto views, supplier quality, and COPQ by defect type.
3. **SPC & Stability** — control charts and rule-based process signals by machine.
4. **Operations, Materials & Traceability** — production order, lot, product, supplier, material, machine, cycle time, and throughput.
5. **Capability & COPQ** — measurement distribution against specification, Cp/Cpk, target bias, energy per good unit, and scrap/rework cost.

The supplied project brief reports a synthetic snapshot with a 13% defect rate, 87% first-pass yield, 4% scrap, 6% rework, and approximately INR 14.75 COPQ per unit. These figures describe the brief's historical snapshot, not a live dashboard or a guaranteed result. The brief also identifies report-design follow-ups, including percentage formatting, blank visuals, and clearer metric definitions.

## Repository contents

```text
.
├── config.py
├── requirements.txt
├── .env.example
├── src/
│   ├── 01_generate_realtime_data_v2.py
│   ├── 02_ingest_csv_to_sql_v2.py
│   └── 03_clean_transform_spc.py
├── sql/
│   ├── 01_create_database.sql
│   ├── 02_create_schema.sql
│   ├── 03_seed_dimensions.sql
│   ├── 04_create_users.sql
│   ├── 05_views_and_checks.sql
│   ├── 06_v2_modifications.sql
│   └── delete_database_tables.sql
├── raw/       # generated CSV staging data; not committed
├── archive/   # generated CSV archive; not committed
├── logs/      # runtime logs; not committed
└── state/     # restart offset; not committed
```

The project uses Python, pandas, NumPy, python-dotenv, and Microsoft's `mssql-python` driver, plus SQL Server and Power BI Desktop. The `powerbi/Quality_Analytics_Realtime.pbix` file in the working folder was empty (0 bytes), so it is not a usable report and is not included. The report pages and intended visuals are described above and in the project brief.

## Setup

### 1. Prepare Python

From the project root in PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` with the SQL Server instance and credentials for your local environment. `.env` is ignored by Git. Do not commit real passwords or other secrets.

### 2. Prepare SQL Server

Run the SQL scripts from SQL Server Management Studio in this order:

1. `sql/01_create_database.sql`
2. `sql/02_create_schema.sql`
3. `sql/03_seed_dimensions.sql`
4. `sql/06_v2_modifications.sql`

`sql/04_create_users.sql` is an optional SQLCMD-mode security setup script. Supply its password variables locally in SSMS; never put real passwords into the script or repository. `sql/05_views_and_checks.sql` checks the schema and data. `sql/delete_database_tables.sql` is destructive: it drops tables for a clean rebuild.

### 3. Run the pipeline

Start each worker in its own PowerShell terminal from the project root:

```powershell
.\.venv\Scripts\python.exe .\src\01_generate_realtime_data_v2.py
```

```powershell
.\.venv\Scripts\python.exe .\src\02_ingest_csv_to_sql_v2.py
```

```powershell
.\.venv\Scripts\python.exe .\src\03_clean_transform_spc.py
```

Stop all three processes to shut down the demo. The CSV, SQL rows, and CSV offset are persistent local runtime data; normal restarts continue from saved state. To rebuild, use the SQL reset and setup scripts above, then clear or replace local runtime data if a fresh simulation is needed.

### 4. Connect Power BI

Connect Power BI Desktop to the configured SQL Server database using **DirectQuery**, with the report model based on `dbo.FactInspection` and its dimensions. Use `dbo.SPCLimits` and `dbo.SPCEvents` for SPC visuals. `dbo.RawInspection` and `dbo.ETL_Log` are staging and diagnostic tables, not report sources. The working folder currently does not contain a valid `.pbix` report file.

## Configuration

Copy `.env.example` to `.env` and configure these values as needed:

| Variable | Default | Purpose |
| --- | --- | --- |
| `SQL_SERVER` | `localhost\SQLEXPRESS` | SQL Server instance |
| `SQL_DATABASE` | `QualityAnalytics` | Database name |
| `SQL_UID` | `qa_etl` | ETL login |
| `SQL_PWD` | unset | ETL login password |
| `PART_INTERVAL_SECONDS` | `2` | Generator interval |
| `BASELINE_SAMPLES_PER_MACHINE` | `40` | Samples used to establish per-machine SPC limits |
| `DRIFT_START_LASER03` | `60` | Sample threshold for simulated Laser-03 drift |
| `DRIFT_SLOPE` | `0.0025` | Simulated Laser-03 drift increment |
| `EXPECTED_GAP_SECONDS` | `2` | Expected time between records |
| `GAP_TOLERANCE_SECONDS` | `1` | Allowed timing-gap tolerance |
| `POLL_SECONDS` | `1` | Worker polling interval |
| `BATCH_SIZE` | `25` | ETL batch size |

## Limitations

- All data is simulated; measurements, costs, and capability results must not be interpreted as evidence about a real production process.
- End-to-end freshness depends on the generation interval, worker polling and ETL batching, plus Power BI's DirectQuery re-query interval.
- The project brief notes that some report visuals were blank or needed refinement. Review measures, relationships, slicers, rate formatting, time windows, and metric definitions before using the design as an operational report.
- Capability indices assume statistical conditions that may not hold for the simulated distribution; the brief recommends checking normality and considering per-machine capability.
- The project brief describes three SPC signals in a Nelson-rule style. Review rule definitions and baseline handling before adapting the demo for production use.

## Glossary

- **CTQ:** critical-to-quality measurement; here, cut edge width.
- **FPY:** first-pass yield, the share of units passing without rework or scrap.
- **SPC:** statistical process control, monitoring process variation for special-cause signals.
- **COPQ:** cost of poor quality, including costs such as scrap and rework.
- **Cp / Cpk:** process capability indices; Cpk accounts for process centring relative to specification limits.
- **OOC:** out of control, indicating a point or pattern that violates a control rule.
- **LSL / USL:** lower and upper specification limits; distinct from statistical control limits.
