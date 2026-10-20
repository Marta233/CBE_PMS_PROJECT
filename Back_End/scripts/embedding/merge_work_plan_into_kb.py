"""
merge_work_plan_into_kb.py

Bridges work_plan_documents.json (produced by Data_Ingestion/WP/work_plan_main.py)
into knowledge_base.json (the file load_knowledge_base() reads).

REPLACEMENT RULE — identical to POST /api/ingest (ingest.py's _dedup_key):
a Work Plan document is identified by (department, fiscal_year, unit). Merging
REPLACES only the documents whose key appears in work_plan_documents.json;
Work Plan documents of OTHER departments / units / fiscal years are left alone.

(The previous version dropped EVERY Work Plan document first, so merging a
folder that only contained one department's file silently deleted the others,
including departments uploaded through the UI.)

Safe to re-run. The knowledge base is written atomically and the previous
version is kept as knowledge_base.json.bak.

Usage (from Back_End/):
    python scripts/embedding/merge_work_plan_into_kb.py
    python scripts/embedding/merge_work_plan_into_kb.py --replace-all
        --replace-all  = delete ALL existing Work Plan documents first (use it when
                         you really want to purge stale units that were removed
                         from a plan; every department you still need must then be
                         in work_plan_documents.json)
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from config import KNOWLEDGE_BASE_FILE  # noqa: E402
from Data_Ingestion.WP.config import OUTPUT_PATH as WORK_PLAN_OUTPUT_PATH  # noqa: E402

WORK_PLAN_DOCUMENTS_PATH = WORK_PLAN_OUTPUT_PATH / "work_plan_documents.json"


def _is_wp(doc: dict) -> bool:
    return isinstance(doc, dict) and doc.get("metadata", {}).get("source") == "WorkPlan"


def _wp_key(doc: dict) -> tuple:
    """Same identity as ingest.py's _dedup_key for Work Plan documents."""
    meta = doc.get("metadata", {})
    return (meta.get("department"), meta.get("fiscal_year"), meta.get("unit"))


def _by_department(docs: list[dict]) -> dict:
    return dict(sorted(Counter(d["metadata"].get("department") or "?" for d in docs).items()))


def merge(
    wp_path: Path | None = None,
    kb_path: Path | None = None,
    *,
    replace_all: bool = False,
    verbose: bool = True,
) -> dict | None:
    """Merge Work Plan documents into the knowledge base. Returns a summary dict (None on error)."""
    wp_path = Path(wp_path or WORK_PLAN_DOCUMENTS_PATH)
    kb_path = Path(kb_path or KNOWLEDGE_BASE_FILE)
    say = print if verbose else (lambda *a, **k: None)

    if not wp_path.exists():
        say(f"⚠️  {wp_path} not found — run work_plan_main.py first.")
        return None
    try:
        new_docs = json.loads(wp_path.read_text(encoding="utf-8"))
        if not isinstance(new_docs, list) or not new_docs:
            raise ValueError("expected a non-empty JSON list")
    except Exception as exc:
        say(f"❌ Could not read {wp_path.name}: {exc} — knowledge base NOT changed.")
        return None
    say(f"📂 Loaded {len(new_docs)} Work Plan documents to merge: {_by_department(new_docs)}")

    # Never fall back to an empty list when the file exists but is unreadable —
    # writing it back would erase the whole knowledge base (same guard as ingest.py).
    kb: list = []
    if kb_path.exists() and kb_path.stat().st_size > 0:
        try:
            kb = json.loads(kb_path.read_text(encoding="utf-8"))
            if not isinstance(kb, list):
                raise ValueError("top-level JSON is not a list")
        except Exception as exc:
            say(f"❌ {kb_path.name} exists but could not be read ({exc}) — "
                f"refusing to overwrite it. Fix or restore the file, then retry.")
            return None

    if not any(not _is_wp(d) for d in kb):
        say("⚠️  The knowledge base has no BSC / JD / LOS documents at all — "
            "ingest those (UI upload) too, or generation will find nothing to retrieve.")

    existing_wp = [d for d in kb if _is_wp(d)]
    new_keys = {_wp_key(d) for d in new_docs}
    new_slots = {(d["metadata"].get("fiscal_year"), d["metadata"].get("unit")) for d in new_docs}

    def _is_replaced(d: dict) -> bool:
        if _wp_key(d) in new_keys:
            return True
        # A plan stored with a BLANK department (older loader) can never match a query and has
        # a different key from the corrected plan — replace it along with the same FY + unit.
        meta = d["metadata"]
        return (not str(meta.get("department") or "").strip()
                and (meta.get("fiscal_year"), meta.get("unit")) in new_slots)

    if replace_all:
        replaced = existing_wp
        kept_wp: list[dict] = []
    else:
        replaced = [d for d in existing_wp if _is_replaced(d)]
        kept_wp = [d for d in existing_wp if not _is_replaced(d)]

    replaced_ids = {id(d) for d in replaced}
    merged = [d for d in kb if id(d) not in replaced_ids] + new_docs

    say(f"♻️  Replaced {len(replaced)} existing Work Plan document(s): {_by_department(replaced) or '-'}")
    say(f"➕ Added {len(new_docs)} document(s)")
    if kept_wp:
        say(f"🔒 Left untouched (not in this file): {len(kept_wp)} Work Plan document(s): {_by_department(kept_wp)}")
    elif replace_all and existing_wp:
        say("🧹 --replace-all: every previous Work Plan document was removed first")

    kb_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = kb_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")  # write fully first
    if kb_path.exists():
        shutil.copy2(kb_path, kb_path.with_suffix(".json.bak"))
    tmp_path.replace(kb_path)                                                                   # then swap in

    final_wp = [d for d in merged if _is_wp(d)]
    say(f"✅ knowledge_base.json now has {len(merged)} documents "
        f"(Work Plan: {len(final_wp)} -> {_by_department(final_wp)})")
    say(f"   Saved -> {kb_path}")
    return {
        "total": len(merged),
        "replaced": len(replaced),
        "added": len(new_docs),
        "kept": len(kept_wp),
        "work_plan_by_department": _by_department(final_wp),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge Work Plan documents into knowledge_base.json")
    parser.add_argument("--replace-all", action="store_true",
                        help="delete ALL existing Work Plan documents first (default: replace only the keys in the file)")
    args = parser.parse_args()
    if merge(replace_all=args.replace_all) is None:
        sys.exit(1)


if __name__ == "__main__":
    main()