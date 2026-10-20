"""Registry retrieval and prompt assembly. No live LLM calls."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from API.routers.org import router as org_router
from common import registry
from common.Schema import validate_doc
from embedding.extractor import QueryExtractor
from llm.config.grade_bands import draft_count, parse_employee_query
from llm.prompts.builder import build_step1_prompt, build_step2_prompt, build_step3_prompt


def _query(division, department, unit, title="Officer", grade="12") -> str:
    return (
        f"Division: {division}\n"
        f"Department: {department}\n"
        f"Unit: {unit}\n"
        f"Job Title: {title}\n"
        f"Job Grade: {grade}"
    )


def _doc(department: str, unit: str = "", text: str = "row") -> dict:
    return {"text": text, "metadata": {"department": department, "unit": unit}}


def test_digital_banking_keeps_grade_twelve_cascade():
    profile = parse_employee_query(_query(
        "Digital Banking",
        "Card Banking",
        "Card Production and Distribution",
        title="Digital Banking Officer",
        grade="12",
    ))
    assert profile.grade_band == "digital_banking_officer"
    assert profile.has_grade_policy is True
    assert profile.critical_weight == 50
    assert profile.remaining_weight == 50
    assert draft_count(5, profile.has_grade_policy) == 4


def test_other_division_does_not_inherit_the_cascade():
    profile = parse_employee_query(_query(
        "Retail & Branch Banking",
        "Branch Operations",
        "Teller",
        title="Officer",
        grade="12",
    ))
    assert profile.grade_band == "officer"
    assert profile.has_grade_policy is False
    assert profile.critical_weight == 0
    assert profile.remaining_weight == 100
    assert draft_count(5, profile.has_grade_policy) == 5

    _, step2 = build_step2_prompt(profile, [{"draft_id": "draft_1", "objective": "Serve customers"}])
    assert "The FIRST objective MUST always be" not in step2
    assert "Critical target weight for this band" not in step2
    assert "primary-channel weight" not in step2
    assert "CBE Birr" not in step2
    assert "As per the SDT" not in step2


def test_unit_notes_stay_on_their_unit():
    merchant = parse_employee_query(_query(
        "Digital Banking",
        "Merchant and Agent Management",
        "Merchant Management",
        title="Team Leader",
        grade="14",
    ))
    card = parse_employee_query(_query(
        "Digital Banking",
        "Card Banking",
        "Card Production and Distribution",
        title="Officer",
        grade="10",
    ))
    mobile = parse_employee_query(_query(
        "Digital Banking",
        "Mobile & Internet Banking",
        "Mobile Banking",
        title="Senior Officer",
        grade="13",
    ))

    _, merchant_prompt = build_step1_prompt(merchant, {}, 2)
    _, card_prompt = build_step1_prompt(card, {}, 2)
    _, mobile_prompt = build_step1_prompt(mobile, {}, 2)
    system, _ = build_step1_prompt(merchant, {}, 2)

    assert "Commercial Bank of Ethiopia" in system
    assert "Digital Banking Division" not in system
    assert "POS Merchant" in merchant_prompt
    assert "As per the SDT" not in merchant_prompt
    assert "As per the SDT" in card_prompt
    assert "POS Merchant" not in card_prompt
    assert "CBE Birr" not in mobile_prompt
    assert "Agent Management" in merchant_prompt

    _, merchant_step2 = build_step2_prompt(merchant, [{"draft_id": "draft_1", "objective": "Grow merchants"}])
    assert "Achieve team critical target" in merchant_step2
    assert "primary-channel weight (15%)" in merchant_step2
    assert "As per quarterly action plan of 100%" in merchant_step2


def test_registry_aliases_match_los_sheet_names():
    mobile_keys = registry.department_match_keys("Mobile & Internet Banking")
    assert registry.loose_key("Online Banking") in mobile_keys
    service_keys = registry.department_match_keys("Digital Service Development")
    assert registry.loose_key("Digital_service_devlopment") in service_keys

    labels = registry.work_plan_unit_labels(
        "Merchant and Agent Management", "Agent Management"
    )
    assert "Agent" in labels
    assert "Both" in labels
    partner_labels = registry.work_plan_unit_labels(
        "Merchant and Agent Management", "Digital Partners Relationship"
    )
    assert "Digital Partners Relationship" in partner_labels


def test_retrieval_uses_aliases_and_unit_labels():
    los_docs = [
        _doc("Online Banking", text="mobile channel objective"),
        _doc("Card", text="card objective"),
        _doc("Mobile Money", text="mobile money objective"),
    ]
    work_plans = [
        _doc("Mobile & Internet Banking", "Mobile Banking", "mobile plan"),
        _doc("Merchant and Agent Management", "Agent", "agent plan"),
        _doc("Merchant and Agent Management", "Merchant", "merchant plan"),
        _doc("Merchant and Agent Management", "Both", "shared plan"),
        _doc("Merchant and Agent Management", "Digital Partners Relationship", "partner plan"),
        _doc("Card Banking", "Card Production and Distribution", "card plan"),
    ]
    extractor = QueryExtractor(los_docs, [], object(), work_plans)

    los = extractor._filter_los_hierarchical("Mobile & Internet Banking", "Mobile Banking")
    assert [doc["metadata"]["department"] for doc in los] == ["Online Banking"]

    money = extractor._filter_los_hierarchical("Mobile Money", "Mobile Money Business")
    assert [doc["metadata"]["department"] for doc in money] == ["Mobile Money"]

    agent_plans = extractor._filter_work_plan(
        "Merchant and Agent Management", "Agent Management"
    )
    units = {doc["metadata"]["unit"] for doc in agent_plans}
    assert units == {"Agent", "Both"}

    partner_plans = extractor._filter_work_plan(
        "Merchant and Agent Management", "Digital Partners Relationship"
    )
    assert {doc["metadata"]["unit"] for doc in partner_plans} == {
        "Digital Partners Relationship",
        "Both",
    }

    card_plans = extractor._filter_work_plan(
        "Card Banking", "Card Production and Distribution"
    )
    assert [doc["metadata"]["unit"] for doc in card_plans] == ["Card Production and Distribution"]

    recon_docs = [
        _doc(
            "Digital Banking Reconciliation and Dispute Management",
            "Merchant and Agent Reconciliation",
            "recon plan",
        ),
        _doc("Digital Banking Reconciliation and Dispute Management", "Agent", "agent plan"),
        _doc("Merchant and Agent Management", "Both", "shared merchant plan"),
    ]
    recon = QueryExtractor([], [], object(), recon_docs)
    recon_plans = recon._filter_work_plan(
        "Digital Banking Reconciliation and Dispute Management",
        "Merchant and Agent Reconciliation",
    )
    assert [doc["metadata"]["unit"] for doc in recon_plans] == ["Merchant and Agent Reconciliation"]

    unknown = extractor._filter_work_plan("Merchant and Agent Management", "Not A Real Unit")
    assert unknown == []


def test_org_endpoint_returns_registry_tree():
    app = FastAPI()
    app.include_router(org_router, prefix="/api")
    response = TestClient(app).get("/api/org")
    assert response.status_code == 200
    divisions = {item["division"]: item for item in response.json()["divisions"]}
    assert "Digital Banking" in divisions
    departments = {item["department"] for item in divisions["Digital Banking"]["departments"]}
    assert "Mobile Money" in departments
    assert "RBB" in divisions


def test_step3_prompt_builds_for_both_policies():
    digital = parse_employee_query(_query(
        "Digital Banking", "Card Banking", "Card Production and Distribution", grade="12"
    ))
    other = parse_employee_query(_query(
        "Retail & Branch Banking", "Branch Operations", "Teller", grade="12"
    ))
    _, digital_step3 = build_step3_prompt(digital, [{"objective": "Issue cards", "category": "Can Exceed"}])
    _, other_step3 = build_step3_prompt(other, [{"objective": "Serve customers", "category": "Can Exceed"}])
    assert "Achieve team critical target" in digital_step3
    assert "Achieve team critical target" not in other_step3


def test_reconciliation_rows_stay_in_their_department():
    from jd.digital_loader import _extract_department_from_context
    from WP.work_plan_loader import _canonical_department, _norm_unit

    assert _norm_unit("Merchant and Agent Reconciliation") == "Merchant and Agent Reconciliation"
    assert _norm_unit("Agent Management") == "Agent"
    assert _canonical_department("Merchant and Agent Reconciliation") == (
        "Digital Banking Reconciliation and Dispute Management"
    )
    assert _canonical_department("Agent") == "Merchant and Agent Management"

    block = "Unit: CBE Birr\nReports Directly To: Manager\n"
    assert _extract_department_from_context(block) == "Mobile Money"


def test_unknown_department_still_fails_ingest_validation():
    document = {
        "text": "objective text",
        "metadata": {
            "source": "LOS",
            "division": "Digital Banking",
            "department": "Treasury Operations",
        },
    }
    problems = validate_doc(document)
    assert any("unknown department" in problem for problem in problems)
