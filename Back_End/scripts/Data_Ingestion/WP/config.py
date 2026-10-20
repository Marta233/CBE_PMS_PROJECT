"""Configuration settings for Work Plan processing"""

from pathlib import Path

# ----------------------------
# PROJECT ROOT (ANCHOR POINT) — same anchor depth as BSC's config.py
# ----------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# ----------------------------
# FILE PATHS
# ----------------------------
# A folder, not a single file: each department issues its own Work Plan
# docx (this one was Merchant and Agent Management's), so new departments
# are onboarded by dropping another .docx in here, not by editing code.
DATA_DIR = PROJECT_ROOT / "Data" / "raw" / "work_plans"
OUTPUT_PATH = PROJECT_ROOT / "Data" / "processed"

# ----------------------------
# TABLE STRUCTURE (fixed by the CBE Work Plan template)
# ----------------------------
QUARTER_LABELS = ("1st Q", "2nd Q", "3rd Q", "4th Q")
QUARTER_NUMBERS = {"1st Q": "Q1", "2nd Q": "Q2", "3rd Q": "Q3", "4th Q": "Q4"}

# Department and unit names are resolved through org_registry.json.
# A title or unit cell that matches a registry name or alias is filed
# under that department. Add a spelling there, not in this file.

# ensure output folder exists
OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)