"""
(hybrid BSC retrieval with JD objectives + division filter)
---------------------------------------
- BSC retrieval uses only 'unit' and 'department' from query
- Extracts objectives from matched JD to boost relevance
- Filters BSC documents by detected division (Digital Banking / RBB)
- Hybrid keyword (stemmed Jaccard) + semantic (FAISS)
- Stemming fixes singular/plural mismatches
- JD flexible matching with debugging
"""

from __future__ import annotations
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional
from langchain_community.vectorstores import FAISS
from nltk.stem import PorterStemmer

_stemmer = PorterStemmer()

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


# =========================================================
# NORMALIZATION & STEMMING
# =========================================================

def _normalize(text: str) -> str:
    """Normalize text for comparison (lowercase, single spaces, trimmed)."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip().lower()


def _stem_tokens(text: str) -> set:
    """Normalize and stem a string, return set of stemmed tokens."""
    if not text:
        return set()
    normalized = _normalize(text)
    tokens = normalized.split()
    return {_stemmer.stem(t) for t in tokens}
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
# Add after your existing maps
UNIT_SYNONYMS: dict[str, list[str]] = {
    "mobile money": ["cbe birr", "cbe-birr"],
    "cbe birr": ["mobile money", "cbe-birr"],
    "cbe-birr": ["mobile money", "cbe birr"],
    "internet banking": ["online banking", "web banking"],
    "card banking": ["card business", "cards"],
}
# =========================================================
# BSC KEYWORD SIGNAL MAP
# =========================================================
# Maps a keyword found in the unit/department query to:
#   "boost"   : substrings that, if found in a BSC KPI name, raise the score
#   "penalise": substrings that, if found in a BSC KPI name, lower the score
#
# This solves the core cross-channel confusion without modifying any source
# data.  "mobile banking" and "CBE-Birr / mobile money" share zero keywords,
# so the mapping perfectly separates them.
#
# Rules:
#   BOOST_MATCH   = +0.40 per matched boost term found in KPI name
#   PENALTY_MATCH = -0.60 per matched penalise term found in KPI name
#   A doc can only receive ONE penalty (first match wins) to avoid stacking.
#   Shared KPIs (Income, Digital Transaction, Operational Expense etc.) are
#   absent from all penalise lists so they always pass through.

BOOST_MATCH   : float = 0.40
PENALTY_MATCH : float = -0.60

# Threshold for FAISS semantic scores — below this on both queries → keyword fallback
SEMANTIC_THRESHOLD: float = 0.5

# Weight given to each FAISS query when combining
# QUERY_A_WEIGHT: float = 0.55   # unit-only query (primary)
# QUERY_B_WEIGHT: float = 0.45   # JD objectives query (enrichment)

UNIT_KEYWORD_SIGNAL: dict[str, dict[str, list[str]]] = {
    # ── Mobile Banking ──────────────────────────────────────────────────────
    "mobile banking": {
        "boost"   : ["mobile banking"],
        "penalise": ["card banking", "internet banking",
                     "cbe-birr", "agents", "agent ",
                     "merchants", "atm", "pos"],
    },
    # ── Internet Banking ─────────────────────────────────────────────────────
    "internet banking": {
        "boost"   : ["internet banking"],
        "penalise": ["card banking", "mobile banking users",
                     "cbe-birr", "agents", "agent ",
                     "merchants", "atm", "pos"],
    },
    # ── Mobile Money / CBE-Birr ───────────────────────────────────────────────
    # "mobile money" must NOT boost "mobile banking users" — they are different
    "mobile money": {
        "boost"   : ["cbe-birr"],
        "penalise": ["card banking", "mobile banking users","mobile banking",
                     "internet banking", "atm","agents", "agent ", "merchants", "CBE-Birr Merchants","POS"],
    },
    "cbe-birr": {                         # alias for mobile money context
        "boost"   : ["cbe-birr"],
        "penalise": ["card banking", "mobile banking users","mobile banking"
                     "internet banking", "atm","agents", "agent ", "merchants","CBE-Birr Merchants","POS"],
    },
    # ── Card Banking ─────────────────────────────────────────────────────────
    "card banking": {
        "boost"   : ["card banking"],
        "penalise": ["mobile banking", "internet banking",
                     "cbe-birr", "agents", "agent ", "merchants"],
    },
    # ── ATM ──────────────────────────────────────────────────────────────────
    "atm operations": {
        "boost"   : ["atm"],
        "penalise": ["mobile banking", "internet banking",
                     "cbe-birr", "card banking users",
                     "merchants"],
    },
    "atm": {
        "boost"   : ["atm"],
        "penalise": ["mobile banking", "internet banking",
                     "cbe-birr", "card banking users",
                     "merchants"],
    },
    # ── Merchant Management ──────────────────────────────────────────────────
    "merchant management": {
        "boost"   : ["merchants", "cbe-birr merchants"],
        "penalise": ["mobile banking users", "internet banking users","mobile Banking","ATM","Internet Banking","internate banking",
                     "card banking users", "card","atm","POS", "agent"],
    },
    # ── Agent Management ─────────────────────────────────────────────────────
    "agent management": {
        "boost"   : ["agents", "agent ",'cbe-birr agents'],
        "penalise": ["mobile banking users", "internet banking users","mobile Banking","ATM","internate banking",
                     "card banking users", "atm","POS"],
    },
    # ── Digital Partners ─────────────────────────────────────────────────────
    # "digital partners": {
    #     "boost"   : ["third parties integration", "features added"],
    #     "penalise": ["atm", "card banking users",
    #                  "mobile banking users", "internet banking users",
    #                  "cbe-birr users"],
    # },
    # ── Card Production / Distribution ───────────────────────────────────────
    "Card Production and Distribution": {
        "boost"   : ["card banking"],
        "penalise": ["mobile banking", "internet banking",
                     "cbe-birr", "agents", "merchants"],
    },
    # ── Reconciliation units — treat as shared, no penalise ──────────────────
    "reconciliation": {
        "boost"   : [],
        "penalise": [],
    },
}


def _get_unit_signal(unit: str) -> dict[str, list[str]]:
    """
    Return the boost/penalise term lists for the given unit name.
    Matches by checking if a signal key is a substring of the unit name
    (longest key wins to prefer specific matches).
    Returns empty lists if no match found (shared/unknown unit).
    """
    unit_norm = _normalize(unit)
    # Sort keys longest-first so "mobile banking" beats "mobile"
    for key in sorted(UNIT_KEYWORD_SIGNAL, key=len, reverse=True):
        if key in unit_norm:
            return UNIT_KEYWORD_SIGNAL[key]
    return {"boost": [], "penalise": []}


def _parse_bsc_weight(doc_text: str) -> float:
    """Parse weight value from BSC document page_content text."""
    m = re.search(r"weight\s*:\s*([0-9.]+)", doc_text, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return 0.0
def _extract_jd_objectives_from_text(text: str) -> str:
    """
    Extract Job Objective + Responsibilities from JD page_content.
    JD has NO metadata 'objectives' attribute — both fields live in text.
    Returns combined text capped at 700 chars for use as FAISS Query B.
    """
    if not text:
        return ""
    parts: list[str] = []

    m_obj = re.search(
        r"Job\s+Objective\s*:\s*(.+?)(?=\nResponsibilities\s*:|$)",
        text, re.IGNORECASE | re.DOTALL
    )
    if m_obj:
        parts.append(m_obj.group(1).strip()[:300])

    m_resp = re.search(
        r"Responsibilities\s*:\s*(.+?)(?:\n[A-Z][a-z]|\Z)",
        text, re.IGNORECASE | re.DOTALL
    )
    if m_resp:
        parts.append(m_resp.group(1).strip()[:400])

    if parts:
        return " ".join(parts)[:700]

    # Fallback: skip the header lines and take the body
    lines = [l for l in text.split("\n") if l.strip()]
    return " ".join(lines[5:])[:500]


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
        return value
    return ""
def _extract_jd_division(text: str) -> str:
    return _extract_jd_field(text, "Division")

def _extract_jd_department(text: str) -> str:
    return _extract_jd_field(text, "Department")


def _extract_jd_unit(text: str) -> str:
    return _extract_jd_field(text, "Unit")


def _extract_jd_job_title(text: str) -> str:
    return _extract_jd_field(text, "Job Title")

def _extract_jd_objectives(text: str) -> str:
    if not text:
        return ""
    pattern = r"(?:Objective)[:\s]+(.+?)(?:\n\n|\n[A-Z]|$)"
    m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if m:
        return m.group(1).strip()
    return ""

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
    bsc_scores: List[float] = field(default_factory=list)   # <-- ADD THIS
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
        fields = self._parse_query_fields(query)

        result.detected_division = fields.get("division")
        result.detected_department_name = fields.get("department") or None
        result.detected_unit = fields.get("unit")
        result.detected_job_title = fields.get("job title")
        result.detected_job_grade = fields.get("job grade")
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

        # JD MATCH (first, so BSC can use it)
        result.jd_doc = self._match_jd_flexible(
            division=result.detected_division,
            department=result.detected_department_name,
            unit=result.detected_unit,
            job_title=result.detected_job_title,
            job_grade=result.detected_job_grade,
        )

        query_text, bsc_docs, bsc_scores = self._retrieve_bsc(
            unit=result.detected_unit,
            division=result.detected_division,
            k=bsc_k,
            jd_doc=result.jd_doc,
        )
        result.bsc_docs   = bsc_docs
        result.bsc_scores = bsc_scores
        result.query_text = query_text
        logger.info(f"  BSC query_text: {query_text[:80]}...")
        logger.info(f"  BSC docs: {len(result.bsc_docs)}")

        logger.info(f"\n{result.summary}")
        return result

    # ----------------------------------------------------------
    # DETECTION METHODS
    # ----------------------------------------------------------
    def _expand_unit_synonyms(self, unit: str) -> str:
        """Expand unit string with known synonyms."""
        if not unit:
            return ""
        unit_norm = _normalize(unit)
        expanded_tokens = [unit_norm]
        for key, syns in UNIT_SYNONYMS.items():
            if key in unit_norm:
                expanded_tokens.extend(syns)
        # Remove duplicates while preserving order
        unique = []
        for t in expanded_tokens:
            if t not in unique:
                unique.append(t)
        return " ".join(unique)
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
        """
        Extract a single field value from a multi-line query.

        Example:
            Department:
            Unit: Merchant and Agent Reconciliation

        Returns:
            None for Department
            Merchant and Agent Reconciliation for Unit
        """

        pattern = rf"^\s*{re.escape(field)}\s*:\s*(.*?)\s*$"

        for line in query.splitlines():
            m = re.match(pattern, line, re.IGNORECASE)
            if m:
                value = m.group(1).strip()
                return value if value else None

        return None
    def _parse_query_fields(self, query: str):

        fields = {}

        for line in query.splitlines():

            line = line.strip()

            if ":" not in line:
                continue

            key, value = line.split(":", 1)

            fields[key.strip().lower()] = value.strip()

        return fields

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
    # helping functions
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
    # ----------------------------------------------------------
    # BSC RETRIEVAL (HYBRID WITH JD OBJECTIVES + DIVISION FILTER)
    # ----------------------------------------------------------

    def _retrieve_bsc(
        self,
        unit: Optional[str],
        division: Optional[str],
        k: int,
        jd_doc: Optional[object] = None,
    ):
        if not self._all_bsc_docs:
            self._load_all_bsc_docs()

        # ── Step 1: Filter by division ────────────────────────────────
        if division:
            div_norm = _normalize(division)
            division_docs = [
                doc for doc in self._all_bsc_docs
                if _normalize(_get_meta(doc).get("division", "")) == div_norm
            ]
        else:
            division_docs = self._all_bsc_docs

        if not division_docs:
            logger.warning("  BSC: no docs found for division")
            return "", [], []

        logger.info(f"  BSC: {len(division_docs)} docs after division filter")

        # ── Step 2: Build query — unit name + synonyms + JD objectives ─
        query_a = unit.strip() if unit else ""

        # Expand unit with synonyms so FAISS can bridge label mismatches
        # e.g. query has "CBE-Birr" but BSC doc says "Mobile Money"
        if query_a:
            unit_norm = _normalize(query_a)
            synonym_expansions = []
            for key, syns in UNIT_SYNONYMS.items():
                if key in unit_norm:
                    synonym_expansions.extend(syns)
            if synonym_expansions:
                query_a = query_a + " " + " ".join(synonym_expansions)
                logger.info(f"  BSC query expanded with synonyms: {query_a}")

        query_b = ""
        if jd_doc:
            query_b = _extract_jd_objectives_from_text(_get_text(jd_doc))

        query_text = " ".join(filter(None, [query_a, query_b]))

        if not query_text.strip():
            logger.warning("  BSC: empty query — returning first k docs")
            return "", division_docs[:k], [0.0] * min(k, len(division_docs))

        logger.info(f"  BSC query ({len(query_text)} chars): {query_text[:120]}...")

        # ── Step 3: Build temp FAISS index for this division only ─────
        temp_vs = FAISS.from_documents(
            division_docs,
            self.bsc_vectorstore.embeddings
        )

        # ── Step 4: Pure semantic search across ALL division docs ─────
        # Fetch all docs so re-ranking can freely re-order the full set.
        # normalize_embeddings=True → FAISS returns L2 distance on unit
        # vectors.  Convert: cosine_sim = 1 - L2² / 2
        fetch_k = len(division_docs)
        raw_results = temp_vs.similarity_search_with_score(query_text, k=fetch_k)

        semantic: list[tuple] = []
        for doc, l2_dist in raw_results:
            cosine_sim = max(0.0, 1.0 - (l2_dist ** 2) / 2.0)
            semantic.append((doc, cosine_sim))

        if semantic:
            logger.info(f"  BSC semantic top={semantic[0][1]:.4f}  bottom={semantic[-1][1]:.4f}")

        # ── Step 5: Re-rank with UNIT_KEYWORD_SIGNAL (penalty only) ──
        # Cosine score is the base. PENALTY_MATCH (-0.60) pushes down
        # KPIs that belong to a different channel (e.g. "card banking"
        # docs when the unit is "Mobile Money"). One penalty max per doc.
        signal         = _get_unit_signal(unit or "")
        penalise_terms = [t.lower() for t in signal.get("penalise", [])]

        reranked: list[tuple] = []
        for doc, cosine_score in semantic:
            kpi_text = _get_text(doc).lower()
            final    = cosine_score

            penalised = False
            for term in penalise_terms:
                if term in kpi_text and not penalised:
                    final += PENALTY_MATCH
                    penalised = True
                    logger.debug(f"    ↓ penalise '{term}' → {final:.4f}")

            reranked.append((doc, final))

        # Sort descending by final score, take top-k
        reranked.sort(key=lambda x: -x[1])
        top_k = reranked[:k]

        docs   = [d for d, _ in top_k]
        scores = [s for _, s in top_k]

        if scores:
            logger.info(f"  BSC reranked: top={scores[0]:.4f}  bottom={scores[-1]:.4f}")
        return query_text, docs, scores

    # ----------------------------------------------------------
    # KEYWORD FALLBACK FOR BSC
    # ----------------------------------------------------------

    def _keyword_bsc_fallback(self,
                               division_docs: list,
                               query_text:    str,
                               unit:          Optional[str],
                               k:             int) -> list:
        """
        Pure stemmed Jaccard keyword scoring when FAISS scores all fall
        below SEMANTIC_THRESHOLD.  Applies the same keyword signal
        boost/penalise as the semantic path so wrong-channel KPIs are
        still pushed down even without embeddings.
        """
        query_stems = _stem_tokens(query_text)
        if not query_stems:
            logger.info("  BSC keyword fallback: empty query stems — returning first k docs")
            return division_docs[:k]

        signal        = _get_unit_signal(unit or "")
        boost_terms   = [t.lower() for t in signal.get("boost",    [])]
        penalise_terms = [t.lower() for t in signal.get("penalise", [])]

        scores: dict[int, float] = {}
        for idx, doc in enumerate(division_docs):
            doc_text  = _get_text(doc)
            doc_stems = _stem_tokens(doc_text)

            inter = len(query_stems & doc_stems)
            if inter == 0:
                continue

            union        = len(query_stems | doc_stems)
            base_jaccard = inter / union if union > 0 else 0.0
            score        = base_jaccard

            # Keyword signal
            kpi_name = _get_meta(doc).get("kpi", "").lower()
            for term in boost_terms:
                if term in kpi_name:
                    score += BOOST_MATCH
            for term in penalise_terms:
                if term in kpi_name:
                    score += PENALTY_MATCH
                    break

            # BSC weight bonus
            score += 0.03 * _parse_bsc_weight(doc_text)

            scores[idx] = score

        if not scores:
            logger.info("  BSC keyword fallback: no overlap — returning first k docs")
            return division_docs[:k]

        ranked = sorted(scores.items(), key=lambda x: -x[1])
        logger.info(f"  BSC keyword fallback top {min(k, 5)}:")
        for idx, sc in ranked[:min(k, 5)]:
            kpi = _get_meta(division_docs[idx]).get("kpi", "?")
            logger.info(f"    {sc:.4f}  kpi='{kpi}'")

        return [division_docs[idx] for idx, _ in ranked[:k]]

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
    # JD FLEXIBLE MATCH
    # ----------------------------------------------------------

    # ----------------------------------------------------------
# JD MATCH
# ----------------------------------------------------------

    def _department_match(
        self,
        query_department: Optional[str],
        jd_department: Optional[str]
    ) -> bool:

        if not query_department or not jd_department:
            return False

        query_department = _normalize(query_department)
        jd_department = _normalize(jd_department)

        # exact match
        if query_department == jd_department:
            return True

        # contains match
        if query_department in jd_department:
            return True

        if jd_department in query_department:
            return True

        # Director variation
        cleaned_jd = jd_department.replace(
            "director", ""
        ).strip()

        if cleaned_jd == query_department:
            return True

        return False

    def _match_jd_flexible(
        self,
        division: Optional[str],
        department: Optional[str],
        unit: Optional[str],
        job_title: Optional[str],
        job_grade: Optional[str] = None,
    ):
        if not self.jd_docs:
            logger.warning(" No JD documents available")
            return None

        q_division = _normalize(division) if division else None
        q_department = _normalize(department) if department else None
        q_unit = _normalize(unit) if unit else None
        q_job_title = _normalize(job_title) if job_title else None

        logger.info("\n JD Match Search")
        logger.info(f"Division={division}, Department={department}, Unit={unit}, Title={job_title}")

        for doc in self.jd_docs:
            text = _get_text(doc)
            jd_division = _normalize(_extract_jd_division(text))
            jd_department = _normalize(_extract_jd_department(text))
            jd_unit = _normalize(_extract_jd_unit(text))
            jd_job_title = _normalize(_extract_jd_job_title(text))

            # Division: only check if query has a value
            if q_division is not None and jd_division != q_division:
                continue

            # Unit: only check if query has a value
            if q_unit is not None and jd_unit != q_unit:
                continue

            # Job Title: only check if query has a value
            if q_job_title is not None and jd_job_title != q_job_title:
                continue

            # Department: flexible match, but only if query has a value
            if q_department is not None:
                if not self._department_match(q_department, jd_department):
                    continue

            logger.info("✓ JD MATCH FOUND")
            return doc

        logger.info("✗ No JD match found")
        return None