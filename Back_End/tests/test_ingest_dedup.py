"""Knowledge-base replace rules used by POST /api/ingest."""
from __future__ import annotations

from API.routers.ingest import dedup_key, merge_knowledge_base


def chunk(source: str, text: str, **meta) -> dict:
    return {"text": text, "metadata": {"source": source, **meta}}


def texts(docs: list) -> list[str]:
    return [doc["text"] for doc in docs]


def test_bsc_reupload_replaces_only_that_division():
    existing = [
        chunk("BSC", "old digital", division="Digital Banking"),
        chunk("BSC", "rbb", division="RBB"),
        chunk("JD", "kept jd", division="Digital Banking", unit="Agent Management"),
    ]
    new_docs = [chunk("BSC", "new digital", division="Digital Banking")]

    merged, removed = merge_knowledge_base(existing, new_docs)

    assert removed == 1
    assert texts(merged) == ["rbb", "kept jd", "new digital"]
    assert dedup_key(new_docs[0]) == ("BSC", "Digital Banking")


def test_jd_and_los_reupload_replaces_the_whole_division():
    existing = [
        chunk("JD", "agent jd", division="Digital Banking", department="Merchant and Agent Management", unit="Agent Management"),
        chunk("JD", "merchant jd", division="Digital Banking", department="Merchant and Agent Management", unit="Merchant Management"),
        chunk("JD", "other division jd", division="RBB", unit="Branch"),
        chunk("LOS", "old los", division="Digital Banking", department="Card Banking"),
        chunk("LOS", "other los", division="RBB", department="Branch"),
    ]
    new_docs = [
        chunk("JD", "new agent jd", division="Digital Banking", department="Merchant and Agent Management", unit="Agent Management"),
        chunk("LOS", "new los", division="Digital Banking", department="Mobile Money"),
    ]

    merged, removed = merge_knowledge_base(existing, new_docs)

    assert removed == 3
    assert texts(merged) == ["other division jd", "other los", "new agent jd", "new los"]


def test_work_plan_reupload_replaces_only_matching_department_year_and_unit():
    existing = [
        chunk("WorkPlan", "old agent", department="Merchant and Agent Management", fiscal_year="2026/27", unit="Agent Management"),
        chunk("WorkPlan", "merchant", department="Merchant and Agent Management", fiscal_year="2026/27", unit="Merchant Management"),
        chunk("WorkPlan", "last year", department="Merchant and Agent Management", fiscal_year="2025/26", unit="Agent Management"),
        chunk("BSC", "scorecard", division="Digital Banking"),
    ]
    new_docs = [
        chunk("WorkPlan", "new agent", department="Merchant and Agent Management", fiscal_year="2026/27", unit="Agent Management"),
    ]

    merged, removed = merge_knowledge_base(existing, new_docs)

    assert removed == 1
    assert texts(merged) == ["merchant", "last year", "scorecard", "new agent"]


def test_work_plan_reupload_drops_stale_blank_department_for_same_slot():
    existing = [
        chunk("WorkPlan", "blank dept", department="", fiscal_year="2026/27", unit="Agent Management"),
        chunk("WorkPlan", "other unit blank", department="  ", fiscal_year="2026/27", unit="Merchant Management"),
    ]
    new_docs = [
        chunk(
            "WorkPlan",
            "named dept",
            department="Merchant and Agent Management",
            fiscal_year="2026/27",
            unit="Agent Management",
        ),
    ]

    merged, removed = merge_knowledge_base(existing, new_docs)

    assert removed == 1
    assert texts(merged) == ["other unit blank", "named dept"]
