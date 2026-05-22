"""Configuration settings for BSC processing"""

from pathlib import Path

# ----------------------------
# PROJECT ROOT (ANCHOR POINT)
# ----------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# ----------------------------
# FILE PATHS
# ----------------------------
DATA_PATH = PROJECT_ROOT / "Data" / "raw" / "Bsc_of_DB_and_RBB_divisions.xlsx"
OUTPUT_PATH = PROJECT_ROOT / "Data" / "processed"

# ----------------------------
# SHEETS
# ----------------------------
RBB_SHEET = " RBB 2025.2026"
DIGITAL_SHEET = "Digital 2025.2026"

# ----------------------------
# COLUMN CONFIG
# ----------------------------
COL_CONFIG = {
    'strategic_obj_col': 0,
    'kpi_col': 1,
    'measurement_col': 2,
    'weight_col': 3,
    'plan_col': 9,
}

# ----------------------------
# SETTINGS
# ----------------------------
START_ROW = 3
WEIGHT_THRESHOLD = 5

# ensure output folder exists
OUTPUT_PATH.mkdir(parents=True, exist_ok=True)