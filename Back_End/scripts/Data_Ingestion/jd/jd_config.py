"""
jd_config.py  –  Central configuration for the JD ingestion pipeline.

There are no division constants here: the division, department and unit are read from each
Job Description itself, and mapped to the canonical names by the organisation registry
(common/org_registry.json) when the document is ingested.
"""
from pathlib import Path
# PROJECT ROOT (ANCHOR POINT)
# ----------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# ----------------------------
# FILE PATHS (only used by the batch CLI, jd_main.py)
# ----------------------------
RAW_DIR = PROJECT_ROOT / "Data" / "raw"
JD_FILES = [
    RAW_DIR / "RBB_JD.docx",
    RAW_DIR / "Digital Banking JD.pdf",
]

OUTPUT_PATH = PROJECT_ROOT / "Data" / "processed"

# ── Behaviour ────────────────────────────────────────────────────────────────
# Many JDs name their unit but leave the Department cell empty. When True, the department is
# taken from the registry: the department that owns the unit named by the JD. It is filled in
# ONLY when the registry gives exactly one answer; otherwise the department stays blank.
INFER_DEPARTMENT_FROM_UNIT = True

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
    "source",
    "division",
    "supervisor",
    "unit",
    "department",
    "job_title",
    "job_grade",         # int or None
    "job_category",
    "job_objective",
    "num_responsibilities",
    "responsibilities",  # list[str]
]
