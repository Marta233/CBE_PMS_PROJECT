"""Configuration settings for BSC processing.

There is NO list of divisions or sheet names here. Every sheet of the workbook is one division;
the division is read from the sheet name through the organisation registry
(common/org_registry.json), so a new division needs a registry entry, not a code change.
"""

from pathlib import Path

# ----------------------------
# PROJECT ROOT (ANCHOR POINT)
# ----------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# ----------------------------
# FILE PATHS (only used by the batch CLI, bsc_main.py)
# ----------------------------
DATA_PATH = PROJECT_ROOT / "Data" / "raw" / "Bsc_of_DB_and_RBB_divisions.xlsx"
OUTPUT_PATH = PROJECT_ROOT / "Data" / "processed"

# ----------------------------
# COLUMN CONFIG (the BSC template: same columns on every division's sheet)
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
START_ROW = 1
WEIGHT_THRESHOLD = 5

# ensure output folder exists
OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
