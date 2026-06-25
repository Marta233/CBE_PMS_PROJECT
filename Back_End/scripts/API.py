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
import threading
import warnings
from pathlib import Path

# ── path setup (must run before scripts.* / llm.* imports) ───────────────────
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
_PROJECT_ROOT = _SCRIPTS_DIR.parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.append(str(_PROJECT_ROOT))

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

# Ensure unicode output doesn't crash in Windows consoles using cp1252.
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from llm.pipeline import generate_objectives as run_objective_pipeline, get_prompt_preview
from llm.llm_client import check_llm_available, LLMUnavailableError, LLMTimeoutError, probe_llm_health
from llm.sanitize import sanitize_user_field
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.documents import Document
from pydantic import BaseModel, Field

from config import (
    FAISS_INDEX_PATH,
    FAISS_DIVISION_INDEX_DIR,
    EMBEDDING_MODEL,
    LOS_DATA_PATH,
    JD_DATA_PATH,
    BSC_Data_PATH,
    USE_ASYNC_QUEUE,
    RETRIEVAL_CACHE_TTL,
    JOB_RESULT_TTL,
    LLM_BACKEND,
)
from embedding.embedder import PMSVectorStore
from embedding.division_indexes import DivisionIndexManager
from embedding.extractor import QueryExtractor, _get_text, _get_meta
from cache.retrieval_cache import redis_available, cache_stats as retrieval_cache_stats
from cache.generation_cache import cache_stats as step1_cache_stats
from jobs.job_store import (
    create_job,
    get_job,
    JobStatus,
    mark_running,
    mark_completed,
    mark_failed,
    update_job,
)

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

def _build_retrieval_incomplete_detail(job_title: str, result) -> dict:
    """Build a 422 payload when required retrieval sources are missing."""
    failed: list[str] = []
    messages: list[str] = []

    if result.jd_doc is None:
        failed.append("job_description")
        messages.append(
            f'"{job_title}" does not have a job description in the system. '
            "Please reach out to the PMS team to resolve this issue."
        )

    if len(result.bsc_docs) == 0:
        failed.append("bsc")
        messages.append(
            "No Balanced Scorecard (BSC) documents were found for your division/department. "
            "Please reach out to the PMS team to resolve this issue."
        )

    return {
        "error": "retrieval_incomplete",
        "failed": failed,
        "message": " ".join(messages),
        "job_title": job_title,
    }


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


def _display_prompt_summary(preview: dict, num_remaining: int):
    _section("STEP 3 OF 4  —  PROMPTS  (3-step modular pipeline — all values model-generated)")
    chars = preview.get("prompt_chars") if isinstance(preview.get("prompt_chars"), dict) else {}
    _kv("Step 1 (draft)",       f"{len(preview.get('step1_user', '')):,} chars")
    _kv("Step 2 (metrics)",     f"{len(preview.get('step2_user', '')):,} chars")
    _kv("Step 3 (appraisal)",   f"{len(preview.get('step3_user', '')):,} chars")
    if chars:
        _kv("Step 1 (ran)",     f"{chars.get('step1', 0):,} chars")
        _kv("Step 2 (ran)",     f"{chars.get('step2', 0):,} chars")
        _kv("Step 3 (ran)",     f"{chars.get('step3', 0):,} chars")
    _kv("Drafts requested",     preview.get("num_drafts", str(num_remaining)))
    _kv("Remaining weight",     f"{preview.get('remaining_weight', '?')}%  (rules in prompt; model assigns)")
    _kv("LLM model",            f"{LLM_BACKEND}  × 3 calls")
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
        if obj.get("appraisal_logic"):
            _kv("Appraisal 5",  obj["appraisal_logic"].get("rating_5", "")[:80], indent=12)
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

    print("\n  [4/4]  Pre-warming division FAISS sub-indexes ...")
    all_bsc_lc = [
        Document(page_content=d["text"], metadata=d.get("metadata", {}))
        if isinstance(d, dict) else d
        for d in bsc_raw
    ]
    division_indexes = DivisionIndexManager(
        bsc_vs.embeddings,
        FAISS_DIVISION_INDEX_DIR,
    )
    division_indexes.build_or_load(all_bsc_lc)
    for div in division_indexes.divisions:
        _kv(f"  {div}", f"{len(division_indexes.get_division_docs(div))} docs indexed")

    _blank()
    _bar("═")
    print("  ✅  API ready")
    _kv("Swagger UI", "http://localhost:8000/docs")
    _kv("Generate",   "POST http://localhost:8000/api/generate")
    _kv("Health",     "GET  http://localhost:8000/api/health")
    _bar("═")
    _blank()

    return QueryExtractor(
        los_docs=los_docs,
        jd_docs=jd_docs,
        bsc_vectorstore=bsc_vs,
        division_indexes=division_indexes,
    )


extractor = None   # initialised in startup event below


# ══════════════════════════════════════════════════════════════════════════════
# FASTAPI APP
# ══════════════════════════════════════════════════════════════════════════════

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    global extractor
    extractor = _build_extractor()   # runs AFTER middleware is registered
    yield

app = FastAPI(
    title="CBE PMS API",
    description="SMART performance objective generation for CBE employees.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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
    employee_id:    str | None = Field(
        default=None,
        description="Optional HR employee ID for deterministic regeneration",
    )
    fiscal_year:    int | None = Field(
        default=None,
        description="Performance planning fiscal year (defaults to current calendar year)",
    )


class AppraisalLogic(BaseModel):
    rating_5: str
    rating_4: str
    rating_3: str
    rating_2: str
    rating_1: str


class Objective(BaseModel):
    objective:       str
    measure:         str
    target:          str
    weight_percent:  float
    category:        str
    tracking_source: str
    time_frame:      str
    source:          str = Field(default="LLM Generated", description="Source of the objective")
    bsc_kpi:         str | None = None
    bsc_strategic_objective: str | None = None
    los_alignment:   str | None = None
    appraisal_logic: AppraisalLogic | None = None


class GenerateResponse(BaseModel):
    employee_profile: dict
    objectives:       list[Objective]
    total_weight:     float
    pipeline_meta:    dict | None = None


class JobAcceptedResponse(BaseModel):
    job_id: str
    status: str = "queued"
    poll_url: str
    message: str = "Generation queued. Poll poll_url until status is completed."


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    result: GenerateResponse | None = None
    partial_result: GenerateResponse | None = None
    progress: dict | None = None
    error: str | None = None
    detail: dict | None = None


def _async_queue_enabled() -> bool:
    return USE_ASYNC_QUEUE


def _run_generation_background(job_id: str, context: dict, num_objectives: int) -> None:
    """Local background fallback when Redis/Celery are unavailable."""
    mark_running(job_id)
    try:
        def _on_progress(update: dict) -> None:
            update_job(
                job_id,
                status=JobStatus.RUNNING.value,
                progress={
                    "stage": update.get("stage"),
                    "message": update.get("message"),
                },
                partial_result=update.get("partial_result"),
            )

        result = run_objective_pipeline(
            context,
            num_objectives,
            progress_callback=_on_progress,
        )
        mark_completed(job_id, result)
    except LLMTimeoutError as exc:
        mark_failed(job_id, str(exc), detail={"error": "llm_timeout"})
    except LLMUnavailableError as exc:
        mark_failed(job_id, str(exc), detail={"error": "llm_unavailable"})
    except json.JSONDecodeError as exc:
        mark_failed(
            job_id,
            f"LLM returned invalid JSON after retries: {exc}",
            detail={"error": "invalid_json"},
        )
    except ValueError as exc:
        detail = str(exc)
        try:
            parsed = json.loads(detail)
            if isinstance(parsed, dict):
                mark_failed(job_id, "Validation failed", detail=parsed)
                return
        except json.JSONDecodeError:
            pass
        mark_failed(job_id, detail)
    except Exception as exc:
        mark_failed(job_id, f"Pipeline error: {exc}")


def _build_query(req: GenerateRequest) -> str:
    division = sanitize_user_field(req.division)
    department = sanitize_user_field(req.department)
    unit = sanitize_user_field(req.unit)
    job_title = sanitize_user_field(req.job_title)
    job_grade = sanitize_user_field(req.job_grade)
    return (
        f"Division: {division}\n"
        f"Department: {department}\n"
        f"Unit: {unit}\n"
        f"Job Title: {job_title}\n"
        f"Job Grade: {job_grade}"
    )


def _build_context(req: GenerateRequest, query: str, payload: dict) -> dict:
    jd_context, bsc_context, los_context = _contexts_from_payload(payload)
    context = {
        "query": query,
        "jd_context": jd_context,
        "bsc_context": bsc_context,
        "los_context": los_context,
    }
    if req.employee_id:
        context["employee_id"] = sanitize_user_field(req.employee_id)
    if req.fiscal_year is not None:
        context["fiscal_year"] = req.fiscal_year
    return context


def _run_retrieval(req: GenerateRequest, query: str):
    """Run FAISS/JD extraction. Returns (result, contexts, cache_hit)."""
    print(f"\n  Running extraction ...")
    try:
        result = extractor.extract(query, bsc_k=5)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {e}")

    jd_context  = _get_text(result.jd_doc) if result.jd_doc else ""
    bsc_context = "\n\n".join(_get_text(d) for d in result.bsc_docs)
    los_context = "\n\n".join(_get_text(d) for d in result.los_docs)

    payload = {
        "query": query,
        "jd_context": jd_context,
        "bsc_context": bsc_context,
        "los_context": los_context,
        "jd_found": result.jd_doc is not None,
        "bsc_count": len(result.bsc_docs),
        "los_count": len(result.los_docs),
        "detected_division": result.detected_division,
        "detected_department_name": result.detected_department_name,
        "detected_department": result.detected_department,
        "detected_unit": result.detected_unit,
        "detected_job_title": result.detected_job_title,
        "detected_job_grade": result.detected_job_grade,
    }
    return result, payload, False


def _contexts_from_payload(payload: dict) -> tuple[str, str, str]:
    return (
        payload.get("jd_context", ""),
        payload.get("bsc_context", ""),
        payload.get("los_context", ""),
    )


def _run_pipeline_sync(context: dict, num_objectives: int) -> dict:
    try:
        return run_objective_pipeline(context, num_objectives)
    except LLMTimeoutError as e:
        raise HTTPException(
            status_code=504,
            detail={"error": "llm_timeout", "message": str(e)},
        )
    except LLMUnavailableError as e:
        raise HTTPException(
            status_code=503,
            detail={"error": "llm_unavailable", "message": str(e)},
        )
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=502,
            detail={
                "error": "invalid_json",
                "message": f"LLM returned invalid JSON after retries: {e}",
            },
        )
    except ValueError as e:
        detail = str(e)
        try:
            parsed = json.loads(detail)
            if isinstance(parsed, dict) and "validation_errors" in parsed:
                raise HTTPException(status_code=502, detail=parsed)
        except json.JSONDecodeError:
            pass
        raise HTTPException(status_code=502, detail=detail)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Pipeline error: {e}")


def _build_generate_response(result_data: dict) -> GenerateResponse:
    return GenerateResponse(
        employee_profile=result_data["employee_profile"],
        objectives=result_data["objectives"],
        total_weight=result_data["total_weight"],
        pipeline_meta=result_data.get("pipeline_meta"),
    )


# ── /api/generate ─────────────────────────────────────────────────────────────

@app.post("/api/generate")
def generate(req: GenerateRequest, response: Response):

    if extractor is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "server_initializing",
                "message": "Server is still initializing. Please retry in a few seconds.",
            },
        )

    job_title = sanitize_user_field(req.job_title)

    _section("NEW REQUEST  —  /api/generate")
    _subsection("STEP 1 OF 4  —  INPUT  (received from UI form)")
    _kv("Division",       req.division)
    _kv("Department",     req.department)
    _kv("Unit",           req.unit)
    _kv("Job Title",      req.job_title)
    _kv("Job Grade",      req.job_grade)
    _kv("Num Objectives", str(req.num_objectives))
    _kv("Async queue",    "enabled" if _async_queue_enabled() else "sync fallback")
    _blank()
    _bar()

    query = _build_query(req)
    result, payload, cache_hit = _run_retrieval(req, query)

    if not cache_hit:
        jd_context, bsc_context, los_context = _contexts_from_payload(payload)
        _display_retrieved(result, jd_context, bsc_context, los_context)

    if not payload.get("jd_found"):
        print(
            f'\n  ⚠️  No job description found for "{job_title}" — '
            "continuing without JD context"
        )

    if int(payload.get("bsc_count", 0)) == 0:
        detail = _build_retrieval_incomplete_detail(job_title, result)
        print(f"\n  ❌  Retrieval incomplete — blocked generation: {detail['failed']}")
        raise HTTPException(status_code=422, detail=detail)

    jd_context, bsc_context, los_context = _contexts_from_payload(payload)
    if not bsc_context.strip():
        detail = _build_retrieval_incomplete_detail(job_title, result)
        detail["message"] = (
            "No Balanced Scorecard (BSC) context was retrieved. "
            "Please reach out to the PMS team to resolve this issue."
        )
        print(f"\n  ❌  Retrieval empty — blocked generation")
        raise HTTPException(status_code=422, detail=detail)

    try:
        check_llm_available()
    except LLMUnavailableError as e:
        print(f"\n  ❌  LLM unavailable: {e}")
        raise HTTPException(
            status_code=503,
            detail={"error": "llm_unavailable", "message": str(e)},
        )

    context = _build_context(req, query, payload)
    preview = get_prompt_preview(context, req.num_objectives)
    _display_prompt_summary(preview, req.num_objectives - 1)

    if _async_queue_enabled():
        job_id = create_job(ttl=JOB_RESULT_TTL)
        if redis_available():
            from tasks.generation_tasks import run_generation

            run_generation.delay(job_id, context, req.num_objectives)
            print(f"\n  Queued generation job {job_id} (Celery)")
        else:
            thread = threading.Thread(
                target=_run_generation_background,
                args=(job_id, context, req.num_objectives),
                daemon=True,
            )
            thread.start()
            print(f"\n  Queued generation job {job_id} (local background)")
        response.status_code = 202
        return JobAcceptedResponse(
            job_id=job_id,
            poll_url=f"/api/jobs/{job_id}",
        )

    print(f"\n  Running 3-step pipeline (draft → metrics → appraisal) ...")
    result_data = _run_pipeline_sync(context, req.num_objectives)

    for warning in result_data.get("pipeline_meta", {}).get("warnings", []):
        print(f"  ⚠️  {warning}")

    meta = result_data.get("pipeline_meta", {})
    if meta.get("step1_cache_hit"):
        print("  Step 1 cache HIT — skipped draft LLM call")
    if meta.get("seed") is not None:
        print(
            f"  🔒  Deterministic seed: {meta['seed']} "
            f"(employee_id={meta.get('employee_id')}, "
            f"fiscal_year={meta.get('fiscal_year')}, "
            f"prompt_version={meta.get('prompt_version')})"
        )

    _display_llm_result(result_data["objectives"], result_data["total_weight"])

    try:
        return _build_generate_response(result_data)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail={"message": "Response validation failed", "error": str(e)},
        )


@app.get("/api/jobs/{job_id}", response_model=JobStatusResponse)
def get_generation_job(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "job_not_found", "message": "Job not found."},
        )

    status = job.get("status", JobStatus.QUEUED.value)
    out = JobStatusResponse(job_id=job_id, status=status)

    if status == JobStatus.COMPLETED.value and job.get("result"):
        try:
            out.result = _build_generate_response(job["result"])
        except Exception as e:
            out.status = JobStatus.FAILED.value
            out.error = f"Response validation failed: {e}"

    if job.get("partial_result"):
        try:
            out.partial_result = _build_generate_response(job["partial_result"])
        except Exception:
            out.partial_result = None

    if isinstance(job.get("progress"), dict):
        out.progress = job.get("progress")

    if status == JobStatus.FAILED.value:
        out.error = job.get("error")
        out.detail = job.get("detail")

    return out


@app.get("/api/health")
def health():
    llm = probe_llm_health()

    return {
        "status": "ok" if extractor is not None else "initializing",
        "extractor_ready": extractor is not None,
        "llm_available": llm["available"],
        "llm_message": llm["message"],
        "llm_backend": llm["backend"],
        "llm_model": llm["model"],
        "llm_reachable": llm["reachable"],
        "llm_model_loaded": llm["model_loaded"],
        "llm_request_timeout_seconds": llm["request_timeout_seconds"],
        "llm_health_timeout_seconds": llm["health_timeout_seconds"],
        "llm_max_concurrent_requests": llm["max_concurrent_requests"],
        "async_queue_enabled": _async_queue_enabled(),
        "redis_available": redis_available(),
        "retrieval_cache_ttl_seconds": RETRIEVAL_CACHE_TTL,
        "retrieval_cache": retrieval_cache_stats(),
        "step1_cache": step1_cache_stats(),
    }




# @app.post("/api/ingest")
# def ingest_document(
#     file:     UploadFile = File(...),
#     doc_type: str        = Form(...),   # "BSC" | "JD" | "LOS"
# ):
#     """
#     Accept a single uploaded file, parse it into chunks, embed, and add to FAISS.

#     doc_type must be one of: BSC, JD, LOS
#     Supported formats:
#       BSC / LOS : .xlsx .xls .csv .pdf
#       JD        : .pdf  .docx .doc .txt
#     """
#     import shutil, tempfile
#     from pathlib import Path as _Path

#     doc_type = doc_type.upper().strip()
#     if doc_type not in ("BSC", "JD", "LOS"):
#         raise HTTPException(status_code=400, detail=f"doc_type must be BSC, JD, or LOS. Got: {doc_type}")

#     # 1. Save upload to a temp file
#     suffix = _Path(file.filename).suffix.lower()
#     with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
#         shutil.copyfileobj(file.file, tmp)
#         tmp_path = _Path(tmp.name)

#     log.info(f"[INGEST] Received file={file.filename!r}, doc_type={doc_type}, size={tmp_path.stat().st_size} bytes")

#     try:
#         # 2. Parse file into text chunks based on doc_type & format
#         chunks = _parse_file(tmp_path, doc_type, file.filename)

#         if not chunks:
#             raise HTTPException(status_code=422, detail="File parsed but produced 0 chunks. Check file content.")

#         # 3. Build Document objects with metadata
#         from langchain_core.documents import Document as _Doc
#         docs = [
#             _Doc(
#                 page_content=chunk["text"],
#                 metadata={
#                     "source":     doc_type,
#                     "filename":   file.filename,
#                     "division":   chunk.get("division", ""),
#                     "department": chunk.get("department", ""),
#                     "kpi":        chunk.get("kpi", ""),
#                     "chunk_id":   i,
#                 }
#             )
#             for i, chunk in enumerate(chunks)
#         ]

#         # 4. Add to the existing FAISS vector store (in-memory + disk)
#         vector_store.add_documents(docs)
#         log.info(f"[INGEST] Added {len(docs)} chunks from {file.filename!r} to FAISS")

#         return {
#             "filename":  file.filename,
#             "doc_type":  doc_type,
#             "chunks":    len(docs),
#             "status":    "success",
#             "detail":    f"Successfully indexed {len(docs)} chunks",
#         }

#     except HTTPException:
#         raise
#     except Exception as e:
#         log.error(f"[INGEST] Error processing {file.filename!r}: {e}")
#         raise HTTPException(status_code=500, detail=str(e))
#     finally:
#         tmp_path.unlink(missing_ok=True)


# def _parse_file(path, doc_type: str, filename: str) -> list[dict]:
#     """
#     Parse uploaded file into list of {text, division?, department?, kpi?} dicts.
#     Handles xlsx/csv for BSC & LOS, pdf/docx/txt for JD.
#     """
#     suffix = path.suffix.lower()
#     chunks = []

#     # ── EXCEL / CSV (BSC and LOS) ─────────────────────────────────────────────
#     if suffix in (".xlsx", ".xls", ".csv"):
#         try:
#             import pandas as pd
#             df = pd.read_csv(path) if suffix == ".csv" else pd.read_excel(path)
#             df.columns = [str(c).strip() for c in df.columns]
#             df = df.fillna("")
#         except Exception as e:
#             raise ValueError(f"Cannot read spreadsheet: {e}")

#         for _, row in df.iterrows():
#             text = "\n".join(f"{col}: {str(val).strip()}" for col, val in row.items() if str(val).strip())
#             if text.strip():
#                 chunk = {"text": text}
#                 # try to extract common metadata columns
#                 for col in df.columns:
#                     cl = col.lower()
#                     if   "division"   in cl: chunk["division"]   = str(row[col]).strip()
#                     elif "department" in cl: chunk["department"] = str(row[col]).strip()
#                     elif "kpi"        in cl: chunk["kpi"]        = str(row[col]).strip()
#                 chunks.append(chunk)
#         return chunks

#     # ── PDF ───────────────────────────────────────────────────────────────────
#     if suffix == ".pdf":
#         try:
#             import pdfplumber
#             with pdfplumber.open(path) as pdf:
#                 for page in pdf.pages:
#                     text = (page.extract_text() or "").strip()
#                     if text:
#                         # split into ~500-char chunks
#                         for i in range(0, len(text), 500):
#                             segment = text[i:i+500].strip()
#                             if segment:
#                                 chunks.append({"text": segment})
#         except ImportError:
#             # fallback: pypdf
#             try:
#                 from pypdf import PdfReader
#                 reader = PdfReader(str(path))
#                 for page in reader.pages:
#                     text = (page.extract_text() or "").strip()
#                     for i in range(0, len(text), 500):
#                         segment = text[i:i+500].strip()
#                         if segment:
#                             chunks.append({"text": segment})
#             except Exception as e:
#                 raise ValueError(f"Cannot read PDF: {e}")
#         return chunks

#     # ── DOCX ──────────────────────────────────────────────────────────────────
#     if suffix in (".docx", ".doc"):
#         try:
#             from docx import Document as _DocxDoc
#             doc = _DocxDoc(str(path))
#             full_text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
#             for i in range(0, len(full_text), 500):
#                 segment = full_text[i:i+500].strip()
#                 if segment:
#                     chunks.append({"text": segment})
#         except Exception as e:
#             raise ValueError(f"Cannot read DOCX: {e}")
#         return chunks

#     # ── TXT ───────────────────────────────────────────────────────────────────
#     if suffix == ".txt":
#         text = path.read_text(encoding="utf-8", errors="ignore").strip()
#         for i in range(0, len(text), 500):
#             segment = text[i:i+500].strip()
#             if segment:
#                 chunks.append({"text": segment})
#         return chunks

#     raise ValueError(f"Unsupported file type: {suffix}. Accepted: xlsx, xls, csv, pdf, docx, doc, txt")


# # ── /api/rebuild-index ────────────────────────────────────────────────────────
# @app.post("/api/rebuild-index")
# def rebuild_index():
#     """
#     Save the current in-memory FAISS index to disk so the pipeline
#     picks up newly ingested documents on the next generation call.
#     """
#     try:
#         vector_store.save(str(BSC_FAISS_PATH))
#         log.info("[REBUILD] FAISS index saved to disk")
#         return {"status": "ok", "message": f"Index rebuilt and saved to {BSC_FAISS_PATH}"}
#     except Exception as e:
#         log.error(f"[REBUILD] Failed: {e}")
#         raise HTTPException(status_code=500, detail=str(e))