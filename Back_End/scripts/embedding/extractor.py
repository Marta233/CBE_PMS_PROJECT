"""
extractor.py  (v6 — flexible matching with debugging)
---------------------------------------
- Shows actual field values from JD docs when no match found
- Department matching: checks exact, substring, and variations
- Unit + Title exact match required
- Division flexible matching
"""

from __future__ import annotations
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


# =========================================================
# NORMALIZATION
# =========================================================

def _normalize(text: str) -> str:
    """Normalize text for comparison (lowercase, single spaces, trimmed)."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip().lower()


# =========================================================
# MAPS
# =========================================================

LOS_DEPARTMENT_MAP: dict[str, list[str]] = {
    "Online Banking": [
        "online banking", "mobile &internet banking",
        "mobile & internet banking", "mobile and internet banking",
        "internet banking", "mobile banking", "mobile &internet",
    ],
    "Card": [
        "card", "card banking", "director card banking",
        "atm", "atm operations",
    ],
    "Digital_service_devlopment": [
        "digital service development", "digital service dev", "dsd",
    ],
    "Digital Banking Reconciliation": [
        "digital banking reconciliation", "reconciliation", "dbr",
    ],
    "Merchant and Agent Management": [
        "merchant and agent management", "merchant and agent banking",
        "merchant agent management", "merchant management",
        "agent management", "pos merchant",
    ],
}


# =========================================================
# JD FIELD EXTRACTION
# =========================================================

def _extract_jd_field(text: str, field_name: str) -> str:
    """Extract field value from JD text."""
    if not text:
        return ""
    
    pattern = rf"(?:^|\n){re.escape(field_name)}\s*:\s*([^\n]+)"
    m = re.search(pattern, text, re.IGNORECASE)
    if m:
        value = m.group(1).strip()
        value = re.sub(r'[,;:]$', '', value)
        return value  # Return original case, not normalized
    
    return ""


def _extract_jd_division(text: str) -> str:
    return _extract_jd_field(text, "Division")


def _extract_jd_department(text: str) -> str:
    return _extract_jd_field(text, "Department")


def _extract_jd_unit(text: str) -> str:
    return _extract_jd_field(text, "Unit")


def _extract_jd_job_title(text: str) -> str:
    return _extract_jd_field(text, "Job Title")


def _extract_jd_job_grade(text: str) -> str:
    return _extract_jd_field(text, "Job Grade")


# =========================================================
# HELPERS
# =========================================================

def _get_text(doc) -> str:
    if isinstance(doc, dict):
        return doc.get("text", "")
    return getattr(doc, "page_content", "")


def _get_meta(doc) -> dict:
    if isinstance(doc, dict):
        return doc.get("metadata", {})
    return getattr(doc, "metadata", {})


# =========================================================
# RESULT CONTAINER
# =========================================================

@dataclass
class ExtractionResult:
    los_docs: List = field(default_factory=list)
    bsc_docs: List = field(default_factory=list)
    jd_doc:   object = None

    detected_division:      Optional[str] = None
    detected_department:    Optional[str] = None
    detected_department_name: Optional[str] = None
    detected_job_title:     Optional[str] = None
    detected_unit:          Optional[str] = None
    detected_job_grade:     Optional[str] = None

    @property
    def summary(self) -> str:
        lines = ["─── Extraction summary ───"]
        lines.append(f"  Division   : {self.detected_division or '(none)'}")
        lines.append(f"  Department : {self.detected_department_name or '(none)'}")
        lines.append(f"  Unit       : {self.detected_unit or '(none)'}")
        lines.append(f"  Job title  : {self.detected_job_title or '(none)'}")
        lines.append(f"  Job grade  : {self.detected_job_grade or '(none)'}")
        lines.append(f"  LOS docs   : {len(self.los_docs)}")
        lines.append(f"  BSC docs   : {len(self.bsc_docs)}")
        lines.append(f"  JD doc     : {'✓ found' if self.jd_doc else '✗ not found'}")
        return "\n".join(lines)

    def as_context(self) -> str:
        parts: list[str] = []
        if self.jd_doc:
            parts.append("=== JOB DESCRIPTION ===")
            parts.append(_get_text(self.jd_doc))
        if self.bsc_docs:
            parts.append("\n=== BSC DOCUMENTS ===")
            for i, doc in enumerate(self.bsc_docs, 1):
                parts.append(f"--- BSC {i} ---")
                parts.append(_get_text(doc))
        if self.los_docs:
            parts.append("\n=== LOS DOCUMENTS ===")
            for i, doc in enumerate(self.los_docs, 1):
                parts.append(f"--- LOS {i} ---")
                parts.append(_get_text(doc))
        return "\n".join(parts)


# =========================================================
# MAIN EXTRACTOR
# =========================================================

class QueryExtractor:

    def __init__(self, los_docs, jd_docs, bsc_vectorstore):
        self.los_docs        = list(los_docs)
        self.jd_docs         = list(jd_docs)
        self.bsc_vectorstore = bsc_vectorstore
        self._all_bsc_docs: Optional[List] = None

    def _load_all_bsc_docs(self) -> List:
        if self._all_bsc_docs is None:
            try:
                self._all_bsc_docs = list(
                    self.bsc_vectorstore.vectorstore.docstore._dict.values()
                )
            except Exception as e:
                logger.warning(f"  Could not load all BSC docs: {e}")
                self._all_bsc_docs = []
        return self._all_bsc_docs

    # ----------------------------------------------------------
    # PUBLIC
    # ----------------------------------------------------------

    def extract(self, query: str, bsc_k: int = 10) -> ExtractionResult:
        result = ExtractionResult()

        # Parse query fields
        result.detected_division        = self._detect_division_keyword(query)
        result.detected_department_name = self._detect_raw_field(query, "department")
        result.detected_unit            = self._detect_raw_field(query, "unit")
        result.detected_job_title       = self._detect_job_title(query)
        result.detected_job_grade       = self._detect_raw_field(query, "job grade")
        result.detected_department      = self._detect_los_department(
            query,
            raw_department=result.detected_department_name,
        )

        logger.info(f"  Query fields:")
        logger.info(f"    Division   : {result.detected_division}")
        logger.info(f"    Department : {result.detected_department_name}")
        logger.info(f"    Unit       : {result.detected_unit}")
        logger.info(f"    Job title  : {result.detected_job_title}")
        logger.info(f"    Job grade  : {result.detected_job_grade}")

        # LOS
        if result.detected_department:
            result.los_docs = self._filter_los(result.detected_department)
            logger.info(f"  LOS docs: {len(result.los_docs)}")

        # BSC
        result.bsc_docs = self._retrieve_bsc(
            unit=result.detected_unit,
            job_title=result.detected_job_title,
            department=result.detected_department_name,
            k=bsc_k,
        )
        logger.info(f"  BSC docs: {len(result.bsc_docs)}")

        # JD MATCH with debugging
        result.jd_doc = self._match_jd_flexible(
            division=result.detected_division,
            department=result.detected_department_name,
            unit=result.detected_unit,
            job_title=result.detected_job_title,
            job_grade=result.detected_job_grade,
        )

        logger.info(f"\n{result.summary}")
        return result

    # ----------------------------------------------------------
    # DETECTION METHODS
    # ----------------------------------------------------------

    def _detect_los_department(self, query: str, raw_department: Optional[str] = None) -> Optional[str]:
        q_norm = _normalize(query)

        pairs = [
            (_normalize(kw), dept_value)
            for dept_value, keywords in LOS_DEPARTMENT_MAP.items()
            for kw in keywords
        ]
        pairs.sort(key=lambda x: len(x[0]), reverse=True)

        for norm_kw, dept_value in pairs:
            if norm_kw in q_norm:
                return dept_value

        if raw_department:
            dept_norm = _normalize(raw_department)
            for norm_kw, dept_value in pairs:
                if norm_kw in dept_norm or dept_norm in norm_kw:
                    return dept_value

        return None

    def _detect_division_keyword(self, query: str) -> Optional[str]:
        q = _normalize(query)
        if "digital banking" in q:
            return "Digital Banking"
        if "retail & branch" in q or "rbb" in q:
            return "Retail & Branch Banking"
        return None

    def _detect_raw_field(self, query: str, field: str) -> Optional[str]:
        m = re.search(rf"{field}\s*:\s*([^\n]+)", query, re.IGNORECASE)
        if m:
            val = re.sub(r"\s+", " ", m.group(1)).strip()
            return val if val else None
        return None

    def _detect_job_title(self, query: str) -> Optional[str]:
        for pattern in [
            r"job\s+role\s*:\s*(.+)",
            r"job\s+title\s*:\s*(.+)",
            r"\brole\s*:\s*(.+)",
        ]:
            m = re.search(pattern, query, re.IGNORECASE)
            if m:
                raw = m.group(1).strip()
                val = raw.split(":", 1)[-1].strip() if ":" in raw else raw
                return re.sub(r"\s+", " ", val).strip()
        return None

    # ----------------------------------------------------------
    # BSC RETRIEVAL
    # ----------------------------------------------------------

    def _retrieve_bsc(self, unit: Optional[str], job_title: Optional[str], department: Optional[str], k: int) -> List:
        seen_ids = set()
        results = []

        if not self._all_bsc_docs:
            self._load_all_bsc_docs()

        if not self._all_bsc_docs:
            return results

        query_text = " ".join(filter(None, [unit, job_title, department]))
        if not query_text:
            query_text = "digital banking"

        query_keywords = set(_normalize(query_text).split())

        for doc in self._all_bsc_docs:
            doc_text = _normalize(_get_text(doc))
            if query_keywords & set(doc_text.split()):
                uid = _get_text(doc)[:80]
                if uid not in seen_ids:
                    seen_ids.add(uid)
                    results.append(doc)
                    if len(results) >= k:
                        break

        return results[:k]

    # ----------------------------------------------------------
    # LOS FILTER
    # ----------------------------------------------------------

    def _filter_los(self, department: str) -> list:
        dept_norm = _normalize(department)
        matched = []
        for doc in self.los_docs:
            meta_dept = _normalize(_get_meta(doc).get("department", ""))
            if meta_dept == dept_norm or dept_norm in meta_dept:
                matched.append(doc)
        return matched

    # ----------------------------------------------------------
    # JD FLEXIBLE MATCH (with debugging)
    # ----------------------------------------------------------

    def _match_jd_flexible(
        self,
        division: Optional[str],
        department: Optional[str],
        unit: Optional[str],
        job_title: Optional[str],
        job_grade: Optional[str] = None,
    ):
        """
        Flexible JD matching:
        - Shows all JD documents with their actual field values when no match found
        - Department: flexible matching (exact, substring, or "Director X" matches "X")
        - Unit and Title: exact match required
        - Division: flexible
        """
        if not self.jd_docs:
            logger.warning("  No JD documents available")
            return None

        logger.info(f"\n  JD Match Search:")
        logger.info(f"  Query: division={division}, department={department}, unit={unit}, title={job_title}, grade={job_grade}")

        # Normalize query values
        q_division = _normalize(division) if division else None
        q_department = _normalize(department) if department else None
        q_unit = _normalize(unit) if unit else None
        q_job_title = _normalize(job_title) if job_title else None
        q_job_grade = _normalize(job_grade) if job_grade else None

        candidates = []
        all_docs_info = []

        for i, doc in enumerate(self.jd_docs):
            text = _get_text(doc)
            
            doc_division_raw = _extract_jd_division(text)
            doc_department_raw = _extract_jd_department(text)
            doc_unit_raw = _extract_jd_unit(text)
            doc_job_title_raw = _extract_jd_job_title(text)
            doc_job_grade_raw = _extract_jd_job_grade(text)
            
            doc_division_norm = _normalize(doc_division_raw)
            doc_department_norm = _normalize(doc_department_raw)
            doc_unit_norm = _normalize(doc_unit_raw)
            doc_job_title_norm = _normalize(doc_job_title_raw)
            doc_job_grade_norm = _normalize(doc_job_grade_raw)

            # Store for debugging
            all_docs_info.append({
                'index': i + 1,
                'division': doc_division_raw,
                'department': doc_department_raw,
                'unit': doc_unit_raw,
                'title': doc_job_title_raw,
                'grade': doc_job_grade_raw
            })

            # Check matches with flexibility
            match_score = 0
            reasons = []

            # Division match (flexible)
            if q_division:
                if doc_division_norm == q_division:
                    match_score += 1
                    reasons.append(f"division ✓ '{doc_division_raw}'")
                elif q_division in doc_division_norm or doc_division_norm in q_division:
                    match_score += 0.5
                    reasons.append(f"division ~ '{doc_division_raw}'")
                else:
                    continue  # Division must match at least partially

            # Department match (flexible: exact OR "Director X" matches "X")
            if q_department:
                # Check exact
                if doc_department_norm == q_department:
                    match_score += 1
                    reasons.append(f"dept ✓ '{doc_department_raw}'")
                # Check if query department is contained in doc department (e.g., "Card" in "Director Card Banking")
                elif q_department in doc_department_norm:
                    match_score += 0.8
                    reasons.append(f"dept ~ '{doc_department_raw}' (contains '{department}')")
                # Check if doc department without "director" matches query
                elif doc_department_norm.replace("director", "").strip() == q_department:
                    match_score += 0.9
                    reasons.append(f"dept ~ '{doc_department_raw}' (Director variant)")
                else:
                    continue  # Department must match at least partially

            # Unit match (required if provided)
            if q_unit:
                if doc_unit_norm == q_unit:
                    match_score += 2
                    reasons.append(f"unit ✓ '{doc_unit_raw}'")
                else:
                    continue  # Unit must match exactly

            # Job title match (required if provided)
            if q_job_title:
                if doc_job_title_norm == q_job_title:
                    match_score += 3
                    reasons.append(f"title ✓ '{doc_job_title_raw}'")
                else:
                    continue  # Title must match exactly

            # Job grade match (bonus if provided)
            if q_job_grade:
                if doc_job_grade_norm == q_job_grade:
                    match_score += 1
                    reasons.append(f"grade ✓ '{doc_job_grade_raw}'")

            if match_score > 0:
                candidates.append((match_score, doc, reasons))

        # Show what we found
        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            best = candidates[0]
            logger.info(f"\n  ✓ MATCH FOUND (score={best[0]}): {', '.join(best[2])}")
            return best[1]
        
        # No match found - show all JD documents for debugging
        logger.info(f"\n  ✗ No match found. Available JD documents in your file:")
        logger.info(f"  " + "-" * 70)
        for info in all_docs_info[:15]:  # Show first 15
            logger.info(f"    JD {info['index']}:")
            logger.info(f"      Division   : {info['division']}")
            logger.info(f"      Department : {info['department']}")
            logger.info(f"      Unit       : {info['unit']}")
            logger.info(f"      Title      : {info['title']}")
            logger.info(f"      Grade      : {info['grade']}")
            logger.info(f"      { '-' * 60}")
        
        if len(all_docs_info) > 15:
            logger.info(f"    ... and {len(all_docs_info) - 15} more JD documents")
        
        return None