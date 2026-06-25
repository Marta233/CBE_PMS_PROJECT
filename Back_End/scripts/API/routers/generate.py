"""
Back_End/scripts/API/routers/generate.py

POST /api/generate — employee form → SMART objectives list
Uses the knowledge base + FAISS index built by the ingestion pipeline.
"""
import json
import logging

import ollama
from fastapi import APIRouter, HTTPException
from langchain_core.documents import Document
from pydantic import BaseModel, Field

from ..config import (
    EMBEDDING_MODEL,
    FAISS_INDEX_PATH,
    KNOWLEDGE_BASE_FILE,
)

logger = logging.getLogger("pms.generate")
router = APIRouter()


# ── Lazy-loaded extractor (initialised on first request) ─────────────────────
_extractor = None


def _get_extractor():
    """
    Build (or return cached) QueryExtractor.
    Called inside the endpoint so startup doesn't crash if the KB is missing.
    """
    global _extractor
    if _extractor is not None:
        return _extractor

    from embedding.embedder import PMSVectorStore          # type: ignore
    from embedding.extractor import QueryExtractor, load_knowledge_base  # type: ignore

    # ── Load knowledge base ───────────────────────────────────────────────────
    if not KNOWLEDGE_BASE_FILE.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                "Knowledge base not found. "
                "Please ingest at least one BSC, JD, and LOS file first."
            ),
        )

    bsc_docs, jd_docs, los_docs = load_knowledge_base(KNOWLEDGE_BASE_FILE)
    logger.info(
        f"Knowledge base loaded — BSC:{len(bsc_docs)} JD:{len(jd_docs)} LOS:{len(los_docs)}"
    )

    # ── BSC vectorstore ───────────────────────────────────────────────────────
    bsc_vs = PMSVectorStore(embedding_model=EMBEDDING_MODEL, index_path=FAISS_INDEX_PATH)

    if FAISS_INDEX_PATH.exists():
        logger.info("Loading existing BSC FAISS index …")
        bsc_vs.load_vectorstore()
    else:
        logger.warning("FAISS index not found — building from knowledge base …")
        lc_bsc = [
            Document(page_content=d.page_content, metadata=d.metadata)
            for d in bsc_docs
        ]
        if lc_bsc:
            bsc_vs.create_vectorstore(lc_bsc)
            bsc_vs.save_vectorstore()
            logger.info(f"FAISS index built with {len(lc_bsc)} documents.")
        else:
            logger.warning("No BSC documents to index — FAISS will be empty.")

    _extractor = QueryExtractor(
        los_docs=los_docs, jd_docs=jd_docs, bsc_vectorstore=bsc_vs
    )
    return _extractor


# ══════════════════════════════════════════════════════════════════════════════
# TERMINAL DISPLAY HELPERS
# ══════════════════════════════════════════════════════════════════════════════

W = 90

def _bar(char="═"):   print(char * W)
def _thin():          print("─" * W)
def _blank():         print()

def _section(title):
    _blank(); _bar("═"); print(f"  {title}"); _bar("═")

def _subsection(title):
    _blank(); print(f"  ── {title} {'─' * (W - len(title) - 6)}")

def _kv(label, value, indent=4):
    print(f"{' ' * indent}{label + ':':<24}{value}")

def _doc_preview(doc, index, max_chars=600):
    from embedding.extractor import _get_meta, _get_text  # type: ignore
    meta = _get_meta(doc)
    text = _get_text(doc)
    print(f"\n    [{index}]  metadata : {json.dumps(meta, ensure_ascii=False)}")
    print(f"         text     : {text[:max_chars]}{'...' if len(text) > max_chars else ''}")

def _display_retrieved(result, jd_ctx, bsc_ctx, los_ctx):
    from embedding.extractor import _get_meta, _get_text  # type: ignore
    _section("STEP 2 OF 4  —  RETRIEVED CONTEXT")
    _subsection("QUERY PARSING RESULT")
    _kv("Division detected",   result.detected_division   or "❌ not detected")
    _kv("Department detected", result.detected_department_name or "❌ not detected")
    _kv("LOS dept key",        result.detected_department or "❌ not detected")
    _kv("Unit detected",       result.detected_unit       or "❌ not detected")
    _kv("Job title detected",  result.detected_job_title  or "❌ not detected")
    _subsection("RETRIEVAL COUNTS")
    _kv("JD document",   "✅  1 found" if result.jd_doc else "❌  not found")
    _kv("BSC documents", f"✅  {len(result.bsc_docs)} retrieved")
    _kv("LOS documents", f"✅  {len(result.los_docs)} retrieved" if result.los_docs else "❌  0 found")
    _kv("JD length",     f"{len(jd_ctx):,} chars")
    _kv("BSC length",    f"{len(bsc_ctx):,} chars")
    _kv("LOS length",    f"{len(los_ctx):,} chars")
    _subsection("JD DOCUMENT")
    if result.jd_doc:
        meta = _get_meta(result.jd_doc)
        text = _get_text(result.jd_doc)
        print(f"    metadata : {json.dumps(meta, ensure_ascii=False)}")
        _blank(); print("    text preview:")
        for line in text[:1200].splitlines():
            print(f"      {line}")
        if len(text) > 1200:
            print(f"      ... [{len(text)-1200:,} more chars]")
    else:
        print("    No JD document found.")
    _subsection(f"BSC DOCUMENTS ({len(result.bsc_docs)} docs)")
    for i, doc in enumerate(result.bsc_docs, 1): _doc_preview(doc, i, 400)
    _subsection(f"LOS DOCUMENTS ({len(result.los_docs)} docs)")
    for i, doc in enumerate(result.los_docs, 1): _doc_preview(doc, i, 400)
    _blank(); _bar()

def _display_prompt_summary(prompt, num_remaining):
    _section("STEP 3 OF 4  —  PROMPT")
    _kv("Prompt length",        f"{len(prompt):,} chars")
    _kv("Objectives requested", f"{num_remaining}  (LLM generates)")
    _kv("LLM model",            "llama3 via Ollama")
    _kv("Temperature",          "0.3")
    _blank(); _bar()

def _display_llm_result(all_objectives, total_weight):
    _section("STEP 4 OF 4  —  LLM OUTPUT")
    _blank()
    for i, obj in enumerate(all_objectives, 1):
        tag = "📌 FIXED" if i == 1 else f"   [{i}]   "
        print(f"  {tag}  {obj.get('objective', '')}")
        _kv("Measure",  obj.get("measure", ""),                          indent=12)
        _kv("Target",   obj.get("target", ""),                           indent=12)
        _kv("Weight",   f"{obj.get('weight_percent', '')}%  |  {obj.get('category', '')}", indent=12)
        _kv("Tracking", f"{obj.get('tracking_source', '')}  |  {obj.get('time_frame', '')}", indent=12)
        _blank()
    _thin()
    status = "✅" if total_weight == 100 else "⚠️ "
    print(f"    Total weight : {total_weight}%  {status}")
    _bar(); _blank()


# ══════════════════════════════════════════════════════════════════════════════
# PYDANTIC MODELS
# ══════════════════════════════════════════════════════════════════════════════

class GenerateRequest(BaseModel):
    division:       str = Field(..., example="Digital Banking")
    department:     str = Field(..., example="Mobile & Internet Banking")
    unit:           str = Field(..., example="Internet Banking Business")
    job_title:      str = Field(..., example="Senior Digital Banking Officer")
    job_grade:      str = Field(..., example="13")
    num_objectives: int = Field(default=5, ge=2, le=10)

class Objective(BaseModel):
    objective:       str
    measure:         str
    target:          str
    weight_percent:  int
    category:        str
    tracking_source: str
    time_frame:      str

class GenerateResponse(BaseModel):
    employee_profile: dict
    objectives:       list[Objective]
    total_weight:     int


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINT
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/generate", response_model=GenerateResponse, tags=["generation"])
def generate(req: GenerateRequest):
    from embedding.extractor import _get_text  # type: ignore
    from llm.prompt_builder import build_prompt, load_critical_target  # type: ignore

    _section("NEW REQUEST  —  /api/generate")
    _subsection("STEP 1 OF 4  —  INPUT")
    _kv("Division",       req.division)
    _kv("Department",     req.department)
    _kv("Unit",           req.unit)
    _kv("Job Title",      req.job_title)
    _kv("Job Grade",      req.job_grade)
    _kv("Num Objectives", str(req.num_objectives))
    _blank(); _bar()

    # ── Get extractor (lazy init) ─────────────────────────────────────────────
    extractor = _get_extractor()

    # ── Build query string ────────────────────────────────────────────────────
    query = (
        f"Division: {req.division}\n"
        f"Department: {req.department}\n"
        f"Unit: {req.unit}\n"
        f"Job Title: {req.job_title}\n"
        f"Job Grade: {req.job_grade}"
    )

    # ── Extract relevant context ──────────────────────────────────────────────
    print("\n  Running extraction …")
    try:
        result = extractor.extract(query, bsc_k=5)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {e}")

    jd_context  = _get_text(result.jd_doc) if result.jd_doc else ""
    bsc_context = "\n\n".join(_get_text(d) for d in result.bsc_docs)
    los_context = "\n\n".join(_get_text(d) for d in result.los_docs)

    _display_retrieved(result, jd_context, bsc_context, los_context)

    # ── Build prompt ──────────────────────────────────────────────────────────
    context = {
        "query":       query,
        "jd_context":  jd_context,
        "bsc_context": bsc_context,
        "los_context": los_context,
    }
    prompt = build_prompt(context, req.num_objectives)
    _display_prompt_summary(prompt, req.num_objectives - 1)

    # ── Call LLM ──────────────────────────────────────────────────────────────
    print("\n  Calling llama3 via Ollama …")
    try:
        response = ollama.chat(
            model="llama3",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a PMS expert for Commercial Bank of Ethiopia. "
                        "Output ONLY valid JSON. No markdown, no explanation."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            options={"temperature": 0.3, "top_p": 0.9},
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ollama error: {e}")

    # ── Parse LLM response ────────────────────────────────────────────────────
    raw = response["message"]["content"].strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        llm_objectives = json.loads(raw).get("objectives", [])
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=502,
            detail=f"LLM returned invalid JSON: {e}. Raw: {raw[:300]}",
        )

    # ── Fix weights to sum to 50 (critical target holds the other 50) ─────────
    for obj in llm_objectives:
        obj["weight_percent"] = int(round(obj.get("weight_percent", 0)))
    llm_weight = sum(o.get("weight_percent", 0) for o in llm_objectives)
    if llm_weight != 50 and llm_objectives:
        llm_objectives[-1]["weight_percent"] += 50 - llm_weight

    # ── Prepend fixed critical target ─────────────────────────────────────────
    all_objectives = [load_critical_target()] + llm_objectives
    total_weight   = sum(o.get("weight_percent", 0) for o in all_objectives)

    _display_llm_result(all_objectives, total_weight)

    return GenerateResponse(
        employee_profile={
            "division":   req.division,
            "department": req.department,
            "unit":       req.unit,
            "job_title":  req.job_title,
            "job_grade":  req.job_grade,
        },
        objectives   = all_objectives,
        total_weight = total_weight,
    )