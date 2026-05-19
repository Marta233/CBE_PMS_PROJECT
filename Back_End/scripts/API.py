"""
API.py  —  CBE PMS Objective Generation API

  POST /api/generate  →  employee form + num_objectives → objectives list
  GET  /api/health    →  server status

Start:
  uvicorn API:app --host 0.0.0.0 --port 8000 --reload

Swagger UI:  http://localhost:8000/docs
"""

from __future__ import annotations

import json
import logging
import os
import sys
import warnings
from pathlib import Path

# ── silence noisy third-party loggers before anything else ───────────────────
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("langchain").setLevel(logging.ERROR)
logging.getLogger("faiss").setLevel(logging.ERROR)
warnings.filterwarnings("ignore")
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_VERBOSITY"]       = "error"

# ── clean app logger ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)
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
from embedding.extractor import QueryExtractor, _get_text
from llm.prompt_builder  import build_prompt, load_critical_target

BSC_FAISS_PATH = Path(FAISS_INDEX_PATH)


# ── helpers ───────────────────────────────────────────────────────────────────
def _load_json_docs(path) -> list:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Document file not found: {p}")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


# ── startup: load docs + vectorstore once ─────────────────────────────────────
def _build_extractor() -> QueryExtractor:
    log.info("━" * 55)
    log.info("  CBE PMS API  —  Starting up")
    log.info("━" * 55)

    log.info("  Loading documents ...")
    los_docs = _load_json_docs(LOS_DATA_PATH)
    jd_docs  = _load_json_docs(JD_DATA_PATH)
    bsc_raw  = _load_json_docs(BSC_Data_PATH)
    log.info(f"    LOS : {len(los_docs)} docs")
    log.info(f"    JD  : {len(jd_docs)} docs")
    log.info(f"    BSC : {len(bsc_raw)} docs")

    log.info("  Loading embedding model ...")
    bsc_vs = PMSVectorStore(embedding_model=EMBEDDING_MODEL, index_path=BSC_FAISS_PATH)

    if BSC_FAISS_PATH.exists():
        log.info("  Loading BSC FAISS index from disk ...")
        bsc_vs.load_vectorstore()
    else:
        log.info("  Building BSC FAISS index (first run) ...")
        bsc_lc = [
            Document(page_content=d["text"], metadata=d.get("metadata", {}))
            if isinstance(d, dict) else d
            for d in bsc_raw
        ]
        bsc_vs.create_vectorstore(bsc_lc)
        bsc_vs.save_vectorstore()

    log.info("━" * 55)
    log.info("  ✅  API ready  —  http://localhost:8000/docs")
    log.info("━" * 55)

    return QueryExtractor(
        los_docs=los_docs,
        jd_docs=jd_docs,
        bsc_vectorstore=bsc_vs,
    )


extractor = _build_extractor()


# ── FastAPI app ───────────────────────────────────────────────────────────────
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
    department:     str = Field(..., example="Card Banking")
    unit:           str = Field(..., example="ATM Operations")
    job_title:      str = Field(..., example="Junior Officer")
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


# ── endpoint ──────────────────────────────────────────────────────────────────
@app.post("/api/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest):

    log.info("─" * 55)
    log.info(f"  REQUEST  │  {req.job_title}  │  {req.department}  │  Grade {req.job_grade}")
    log.info("─" * 55)

    # 1. build query
    query = (
        f"Division: {req.division}\n"
        f"Department: {req.department}\n"
        f"Unit: {req.unit}\n"
        f"Job Title: {req.job_title}\n"
        f"Job Grade: {req.job_grade}"
    )

    # 2. extraction
    log.info("  [1/4]  Extracting context ...")
    try:
        result = extractor.extract(query, bsc_k=5)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {e}")

    log.info(f"         JD  : {'✅ found' if result.jd_doc else '❌ not found'}")
    log.info(f"         BSC : {len(result.bsc_docs)} docs")
    log.info(f"         LOS : {len(result.los_docs)} docs")

    jd_context  = _get_text(result.jd_doc) if result.jd_doc else ""
    bsc_context = "\n\n".join(_get_text(d) for d in result.bsc_docs)
    los_context = "\n\n".join(_get_text(d) for d in result.los_docs)
    context = {
        "query": query,
        "jd_context":  jd_context,
        "bsc_context": bsc_context,
        "los_context": los_context,
    }
            # ============================================
    log.info("=" * 80)
    log.info("RETRIEVED CONTEXT DEBUG")

    log.info(f"JD length  : {len(jd_context)}")
    log.info(f"BSC length : {len(bsc_context)}")
    log.info(f"LOS length : {len(los_context)}")

    log.info("JD preview:")
    log.info(jd_context[:1000] if jd_context else "No JD found")

    for i, doc in enumerate(result.bsc_docs, 1):
        txt = _get_text(doc)
        log.info(f"BSC Doc {i} | len={len(txt)}")
        log.info(txt[:500])

    for i, doc in enumerate(result.los_docs, 1):
        txt = _get_text(doc)
        log.info(f"LOS Doc {i} | len={len(txt)}")
        log.info(txt[:500])

    log.info("=" * 80)

    print("=" * 100)
    # 3. build prompt
    log.info("  [2/4]  Building prompt ...")
    prompt = build_prompt(context, req.num_objectives)
    log.info(f"         Requesting {req.num_objectives - 1} objectives from LLM ...")

    # 4. call Ollama
    log.info("  [3/4]  Calling Ollama (llama3) ...")
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

    # 5. parse
    log.info("  [4/4]  Parsing LLM response ...")
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

    # fix weight sum
    llm_weight = sum(o.get("weight_percent", 0) for o in llm_objectives)
    if llm_weight != 50 and llm_objectives:
        llm_objectives[-1]["weight_percent"] += 50 - llm_weight

    # prepend fixed critical target
    all_objectives = [load_critical_target()] + llm_objectives
    total_weight   = sum(o.get("weight_percent", 0) for o in all_objectives)

    log.info(f"  ✅  Done  │  {len(all_objectives)} objectives  │  Total weight: {total_weight}%")
    log.info("─" * 55)

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