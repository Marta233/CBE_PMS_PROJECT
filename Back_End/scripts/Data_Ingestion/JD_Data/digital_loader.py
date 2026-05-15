import re
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from pypdf import PdfReader

from jd_config import (
    DIGITAL_JD_PATH,
    DIVISION_DIGITAL,
    RESP_STOP_KEYWORDS,
)

# ─────────────────────────────────────────────────────────────
# PDF text extraction
# ─────────────────────────────────────────────────────────────

def _extract_full_text(path: Path) -> str:
    """Read all pages and join into one text."""
    reader = PdfReader(str(path))
    return "\f".join(page.extract_text() or "" for page in reader.pages)


# ─────────────────────────────────────────────────────────────
# Split into JD blocks
# ─────────────────────────────────────────────────────────────

_BLOCK_RE = re.compile(r"I\.\s+Job Details\s*/Profile/\s*:", re.IGNORECASE)


def _split_blocks(text: str) -> List[str]:
    positions = [m.start() for m in _BLOCK_RE.finditer(text)]
    if not positions:
        return []

    return [
        text[positions[i]: positions[i + 1] if i + 1 < len(positions) else len(text)]
        for i in range(len(positions))
    ]
# ─────────────────────────────────────────────────────────────
# Text cleaning helper
# ─────────────────────────────────────────────────────────────

def _clean_text(text: str) -> str:
    """Fix encoding artifacts and remove unwanted symbols."""

    replacements = {
        "â€™": "'",
        "â€œ": '"',
        "â€\x9d": '"',
        "â€“": "-",
        "â€”": "-",
        "Â": "",
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)

    text = re.sub(r"[\u2022\u25cf\u25a0\uf0b7]", "", text)
    text = re.sub(r"[^\w\s,.;:/&()'\-]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
# ─────────────────────────────────────────────────────────────
# Scalar field extraction
# ─────────────────────────────────────────────────────────────

def _extract_field(text: str, label: str) -> Optional[str]:
    stop_labels = [
        "Organizational Relationships",
        "Job Code",
        "Reports Directly To",
        "Division",
        "Supervises",
        "Department",
        "Type of Employment",
        "Job Objective",
        "Job Grade",
        "Unit",
        "Job Category",
        "II.",
        "III.",
        "IV.",
        "V.",
        "VI.",
        "VII."
    ]

    stop_pattern = "|".join(re.escape(x) for x in stop_labels)

    pattern = (
        rf"{re.escape(label)}\s*[:\?\uff1a]\s*"
        rf"(.*?)"
        rf"(?=\s*(?:{stop_pattern})\s*[:\uff1a]?|$)"
    )

    m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)

    if not m:
        return None

    return _clean_text(m.group(1))


def _extract_objective(block: str) -> str:
    m = re.search(
        r"II\.?\s*Job Objective\s*[:\uff1a]\s*(.+?)(?=III\.?|$)",
        block,
        re.IGNORECASE | re.DOTALL
    )

    return _clean_text(m.group(1)) if m else ""


def _parse_grade(raw: Optional[str]) -> Optional[int]:
    if not raw:
        return None

    m = re.search(r"(\d+)", raw)
    return int(m.group(1)) if m else None


# ─────────────────────────────────────────────────────────────
# Responsibilities extraction
# ─────────────────────────────────────────────────────────────

_BULLET = "\uf0b7"


def _extract_responsibilities(block: str) -> List[str]:
    m_start = re.search(
        r"III\.\s*Key Job Duties and Responsibilities[^:]*:.*?(?=\n)",
        block,
        re.IGNORECASE
    )

    if not m_start:
        m_start = re.search(
            r"Key Job Duties and Responsibilities[^:]*:.*?(?=\n)",
            block,
            re.IGNORECASE
        )

    if not m_start:
        return []

    slice_start = m_start.end()

    m_end = re.search(r"\bIV\b", block[slice_start:], re.IGNORECASE)
    slice_end = slice_start + m_end.start() if m_end else len(block)

    resp_blob = block[slice_start:slice_end]

    raw_bullets = resp_blob.split(_BULLET)

    responsibilities: List[str] = []

    for raw in raw_bullets:
        clean = _clean_text(raw)

        if len(clean) < 8:
            continue

        if any(kw.lower() in clean.lower() for kw in RESP_STOP_KEYWORDS):
            break

        responsibilities.append(clean)

    return responsibilities


# ─────────────────────────────────────────────────────────────
# Parse one JD block
# ─────────────────────────────────────────────────────────────

def _parse_block(block: str) -> Optional[Dict]:
    job_title = _extract_field(block, "Job Title")
    division = _extract_field(block, "Division") or DIVISION_DIGITAL
    supervisor = _extract_field(block, "Supervises")
    unit = _extract_field(block, "Unit")
    department = _extract_field(block, "Department")
    job_grade = _parse_grade(_extract_field(block, "Job Grade"))
    job_category = _extract_field(block, "Job Category") or ""
    job_objective = _extract_objective(block)
    responsibilities = _extract_responsibilities(block)

    if not job_title:
        return None

    job_title = re.split(r"Organizational", job_title)[0].strip()

    return {
        "source": "JD",
        "division": division,
        "supervisor": supervisor,
        "unit": unit,
        "department": department,
        "job_title": job_title,
        "job_grade": job_grade,
        "job_category": job_category,
        "job_objective": job_objective,
        "responsibilities": responsibilities,
        "num_responsibilities": len(responsibilities),
    }


# ─────────────────────────────────────────────────────────────
# Loader class
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
        blocks = _split_blocks(full_text)

        print(f"Found {len(blocks)} JD blocks")

        records = []

        for block in blocks:
            rec = _parse_block(block)

            if rec:
                records.append(rec)
                grade_str = str(rec["job_grade"]) if rec["job_grade"] else "?"
                print(
                    f"✓ [{grade_str}] {rec['job_title']} "
                    f"({rec['num_responsibilities']} responsibilities)"
                )

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