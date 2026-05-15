"""
extractor.py
------------
Extraction strategy per source:

  JD  → division → department → unit → job title (four-stage funnel) → 1 doc
  LOS → filter by department metadata                                 → all matching
  BSC → keyword boost  +  FAISS similarity, merged and deduplicated  → K docs

Supports both raw dicts {"text": ..., "metadata": {...}}
and LangChain Document objects interchangeably.
"""
from __future__ import annotations
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)
# =========================================================
# MAPS
# =========================================================
# Multiple query keywords can map to the same LOS department metadata value.
# Structure: { "exact metadata value in LOS doc" : ["keyword1", "keyword2", ...] }
# Keywords are matched case-insensitively against the user query.
LOS_DEPARTMENT_MAP: dict[str, list[str]] = {
    "Online Banking ": [
        "online banking",
        "Mobile &Internet Banking",
        "mobile banking",
    ],
    "Card": [
        "card",
        "Card Banking",
           # ATM unit lives under Card department in LOS
    ],
    "Digital_service_devlopment": [
        "digital service development",
    ],
    "Digital Banking Reconciliation": [ 
        "Digital Banking Reconciliation " ,
        "Digital Banking Reconciliation ",
    ],
    "Merchant and Agent Management": [ 
        "merchant and agent management",
        "Merchant and Agent Banking",
        "Merchant and Agent Management",
    ],
}

JD_DIVISION_MAP: dict[str, str] = {
    "digital banking":    "Digital Banking",
    "rbb":                "Retail & Branch Banking",
    "retail banking":     "Retail & Branch Banking",
}

# Words to always ignore when building keyword boost list
_STOP_WORDS = {
    "the", "and", "for", "from", "with", "this", "that", "are", "was",
    "banking", "bank", "digital", "senior", "officer", "support", "operations",
}


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


def _parse_field(doc, field_name: str) -> str:
    text = _get_text(doc)
    m = re.search(rf"{re.escape(field_name)}\s*:\s*(.+)", text, re.IGNORECASE)
    return m.group(1).strip().lower() if m else ""


def _doc_id(doc) -> str:
    """Stable identity for deduplication."""
    return _get_text(doc)[:80]


def _extract_keywords(text: str, min_len: int = 3) -> List[str]:
    """
    Pull meaningful words from a phrase, dropping stop words.
    e.g. "ATM Operations Support" → ["ATM", "Operations"]
    """
    words = re.findall(r"[A-Za-z]+", text)
    return [
        w for w in words
        if len(w) >= min_len and w.lower() not in _STOP_WORDS
    ]


# =========================================================
# RESULT CONTAINER
# =========================================================

@dataclass
class ExtractionResult:
    los_docs: List = field(default_factory=list)
    bsc_docs: List = field(default_factory=list)
    jd_doc:   object = None

    detected_department:      Optional[str] = None
    detected_department_name: Optional[str] = None
    detected_division:        Optional[str] = None
    detected_job_title:       Optional[str] = None
    detected_unit:            Optional[str] = None

    @property
    def summary(self) -> str:
        lines = ["─── Extraction summary ───"]
        lines.append(f"  Division   : {self.detected_division        or '(none)'}")
        lines.append(f"  Department : {self.detected_department_name or '(none)'}")
        lines.append(f"  Unit       : {self.detected_unit            or '(none)'}")
        lines.append(f"  Job title  : {self.detected_job_title       or '(none)'}")
        lines.append(f"  LOS docs   : {len(self.los_docs)}  (department filter)")
        lines.append(f"  BSC docs   : {len(self.bsc_docs)}  (keyword boost + FAISS)")
        lines.append(f"  JD doc     : {'found' if self.jd_doc else 'not found'}  (4-stage funnel)")
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

        # Cache all BSC docs from the vectorstore for keyword scanning
        self._all_bsc_docs: Optional[List] = None

    def _load_all_bsc_docs(self) -> List:
        """Load all docs from FAISS docstore once and cache them."""
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

        result.detected_division        = self._detect_division_keyword(query)
        result.detected_department_name = self._detect_raw_field(query, "department")
        result.detected_unit            = self._detect_raw_field(query, "unit")
        result.detected_job_title       = self._detect_job_title(query)
        result.detected_department      = self._detect_los_department(query)

        logger.info(f"  Division   : {result.detected_division}")
        logger.info(f"  Department : {result.detected_department_name}")
        logger.info(f"  Unit       : {result.detected_unit}")
        logger.info(f"  Job title  : {result.detected_job_title}")

        # ── LOS ──────────────────────────────────────────────
        if result.detected_department:
            result.los_docs = self._filter_los(result.detected_department)
            logger.info(f"  LOS docs   : {len(result.los_docs)}")
        else:
            logger.warning("  No department detected — LOS skipped")

        # ── BSC: keyword boost + FAISS ────────────────────────
        result.bsc_docs = self._retrieve_bsc(
            unit=result.detected_unit,
            job_title=result.detected_job_title,
            department=result.detected_department_name,
            k=bsc_k,
        )
        logger.info(f"  BSC docs   : {len(result.bsc_docs)}")

        # ── JD ───────────────────────────────────────────────
        result.jd_doc = self._match_jd(
            division_keyword=result.detected_division,
            department=result.detected_department_name,
            unit=result.detected_unit,
            job_title=result.detected_job_title,
        )

        logger.info(f"\n{result.summary}")
        return result

    # ----------------------------------------------------------
    # DETECTION
    # ----------------------------------------------------------

    def _detect_los_department(self, query: str) -> Optional[str]:
        """
        Returns the LOS metadata department value that matches the query.
        Tries longer keywords first to avoid short-word false matches
        (e.g. "card" inside "scorecard").
        """
        q = query.lower()
        # flatten to (keyword, metadata_value) pairs, longest keyword first
        pairs = [
            (kw, dept_value)
            for dept_value, keywords in LOS_DEPARTMENT_MAP.items()
            for kw in keywords
        ]
        pairs.sort(key=lambda x: len(x[0]), reverse=True)
        for keyword, dept_value in pairs:
            if keyword in q:
                return dept_value
        return None

    def _detect_division_keyword(self, query: str) -> Optional[str]:
        q = query.lower()
        for keyword in JD_DIVISION_MAP:
            if keyword in q:
                return keyword
        return None

    def _detect_raw_field(self, query: str, field: str) -> Optional[str]:
        m = re.search(rf"{field}\s*:\s*(.+)", query, re.IGNORECASE)
        return m.group(1).strip() if m else None

    def _detect_job_title(self, query: str) -> Optional[str]:
        m = re.search(r"job\s+role\s*:\s*(.+)", query, re.IGNORECASE)
        if m:
            raw = m.group(1).strip()
            return raw.split(":", 1)[-1].strip() if ":" in raw else raw
        m = re.search(r"job\s+title\s*:\s*(.+)", query, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        m = re.search(r"\brole\s*:\s*(.+)", query, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        return None

    # ----------------------------------------------------------
    # BSC RETRIEVAL: keyword boost + FAISS merge
    # ----------------------------------------------------------

    def _retrieve_bsc(
        self,
        unit: Optional[str],
        job_title: Optional[str],
        department: Optional[str],
        k: int,
    ) -> List:
        """
        Step 1 — Keyword boost:
            Extract meaningful words from unit + department (e.g. "ATM").
            Scan every BSC doc's text and KPI metadata for those words.
            These are guaranteed relevant hits FAISS might miss.

        Step 2 — FAISS similarity:
            Search with a focused query (unit + job title).
            Fills remaining slots up to K.

        Step 3 — Merge, deduplicate, cap at K.
        """
        seen_ids = set()
        results  = []

        # ── Step 1: keyword boost ─────────────────────────────
        boost_sources = " ".join(filter(None, [unit, department]))
        keywords = _extract_keywords(boost_sources)
        logger.info(f"  BSC boost keywords: {keywords}")

        if keywords:
            all_bsc = self._load_all_bsc_docs()
            for doc in all_bsc:
                doc_text = (_get_text(doc) + " " + _get_meta(doc).get("kpi", "")).lower()
                if any(kw.lower() in doc_text for kw in keywords):
                    uid = _doc_id(doc)
                    if uid not in seen_ids:
                        seen_ids.add(uid)
                        results.append(doc)

            logger.info(f"  BSC keyword hits  : {len(results)}")

        # ── Step 2: FAISS similarity ──────────────────────────
        remaining = k - len(results)
        if remaining > 0:
            # fetch more from FAISS so we have enough after dedup
            fetch_k = max(remaining + 10, k)
            focused_query = " ".join(filter(None, [unit, job_title, department]))
            if not focused_query:
                focused_query = "digital banking performance"

            try:
                faiss_hits = self.bsc_vectorstore.vectorstore.similarity_search(
                    focused_query, k=fetch_k
                )
                for doc in faiss_hits:
                    uid = _doc_id(doc)
                    if uid not in seen_ids:
                        seen_ids.add(uid)
                        results.append(doc)
                        if len(results) >= k:
                            break
            except Exception as e:
                logger.error(f"  BSC FAISS search failed: {e}")

        return results[:k]

    # ----------------------------------------------------------
    # LOS FILTER
    # ----------------------------------------------------------

    def _filter_los(self, department: str) -> list:
        dept_lower = department.strip().lower()
        return [
            doc for doc in self.los_docs
            if _get_meta(doc).get("department", "").strip().lower() == dept_lower
        ]

    # ----------------------------------------------------------
    # JD FOUR-STAGE FUNNEL
    # ----------------------------------------------------------

    def _match_jd(
        self,
        division_keyword: Optional[str],
        department:       Optional[str],
        unit:             Optional[str],
        job_title:        Optional[str],
    ):
        if not any([division_keyword, department, unit, job_title]):
            return None

        candidates = self.jd_docs

        # Stage 1: division
        if division_keyword:
            jd_div = JD_DIVISION_MAP.get(division_keyword, "").lower()
            filtered = [d for d in candidates if jd_div in _parse_field(d, "division")]
            if filtered:
                candidates = filtered
                logger.info(f"  JD after division  : {len(candidates)}")

        # Stage 2: department
        if department:
            dl = department.strip().lower()
            filtered = [
                d for d in candidates
                if dl in _parse_field(d, "department")
                or _parse_field(d, "department") in dl
            ]
            if filtered:
                candidates = filtered
                logger.info(f"  JD after dept      : {len(candidates)}")
            else:
                logger.warning(f"  JD dept '{department}' not matched — keeping {len(candidates)}")

        # Stage 3: unit
        if unit:
            ul = unit.strip().lower()
            filtered = [
                d for d in candidates
                if ul in _parse_field(d, "unit")
                or _parse_field(d, "unit") in ul
            ]
            if filtered:
                candidates = filtered
                logger.info(f"  JD after unit      : {len(candidates)}")
            else:
                logger.warning(f"  JD unit '{unit}' not matched — keeping {len(candidates)}")

        if not candidates:
            return None

        # Stage 4: job title
        if job_title:
            jt = job_title.strip().lower()

            exact = [d for d in candidates if jt in _parse_field(d, "job title")]
            if exact:
                logger.info(f"  JD title match     : {_parse_field(exact[0], 'job title')}")
                return exact[0]

            words = [w for w in jt.split() if len(w) > 3]
            scored = [
                (sum(1 for w in words if w in _parse_field(d, "job title")), d)
                for d in candidates
            ]
            scored = [(s, d) for s, d in scored if s > 0]
            if scored:
                scored.sort(key=lambda x: x[0], reverse=True)
                best = scored[0][1]
                logger.info(f"  JD partial match   : {_parse_field(best, 'job title')} (score={scored[0][0]})")
                return best

            logger.warning(f"  No title match for '{job_title}' — using top candidate")

        return candidates[0]