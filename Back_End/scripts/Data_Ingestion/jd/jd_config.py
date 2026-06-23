"""
jd_config.py  –  Central configuration for the JD ingestion pipeline.
"""
from pathlib import Path
# PROJECT ROOT (ANCHOR POINT)
# ----------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# ----------------------------
# FILE PATHS
# ----------------------------
RBB_JD_PATH = PROJECT_ROOT / "Data" / "raw" / "RBB_JD.docx"

DIGITAL_JD_PATH = PROJECT_ROOT / "Data" / "raw" / "Digital Banking JD.pdf"

OUTPUT_PATH = PROJECT_ROOT / "Data" / "processed"

# ── Source labels ─────────────────────────────────────────────────────────────
DIVISION_RBB     = "Retail & Branch Banking"
DIVISION_DIGITAL = "Digital Banking"

# ── Section boundary keywords (lowercase) ────────────────────────────────────
RESP_START_KEYWORDS = [
    "key job duties and responsibilities",
    "key duties and responsibilities",
]

RESP_STOP_KEYWORDS = [
    "key performance indicators",
    "summary of key competency",
    "educational and professional",
    "approvals:",
    "statement/employee acknowledgment",
]

# ── Output columns (unified schema) ──────────────────────────────────────────
OUTPUT_COLS = [
    "source",            # "RBB" | "Digital"
    "division",
    "supervisor",        # only for Digital (from "Supervisor" field)
    "unit",              # new field for department/unit
    "department",        # new field for department
    "job_title",
    "job_grade",         # int or None
    "job_category",
    "job_objective",
    "num_responsibilities",
    "responsibilities",  # list[str]
]
