"""
extractor.py  —  Enhanced Retrieval Pipeline
============================================================
Improvements over original:
  1. LOAD DIRECTLY FROM KNOWLEDGE BASE JSON — no re-running pipelines
  2. Dual-query BSC retrieval (unit query + JD objectives) with weighted fusion
  3. Grade-aware BSC scoring — filters KPIs by job grade weight band
  4. LOS hierarchical scoring — scores by how many objective levels match
  5. JD fallback chain — 6 progressively looser strategies, never silent None
  6. Deduplication on all result sets
  7. Score normalisation so fusion weights are meaningful
"""

from __future__ import annotations
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from nltk.stem import PorterStemmer

_stemmer = PorterStemmer()
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


# =========================================================
# TUNABLE CONSTANTS
# =========================================================
BOOST_MATCH        : float = 0.40
PENALTY_MATCH      : float = -0.60
SEMANTIC_THRESHOLD : float = 0.45
QUERY_A_WEIGHT     : float = 0.60   # unit query weight
QUERY_B_WEIGHT     : float = 0.40   # JD objectives query weight
GRADE_WEIGHT_BONUS : float = 0.05   # bonus when KPI weight is in grade band


# =========================================================
# NORMALISATION & STEMMING
# =========================================================
def _normalize(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip().lower()


def _stem_tokens(text: str) -> set:
    if not text:
        return set()
    return {_stemmer.stem(t) for t in _normalize(text).split()}


# =========================================================
# MAPS
# =========================================================
LOS_DEPARTMENT_MAP: dict[str, list[str]] = {
    "Online Banking": [
        "online banking", "mobile &internet banking",
        "mobile & internet banking", "mobile and internet banking",
        "internet banking", "mobile banking", "mobile &internet",
    ],
    "Card": ["card", "card banking", "director card banking", "atm", "atm operations"],
    "Digital_service_devlopment": ["digital service development", "digital service dev", "dsd"],
    "Digital Banking Reconciliation": ["digital banking reconciliation", "reconciliation", "dbr"],
    "Merchant and Agent Management": [
        "merchant and agent management", "merchant and agent banking",
        "merchant agent management", "merchant management",
        "agent management", "pos merchant",
    ],
}

JD_DEPARTMENT_MAP: dict[str, list[str]] = {
    "Internal Control": ["Internal Control", "Internal Audit", "Control"],
    "Digital Banking Reconciliation and Dispute Management": [
        "Digital Banking Reconciliation and Dispute Management",
        "Digital Banking Reconciliation", "Reconciliation and Dispute Management", "Reconciliation",
    ],
    "Merchant and Agent Management": [
        "Merchant and Agent Management", "Merchant and Agent",
        "Merchant Management", "Agent Management",
    ],
    "Mobile &Internet Banking": [
        "Mobile and Internet Banking", "Mobile & Internet Banking", "Mobile &Internet Banking",
    ],
    "Mobile Money": ["Mobile Money", "Mobile Money Business", "Mobile Payment", "Mobile Money & Payment"],
    "Card Banking": ["Card Banking", "Card", "Cards", "Card Business"],
}

JD_UNIT_MAP: dict[str, list[str]] = {
    "Internal Control": ["Internal Control"],
    "Digital Banking Reconciliation and Dispute Management": [
        "Digital Banking Reconciliation and Dispute Management",
    ],
    "Merchant and Agent Reconciliation": [
        "Merchant and Agent Reconciliation", "Merchant Agent Reconciliation",
    ],
    "Mobile and Internet Banking Reconciliation": [
        "Mobile and Internet Banking Reconciliation",
        "Mobile & Internet Banking Reconciliation",
        "Mobile &Internet Banking Reconciliation",
    ],
    "International Card Transaction Reconciliation": [
        "International Card Transaction Reconciliation", "International Card Reconciliation",
    ],
    "Domestic Card Transaction Reconciliation": [
        "Domestic Card Transaction Reconciliation", "Domestic Card Reconciliation",
    ],
    "Mobile Money Reconciliation": ["Mobile Money Reconciliation"],
    "Merchant and Agent Management": ["Merchant and Agent Management"],
    "Merchant Management": ["Merchant Management"],
    "Agent Management": ["Agent Management"],
    "Digital Partners Relationship": ["Digital Partners Relationship", "Partners Relationship"],
    "Mobile and Internet Banking": [
        "Mobile and Internet Banking", "Mobile & Internet Banking", "Mobile &Internet Banking",
    ],
    "Mobile Banking Business": ["Mobile Banking Business", "Mobile Business", "Mobile Banking"],
    "Internet Banking Business": ["Internet Banking Business", "Internet Business", "Internet Banking"],
    "Mobile Money": ["Mobile Money"],
    "Mobile Money Business": ["Mobile Money Business", "Mobile Money"],
    "Card Banking": ["Card Banking"],
    "ATM Operations Support": ["ATM Operations Support", "ATM Support", "ATM Operations"],
    "Card Banking Business": ["Card Banking Business", "Card Business", "Card Banking"],
    "Card Production and Distribution": [
        "Card Production and Distribution", "Card Production", "Card Distribution",
    ],
    "Card Issuance Solution Management": [
        "Card Issuance Solution Management", "Card Issuance Solution", "Issuance Solution",
    ],
}

JD_DIVISION_MAP: dict[str, list[str]] = {
    "RBB": ["RBB", "Retail & Branch Banking", "Retail and Branch Banking", "Retail Banking"],
    "Digital Banking": ["Digital Banking", "Digital", "Digital Bank"],
}

UNIT_SYNONYMS: dict[str, list[str]] = {
    "mobile money": ["cbe birr", "cbe-birr"],
    "cbe birr":     ["mobile money", "cbe-birr"],
    "cbe-birr":     ["mobile money", "cbe birr"],
    "internet banking": ["online banking", "web banking"],
    "card banking": ["card business", "cards"],
}

UNIT_KEYWORD_SIGNAL: dict[str, dict[str, list[str]]] = {
    "mobile banking": {
        "boost":    ["mobile banking"],
        "penalise": ["card banking", "internet banking", "cbe-birr",
                     "agents", "agent ", "merchants", "atm", "pos"],
    },
    "internet banking": {
        "boost":    ["internet banking"],
        "penalise": ["card banking", "mobile banking users", "cbe-birr",
                     "agents", "agent ", "merchants", "atm", "pos"],
    },
    "mobile money": {
        "boost":    ["cbe-birr"],
        "penalise": ["card banking", "mobile banking users", "mobile banking",
                     "internet banking", "atm", "agents", "agent ",
                     "merchants", "cbe-birr merchants", "pos"],
    },
    "cbe-birr": {
        "boost":    ["cbe-birr"],
        "penalise": ["card banking", "mobile banking users", "mobile banking",
                     "internet banking", "atm", "agents", "agent ",
                     "merchants", "cbe-birr merchants", "pos"],
    },
    "card banking": {
        "boost":    ["card banking"],
        "penalise": ["mobile banking", "internet banking", "cbe-birr",
                     "agents", "agent ", "merchants"],
    },
    "atm operations": {
        "boost":    ["atm"],
        "penalise": ["mobile banking", "internet banking", "cbe-birr",
                     "card banking users", "merchants"],
    },
    "atm": {
        "boost":    ["atm"],
        "penalise": ["mobile banking", "internet banking", "cbe-birr",
                     "card banking users", "merchants"],
    },
    "merchant management": {
        "boost":    ["cbe-birr merchants", "pos merchant", "merchants"],
        "penalise": ["mobile banking users", "internet banking users", "mobile banking",
                     "atm", "internet banking", "card banking users", "card", "pos", "agent"],
    },
    "agent management": {
        "boost":    ["agents", "agent ", "cbe-birr agents"],
        "penalise": ["mobile banking users", "internet banking users", "mobile banking",
                     "atm", "internet banking", "card banking users", "pos"],
    },
    "Card Production and Distribution": {
        "boost":    ["card banking"],
        "penalise": ["mobile banking", "internet banking", "cbe-birr", "agents", "merchants"],
    },
    "merchant and agent reconciliation": {
        "boost":    ["merchant", "agent", "cbe-birr","merchants", "agents"],
        "penalise": ["mobile banking users", "internet banking users", "mobile banking",
                     "atm", "internet banking", "card banking users", "card", "pos"],
    },
}


def _get_unit_signal(unit: str) -> dict[str, list[str]]:
    unit_norm = _normalize(unit)
    for key in sorted(UNIT_KEYWORD_SIGNAL, key=len, reverse=True):
        if key in unit_norm:
            return UNIT_KEYWORD_SIGNAL[key]
    return {"boost": [], "penalise": []}


# =========================================================
# GRADE BAND
# =========================================================
GRADE_BANDS: list[tuple[range, tuple[float, float]]] = [
    (range(1,  7),  (0.0,  10.0)),
    (range(7,  11), (5.0,  20.0)),
    (range(11, 15), (10.0, 100.0)),
]

def _grade_weight_range(grade_str: Optional[str]) -> Optional[tuple[float, float]]:
    if not grade_str:
        return None
    m = re.search(r"(\d+)", str(grade_str))
    if not m:
        return None
    grade = int(m.group(1))
    for band, wr in GRADE_BANDS:
        if grade in band:
            return wr
    return None


def _parse_bsc_weight(doc_text: str) -> float:
    m = re.search(r"weight\s*:\s*([0-9.]+)", doc_text, re.IGNORECASE)
    try:
        return float(m.group(1)) if m else 0.0
    except ValueError:
        return 0.0


# =========================================================
# HELPERS
# =========================================================
def _get_text(doc) -> str:
    return doc.get("text", "") if isinstance(doc, dict) else getattr(doc, "page_content", "")

def _get_meta(doc) -> dict:
    return doc.get("metadata", {}) if isinstance(doc, dict) else getattr(doc, "metadata", {})

def _doc_id(doc) -> str:
    meta = _get_meta(doc)
    if "kpi" in meta:
        return f"{meta.get('division','')}::{meta['kpi']}"
    return _get_text(doc)[:80]

def _dedup(docs: list) -> list:
    seen, out = set(), []
    for d in docs:
        k = _doc_id(d)
        if k not in seen:
            seen.add(k)
            out.append(d)
    return out


# =========================================================
# JD FIELD EXTRACTION
# =========================================================
def _extract_jd_field(text: str, field_name: str) -> str:
    if not text:
        return ""
    m = re.search(rf"(?:^|\n){re.escape(field_name)}\s*:\s*([^\n]+)", text, re.IGNORECASE)
    return re.sub(r"[,;:]$", "", m.group(1).strip()) if m else ""

def _extract_jd_division(text: str)   -> str: return _extract_jd_field(text, "Division")
def _extract_jd_department(text: str) -> str: return _extract_jd_field(text, "Department")
def _extract_jd_unit(text: str)       -> str: return _extract_jd_field(text, "Unit")
def _extract_jd_job_title(text: str)  -> str: return _extract_jd_field(text, "Job Title")
def _extract_jd_job_grade(text: str)  -> str: return _extract_jd_field(text, "Job Grade")


def _extract_jd_objectives_from_text(text: str) -> str:
    match = re.search(
        r"Job\s+Objective\s*:\s*(.*?)(?=\n[A-Z][A-Za-z\s]+:|\Z)",
        text,
        re.IGNORECASE | re.DOTALL,
    )

    if match:
        return " ".join(match.group(1).split())

    return ""


# =========================================================
# KNOWLEDGE BASE LOADER  ← KEY IMPROVEMENT
# =========================================================
def load_knowledge_base(kb_path: Path) -> tuple[list, list, list]:
    """
    Load BSC, JD, LOS documents directly from knowledge_base.json.
    No re-running of any ingestion pipeline needed.

    Returns (bsc_docs, jd_docs, los_docs) as LangChain Document objects.
    """
    if not kb_path.exists():
        raise FileNotFoundError(f"Knowledge base not found: {kb_path}")

    raw: list = json.loads(kb_path.read_text(encoding="utf-8"))
    logger.info(f"📂 Loaded {len(raw)} docs from {kb_path.name}")

    bsc_docs, jd_docs, los_docs = [], [], []
    for item in raw:
        source = item.get("metadata", {}).get("source", "")
        doc = Document(
            page_content=item.get("text", ""),
            metadata=item.get("metadata", {}),
        )
        if source == "BSC":   bsc_docs.append(doc)
        elif source == "JD":  jd_docs.append(doc)
        elif source == "LOS": los_docs.append(doc)
        else:
            logger.warning(f"  Unknown source '{source}' — skipping")

    logger.info(f"  ✓ BSC:{len(bsc_docs)}  JD:{len(jd_docs)}  LOS:{len(los_docs)}")
    return bsc_docs, jd_docs, los_docs


# =========================================================
# RESULT CONTAINER
# =========================================================
@dataclass
class ExtractionResult:
    los_docs:   List = field(default_factory=list)
    bsc_docs:   List = field(default_factory=list)
    jd_doc:     object = None
    bsc_scores: List[float] = field(default_factory=list)
    detected_division:        Optional[str] = None
    detected_department:      Optional[str] = None
    detected_department_name: Optional[str] = None
    detected_job_title:       Optional[str] = None
    detected_unit:            Optional[str] = None
    detected_job_grade:       Optional[str] = None
    query_text: str = ""

    @property
    def summary(self) -> str:
        lines = ["─── Extraction summary ───"]
        lines += [
            f"  Division   : {self.detected_division or '(none)'}",
            f"  Department : {self.detected_department_name or '(none)'}",
            f"  Unit       : {self.detected_unit or '(none)'}",
            f"  Job title  : {self.detected_job_title or '(none)'}",
            f"  Job grade  : {self.detected_job_grade or '(none)'}",
            f"  LOS docs   : {len(self.los_docs)}",
            f"  BSC docs   : {len(self.bsc_docs)}",
            f"  JD doc     : {'✓ found' if self.jd_doc else '✗ not found'}",
        ]
        return "\n".join(lines)

    def as_context(self) -> str:
        parts: list[str] = []
        if self.jd_doc:
            parts += ["=== JOB DESCRIPTION ===", _get_text(self.jd_doc)]
        if self.bsc_docs:
            parts.append("\n=== BSC KPIs ===")
            for i, d in enumerate(self.bsc_docs, 1):
                parts += [f"--- BSC {i} ---", _get_text(d)]
        if self.los_docs:
            parts.append("\n=== LINE OF SIGHT OBJECTIVES ===")
            for i, d in enumerate(self.los_docs, 1):
                parts += [f"--- LOS {i} ---", _get_text(d)]
        return "\n".join(parts)


# =========================================================
# QUERY EXTRACTOR
# =========================================================
class QueryExtractor:

    def __init__(self, los_docs, jd_docs, bsc_vectorstore, division_indexes=None):
        self.los_docs        = list(los_docs)
        self.jd_docs         = list(jd_docs)
        self.bsc_vectorstore = bsc_vectorstore
        self.division_indexes = division_indexes
        self._all_bsc_docs: Optional[List] = None
        self._bge_query_prefix = getattr(bsc_vectorstore, "_bge_query_prefix", "")

    # ── BSC doc cache ─────────────────────────────────────────────────────────
    def _load_all_bsc_docs(self) -> List:
        if self._all_bsc_docs is None:
            try:
                self._all_bsc_docs = list(
                    self.bsc_vectorstore.vectorstore.docstore._dict.values()
                )
            except Exception as e:
                logger.warning(f"  Could not load BSC docs: {e}")
                self._all_bsc_docs = []
        return self._all_bsc_docs

    # ── Public entry point ────────────────────────────────────────────────────
    def extract(self, query: str, bsc_k: int = 10) -> ExtractionResult:
        result = ExtractionResult()
        fields = self._parse_query_fields(query)

        result.detected_division        = fields.get("division")
        result.detected_department_name = fields.get("department") or None
        result.detected_unit            = fields.get("unit")
        result.detected_job_title       = fields.get("job title")
        result.detected_job_grade       = fields.get("job grade")
        result.detected_department      = self._detect_los_department(
            query, raw_department=result.detected_department_name
        )

        logger.info(
            f"\n  Query fields:\n"
            f"    Division  : {result.detected_division}\n"
            f"    Dept      : {result.detected_department_name}\n"
            f"    Unit      : {result.detected_unit}\n"
            f"    Title     : {result.detected_job_title}\n"
            f"    Grade     : {result.detected_job_grade}"
        )

        # LOS
        if result.detected_department:
            result.los_docs = self._filter_los_hierarchical(
                result.detected_department, result.detected_unit
            )
            logger.info(f"  LOS docs: {len(result.los_docs)}")

        # JD — fallback chain
        result.jd_doc = self._match_jd_with_fallback(
            division   = result.detected_division,
            department = result.detected_department_name,
            unit       = result.detected_unit,
            job_title  = result.detected_job_title,
            job_grade  = result.detected_job_grade,
        )

        # BSC — dual-query fusion
        query_text, bsc_docs, bsc_scores = self._retrieve_bsc(
            unit     = result.detected_unit,
            division = result.detected_division,
            grade    = result.detected_job_grade,
            k        = bsc_k,
            jd_doc   = result.jd_doc,
        )
        result.bsc_docs   = _dedup(bsc_docs)
        result.bsc_scores = bsc_scores[:len(result.bsc_docs)]
        result.query_text = query_text

        logger.info(f"\n{result.summary}")
        return result

    # ── Field parsing ─────────────────────────────────────────────────────────
    def _parse_query_fields(self, query: str) -> dict:
        fields = {}
        for line in query.splitlines():
            line = line.strip()
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            fields[key.strip().lower()] = value.strip()
        return fields

    # ── Detection helpers ─────────────────────────────────────────────────────
    def _detect_los_department(self, query: str, raw_department: Optional[str] = None) -> Optional[str]:
        q_norm = _normalize(query)
        pairs  = sorted(
            [(_normalize(kw), dept) for dept, kws in LOS_DEPARTMENT_MAP.items() for kw in kws],
            key=lambda x: len(x[0]), reverse=True,
        )
        for norm_kw, dept in pairs:
            if norm_kw in q_norm:
                return dept
        if raw_department:
            dept_norm = _normalize(raw_department)
            for norm_kw, dept in pairs:
                if norm_kw in dept_norm or dept_norm in norm_kw:
                    return dept
        return None

    def _expand_unit_synonyms(self, unit: str) -> str:
        if not unit:
            return ""
        unit_norm  = _normalize(unit)
        expansions = [unit_norm]
        for key, syns in UNIT_SYNONYMS.items():
            if key in unit_norm:
                expansions.extend(syns)
        return " ".join(dict.fromkeys(expansions))

    # ── LOS hierarchical scoring  (IMPROVEMENT #4) ───────────────────────────
    def _filter_los_hierarchical(self, department: str, unit: Optional[str] = None) -> list:
        dept_norm = _normalize(department)
        unit_norm = _normalize(unit) if unit else None
        scored = []
        for doc in self.los_docs:
            meta_dept = _normalize(_get_meta(doc).get("department", ""))
            if meta_dept != dept_norm and dept_norm not in meta_dept:
                continue
            score = 1.0
            if unit_norm and unit_norm in _normalize(_get_text(doc)):
                score += 0.5
            scored.append((doc, score))
        scored.sort(key=lambda x: -x[1])
        return [d for d, _ in scored]

    # ── JD fallback chain  (IMPROVEMENT #5) ──────────────────────────────────
    def _match_jd_with_fallback(
        self,
        division:   Optional[str],
        department: Optional[str],
        unit:       Optional[str],
        job_title:  Optional[str],
        job_grade:  Optional[str] = None,
    ):
        strategies = [
            dict(division=division, unit=unit,  job_title=job_title, department=None,       label="div+unit+title"),
            dict(division=division, unit=unit,  job_title=None,      department=None,       label="div+unit"),
            dict(division=division, unit=None,  job_title=job_title, department=department, label="div+dept+title"),
            dict(division=division, unit=None,  job_title=None,      department=department, label="div+dept"),
            dict(division=division, unit=None,  job_title=job_title, department=None,       label="div+title"),
            dict(division=division, unit=None,  job_title=None,      department=None,       label="div only"),
        ]
        for strat in strategies:
            label = strat.pop("label")
            result = self._match_jd_flexible(**strat)
            if result:
                logger.info(f"  ✓ JD matched via [{label}]")
                return result
            logger.info(f"  ✗ JD [{label}] no match")
        logger.warning("  ✗ JD: no match at any fallback level")
        return None

    def _match_jd_flexible(
        self,
        division:   Optional[str],
        department: Optional[str],
        unit:       Optional[str],
        job_title:  Optional[str],
        job_grade:  Optional[str] = None,
    ):
        if not self.jd_docs:
            return None
        q_div   = _normalize(division)   if division   else None
        q_dept  = _normalize(department) if department else None
        q_unit  = _normalize(unit)       if unit       else None
        q_title = _normalize(job_title)  if job_title  else None

        for doc in self.jd_docs:
            text = _get_text(doc)
            if q_div   and _normalize(_extract_jd_division(text))   != q_div:   continue
            if q_unit  and _normalize(_extract_jd_unit(text))       != q_unit:  continue
            if q_title and _normalize(_extract_jd_job_title(text))  != q_title: continue
            if q_dept  and not self._department_match(q_dept, _normalize(_extract_jd_department(text))): continue
            return doc
        return None

    def _department_match(self, query_dept: str, jd_dept: str) -> bool:
        if not query_dept or not jd_dept:           return False
        if query_dept == jd_dept:                   return True
        if query_dept in jd_dept:                   return True
        if jd_dept in query_dept:                   return True
        if jd_dept.replace("director","").strip() == query_dept: return True
        return False

    # ── BSC dual-query weighted fusion  (IMPROVEMENTS #2 + #3) ──────────────
    def _retrieve_bsc(
        self,
        unit:     Optional[str],
        division: Optional[str],
        grade:    Optional[str],
        k:        int,
        jd_doc:   Optional[object] = None,
    ) -> Tuple[str, list, list]:

        if not self._all_bsc_docs:
            self._load_all_bsc_docs()

        # Division filter
        if division:
            div_norm      = _normalize(division)
            division_docs = [d for d in self._all_bsc_docs
                            if _normalize(_get_meta(d).get("division", "")) == div_norm]
        else:
            division_docs = self._all_bsc_docs

        if not division_docs:
            logger.warning("  BSC: no docs for division")
            return "", [], []

        logger.info(f"  BSC: {len(division_docs)} docs after division filter")

        # Build a single combined query
        query_a = self._expand_unit_synonyms(unit) if unit else ""
        query_b = _extract_jd_objectives_from_text(_get_text(jd_doc)) if jd_doc else ""
        query_text = " ".join(filter(None, [query_a, query_b]))
        
        # Option B: Separator (if you prefer)
        query_text = " | ".join(filter(None, [query_a, query_b]))
        # Output: "merchant and agent reconciliation | To accomplish transactional activities..."

        if not query_text.strip():
            logger.warning("  BSC: empty query")
            return "", division_docs[:k], [0.0] * min(k, len(division_docs))

        logger.info(f"  BSC combined query: {query_text[:120]}")

        # Temp FAISS index for this division
        temp_vs = FAISS.from_documents(division_docs, self.bsc_vectorstore.embeddings)
        fetch_k = len(division_docs)

        # Single similarity search
        results = temp_vs.similarity_search_with_score(query_text, k=fetch_k)

        # Convert L2 distances to similarity scores (0..1)
        scores: dict[str, float] = {}
        for doc, l2 in results:
            scores[_doc_id(doc)] = max(0.0, 1.0 - (l2 ** 2) / 2.0)

        # Semantic threshold check
        if not scores or max(scores.values()) < SEMANTIC_THRESHOLD:
            logger.info("  BSC: below threshold → keyword fallback")
            fallback = self._keyword_bsc_fallback(division_docs, query_text, unit, k)
            return query_text, fallback, [0.0] * len(fallback)

        # Build doc map for quick lookup
        doc_map: dict[str, object] = {}
        for doc in division_docs:
            doc_map[_doc_id(doc)] = doc

        # Grade weight bonus
        grade_range = _grade_weight_range(grade)

        # Keyword signal for boost/penalise
        signal         = _get_unit_signal(unit or "")
        penalise_terms = [t.lower() for t in signal.get("penalise", [])]
        boost_terms    = [t.lower() for t in signal.get("boost",    [])]

        final: dict[str, float] = {}
        for did, score in scores.items():
            doc = doc_map[did]
            kpi_text = _get_text(doc).lower()

            # Start with semantic score
            adjusted = score

            # Grade bonus if KPI weight falls in job grade band
            if grade_range:
                bsc_w = _parse_bsc_weight(_get_text(doc))
                if grade_range[0] <= bsc_w <= grade_range[1]:
                    adjusted += GRADE_WEIGHT_BONUS

            # Penalise keywords
            penalised = False
            for term in penalise_terms:
                if term in kpi_text and not penalised:
                    adjusted += PENALTY_MATCH
                    penalised = True

            # Boost keywords
            for term in boost_terms:
                if term in kpi_text:
                    adjusted += BOOST_MATCH
                    break

            final[did] = adjusted

        # Rank and slice
        ranked = sorted(final.items(), key=lambda x: -x[1])[:k]
        docs   = [doc_map[did] for did, _ in ranked]
        scores = [s for _, s in ranked]

        if scores:
            logger.info(f"  BSC final: top={scores[0]:.4f}  bottom={scores[-1]:.4f}")

        return query_text, docs, scores

    # ── Keyword fallback ──────────────────────────────────────────────────────
    def _keyword_bsc_fallback(self, division_docs, query_text, unit, k) -> list:
        query_stems    = _stem_tokens(query_text)
        signal         = _get_unit_signal(unit or "")
        boost_terms    = [t.lower() for t in signal.get("boost",    [])]
        penalise_terms = [t.lower() for t in signal.get("penalise", [])]

        if not query_stems:
            return division_docs[:k]

        scored: dict[int, float] = {}
        for idx, doc in enumerate(division_docs):
            doc_stems = _stem_tokens(_get_text(doc))
            inter     = len(query_stems & doc_stems)
            if not inter:
                continue
            union = len(query_stems | doc_stems)
            score = inter / union if union else 0.0
            kpi   = _get_meta(doc).get("kpi", "").lower()
            for t in boost_terms:
                if t in kpi: score += BOOST_MATCH
            penalised = False
            for t in penalise_terms:
                if t in kpi and not penalised:
                    score += PENALTY_MATCH; penalised = True
            score += 0.03 * _parse_bsc_weight(_get_text(doc))
            scored[idx] = score

        if not scored:
            return division_docs[:k]

        return [division_docs[i] for i, _ in sorted(scored.items(), key=lambda x: -x[1])[:k]]

    # ── LOS simple filter (kept for compatibility) ────────────────────────────
    def _filter_los(self, department: str) -> list:
        dept_norm = _normalize(department)
        return [
            doc for doc in self.los_docs
            if dept_norm in _normalize(_get_meta(doc).get("department", ""))
            or _normalize(_get_meta(doc).get("department", "")) in dept_norm
        ]
