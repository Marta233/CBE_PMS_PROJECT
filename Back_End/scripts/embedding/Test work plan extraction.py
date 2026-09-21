"""
test_work_plan_extraction.py

Verifies the Work Plan integration in extractor.py end-to-end, including
a REAL run of QueryExtractor.extract() — not a simulation. The only thing
faked is the embedding model itself (HuggingFace download is blocked in
this sandbox); FAISS index-building and similarity search run for real
against deterministic hash-based vectors instead of downloaded weights.

Run this in the actual project (with the real embedding model available)
by deleting FakeEmbeddings and passing a real PMSVectorStore instead —
everything else in this script stays the same.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from langchain_community.vectorstores import FAISS  # noqa: E402
from langchain_core.documents import Document  # noqa: E402
from langchain_core.embeddings import Embeddings  # noqa: E402
from extractor import ExtractionResult, QueryExtractor, load_knowledge_base  # noqa: E402


# ---------------------------------------------------------------------------
# Fake embeddings — deterministic, offline, but REAL FAISS operations run
# against them (embed_documents/embed_query is the only interface FAISS
# actually calls; it doesn't care whether the vectors are meaningful).
# Subclassing Embeddings (not duck-typing) matters — FAISS treats a plain
# object without this base class as a raw callable, not an Embeddings
# instance, and calls it incorrectly.
# ---------------------------------------------------------------------------
class FakeEmbeddings(Embeddings):
    DIM = 32

    def _vec(self, text: str) -> list[float]:
        h = hashlib.sha256(text.encode()).digest()
        return [b / 255.0 for b in h[: self.DIM]]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)


class FakeVectorStore:
    """
    Stand-in for PMSVectorStore that builds a REAL FAISS index (same as
    process_embeddings.py does for the actual BSC vectorstore) — only the
    embedding model itself is faked, so _load_all_bsc_docs(), the dual-query
    fusion, grade scoring, and keyword fallback in extractor.py all run
    against a genuine FAISS index, not a mock.
    """
    def __init__(self, bsc_docs: list[dict]):
        self.embeddings = FakeEmbeddings()
        self._bge_query_prefix = ""
        lc_docs = [Document(page_content=d["text"], metadata=d["metadata"]) for d in bsc_docs]
        self.vectorstore = FAISS.from_documents(lc_docs, self.embeddings)


# ---------------------------------------------------------------------------
# Build a realistic fake knowledge_base.json: real Work Plan data (loaded
# via the actual production loader) + representative BSC/JD/LOS docs
# ---------------------------------------------------------------------------
def build_fixture_knowledge_base(work_plan_docs: list[dict]) -> list[dict]:
    jd_docs = [
        {
            "text": (
                "Division: Digital Banking\n"
                "Department: Merchant and Agent Management\n"
                "Unit: Agent Management\n"
                "Job Title: Senior Digital Banking Officer\n"
                "Job Grade: 12\n"
                "Job Objective: To accomplish agent recruitment, support, and "
                "performance monitoring activities for the agent network."
            ),
            "metadata": {"source": "JD", "department": "Merchant and Agent Management", "unit": "Agent Management"},
        },
        {
            "text": (
                "Division: Digital Banking\n"
                "Department: Merchant and Agent Management\n"
                "Unit: Merchant Management\n"
                "Job Title: Associate Digital Banking Officer II\n"
                "Job Grade: 9\n"
                "Job Objective: To accomplish merchant recruitment, onboarding, "
                "and POS activation activities."
            ),
            "metadata": {"source": "JD", "department": "Merchant and Agent Management", "unit": "Merchant Management"},
        },
    ]

    los_docs = [
        {"text": "Agent Management LOS objective: Increase active agent transactions.",
         "metadata": {"source": "LOS", "department": "Merchant and Agent Management"}},
        {"text": "Merchant Management LOS objective: Increase merchant POS activation.",
         "metadata": {"source": "LOS", "department": "Merchant and Agent Management"}},
    ]

    bsc_docs = [
        {"text": "Strategic Objective: Enhance Digital Channel Utilization\nKPI: Active Agents Incremental\nMeasurement: Count\nTarget: 2504\nweight: 15",
         "metadata": {"source": "BSC", "division": "Digital Banking", "kpi": "Active Agents Incremental"}},
        {"text": "Strategic Objective: Enhance Digital Channel Utilization\nKPI: Active CBE-Birr Merchants\nMeasurement: Count\nTarget: 5000\nweight: 15",
         "metadata": {"source": "BSC", "division": "Digital Banking", "kpi": "Active CBE-Birr Merchants"}},
        {"text": "Strategic Objective: Enhance Digital Channel Utilization\nKPI: Card Activation Rate\nMeasurement: Percentage\nTarget: 80\nweight: 10",
         "metadata": {"source": "BSC", "division": "Digital Banking", "kpi": "Card Activation Rate"}},
    ]

    return jd_docs + los_docs + bsc_docs + work_plan_docs


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------
QUERIES = {
    "agent_employee": """
Division: Digital Banking
Department: Merchant and Agent Management
Unit: Agent Management
Job Title: Senior Digital Banking Officer
Job Grade: 12
""",
    "merchant_employee": """
Division: Digital Banking
Department: Merchant and Agent Management
Unit: Merchant Management
Job Title: Associate Digital Banking Officer II
Job Grade: 9
""",
    "unrelated_department": """
Division: Digital Banking
Department: Card Banking
Unit: Card Production and Distribution
Job Title: Junior Officer II
Job Grade: 5
""",
    "no_unit_specified": """
Division: Digital Banking
Department: Merchant and Agent Management
Job Title: Unit Manager
Job Grade: 15
""",
}


def run_checks():
    failures: list[str] = []

    def check(name: str, condition: bool, detail: str = ""):
        status = "PASS" if condition else "FAIL"
        print(f"  [{status}] {name}" + (f" — {detail}" if detail and not condition else ""))
        if not condition:
            failures.append(name)

    print("=" * 70)
    print("1. Building fixture knowledge base from REAL Work Plan data")
    print("=" * 70)
    work_plan_path = Path(__file__).resolve().parent / "work_plan" / "ingestion" / "work_plan_documents.json"
    real_work_plan_docs = json.loads(work_plan_path.read_text(encoding="utf-8"))
    fixture = build_fixture_knowledge_base(real_work_plan_docs)
    fixture_path = Path(__file__).resolve().parent / "tests" / "fixture_knowledge_base.json"
    fixture_path.write_text(json.dumps(fixture, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Fixture written: {len(fixture)} total docs ({len(real_work_plan_docs)} Work Plan)")

    print("\n" + "=" * 70)
    print("2. load_knowledge_base() — 4-way bucketing")
    print("=" * 70)
    bsc_docs, jd_docs, los_docs, work_plan_docs = load_knowledge_base(fixture_path)
    check("BSC docs loaded", len(bsc_docs) == 3, f"got {len(bsc_docs)}")
    check("JD docs loaded", len(jd_docs) == 2, f"got {len(jd_docs)}")
    check("LOS docs loaded", len(los_docs) == 2, f"got {len(los_docs)}")
    check("Work Plan docs loaded", len(work_plan_docs) == len(real_work_plan_docs),
          f"got {len(work_plan_docs)}, expected {len(real_work_plan_docs)}")

    print("\n" + "=" * 70)
    print("3. Full extract() — REAL FAISS run (fake embeddings, real logic)")
    print("=" * 70)
    fake_vs = FakeVectorStore(bsc_docs=[{"text": d.page_content, "metadata": d.metadata} for d in bsc_docs])
    extractor = QueryExtractor(
        los_docs=los_docs, jd_docs=jd_docs, bsc_vectorstore=fake_vs, work_plan_docs=work_plan_docs
    )

    print("\n--- Query: agent_employee ---")
    r1: ExtractionResult = extractor.extract(QUERIES["agent_employee"], bsc_k=5)
    check("Agent query detects correct department", r1.detected_department_name == "Merchant and Agent Management")
    check("Agent query returns Work Plan docs", len(r1.work_plan_docs) > 0, f"got {len(r1.work_plan_docs)}")
    agent_units = {doc.metadata.get("unit") for doc in r1.work_plan_docs}
    check("Agent query excludes Merchant-only entries", "Merchant" not in agent_units, f"units present: {agent_units}")
    check("Agent query excludes Mesob-only entries", "Mesob" not in agent_units, f"units present: {agent_units}")
    check("Agent query includes Agent entries", "Agent" in agent_units, f"units present: {agent_units}")
    check("Agent query BSC docs non-empty", len(r1.bsc_docs) > 0, f"got {len(r1.bsc_docs)}")
    check("Agent query JD matched", r1.jd_doc is not None)

    print("\n--- Query: merchant_employee ---")
    r2: ExtractionResult = extractor.extract(QUERIES["merchant_employee"], bsc_k=5)
    merchant_units = {doc.metadata.get("unit") for doc in r2.work_plan_docs}
    check("Merchant query excludes Agent-only entries", "Agent" not in merchant_units, f"units present: {merchant_units}")
    check("Merchant query includes Merchant entries", "Merchant" in merchant_units, f"units present: {merchant_units}")

    print("\n--- Query: unrelated_department (Card Banking — no Work Plan data exists) ---")
    r3: ExtractionResult = extractor.extract(QUERIES["unrelated_department"], bsc_k=5)
    check("Unrelated department returns empty Work Plan (no crash)", r3.work_plan_docs == [],
          f"got {len(r3.work_plan_docs)} docs")

    print("\n--- Query: no_unit_specified (department known, unit blank) ---")
    r4: ExtractionResult = extractor.extract(QUERIES["no_unit_specified"], bsc_k=5)
    no_unit_units = {doc.metadata.get("unit") for doc in r4.work_plan_docs}
    check("No-unit query does not crash and returns department's docs",
          len(r4.work_plan_docs) > 0, f"got {len(r4.work_plan_docs)}")
    check("No-unit query includes multiple units (fails open, not closed)",
          len(no_unit_units) > 1, f"units present: {no_unit_units} — see note below")

    print("\n" + "=" * 70)
    print("4. Cross-check: as_context() puts Work Plan first, labeled Priority 1")
    print("=" * 70)
    ctx = r1.as_context()
    check("Work Plan section appears in as_context()", "WORK PLAN (PRIORITY 1)" in ctx)
    check("Work Plan section appears BEFORE JD section", ctx.index("WORK PLAN") < ctx.index("JOB DESCRIPTION"))

    print("\n" + "=" * 70)
    if failures:
        print(f"RESULT: {len(failures)} check(s) FAILED: {failures}")
    else:
        print("RESULT: ALL CHECKS PASSED")
    print("=" * 70)
    return failures


if __name__ == "__main__":
    failures = run_checks()
    sys.exit(1 if failures else 0)