"""
merge_work_plan_into_kb.py

Bridges work_plan_documents.json (produced by Data_Ingestion/work_plan/
work_plan_main.py) into knowledge_base.json (the file load_knowledge_base()
reads) until POST /api/ingest is updated to ingest Work Plan docx files
natively alongside BSC/JD/LOS.

Safe to re-run: removes any previously-merged WorkPlan entries first, so
re-running after a Work Plan docx update doesn't duplicate documents.

Usage (from Back_End/):
    python scripts/embedding/merge_work_plan_into_kb.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from config import KNOWLEDGE_BASE_FILE  # noqa: E402
from Data_Ingestion.WP.config import OUTPUT_PATH as WORK_PLAN_OUTPUT_PATH  # noqa: E402

WORK_PLAN_DOCUMENTS_PATH = WORK_PLAN_OUTPUT_PATH / "work_plan_documents.json"


def merge() -> None:
    if not WORK_PLAN_DOCUMENTS_PATH.exists():
        print(f"⚠️  {WORK_PLAN_DOCUMENTS_PATH} not found — run work_plan_main.py first.")
        return

    work_plan_docs = json.loads(WORK_PLAN_DOCUMENTS_PATH.read_text(encoding="utf-8"))
    print(f"📂 Loaded {len(work_plan_docs)} Work Plan documents")

    if KNOWLEDGE_BASE_FILE.exists():
        kb = json.loads(KNOWLEDGE_BASE_FILE.read_text(encoding="utf-8"))
    else:
        kb = []
    before = len(kb)

    # Drop any previously-merged WorkPlan entries so re-running doesn't duplicate.
    kb = [item for item in kb if item.get("metadata", {}).get("source") != "WorkPlan"]
    removed = before - len(kb)
    if removed:
        print(f"🧹 Removed {removed} previously-merged WorkPlan entries")

    kb.extend(work_plan_docs)

    KNOWLEDGE_BASE_FILE.parent.mkdir(parents=True, exist_ok=True)
    KNOWLEDGE_BASE_FILE.write_text(
        json.dumps(kb, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"✅ knowledge_base.json now has {len(kb)} total documents "
          f"({len(work_plan_docs)} WorkPlan)")
    print(f"   Saved -> {KNOWLEDGE_BASE_FILE}")


if __name__ == "__main__":
    merge()