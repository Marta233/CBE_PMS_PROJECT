"""
work_plan_main.py

Batch CLI entry point — processes EVERY .docx in DATA_DIR at once, for
local/manual runs. Calls THIS PACKAGE'S OWN run() (defined in
__init__.py, the same function POST /api/ingest calls for a single
upload) for the actual per-file parsing — no separate wp.py module,
matching how LOS's __init__.py is the one and only entry point for LOS.

Usage (from Back_End/):
    python -m scripts.Data_Ingestion.WP.work_plan_main
"""
from pathlib import Path
import json

from . import run as run_one_file  # this package's own __init__.py
from .config import DATA_DIR, OUTPUT_PATH


def run_work_plan_pipeline() -> list:
    """
    Work Plan batch pipeline:
    1. Find every .docx in DATA_DIR (one per department)
    2. Parse each one via this package's own run() — the SAME function
       POST /api/ingest uses for a single upload
    3. Combine and save work_plan_documents.json
    """
    print("🚀 Starting Work Plan processing...")

    docx_files = sorted(DATA_DIR.glob("*.docx"))
    if not docx_files:
        print(f"⚠️  No Work Plan .docx files found in {DATA_DIR}")
        return []

    all_documents = []
    for path in docx_files:
        print(f"\n📂 Processing {path.name}")
        docs = run_one_file(path)
        dept = docs[0]["metadata"]["department"] if docs else "unknown"
        fy = docs[0]["metadata"]["fiscal_year"] if docs else "unknown"
        print(f"   Generated {len(docs)} documents for {dept} ({fy})")
        all_documents.extend(docs)

    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_PATH / "work_plan_documents.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_documents, f, indent=2, ensure_ascii=False)

    print(f"\n✅ {len(all_documents)} total Work Plan documents saved at: {output_file}")
    return all_documents


if __name__ == "__main__":
    run_work_plan_pipeline()