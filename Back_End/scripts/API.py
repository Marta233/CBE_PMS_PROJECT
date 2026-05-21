"""
API.py  —  CBE PMS Objective Generation API

  POST /api/generate  →  employee form + num_objectives → objectives list
  GET  /api/health    →  server status

Start:
  uvicorn Back_End.API:app --host 0.0.0.0 --port 8000 --reload

Swagger UI:  http://localhost:8000/docs
"""

from __future__ import annotations

import json
import logging
import os
import sys
import warnings
from pathlib import Path

# ── silence noisy third-party loggers ────────────────────────────────────────
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("langchain").setLevel(logging.ERROR)
logging.getLogger("faiss").setLevel(logging.ERROR)
warnings.filterwarnings("ignore")
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_VERBOSITY"]       = "error"

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("pms")

import ollama
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.documents import Document
from pydantic import BaseModel, Field

# ── path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parents[2]))

from config import FAISS_INDEX_PATH, EMBEDDING_MODEL, LOS_DATA_PATH, JD_DATA_PATH, BSC_Data_PATH
from embedding.embedder  import PMSVectorStore
from embedding.extractor import QueryExtractor, _get_text, _get_meta
from llm.prompt_builder  import build_prompt, load_critical_target

BSC_FAISS_PATH = Path(FAISS_INDEX_PATH)


# ══════════════════════════════════════════════════════════════════════════════
# TERMINAL DISPLAY HELPERS
# ══════════════════════════════════════════════════════════════════════════════

W = 90   # terminal width

def _bar(char="═"):  print(char * W)
def _thin(): print("─" * W)
def _blank(): print()

def _section(title: str):
    _blank()
    _bar("═")
    print(f"  {title}")
    _bar("═")

def _subsection(title: str):
    _blank()
    print(f"  ── {title} {'─' * (W - len(title) - 6)}")

def _kv(label: str, value: str, indent: int = 4):
    pad = " " * indent
    label_col = f"{label}:".ljust(24)
    print(f"{pad}{label_col}{value}")

def _doc_preview(doc, index: int, max_chars: int = 600):
    meta = _get_meta(doc)
    text = _get_text(doc)
    print(f"\n    [{index}]  metadata : {json.dumps(meta, ensure_ascii=False)}")
    print(f"         text     : {text[:max_chars]}{'...' if len(text) > max_chars else ''}")

def _display_retrieved(result, jd_context, bsc_context, los_context):
    """
    Print the full retrieved context summary to the terminal.
    Called inside /api/generate after extraction completes.
    """

    # ── Header ───────────────────────────────────────────────────────────────
    _section("STEP 2 OF 4  —  RETRIEVED CONTEXT  (what the pipeline found for your query)")

    # ── Detection summary ─────────────────────────────────────────────────────
    _subsection("QUERY PARSING RESULT")
    _kv("Division detected",   result.detected_division        or "❌ not detected")
    _kv("Department detected", result.detected_department_name or "❌ not detected")
    _kv("LOS dept key",        result.detected_department      or "❌ not detected")
    _kv("Unit detected",       result.detected_unit            or "❌ not detected")
    _kv("Job title detected",  result.detected_job_title       or "❌ not detected")

    # ── Counts ───────────────────────────────────────────────────────────────
    _subsection("RETRIEVAL COUNTS")
    _kv("JD document",   "✅  1 found"                    if result.jd_doc  else "❌  not found")
    _kv("BSC documents", f"✅  {len(result.bsc_docs)} retrieved  (keyword boost + FAISS similarity)")
    _kv("LOS documents", f"✅  {len(result.los_docs)} retrieved  (department metadata filter)"
                         if result.los_docs else "❌  0 found  (department not matched)")
    _kv("JD length",     f"{len(jd_context):,} chars")
    _kv("BSC length",    f"{len(bsc_context):,} chars  ({len(result.bsc_docs)} docs combined)")
    _kv("LOS length",    f"{len(los_context):,} chars  ({len(result.los_docs)} docs combined)")

    # ── JD ───────────────────────────────────────────────────────────────────
    _subsection("JD DOCUMENT  (1 doc — matched via 4-stage funnel: division → dept → unit → job title)")
    if result.jd_doc:
        meta = _get_meta(result.jd_doc)
        text = _get_text(result.jd_doc)
        print(f"    metadata : {json.dumps(meta, ensure_ascii=False)}")
        _blank()
        print(f"    text preview:")
        for line in text[:1200].splitlines():
            print(f"      {line}")
        if len(text) > 1200:
            print(f"      ... [{len(text)-1200:,} more chars]")
    else:
        print("    No JD document found.")
        print("    Tip: check that Division / Department / Unit / Job Title match your JD JSON metadata.")

    # ── BSC ──────────────────────────────────────────────────────────────────
    _subsection(f"BSC DOCUMENTS  ({len(result.bsc_docs)} docs — keyword boost then FAISS similarity fill)")
    if result.bsc_docs:
        for i, doc in enumerate(result.bsc_docs, 1):
            _doc_preview(doc, i, max_chars=400)
    else:
        print("    No BSC documents retrieved.")

    # ── LOS ──────────────────────────────────────────────────────────────────
    _subsection(f"LOS DOCUMENTS  ({len(result.los_docs)} docs — filtered by department metadata)")
    if result.los_docs:
        for i, doc in enumerate(result.los_docs, 1):
            _doc_preview(doc, i, max_chars=400)
    else:
        print("    No LOS documents found.")
        print("    Tip: check LOS_DEPARTMENT_MAP in extractor.py — your department keyword must be listed.")

    _blank()
    _bar()


def _display_prompt_summary(prompt: str, num_remaining: int):
    _section("STEP 3 OF 4  —  PROMPT  (what is sent to the LLM)")
    _kv("Prompt length",       f"{len(prompt):,} chars")
    _kv("Objectives requested", f"{num_remaining}  (LLM generates these; critical target prepended separately)")
    _kv("LLM model",           "llama3  via Ollama")
    _kv("Temperature",         "0.3  (low = consistent structured output)")
    _blank()
    _bar()


def _display_llm_result(all_objectives: list, total_weight: int):
    _section("STEP 4 OF 4  —  LLM OUTPUT  (generated objectives)")
    _blank()
    for i, obj in enumerate(all_objectives, 1):
        tag = "📌 FIXED" if i == 1 else f"   [{i}]   "
        print(f"  {tag}  {obj.get('objective', '')}")
        _kv("Measure",        obj.get("measure", ""),        indent=12)
        _kv("Target",         obj.get("target", ""),         indent=12)
        _kv("Weight",         f"{obj.get('weight_percent', '')}%  |  {obj.get('category', '')}",  indent=12)
        _kv("Tracking",       f"{obj.get('tracking_source', '')}  |  {obj.get('time_frame', '')}",indent=12)
        _blank()
    _thin()
    status = "✅" if total_weight == 100 else "⚠️ "
    print(f"    Total weight : {total_weight}%  {status}")
    _bar()
    _blank()


# ══════════════════════════════════════════════════════════════════════════════
# STARTUP
# ══════════════════════════════════════════════════════════════════════════════

def _load_json_docs(path) -> list:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Document file not found: {p}")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _build_extractor() -> QueryExtractor:
    _bar("═")
    print("  CBE PMS API  —  Starting up")
    _bar("═")

    print("  [1/3]  Loading documents ...")
    los_docs = _load_json_docs(LOS_DATA_PATH)
    jd_docs  = _load_json_docs(JD_DATA_PATH)
    bsc_raw  = _load_json_docs(BSC_Data_PATH)
    _kv("LOS", f"{len(los_docs)} docs")
    _kv("JD",  f"{len(jd_docs)} docs")
    _kv("BSC", f"{len(bsc_raw)} docs")

    print("\n  [2/3]  Loading embedding model ...")
    _kv("Model", EMBEDDING_MODEL)
    bsc_vs = PMSVectorStore(embedding_model=EMBEDDING_MODEL, index_path=BSC_FAISS_PATH)

    if BSC_FAISS_PATH.exists():
        print("\n  [3/3]  Loading BSC FAISS index from disk ...")
        bsc_vs.load_vectorstore()
    else:
        print("\n  [3/3]  Building BSC FAISS index (first run — may take a minute) ...")
        bsc_lc = [
            Document(page_content=d["text"], metadata=d.get("metadata", {}))
            if isinstance(d, dict) else d
            for d in bsc_raw
        ]
        bsc_vs.create_vectorstore(bsc_lc)
        bsc_vs.save_vectorstore()

    _blank()
    _bar("═")
    print("  ✅  API ready")
    _kv("Swagger UI", "http://localhost:8000/docs")
    _kv("Generate",   "POST http://localhost:8000/api/generate")
    _kv("Health",     "GET  http://localhost:8000/api/health")
    _bar("═")
    _blank()

    return QueryExtractor(los_docs=los_docs, jd_docs=jd_docs, bsc_vectorstore=bsc_vs)


extractor = _build_extractor()


# ══════════════════════════════════════════════════════════════════════════════
# FASTAPI APP
# ══════════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="CBE PMS API",
    description="SMART performance objective generation for CBE employees.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── models ────────────────────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    division:       str = Field(..., example="Digital Banking")
    department:     str = Field(..., example="Mobile &Internet Banking")
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


# ── /api/generate ─────────────────────────────────────────────────────────────

@app.post("/api/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest):

    # ── Request banner ────────────────────────────────────────────────────────
    _section("NEW REQUEST  —  /api/generate")
    _subsection("STEP 1 OF 4  —  INPUT  (received from UI form)")
    _kv("Division",       req.division)
    _kv("Department",     req.department)
    _kv("Unit",           req.unit)
    _kv("Job Title",      req.job_title)
    _kv("Job Grade",      req.job_grade)
    _kv("Num Objectives", str(req.num_objectives))
    _blank()
    _bar()

    # 1. Build query string
    query = (
        f"Division: {req.division}\n"
        f"Department: {req.department}\n"
        f"Unit: {req.unit}\n"
        f"Job Title: {req.job_title}\n"
        f"Job Grade: {req.job_grade}"
    )

    # 2. Extraction
    print(f"\n  Running extraction ...")
    try:
        result = extractor.extract(query, bsc_k=5)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {e}")

    jd_context  = _get_text(result.jd_doc) if result.jd_doc else ""
    bsc_context = "\n\n".join(_get_text(d) for d in result.bsc_docs)
    los_context = "\n\n".join(_get_text(d) for d in result.los_docs)

    # ── Full terminal display of retrieved context ────────────────────────────
    _display_retrieved(result, jd_context, bsc_context, los_context)

    context = {
        "query":       query,
        "jd_context":  jd_context,
        "bsc_context": bsc_context,
        "los_context": los_context,
    }

    # 3. Build prompt
    prompt = build_prompt(context, req.num_objectives)
    _display_prompt_summary(prompt, req.num_objectives - 1)

    # 4. Call Ollama
    print(f"\n  Calling llama3 via Ollama ...")
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

    # 5. Parse
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

    # Fix weight sum to remaining budget
    # fix weight sum
    llm_weight = sum(o.get("weight_percent", 0) for o in llm_objectives)
    if llm_weight != 50 and llm_objectives:
        llm_objectives[-1]["weight_percent"] += 50 - llm_weight
 
    # prepend fixed critical target
    all_objectives = [load_critical_target()] + llm_objectives
    total_weight   = sum(o.get("weight_percent", 0) for o in all_objectives)

    # ── Full terminal display of objectives ───────────────────────────────────
    _display_llm_result(all_objectives, total_weight)

    return GenerateResponse(
        employee_profile={
            "division":   req.division,
            "department": req.department,
            "unit":       req.unit,
            "job_title":  req.job_title,
            "job_grade":  req.job_grade,
        },
        objectives=all_objectives,
        total_weight=total_weight,
    )


@app.get("/api/health")
def health():
    return {"status": "ok"}