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
    # Replace ampersand variations with 'and' for consistent matching
    text = text.replace("&", "and")
    # Remove extra spaces that might come from "& " -> "and " (space remains)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


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


# ─────────────────────────────────────────────────────────────────────────
# JD DEPARTMENT MAPPING - Maps UI department values to JD department field
# ─────────────────────────────────────────────────────────────────────────

JD_DEPARTMENT_MAP: dict[str, list[str]] = {
    # Digital Banking Departments
    "Internal Control": ["Internal Control", "Internal Audit", "Control"],
    
    "Digital Banking Reconciliation and Dispute Management": [
        "Digital Banking Reconciliation and Dispute Management",
        "Digital Banking Reconciliation",
        "Reconciliation and Dispute Management",
        "Reconciliation",
    ],
    
    "Merchant and Agent Management": [
        "Merchant and Agent Management",
        "Merchant and Agent",
        "Merchant Management",
        "Agent Management",
    ],
    
    # CRITICAL: Handle all variations of Mobile & Internet Banking
    "Mobile &Internet Banking": [
        "Mobile and Internet Banking",
        "Mobile & Internet Banking",
        "Mobile &Internet Banking",
    ],
    
    "Mobile Money": [
        "Mobile Money", 
        "Mobile Money Business", 
        "Mobile Payment",
        "Mobile Money & Payment",
    ],
    
    "Card Banking": [
        "Card Banking", 
        "Card", 
        "Cards",
        "Card Business",
    ],
}
# ─────────────────────────────────────────────────────────────────────────
# JD UNIT MAPPING - Maps UI unit values to JD Unit field
# ─────────────────────────────────────────────────────────────────────────
JD_UNIT_MAP: dict[str, list[str]] = {
    # Internal Control
    "Internal Control": ["Internal Control"],
    
    # Digital Banking Reconciliation and Dispute Management
    "Digital Banking Reconciliation and Dispute Management": [
        "Digital Banking Reconciliation and Dispute Management",
    ],
    "Merchant and Agent Reconciliation": [
        "Merchant and Agent Reconciliation",
        "Merchant Agent Reconciliation",
    ],
    "Mobile and Internet Banking Reconciliation": [
        "Mobile and Internet Banking Reconciliation",
        "Mobile & Internet Banking Reconciliation",
        "Mobile &Internet Banking Reconciliation",
    ],
    "International Card Transaction Reconciliation": [
        "International Card Transaction Reconciliation",
        "International Card Reconciliation",
    ],
    "Domestic Card Transaction Reconciliation": [
        "Domestic Card Transaction Reconciliation",
        "Domestic Card Reconciliation",
    ],
    "Mobile Money Reconciliation": [
        "Mobile Money Reconciliation",
    ],
    
    # Merchant and Agent Management
    "Merchant and Agent Management": ["Merchant and Agent Management"],
    "Merchant Management": ["Merchant Management"],
    "Agent Management": ["Agent Management"],
    "Digital Partners Relationship": ["Digital Partners Relationship", "Partners Relationship"],
    
    # Mobile and Internet Banking
    "Mobile and Internet Banking": [
        "Mobile and Internet Banking",
        "Mobile & Internet Banking",
        "Mobile &Internet Banking",
    ],
    "Mobile Banking Business": [
        "Mobile Banking Business", 
        "Mobile Business",
        "Mobile Banking",
    ],
    "Internet Banking Business": [
        "Internet Banking Business", 
        "Internet Business",
        "Internet Banking",
    ],
    
    # Mobile Money
    "Mobile Money": ["Mobile Money"],
    "Mobile Money Business": [
        "Mobile Money Business",
        "Mobile Money",
    ],
    
    # Card Banking
    "Card Banking": ["Card Banking"],
    "ATM Operations Support": [
        "ATM Operations Support", 
        "ATM Support", 
        "ATM Operations",
    ],
    "Card Banking Business": [
        "Card Banking Business", 
        "Card Business",
        "Card Banking",
    ],
    "Card Production and Distribution": [
        "Card Production and Distribution", 
        "Card Production", 
        "Card Distribution",
    ],
    "Card Issuance Solution Management": [
        "Card Issuance Solution Management",
        "Card Issuance Solution",
        "Issuance Solution",
    ],
}

# ─────────────────────────────────────────────────────────────────────────
# DIVISION MAPPING
# ─────────────────────────────────────────────────────────────────────────

JD_DIVISION_MAP: dict[str, list[str]] = {
    "RBB": ["RBB", "Retail & Branch Banking", "Retail and Branch Banking", "Retail Banking"],
    "Digital Banking": ["Digital Banking", "Digital", "Digital Bank"],
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

    def extract(self, query: str, bsc_k: int = 5) -> ExtractionResult:
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
        
        # Check mapping
        for jd_div, ui_list in JD_DIVISION_MAP.items():
            for ui_val in ui_list:
                if _normalize(ui_val) in q:
                    return jd_div
        
        # Fallback to simple detection
        if "digital banking" in q:
            return "Digital Banking"
        if "retail & branch" in q or "rbb" in q:
            return "RBB"
        return None

    def _detect_raw_field(self, query: str, field: str) -> Optional[str]:
        m = re.search(rf"{field}\s*:\s*(.+)", query, re.IGNORECASE)
        if m:
            return re.sub(r"\s+", " ", m.group(1)).strip()
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
    # HELPER METHODS FOR MAPPING
    # ----------------------------------------------------------

    def _get_division_variants(self, division: Optional[str]) -> set:
        """Get all possible variants for a division name."""
        if not division:
            return set()
        
        division_norm = _normalize(division)
        variants = {division_norm}
        
        # Check mapping
        for jd_div, ui_list in JD_DIVISION_MAP.items():
            for ui_val in ui_list:
                if _normalize(ui_val) == division_norm:
                    variants.add(_normalize(jd_div))
                    break
        
        return variants

    def _get_department_variants(self, department: Optional[str]) -> set:
        """Get all possible variants for a department name."""
        if not department:
            return set()
        
        dept_norm = _normalize(department)
        variants = {dept_norm}
        
        # Check mapping
        for jd_dept, ui_list in JD_DEPARTMENT_MAP.items():
            for ui_val in ui_list:
                if _normalize(ui_val) == dept_norm:
                    variants.add(_normalize(jd_dept))
                    break
        
        return variants

    def _get_unit_variants(self, unit: Optional[str]) -> set:
        """Get all possible variants for a unit name."""
        if not unit:
            return set()
        
        unit_norm = _normalize(unit)
        variants = {unit_norm}
        
        # Check mapping
        for jd_unit, ui_list in JD_UNIT_MAP.items():
            for ui_val in ui_list:
                if _normalize(ui_val) == unit_norm:
                    variants.add(_normalize(jd_unit))
                    break
        
        return variants

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
    # JD FLEXIBLE MATCH (with mapping support)
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
        Flexible JD matching with mapping support for department and unit.
        """
        if not self.jd_docs:
            logger.warning("  No JD documents available")
            return None

        logger.info(f"\n  JD Match Search:")
        logger.info(f"  Query: division={division}, department={department}, unit={unit}, title={job_title}, grade={job_grade}")

        # Get mapped variants for flexible matching
        q_division_variants = self._get_division_variants(division)
        q_department_variants = self._get_department_variants(department)
        q_unit_variants = self._get_unit_variants(unit)
        q_job_title_norm = _normalize(job_title) if job_title else None
        
        # Debug logging
        logger.info(f"  Division variants: {q_division_variants}")
        logger.info(f"  Department variants: {q_department_variants}")
        logger.info(f"  Unit variants: {q_unit_variants}")

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

            # Check matches with mapping support
            match_score = 0
            reasons = []

            # Division match (using variants)
            if q_division_variants:
                if doc_division_norm in q_division_variants or any(
                    variant in doc_division_norm for variant in q_division_variants
                ):
                    match_score += 1
                    reasons.append(f"division ✓ '{doc_division_raw}'")
                else:
                    continue

            # Department match (using mapped variants)
            if q_department_variants:
                dept_matched = False
                for variant in q_department_variants:
                    if variant in doc_department_norm or doc_department_norm in variant:
                        dept_matched = True
                        match_score += 1
                        reasons.append(f"dept ✓ '{doc_department_raw}' (matched via '{variant}')")
                        break
                    # Check without "Director" prefix
                    doc_dept_clean = doc_department_norm.replace("director", "").strip()
                    if variant == doc_dept_clean:
                        dept_matched = True
                        match_score += 0.9
                        reasons.append(f"dept ~ '{doc_department_raw}' (Director variant)")
                        break
                if not dept_matched:
                    continue

            # Unit match (using mapped variants)
            if q_unit_variants:
                unit_matched = False
                for variant in q_unit_variants:
                    if variant == doc_unit_norm or variant in doc_unit_norm or doc_unit_norm in variant:
                        unit_matched = True
                        match_score += 2
                        reasons.append(f"unit ✓ '{doc_unit_raw}' (matched via '{variant}')")
                        break
                if not unit_matched:
                    continue

            # Job title match (exact required if provided)
            if q_job_title_norm:
                if doc_job_title_norm == q_job_title_norm:
                    match_score += 3
                    reasons.append(f"title ✓ '{doc_job_title_raw}'")
                else:
                    continue

            # Job grade match (bonus if provided)
            if job_grade:
                if doc_job_grade_norm == _normalize(job_grade):
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
        for info in all_docs_info[:15]:
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