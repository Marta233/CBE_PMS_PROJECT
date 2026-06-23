import re
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from pypdf import PdfReader

from .jd_config import (
    DIGITAL_JD_PATH,
    DIVISION_DIGITAL,
    RESP_STOP_KEYWORDS,
)

# ─────────────────────────────────────────────────────────────
# PDF text extraction
# ─────────────────────────────────────────────────────────────

def _extract_full_text(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


# ─────────────────────────────────────────────────────────────
# Split into JD blocks
# FIX 1: "I." prefix is optional — some blocks omit it
# ─────────────────────────────────────────────────────────────

_BLOCK_RE = re.compile(r"(?:I\.?\s*)?Job Details\s*/Profile/\s*:", re.IGNORECASE)


def _split_blocks(text: str) -> List[str]:
    positions = [m.start() for m in _BLOCK_RE.finditer(text)]
    if not positions:
        return []
    return [
        text[positions[i]: positions[i + 1] if i + 1 < len(positions) else len(text)]
        for i in range(len(positions))
    ]


# ─────────────────────────────────────────────────────────────
# Text cleaning
# ─────────────────────────────────────────────────────────────

def _clean_text(text: str) -> str:
    text = re.sub(r"[\u2022\u25cf\u25a0\uf0b7]", "", text)
    text = re.sub(r"[^\w\s,.;:/&()'\-]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ─────────────────────────────────────────────────────────────
# Job title extraction — fully rewritten
#
# The PDF has a two-column layout that produces three title formats:
#
#  FORMAT A — title fits on one line, "Organizational" on the same line:
#    "Job Title: Senior Reconciliation and Settlement Officer  Organizational Relationships:"
#
#  FORMAT B — title wraps onto the next line, blank lines before "Organizational":
#    "Job Title:  Senior Card and Pin Personalization Officer \n \n \nOrganizational Relationships:"
#
#  FORMAT C — title continuation word on next line (no blank lines):
#    "Job Title: Team Leader POS  Merchant  \nManagement \nOrganizational Relationships:"
#    "Job Title: Manager Digital Banking Reconciliation \nand Dispute Management \nOrganizational"
#
# Strategy: grab everything from "Job Title:" up to (but not including)
# "Organizational Relationships" or "Job Code", strip blank/noise lines,
# collapse into one string, then clean.
# ─────────────────────────────────────────────────────────────

def _extract_job_title(block: str) -> Optional[str]:
    # Capture everything between "Job Title[  :]" and the first field boundary
    m = re.search(
        r"Job\s+Title\s*[:\?\uff1a]\s*(.*?)(?=Organizational\s+Relationships|Job\s+Code)",
        block,
        re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return None

    raw = m.group(1)

    # Split into lines, drop empty/whitespace-only lines, join remainder
    lines = [ln.strip() for ln in raw.splitlines()]
    lines = [ln for ln in lines if ln]

    if not lines:
        return None

    title = " ".join(lines)
    title = _clean_text(title)
    # Remove any trailing noise like section numbers that leaked in
    title = re.sub(r"\s*\d+\.\d+.*$", "", title).strip()
    return title if title else None


# ─────────────────────────────────────────────────────────────
# Generic scalar field extraction
# ─────────────────────────────────────────────────────────────

_STOP_LABELS = [
    "Organizational Relationships", "Job Code", "Reports Directly To",
    "Reports Directly to", "Division", "Supervises", "Department",
    "Type of Employment", "Job Objective", "Job Grade", "Unit",
    "Job Category", "II.", "III.", "IV.", "V.", "VI.", "VII.",
]
_STOP_PAT = "|".join(re.escape(x) for x in _STOP_LABELS)


def _extract_field(text: str, label: str) -> Optional[str]:
    pattern = (
        rf"{re.escape(label)}\s*[:\?\uff1a]\s*"
        rf"(.*?)"
        rf"(?=\s*(?:{_STOP_PAT})\s*[:\uff1a]?|$)"
    )
    m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    return _clean_text(m.group(1))


def _extract_reports_to(block: str) -> str:
    """Extract 'Reports Directly To/to' — used for dedup key."""
    m = re.search(
        r"Reports\s+Directly\s+[Tt]o\s*[:\?\uff1a]\s*(.+?)(?=Division|Department|Job\s+Grade|$)",
        block, re.IGNORECASE | re.DOTALL,
    )
    return _clean_text(m.group(1)) if m else ""


# ─────────────────────────────────────────────────────────────
# Department inference
# The Department field is blank in most Digital Banking JDs.
# Infer from Unit and Reports-to context.
# ─────────────────────────────────────────────────────────────

def _extract_department_from_context(block: str) -> str:
    dept_val = _extract_field(block, "Department")
    if dept_val and len(dept_val) > 3:
        return dept_val

    reports_to = _extract_reports_to(block).lower()
    unit = (_extract_field(block, "Unit") or "").lower()

    if any(k in unit or k in reports_to for k in [
        "merchant and agent reconciliation",
        "mobile and internet banking reconciliation",
        "international card transaction reconciliation",
        "domestic card transaction reconciliation",
        "mobile money reconciliation",
    ]):
        return "Digital Banking Reconciliation and Dispute Management"

    if any(k in unit or k in reports_to for k in [
        "merchant management", "agent management",
        "digital partners", "pos merchant",
    ]):
        return "Merchant and Agent Management"

    if any(k in unit or k in reports_to for k in ["mobile banking", "internet banking"]):
        return "Mobile &Internet Banking"

    if any(k in unit or k in reports_to for k in ["mobile money", "cbe-birr", "cbe birr"]):
        return "Mobile Money"

    if any(k in unit or k in reports_to for k in [
        "atm", "card banking", "card production",
        "card distribution", "card issuance", "card and pin",
    ]):
        return "Card Banking"

    if "internal control" in unit or "internal control" in reports_to:
        return "Internal Control"

    return ""


# ─────────────────────────────────────────────────────────────
# Job objective
# ─────────────────────────────────────────────────────────────

def _extract_objective(block: str) -> str:
    m = re.search(
        r"II\.?\s*Job\s+Objective\s*[:\uff1a]\s*(.+?)(?=III\.?|$)",
        block, re.IGNORECASE | re.DOTALL,
    )
    return _clean_text(m.group(1)) if m else ""


def _parse_grade(raw: Optional[str]) -> Optional[int]:
    if not raw:
        return None
    m = re.search(r"(\d+)", raw)
    return int(m.group(1)) if m else None


# ─────────────────────────────────────────────────────────────
# Responsibilities
# ─────────────────────────────────────────────────────────────

_BULLET = "\uf0b7"


def _extract_responsibilities(block: str) -> List[str]:
    m_start = re.search(
        r"III\.\s*Key Job Duties and Responsibilities[^:]*:.*?(?=\n)",
        block, re.IGNORECASE,
    )
    if not m_start:
        m_start = re.search(
            r"Key Job Duties and Responsibilities[^:]*:.*?(?=\n)",
            block, re.IGNORECASE,
        )
    if not m_start:
        return []

    slice_start = m_start.end()
    m_end = re.search(r"\bIV\.?\s*Key\s+[Pp]erformance", block[slice_start:], re.IGNORECASE)
    if not m_end:
        m_end = re.search(r"\bIV\b", block[slice_start:], re.IGNORECASE)

    slice_end = slice_start + m_end.start() if m_end else len(block)
    resp_blob = block[slice_start:slice_end]

    responsibilities: List[str] = []
    for raw in resp_blob.split(_BULLET):
        clean = _clean_text(raw)
        if len(clean) < 8:
            continue
        if any(kw.lower() in clean.lower() for kw in RESP_STOP_KEYWORDS):
            break
        responsibilities.append(clean)

    return responsibilities


# ─────────────────────────────────────────────────────────────
# Parse one block
# ─────────────────────────────────────────────────────────────

def _parse_block(block: str) -> Optional[Dict]:
    job_title = _extract_job_title(block)

    if not job_title:
        return None

    division         = _extract_field(block, "Division") or DIVISION_DIGITAL
    supervisor       = _extract_field(block, "Supervises")
    unit             = _extract_field(block, "Unit")
    job_grade        = _parse_grade(_extract_field(block, "Job Grade"))
    job_category     = _extract_field(block, "Job Category") or ""
    job_objective    = _extract_objective(block)
    responsibilities = _extract_responsibilities(block)
    department       = _extract_department_from_context(block)
    reports_to       = _extract_reports_to(block)   # dedup key only

    return {
        "source":               "JD",
        "division":             division,
        "supervisor":           supervisor,
        "unit":                 unit,
        "department":           department,
        "reports_to":           reports_to,
        "job_title":            job_title,
        "job_grade":            job_grade,
        "job_category":         job_category,
        "job_objective":        job_objective,
        "responsibilities":     responsibilities,
        "num_responsibilities": len(responsibilities),
    }


# ─────────────────────────────────────────────────────────────
# Loader
# ─────────────────────────────────────────────────────────────

class DigitalLoader:
    """Parse Digital Banking JD PDF."""

    def __init__(self, file_path: Optional[Path] = None):
        self.file_path = file_path or DIGITAL_JD_PATH
        self._df: Optional[pd.DataFrame] = None
        print(f"📁 DigitalLoader → {self.file_path.name}")

    def load(self) -> pd.DataFrame:
        print(f"\n📂 Parsing {self.file_path.name} ...")

        full_text = _extract_full_text(self.file_path)
        blocks    = _split_blocks(full_text)
        print(f"Found {len(blocks)} JD blocks")

        records = []
        skipped = []
        for i, block in enumerate(blocks):
            rec = _parse_block(block)
            if rec:
                records.append(rec)
                grade_str = str(rec["job_grade"]) if rec["job_grade"] else "?"
                print(
                    f"✓ [{grade_str:>2}] {rec['job_title'][:45]:<45} | "
                    f"Unit: {(rec['unit'] or '—')[:35]}"
                )
            else:
                skipped.append(i + 1)

        if skipped:
            print(f"\n⚠️  Skipped {len(skipped)} blocks with no title: {skipped}")

        self._df = pd.DataFrame(records)
        print(
            f"\n✅ Parsed {len(self._df)} JDs | "
            f"{self._df['num_responsibilities'].sum()} total responsibilities"
        )
        return self._df

    def get_dataframe(self) -> pd.DataFrame:
        if self._df is None:
            self.load()
        return self._df