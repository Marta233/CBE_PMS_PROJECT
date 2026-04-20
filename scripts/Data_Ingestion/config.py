# config.py
"""Configuration settings for BSC processing"""

from pathlib import Path

# File paths
DATA_PATH = Path("./Data/raw/Bsc_of_DB_and_RBB_divisions.xlsx")
OUTPUT_PATH = Path("./Data/processed")

# Sheet names
RBB_SHEET = " RBB 2025.2026"
DIGITAL_SHEET = "Digital 2025.2026"

# Column indices (based on Excel structure)
COL_CONFIG = {
    'strategic_obj_col': 0,  # Column A
    'kpi_col': 1,             # Column B  
    'measurement_col': 2,     # Column C
    'weight_col': 3,          # Column D
    'plan_col': 9,            # Column J
}

# Processing settings
START_ROW = 3  # Data starts from row 3 (index 2)
WEIGHT_THRESHOLD = 5  # For high priority metrics

# Create output directory if not exists
OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

# jd_config.py
"""JD Configuration - Similar structure to BSC config"""

from pathlib import Path

# File paths
JD_FILE_PATH = Path("./Data/raw/RBB_JD.docx")
# Fields to extract (matching your BSC structure)
JD_FIELDS = [
    "job_title",
    "division", 
    "department",
    "job_grade",
    "job_category",
    "job_objective"
]

# Create output directory
OUTPUT_PATH.mkdir(parents=True, exist_ok=True)