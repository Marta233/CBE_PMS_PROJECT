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


def _loose_key(text) -> str:
    """Comparison key that ignores case and how '&' is spaced or spelled:
    'Mobile &Internet Banking' == 'Mobile & Internet Banking' == 'mobile and internet banking'."""
    return re.sub(r"\s+", " ", str(text or "").replace("&", " and ")).strip().lower()


def _stem_tokens(text: str) -> set:
    if not text:
        return set()
    return {_stemmer.stem(t) for t in _normalize(text).split()}


# =========================================================
# RETRIEVAL SIGNALS
# Department identity comes from org_registry.json. Keyword boosts are
# optional precision hints for units that have an entry in
# llm/profiles/retrieval_signals.json. A unit with no entry is neutral.
# =========================================================
_SIGNALS: Optional[dict] = None


def _org():
    try:
        from common import registry
    except ImportError:
        import sys
        ingestion = Path(__file__).resolve().parents[1] / "Data_Ingestion"
        if str(ingestion) not in sys.path:
            sys.path.insert(0, str(ingestion))
        from common import registry
    return registry


def _signal_tables() -> dict:
    global _SIGNALS
    if _SIGNALS is None:
        from llm.profiles.policy import retrieval_signals
        _SIGNALS = retrieval_signals()
    return _SIGNALS

def _get_unit_signal(unit: str) -> dict[str, list[str]]:
    signals = _signal_tables().get("unit_keyword_signal", {})
    unit_norm = _normalize(unit)
    for key in sorted(signals, key=len, reverse=True):
        if key.lower() in unit_norm:
            return signals[key]
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


def _get_bsc_weight(doc) -> float:
    """
    Read BSC weight from `metadata` (set in bsc_loader.py's to_documents()).
    Previously _parse_bsc_weight regex-extracted "weight:" from the text
    field directly — text no longer contains it, since BSC context was
    trimmed to Strategic Objective + KPI only. _parse_bsc_weight is kept
    above only in case older, not-yet-re-ingested documents still carry
    weight in their text; this is the function actually called now.
    """
    meta = _get_meta(doc)
    try:
        return float(meta.get("weight", 0.0) or 0.0)
    except (TypeError, ValueError):
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

# NOTE: division/department/unit/job_title are no longer parsed from JD
# text (that field only holds Job Objective + Responsibilities now) —
# _match_jd_flexible reads them from `metadata` instead. These four
# wrappers are kept only in case something else still calls them; they
# will return "" against current JD documents.
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
def load_knowledge_base(kb_path: Path) -> tuple[list, list, list, list]:
    """
    Load BSC, JD, LOS, and Work Plan documents directly from knowledge_base.json.
    No re-running of any ingestion pipeline needed.

    Returns (bsc_docs, jd_docs, los_docs, work_plan_docs) as LangChain Document objects.
    """
    if not kb_path.exists():
        raise FileNotFoundError(f"Knowledge base not found: {kb_path}")

    raw: list = json.loads(kb_path.read_text(encoding="utf-8"))
    logger.info(f"📂 Loaded {len(raw)} docs from {kb_path.name}")

    bsc_docs, jd_docs, los_docs, work_plan_docs = [], [], [], []
    for item in raw:
        source = item.get("metadata", {}).get("source", "")
        doc = Document(
            page_content=item.get("text", ""),
            metadata=item.get("metadata", {}),
        )
        if source == "BSC":        bsc_docs.append(doc)
        elif source == "JD":       jd_docs.append(doc)
        elif source == "LOS":      los_docs.append(doc)
        elif source == "WorkPlan": work_plan_docs.append(doc)
        else:
            logger.warning(f"  Unknown source '{source}' — skipping")

    logger.info(
        f"  ✓ BSC:{len(bsc_docs)}  JD:{len(jd_docs)}  LOS:{len(los_docs)}  "
        f"WorkPlan:{len(work_plan_docs)}"
    )
    return bsc_docs, jd_docs, los_docs, work_plan_docs


# =========================================================
# RESULT CONTAINER
# =========================================================
@dataclass
class ExtractionResult:
    los_docs:   List = field(default_factory=list)
    bsc_docs:   List = field(default_factory=list)
    work_plan_docs: List = field(default_factory=list)
    jd_doc:     object = None
    bsc_scores: List[float] = field(default_factory=list)
    detected_division:        Optional[str] = None
    detected_department:      Optional[str] = None
    detected_department_name: Optional[str] = None
    detected_work_plan_department: Optional[str] = None
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
            f"  WP Dept    : {self.detected_work_plan_department or '(none)'}",
            f"  Unit       : {self.detected_unit or '(none)'}",
            f"  Job title  : {self.detected_job_title or '(none)'}",
            f"  Job grade  : {self.detected_job_grade or '(none)'}",
            f"  LOS docs   : {len(self.los_docs)}",
            f"  BSC docs   : {len(self.bsc_docs)}",
            f"  Work Plan docs : {len(self.work_plan_docs)}  (Priority 1)",
            f"  JD doc     : {'✓ found' if self.jd_doc else '✗ not found'}",
        ]
        return "\n".join(lines)

    def as_context(self) -> str:
        parts: list[str] = []
        if self.work_plan_docs:
            parts.append("=== WORK PLAN (PRIORITY 1) ===")
            for i, d in enumerate(self.work_plan_docs, 1):
                parts += [f"--- Work Plan {i} ---", _get_text(d)]
        if self.jd_doc:
            parts += ["\n=== JOB DESCRIPTION ===", _get_text(self.jd_doc)]
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

    def __init__(self, los_docs, jd_docs, bsc_vectorstore, work_plan_docs=None):
        self.los_docs        = list(los_docs)
        self.jd_docs         = list(jd_docs)
        self.work_plan_docs  = list(work_plan_docs or [])
        self.bsc_vectorstore = bsc_vectorstore
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

        raw_division = fields.get("division") or ""
        raw_department = fields.get("department") or ""
        raw_unit = fields.get("unit") or ""
        resolved = _org().resolve(raw_division, raw_department, raw_unit)
        result.detected_division        = resolved.division or raw_division or None
        result.detected_department_name = resolved.department or raw_department or None
        result.detected_unit            = resolved.unit or raw_unit or None
        result.detected_job_title       = fields.get("job title")
        result.detected_job_grade       = fields.get("job grade")
        # One canonical department for LOS and Work Plan. Alias spellings
        # (LOS sheet "Online Banking", work-plan "Mobile & Internet Banking")
        # are matched inside the filters via department_match_keys.
        result.detected_department = resolved.department or None
        result.detected_work_plan_department = resolved.department or None

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

        if result.detected_work_plan_department:
            result.work_plan_docs = self._filter_work_plan(
                result.detected_work_plan_department, result.detected_unit
            )
            logger.info(f"  Work Plan docs: {len(result.work_plan_docs)}")
        else:
            logger.warning(
                f"  Work Plan: department {raw_department!r} is not in the org registry "
                "— no Work Plan retrieved."
            )

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
    def _expand_unit_synonyms(self, unit: str) -> str:
        if not unit:
            return ""
        unit_norm  = _normalize(unit)
        expansions = [unit_norm]
        for key, syns in _signal_tables().get("unit_synonyms", {}).items():
            if key in unit_norm:
                expansions.extend(syns)
        return " ".join(dict.fromkeys(expansions))

    # ── LOS hierarchical scoring  (IMPROVEMENT #4) ───────────────────────────
    def _filter_los_hierarchical(self, department: str, unit: Optional[str] = None) -> list:
        dept_keys = _org().department_match_keys(department)
        unit_norm = _normalize(unit) if unit else None
        scored = []
        for doc in self.los_docs:
            meta_dept = _org().loose_key(_get_meta(doc).get("department", ""))
            if meta_dept not in dept_keys:
                continue
            score = 1.0
            if unit_norm and unit_norm in _normalize(_get_text(doc)):
                score += 0.5
            scored.append((doc, score))
        scored.sort(key=lambda x: -x[1])
        return [d for d, _ in scored]

    # ── Work Plan filtering — PRIORITY 1, same pattern as LOS ────────────────
    def _filter_work_plan(self, department: Optional[str], unit: Optional[str]) -> list:
        """
        Department filtering matches the registry name or any alias.

        Unit filtering is DELIBERATELY a HARD filter, unlike LOS's soft rank
        boost. LOS only nudges a unit-matching doc higher while still
        returning everything in the department, because its unit signal is
        a fuzzy substring search over raw text. Work Plan's entire purpose
        is preventing cross-unit mixing (e.g. Agent objectives blending
        with Merchant/POS data) — a soft rank would still leave a
        wrong-unit entry in the context for the model to see, just lower
        down, which doesn't solve the problem. Work Plan's unit field is
        also clean, already-normalized metadata (Agent/Merchant/Both/
        Mesob), not text requiring a fuzzy match, so a hard filter here
        doesn't risk losing genuinely relevant docs the way it might for
        LOS's fuzzier signal. "Both"-tagged entries always pass through,
        since they apply to every unit in the department.
        """
        if not department:
            return []
        registry = _org()
        dept_keys = registry.department_match_keys(department)
        allowed = registry.work_plan_unit_labels(department, unit)
        allowed_keys = None if allowed is None else {registry.loose_key(label) for label in allowed}
        shared_keys = {registry.loose_key(token) for token in ("both", "all", "all units", "any")}
        asked_key = registry.loose_key(unit or "")
        reconciliation_query = "reconciliation" in asked_key

        matched = []
        for doc in self.work_plan_docs:
            meta = _get_meta(doc)
            meta_dept = registry.loose_key(meta.get("department", ""))
            if meta_dept not in dept_keys:
                continue
            doc_unit = str(meta.get("unit", "") or "")
            doc_unit_key = registry.loose_key(doc_unit)
            # A shortened reconciliation label still belongs to that unit.
            # It must not pull Agent or Merchant rows that merely share a word.
            if (
                reconciliation_query
                and "reconciliation" in doc_unit_key
                and (doc_unit_key in asked_key or asked_key in doc_unit_key)
            ):
                matched.append(doc)
                continue
            # A plan whose docx has no Unit column is filed under the department
            # name. It applies to every unit of that department.
            # "Both" passes only for a unit the registry knows. An unknown unit
            # does not inherit shared rows.
            if allowed:
                department_wide = doc_unit_key in dept_keys or doc_unit_key in shared_keys
            else:
                department_wide = doc_unit_key in dept_keys
            if allowed_keys is not None and doc_unit_key not in allowed_keys and not department_wide:
                continue
            matched.append(doc)
        if not matched:
            self._explain_empty_work_plan(department, unit)
        return matched

    def _explain_empty_work_plan(self, department: Optional[str], unit: Optional[str]) -> None:
        """Say WHY no Work Plan document matched (this used to be a silent 0)."""
        if not self.work_plan_docs:
            logger.warning("  Work Plan: the knowledge base holds NO Work Plan documents "
                           "(upload them, or run merge_work_plan_into_kb.py).")
            return
        stored: dict[tuple, int] = {}
        for d in self.work_plan_docs:
            m = _get_meta(d)
            key = (str(m.get("department", "")), str(m.get("unit", "")))
            stored[key] = stored.get(key, 0) + 1
        dept_keys = _org().department_match_keys(department)
        same_dept = {k: n for k, n in stored.items()
                     if _org().loose_key(k[0]) in dept_keys}
        if not same_dept:
            logger.warning(f"  Work Plan: nothing is stored for department {department!r}. "
                           f"Departments in the knowledge base: {sorted({k[0] for k in stored})}")
        else:
            units = sorted(f"{u!r} x{n}" for (_, u), n in same_dept.items())
            logger.warning(f"  Work Plan: department {department!r} is stored, but no unit fits "
                           f"the query unit {unit!r}. Stored units: {', '.join(units)}")

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
            result = self._match_jd_flexible(job_grade=job_grade, **strat)
            if result:
                m = _get_meta(result)
                logger.info(
                    f"  ✓ JD matched via [{label}] → {m.get('job_title')!r} | "
                    f"unit {m.get('unit')!r} | grade {m.get('job_grade')}"
                )
                if strat.get("job_title") is None and job_title:
                    logger.warning(
                        f"  ⚠ JD matched WITHOUT the job title — this may be a different role than {job_title!r}"
                    )
                asked, got = self._grade_number(job_grade), self._grade_number(m.get("job_grade"))
                if asked is not None and got is not None and asked != got:
                    logger.warning(
                        f"  ⚠ JD grade {got} differs from the requested grade {asked} "
                        f"(no JD with that grade matched)"
                    )
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
        """
        Matches against `metadata`, NOT the text field. JD text no longer
        contains Division/Unit/Department/Job Title/Job Grade (trimmed out
        as redundant with the query — see jd/__init__.py and jd_main.py),
        so regex-extracting those fields from text would always come back
        empty. Metadata already carries all five fields structured, and is
        more robust than regex-parsing free text ever was.
        """
        if not self.jd_docs:
            return None
        q_div   = _normalize(division)   if division   else None
        q_dept  = _loose_key(department) if department else None
        q_unit  = unit                   if unit       else None
        q_title = _loose_key(job_title)  if job_title  else None
        q_grade = self._grade_number(job_grade)

        # Several JDs can pass the filters (same unit + title at different
        # grades, or 'Mobile Banking' vs 'Mobile Banking Business'). Pick the
        # best one — exact unit, then exact department, then same grade — and
        # keep the FIRST on a tie, which is what the old first-match loop did.
        best, best_rank = None, None
        for doc in self.jd_docs:
            meta = _get_meta(doc)
            if q_div and _normalize(meta.get("division", "")) != q_div:
                continue
            unit_score = 2
            if q_unit:
                unit_score = self._unit_match(q_unit, meta.get("unit", ""))
                if not unit_score:
                    continue
            if q_title and _loose_key(meta.get("job_title", "")) != q_title:
                continue
            dept_score = 2
            if q_dept:
                jd_dept = _loose_key(meta.get("department", ""))
                if not self._department_match(q_dept, jd_dept):
                    continue
                dept_score = 2 if q_dept == jd_dept else 1
            grade_score = 1 if (q_grade is not None and q_grade == self._grade_number(meta.get("job_grade"))) else 0
            rank = (unit_score, dept_score, grade_score)
            if best_rank is None or rank > best_rank:
                best, best_rank = doc, rank
        return best

    def _unit_match(self, query_unit: str, jd_unit: str) -> int:
        """
        2 = the same unit.
        1 = the same unit written differently: one name is the other plus
            trailing words, e.g. 'Mobile Banking' vs 'Mobile Banking Business'.
        0 = a different unit. Whole-WORD prefix only, so 'Merchant Management'
            never matches 'POS Merchant Management' or 'Mobile Money Merchant
            Management', and a unit never inherits its Reconciliation sub-unit.
        """
        a, b = _loose_key(query_unit), _loose_key(jd_unit)
        if not a or not b:
            return 0
        if a == b:
            return 2
        aw, bw = a.split(), b.split()
        short, long_ = (aw, bw) if len(aw) <= len(bw) else (bw, aw)
        if long_[:len(short)] != short:
            return 0
        if ("reconciliation" in aw) != ("reconciliation" in bw):
            return 0
        return 1

    @staticmethod
    def _grade_number(value) -> Optional[int]:
        """'9' / '9.0' / 'JG-13' -> 9 / 9 / 13 ; empty or 'None' -> None."""
        m = re.search(r"\d+", str(value or ""))
        return int(m.group()) if m else None

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

        # Search the index that is already built. Do not re-embed the division.
        index = self.bsc_vectorstore.vectorstore
        ntotal = int(getattr(getattr(index, "index", None), "ntotal", 0) or 0)
        if ntotal <= 0:
            logger.warning("  BSC: stored index is empty → keyword fallback")
            fallback = self._keyword_bsc_fallback(division_docs, query_text, unit, k)
            return query_text, fallback, [0.0] * len(fallback)

        prepared = query_text
        prepare = getattr(self.bsc_vectorstore, "_prepare_query", None)
        if callable(prepare):
            prepared = prepare(query_text)
        results = index.similarity_search_with_score(prepared, k=ntotal)
        if division:
            results = [
                (doc, score) for doc, score in results
                if _normalize(_get_meta(doc).get("division", "")) == div_norm
            ]

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
                bsc_w = _get_bsc_weight(doc)
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
            score += 0.03 * _get_bsc_weight(doc)
            scored[idx] = score

        if not scored:
            return division_docs[:k]

        return [division_docs[i] for i, _ in sorted(scored.items(), key=lambda x: -x[1])[:k]]

    # ── LOS simple filter (kept for compatibility) ────────────────────────────
    def _filter_los(self, department: str) -> list:
        dept_keys = _org().department_match_keys(department)
        return [
            doc for doc in self.los_docs
            if _org().loose_key(_get_meta(doc).get("department", "")) in dept_keys
        ]