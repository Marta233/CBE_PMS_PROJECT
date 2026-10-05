"""
Back_End/scripts/API/routers/generate.py

POST /api/generate — employee form → SMART objectives (3-step LLM pipeline)
GET  /api/jobs/{job_id} — poll async generation jobs
"""
from __future__ import annotations

import csv
import json
import logging
import os
import sys
import threading
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Response
from langchain_core.documents import Document
from pydantic import BaseModel, Field

from cache.retrieval_cache import redis_available
from config import JOB_RESULT_TTL, LLM_BACKEND, USE_ASYNC_QUEUE
from jobs.job_store import (
    JobStatus,
    create_job,
    get_job,
    mark_completed,
    mark_failed,
    mark_running,
    update_job,
)
from llm.llm_client import LLMTimeoutError, LLMUnavailableError, check_llm_available
from llm.pipeline import generate_objectives as run_objective_pipeline
from llm.pipeline import get_prompt_preview
from llm.sanitize import sanitize_user_field

from ..config import EMBEDDING_MODEL, FAISS_INDEX_PATH, KNOWLEDGE_BASE_FILE

logger = logging.getLogger("pms.generate")
router = APIRouter()

_extractor = None
_extractor_signature: tuple | None = None
_extractor_lock = threading.Lock()

W = 90


def _mtime(path: Path) -> int:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return 0


def _knowledge_signature() -> tuple:
    """
    Changes whenever ingestion rewrites knowledge_base.json or rebuilds the BSC
    FAISS index. _get_extractor() compares it, so a re-upload through
    /api/ingest is picked up WITHOUT restarting the server (previously the
    extractor was cached forever and kept serving the old documents).
    """
    try:
        faiss_m = max(
            (_mtime(f) for f in FAISS_INDEX_PATH.rglob("*") if f.is_file()),
            default=0,
        )
    except OSError:
        faiss_m = 0
    return (_mtime(KNOWLEDGE_BASE_FILE), faiss_m)


def _get_extractor():
    """
    Build (or return cached) QueryExtractor from the ingested knowledge base.
    Rebuilt automatically when knowledge_base.json / the BSC index change on disk.
    """
    global _extractor, _extractor_signature
    signature = _knowledge_signature()
    if _extractor is not None and signature == _extractor_signature:
        return _extractor

    with _extractor_lock:
        signature = _knowledge_signature()
        if _extractor is not None and signature == _extractor_signature:
            return _extractor  # another request already reloaded it
        if _extractor is not None:
            logger.info("Knowledge base changed on disk — reloading extractor …")
        return _build_extractor(signature)


def _build_extractor(signature: tuple):
    global _extractor, _extractor_signature

    from embedding.embedder import PMSVectorStore  # type: ignore
    from embedding.extractor import QueryExtractor, load_knowledge_base  # type: ignore

    if not KNOWLEDGE_BASE_FILE.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                "Knowledge base not found. "
                "Please ingest at least one BSC, JD, and LOS file first."
            ),
        )

    bsc_docs, jd_docs, los_docs, work_plan_docs = load_knowledge_base(KNOWLEDGE_BASE_FILE)
    logger.info(
        "Knowledge base loaded — BSC:%s JD:%s LOS:%s WorkPlan:%s",
        len(bsc_docs),
        len(jd_docs),
        len(los_docs),
        len(work_plan_docs),
    )

    bsc_vs = PMSVectorStore(embedding_model=EMBEDDING_MODEL, index_path=FAISS_INDEX_PATH)
    built_index = False
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
            built_index = True
            logger.info("FAISS index built with %s documents.", len(lc_bsc))

    _extractor = QueryExtractor(
        los_docs=los_docs,
        jd_docs=jd_docs,
        bsc_vectorstore=bsc_vs,
        work_plan_docs=work_plan_docs,
    )
    # If we just wrote the FAISS index ourselves, re-read the signature so that
    # write doesn't look like a "change" and trigger a second, pointless reload.
    _extractor_signature = _knowledge_signature() if built_index else signature
    return _extractor


def _bar(char="="):
    print(char * W)


def _thin():
    print("-" * W)


def _blank():
    print()


def _section(title: str):
    _blank()
    _bar()
    print(f"  {title}")
    _bar()


def _subsection(title: str):
    _blank()
    print(f"  -- {title} {'-' * (W - len(title) - 6)}")


def _kv(label: str, value: str, indent: int = 4):
    print(f"{' ' * indent}{label + ':':<24}{value}")


def _doc_preview(doc, index: int, max_chars: int = 600):
    from embedding.extractor import _get_meta, _get_text  # type: ignore

    meta = _get_meta(doc)
    text = _get_text(doc)
    print(f"\n    [{index}]  metadata : {json.dumps(meta, ensure_ascii=False)}")
    print(f"         text     : {text[:max_chars]}{'...' if len(text) > max_chars else ''}")


def _build_retrieval_incomplete_detail(job_title: str, result) -> dict:
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


def _display_retrieved(result, jd_context, bsc_context, los_context, work_plan_context):
    from embedding.extractor import _get_text  # type: ignore

    _section("STEP 2 OF 4  —  RETRIEVED CONTEXT")
    _subsection("QUERY PARSING RESULT")
    _kv("Division detected", result.detected_division or "not detected")
    _kv("Department detected", result.detected_department_name or "not detected")
    _kv("LOS dept key", result.detected_department or "not detected")
    _kv("Unit detected", result.detected_unit or "not detected")
    _kv("Job title detected", result.detected_job_title or "not detected")
    _subsection("RETRIEVAL COUNTS")
    _kv("JD document", "1 found" if result.jd_doc else "not found")
    _kv("BSC documents", f"{len(result.bsc_docs)} retrieved")
    _kv(
        "LOS documents",
        f"{len(result.los_docs)} retrieved" if result.los_docs else "0 found",
    )
    _kv(
        "Work Plan documents",
        f"{len(result.work_plan_docs)} retrieved (Priority 1)" if result.work_plan_docs else "0 found",
    )
    _kv("JD length", f"{len(jd_context):,} chars")
    _kv("BSC length", f"{len(bsc_context):,} chars")
    _kv("LOS length", f"{len(los_context):,} chars")
    _kv("Work Plan length", f"{len(work_plan_context):,} chars")
    _subsection("WORK PLAN DOCUMENTS (Priority 1)")
    if result.work_plan_docs:
        for i, doc in enumerate(result.work_plan_docs, 1):
            _doc_preview(doc, i, 300)
    else:
        print("    No Work Plan documents found for this unit/department.")
    _subsection("JD DOCUMENT")
    if result.jd_doc:
        from embedding.extractor import _get_meta  # type: ignore

        meta = _get_meta(result.jd_doc)
        text = _get_text(result.jd_doc)
        print(f"    metadata : {json.dumps(meta, ensure_ascii=False)}")
        _blank()
        print("    text preview:")
        for line in text[:1200].splitlines():
            print(f"      {line}")
        if len(text) > 1200:
            print(f"      ... [{len(text) - 1200:,} more chars]")
    else:
        print("    No JD document found.")
    _subsection(f"BSC DOCUMENTS ({len(result.bsc_docs)} docs)")
    for i, doc in enumerate(result.bsc_docs, 1):
        _doc_preview(doc, i, 400)
    _subsection(f"LOS DOCUMENTS ({len(result.los_docs)} docs)")
    for i, doc in enumerate(result.los_docs, 1):
        _doc_preview(doc, i, 400)
    _blank()
    _bar()


def _display_prompt_summary(preview: dict, num_remaining: int):
    _section("STEP 3 OF 4  —  PROMPTS  (3-step modular pipeline)")
    chars = preview.get("prompt_chars") if isinstance(preview.get("prompt_chars"), dict) else {}
    _kv("Step 1 (draft)", f"{len(preview.get('step1_user', '')):,} chars")
    _kv("Step 2 (metrics)", f"{len(preview.get('step2_user', '')):,} chars")
    _kv("Step 3 (appraisal)", f"{len(preview.get('step3_user', '')):,} chars")
    if chars:
        _kv("Step 1 (ran)", f"{chars.get('step1', 0):,} chars")
        _kv("Step 2 (ran)", f"{chars.get('step2', 0):,} chars")
        _kv("Step 3 (ran)", f"{chars.get('step3', 0):,} chars")
    _kv("Drafts requested", preview.get("num_drafts", str(num_remaining)))
    _kv("Remaining weight", f"{preview.get('remaining_weight', '?')}%")
    _kv("LLM model", f"{LLM_BACKEND} x 3 calls")
    _blank()
    _bar()


def _flush():
    sys.stdout.flush()


def _display_objectives_block(
    objectives: list,
    total_weight: int | float,
    *,
    title: str,
    show_appraisal: bool = True,
    draft_mode: bool = False,
) -> None:
    _section(title)
    _blank()
    for i, obj in enumerate(objectives, 1):
        is_critical = obj.get("category") == "Major Critical"
        tag = "CRITICAL" if is_critical else f"   [{i}]   "
        print(f"  {tag}  {obj.get('objective', '')}")
        if draft_mode:
            _kv("BSC KPI", obj.get("bsc_kpi", "") or "—", indent=12)
            _kv("BSC objective", obj.get("bsc_strategic_objective", "") or "—", indent=12)
            _kv("LOS alignment", obj.get("los_alignment", "") or "—", indent=12)
            _kv("Source", obj.get("source", "LLM Draft"), indent=12)
        else:
            _kv("Measure", obj.get("measure", ""), indent=12)
            _kv("Target", obj.get("target", ""), indent=12)
            _kv(
                "Weight",
                f"{obj.get('weight_percent', '')}%  |  {obj.get('category', '')}",
                indent=12,
            )
            _kv(
                "Tracking",
                f"{obj.get('tracking_source', '')}  |  {obj.get('time_frame', '')}",
                indent=12,
            )
            if show_appraisal and obj.get("appraisal_logic"):
                _kv(
                    "Appraisal 5",
                    obj["appraisal_logic"].get("rating_5", "")[:80],
                    indent=12,
                )
        _blank()
    if not draft_mode:
        _thin()
        status = "OK" if total_weight == 100 else "WARN"
        print(f"    Total weight : {total_weight}%  {status}")
    _bar()
    _blank()
    _flush()


def _display_pipeline_progress(update: dict) -> None:
    """Print partial pipeline output after each LLM step completes."""
    stage = update.get("stage", "")
    message = update.get("message", "")
    partial = update.get("partial_result") or {}
    objectives = partial.get("objectives") or []
    total_weight = partial.get("total_weight", 0)

    if stage == "step1_draft":
        if message:
            print(f"\n  {message}")
        _display_objectives_block(
            objectives,
            total_weight,
            title="PIPELINE STEP 1/3  —  DRAFT OBJECTIVES",
            show_appraisal=False,
            draft_mode=True,
        )
    elif stage == "step2_metrics":
        if message:
            print(f"\n  {message}")
        _display_objectives_block(
            objectives,
            total_weight,
            title="PIPELINE STEP 2/3  —  METRICS & WEIGHTS",
            show_appraisal=False,
            draft_mode=False,
        )
    elif stage == "step3_appraisal":
        if message:
            print(f"\n  {message}")
        _flush()
    elif stage == "step3_failed":
        print(f"\n  WARNING: {message}")
        _flush()


def _display_llm_result(all_objectives: list, total_weight: int):
    _display_objectives_block(
        all_objectives,
        total_weight,
        title="STEP 4 OF 4  —  LLM OUTPUT  (final objectives + appraisal)",
        show_appraisal=True,
        draft_mode=False,
    )


class GenerateRequest(BaseModel):
    division: str = Field(..., example="Digital Banking")
    department: str = Field(..., example="Mobile & Internet Banking")
    unit: str = Field(..., example="Internet Banking Business")
    job_title: str = Field(..., example="Senior Digital Banking Officer")
    job_grade: str = Field(..., example="13")
    num_objectives: int = Field(default=5, ge=2, le=10)
    employee_id: str | None = Field(
        default=None,
        description="Optional HR employee ID for deterministic regeneration",
    )
    fiscal_year: int | None = Field(
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
    objective: str
    measure: str
    target: str
    weight_percent: float
    category: str
    tracking_source: str
    time_frame: str
    source: str = Field(default="LLM Generated")
    bsc_kpi: str | None = None
    bsc_strategic_objective: str | None = None
    los_alignment: str | None = None
    appraisal_logic: AppraisalLogic | None = None


class GenerateResponse(BaseModel):
    employee_profile: dict
    objectives: list[Objective]
    total_weight: float
    pipeline_meta: dict | None = None


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
    mark_running(job_id)
    try:
        def _on_progress(update: dict) -> None:
            _display_pipeline_progress(update)
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
    return (
        f"Division: {sanitize_user_field(req.division)}\n"
        f"Department: {sanitize_user_field(req.department)}\n"
        f"Unit: {sanitize_user_field(req.unit)}\n"
        f"Job Title: {sanitize_user_field(req.job_title)}\n"
        f"Job Grade: {sanitize_user_field(req.job_grade)}"
    )


def _contexts_from_payload(payload: dict) -> tuple[str, str, str, str]:
    return (
        payload.get("jd_context", ""),
        payload.get("bsc_context", ""),
        payload.get("los_context", ""),
        payload.get("work_plan_context", ""),
    )


def _build_context(req: GenerateRequest, query: str, payload: dict) -> dict:
    jd_context, bsc_context, los_context, work_plan_context = _contexts_from_payload(payload)
    context = {
        "query": query,
        "jd_context": jd_context,
        "bsc_context": bsc_context,
        "los_context": los_context,
        "work_plan_context": work_plan_context,
    }
    if req.employee_id:
        context["employee_id"] = sanitize_user_field(req.employee_id)
    if req.fiscal_year is not None:
        context["fiscal_year"] = req.fiscal_year
    return context


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _save_retrieval_report(query: str, result, payload: dict, extra: dict | None = None):
    """
    Save a readable Markdown report of what was retrieved for this request, to
    <knowledge base folder>/reports/  (e.g. Data/documents/reports/).

    OFF by default — the CSV in _save_context_csv() is the default saver.
    Best-effort: a problem here must NEVER break generation.
      PMS_SAVE_RETRIEVAL_REPORTS=1   turn these Markdown reports ON
      PMS_REPORTS_KEEP=200           keep only the newest N reports (default 200)
    """
    if os.getenv("PMS_SAVE_RETRIEVAL_REPORTS", "0").strip().lower() not in ("1", "true", "yes", "on"):
        return None
    try:
        from embedding.retrieval_report import prune_reports, write_report  # type: ignore

        out_dir = KNOWLEDGE_BASE_FILE.parent / "reports"
        contexts = {
            key: payload.get(key, "")
            for key in ("work_plan_context", "jd_context", "bsc_context", "los_context")
        }
        path, checks = write_report(query, result, contexts, out_dir, extra=extra)
        prune_reports(out_dir, keep=_env_int("PMS_REPORTS_KEEP", 200))

        print(f"\n  Retrieval report saved -> {path}")
        for level, message in checks:
            if level == "warn":
                print(f"    WARNING: {message}")
        return path, checks
    except Exception as exc:  # noqa: BLE001 — reporting must not break generation
        logger.warning("Could not save retrieval report: %s", exc)
        return None


_CSV_COLUMNS = [
    "timestamp", "employee_id", "fiscal_year",
    "division", "department", "unit", "job_title", "job_grade",
    "work_plan_docs", "jd_docs", "bsc_docs", "los_docs",
    "work_plan_department_detected", "unit_detected",
    "work_plan_context", "jd_context", "bsc_context", "los_context",
]
_csv_lock = threading.Lock()


def _csv_safe(value) -> str:
    """Stop Excel treating a cell as a formula (= + - @): the request fields are user input."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def _write_context_row(path: Path, row: list) -> None:
    is_new = not path.exists() or path.stat().st_size == 0
    # utf-8-sig = UTF-8 with a BOM so Excel shows the text correctly (Python writes
    # the BOM only once, at the start of a new file, even in append mode).
    with path.open("a", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        if is_new:
            writer.writerow(_CSV_COLUMNS)
        writer.writerow(row)


def _save_context_csv(result, payload: dict, extra: dict | None = None):
    """
    Append ONE ROW PER REQUEST — the exact retrieved context that goes to the LLM —
    to <knowledge base folder>/retrieved_contexts.csv (e.g. Data/documents/).
    This is the API-side equivalent of what process_embeddings.py saves.

    Best-effort: a problem here must NEVER break generation.
      PMS_SAVE_CONTEXT_CSV=0   turn saving off
    """
    if os.getenv("PMS_SAVE_CONTEXT_CSV", "1").strip().lower() in ("0", "false", "no", "off"):
        return None
    try:
        extra = extra or {}
        row = [_csv_safe(v) for v in (
            datetime.now().isoformat(timespec="seconds"),
            extra.get("employee_id"), extra.get("fiscal_year"),
            extra.get("division"), extra.get("department"), extra.get("unit"),
            extra.get("job_title"), extra.get("job_grade"),
            payload.get("work_plan_count", 0), 1 if payload.get("jd_found") else 0,
            payload.get("bsc_count", 0), payload.get("los_count", 0),
            getattr(result, "detected_work_plan_department", None), getattr(result, "detected_unit", None),
            payload.get("work_plan_context", ""), payload.get("jd_context", ""),
            payload.get("bsc_context", ""), payload.get("los_context", ""),
        )]
        path = KNOWLEDGE_BASE_FILE.parent / "retrieved_contexts.csv"
        with _csv_lock:
            try:
                _write_context_row(path, row)
            except PermissionError:
                # Windows locks a CSV that is open in Excel. Keep the row in a side
                # file instead of losing it (and instead of failing the request).
                path = path.with_name(f"{path.stem}_locked_{datetime.now():%Y%m%d_%H%M%S_%f}{path.suffix}")
                _write_context_row(path, row)
                logger.warning("retrieved_contexts.csv is open elsewhere (Excel?) - "
                               "saved this row to %s instead", path.name)
        print(f"\n  Context saved to CSV -> {path}")
        return path
    except Exception as exc:  # noqa: BLE001 — saving must not break generation
        logger.warning("Could not save context CSV: %s", exc)
        return None


def _run_retrieval(query: str, extra: dict | None = None):
    from embedding.extractor import _get_text  # type: ignore

    extractor = _get_extractor()
    print("\n  Running extraction …")
    try:
        result = extractor.extract(query, bsc_k=5)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {e}") from e

    jd_context = _get_text(result.jd_doc) if result.jd_doc else ""
    bsc_context = "\n\n".join(_get_text(d) for d in result.bsc_docs)
    los_context = "\n\n".join(_get_text(d) for d in result.los_docs)
    work_plan_context = "\n\n".join(_get_text(d) for d in result.work_plan_docs)

    payload = {
        "query": query,
        "jd_context": jd_context,
        "bsc_context": bsc_context,
        "los_context": los_context,
        "work_plan_context": work_plan_context,
        "jd_found": result.jd_doc is not None,
        "bsc_count": len(result.bsc_docs),
        "los_count": len(result.los_docs),
        "work_plan_count": len(result.work_plan_docs),
    }
    _save_context_csv(result, payload, extra)
    report = _save_retrieval_report(query, result, payload, extra)
    if report:
        payload["report_path"] = str(report[0])
    return result, payload


def _run_pipeline_sync(context: dict, num_objectives: int) -> dict:
    try:
        return run_objective_pipeline(
            context,
            num_objectives,
            progress_callback=_display_pipeline_progress,
        )
    except LLMTimeoutError as e:
        raise HTTPException(
            status_code=504,
            detail={"error": "llm_timeout", "message": str(e)},
        ) from e
    except LLMUnavailableError as e:
        raise HTTPException(
            status_code=503,
            detail={"error": "llm_unavailable", "message": str(e)},
        ) from e
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=502,
            detail={
                "error": "invalid_json",
                "message": f"LLM returned invalid JSON after retries: {e}",
            },
        ) from e
    except ValueError as e:
        detail = str(e)
        try:
            parsed = json.loads(detail)
            if isinstance(parsed, dict) and "validation_errors" in parsed:
                raise HTTPException(status_code=502, detail=parsed) from e
        except json.JSONDecodeError:
            pass
        raise HTTPException(status_code=502, detail=detail) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Pipeline error: {e}") from e


def _build_generate_response(result_data: dict) -> GenerateResponse:
    return GenerateResponse(
        employee_profile=result_data["employee_profile"],
        objectives=result_data["objectives"],
        total_weight=result_data["total_weight"],
        pipeline_meta=result_data.get("pipeline_meta"),
    )


@router.post("/generate", tags=["generation"])
def generate(req: GenerateRequest, response: Response):
    job_title = sanitize_user_field(req.job_title)

    _section("NEW REQUEST  —  /api/generate")
    _subsection("STEP 1 OF 4  —  INPUT")
    _kv("Division", req.division)
    _kv("Department", req.department)
    _kv("Unit", req.unit)
    _kv("Job Title", req.job_title)
    _kv("Job Grade", req.job_grade)
    _kv("Num Objectives", str(req.num_objectives))
    _kv("Async queue", "enabled" if _async_queue_enabled() else "sync")
    _blank()
    _bar()

    query = _build_query(req)
    result, payload = _run_retrieval(
        query,
        extra={
            "source": "POST /api/generate",
            "employee_id": sanitize_user_field(req.employee_id) if req.employee_id else None,
            "fiscal_year": req.fiscal_year,
            "num_objectives": req.num_objectives,
            "division": sanitize_user_field(req.division),
            "department": sanitize_user_field(req.department),
            "unit": sanitize_user_field(req.unit),
            "job_title": sanitize_user_field(req.job_title),
            "job_grade": sanitize_user_field(req.job_grade),
        },
    )

    jd_context, bsc_context, los_context, work_plan_context = _contexts_from_payload(payload)
    _display_retrieved(result, jd_context, bsc_context, los_context, work_plan_context)

    if not payload.get("jd_found"):
        print(f'\n  No job description found for "{job_title}" — continuing without JD context')

    if int(payload.get("bsc_count", 0)) == 0:
        detail = _build_retrieval_incomplete_detail(job_title, result)
        print(f"\n  Retrieval incomplete — blocked generation: {detail['failed']}")
        raise HTTPException(status_code=422, detail=detail)

    if not bsc_context.strip():
        detail = _build_retrieval_incomplete_detail(job_title, result)
        detail["message"] = (
            "No Balanced Scorecard (BSC) context was retrieved. "
            "Please reach out to the PMS team to resolve this issue."
        )
        print("\n  Retrieval empty — blocked generation")
        raise HTTPException(status_code=422, detail=detail)

    try:
        check_llm_available()
    except LLMUnavailableError as e:
        print(f"\n  LLM unavailable: {e}")
        raise HTTPException(
            status_code=503,
            detail={"error": "llm_unavailable", "message": str(e)},
        ) from e

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

    print("\n  Running 3-step pipeline (draft -> metrics -> appraisal) …")
    _flush()
    result_data = _run_pipeline_sync(context, req.num_objectives)

    for warning in result_data.get("pipeline_meta", {}).get("warnings", []):
        print(f"  WARNING: {warning}")

    meta = result_data.get("pipeline_meta", {})
    if meta.get("step1_cache_hit"):
        print("  Step 1 cache HIT — skipped draft LLM call")

    _display_llm_result(result_data["objectives"], result_data["total_weight"])

    try:
        return _build_generate_response(result_data)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail={"message": "Response validation failed", "error": str(e)},
        ) from e


@router.get("/jobs/{job_id}", response_model=JobStatusResponse, tags=["generation"])
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