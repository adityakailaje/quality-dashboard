import os
from pathlib import Path
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "raw"
STATE_DIR = ROOT / "state"
LOG_DIR = ROOT / "logs"
RAW_PATH = RAW_DIR / "laser_cut_inspection_stream.csv"
OFFSET_PATH = STATE_DIR / "csv_offset.json"
RAW_DIR.mkdir(parents=True, exist_ok=True)
STATE_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
load_dotenv(ROOT / ".env")
SQL_SERVER = os.getenv("SQL_SERVER", "localhost\\SQLEXPRESS")
SQL_DATABASE = os.getenv("SQL_DATABASE", "QualityAnalytics")
SQL_UID = os.getenv("SQL_UID", "qa_etl")
SQL_PWD = os.getenv("SQL_PWD")
SQL_CONNECTION = {
    "server": SQL_SERVER,
    "database": SQL_DATABASE,
    "uid": SQL_UID,
    "pwd": SQL_PWD,
    "encrypt": "yes",
    "trust_server_certificate": "yes",
}
PART_INTERVAL_SECONDS = float(os.getenv("PART_INTERVAL_SECONDS", "2"))
BASELINE_SAMPLES_PER_MACHINE = int(os.getenv("BASELINE_SAMPLES_PER_MACHINE", "40"))
DRIFT_START_LASER03 = int(os.getenv("DRIFT_START_LASER03", "60"))
DRIFT_SLOPE = float(os.getenv("DRIFT_SLOPE", "0.0025"))
EXPECTED_GAP_SECONDS = float(os.getenv("EXPECTED_GAP_SECONDS", "2"))
GAP_TOLERANCE_SECONDS = float(os.getenv("GAP_TOLERANCE_SECONDS", "1"))
POLL_SECONDS = float(os.getenv("POLL_SECONDS", "1"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "25"))
USL = 10.15
LSL = 9.85
TARGET = 10.00