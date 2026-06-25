# los_config.py
"""Configuration settings for LOS processing"""

from pathlib import Path
# PROJECT ROOT (ANCHOR POINT)
# ----------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# ----------------------------
# FILE PATHS
# ----------------------------
LOS_DATA_PATH = PROJECT_ROOT / "Data" / "raw" / "Data_Processed.xlsx"
OUTPUT_PATH = PROJECT_ROOT / "Data" / "processed"


LOS_COL_CONFIG = {

    # Column A
    'perspective_col': 0,

    # Column B
    'strategic_obj_col': 1,

    # Column C
    'division_obj_col': 2,

    # Column D
    'department_obj_col': 3,

    # Column E
    'unit_obj_col': 4,
}


# =========================================================
# PROCESSING SETTINGS
# =========================================================

LOS_START_ROW = 1

EMPTY_ROW_THRESHOLD = 5

REMOVE_DUPLICATES = True


# =========================================================
# METADATA SETTINGS
# =========================================================

DEFAULT_DIVISION = "Digital Banking Division"

SOURCE_NAME = "LOS"


# =========================================================
# DOCUMENT SETTINGS
# =========================================================

INCLUDE_METADATA_IN_TEXT = True

DOCUMENT_TYPE = "los_objective"


# =========================================================
# OUTPUT DIRECTORY
# =========================================================

OUTPUT_PATH.mkdir(parents=True, exist_ok=True)