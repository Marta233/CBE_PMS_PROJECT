"""Document schema checks against the organisation registry."""
from __future__ import annotations

import pytest

from common.Schema import check_doc, replace_key, validate_doc


def doc(source: str, text: str = "body", **meta) -> dict:
    return {"text": text, "metadata": {"source": source, **meta}}


def test_valid_bsc_los_jd_and_work_plan_have_no_problems():
    documents = [
        doc("BSC", division="Digital Banking"),
        doc("LOS", division="Digital Banking", department="Mobile & Internet Banking"),
        doc(
            "JD",
            division="Digital Banking",
            department="Merchant and Agent Management",
            unit="Agent Management",
            job_title="Digital Banking Officer",
        ),
        doc(
            "WorkPlan",
            scope_level="unit",
            division="Digital Banking",
            department="Merchant and Agent Management",
            unit="Agent Management",
            fiscal_year="2026/27",
        ),
    ]
    for document in documents:
        assert validate_doc(document) == []
        errors, warnings = check_doc(document)
        assert errors == []
        assert warnings == []


def test_alias_is_reported_until_it_is_the_canonical_name():
    document = doc("LOS", division="Digital Banking", department="Online Banking")
    problems = validate_doc(document)
    assert any("Mobile & Internet Banking" in problem for problem in problems)


def test_unknown_source_empty_text_and_forbidden_scope_fields():
    assert any("unknown source" in problem for problem in validate_doc(doc("NOTE")))
    assert "empty text" in validate_doc(doc("BSC", text="  ", division="Digital Banking"))
    problems = validate_doc(doc("BSC", division="Digital Banking", department="Mobile Money"))
    assert any("must be empty at division scope" in problem for problem in problems)
    assert any("unknown division" in problem for problem in validate_doc(doc("BSC", division="Technology")))


def test_work_plan_fiscal_year_must_be_short_form():
    bad = doc(
        "WorkPlan",
        scope_level="unit",
        division="Digital Banking",
        department="Mobile Money",
        unit="Mobile Money Business",
        fiscal_year="2026/2027",
    )
    assert any("2026/27" in problem for problem in validate_doc(bad))


def test_jd_missing_department_is_a_warning_and_is_not_inferred():
    document = doc(
        "JD",
        division="Digital Banking",
        unit="Agent Management",
        job_title="Digital Banking Officer",
    )
    errors, warnings = check_doc(document)
    assert any(warning.startswith("missing department") for warning in warnings)
    assert any("cannot place unit" in error for error in errors)


def test_replace_key_stays_inside_the_uploaded_batch():
    bsc = doc("BSC", division="Digital Banking")
    los = doc("LOS", division="Digital Banking", department="Card Banking")
    jd = doc("JD", division="Digital Banking", department="Mobile Money", unit="Mobile Money Business")
    plan = doc(
        "WorkPlan",
        scope_level="unit",
        division="Digital Banking",
        department="Mobile Money",
        unit="Mobile Money Business",
        fiscal_year="2026/27",
    )

    assert replace_key(bsc) == ("BSC", "Digital Banking")
    assert replace_key(los) == ("LOS", "Digital Banking", "Card Banking")
    assert replace_key(jd) == ("JD", "Digital Banking", "Mobile Money", "Mobile Money Business")
    assert replace_key(plan) == (
        "WorkPlan",
        "unit",
        "Digital Banking",
        "Mobile Money",
        "Mobile Money Business",
        "2026/27",
    )


def test_replace_key_rejects_an_unknown_source():
    with pytest.raises(ValueError, match="unknown source"):
        replace_key({"metadata": {"source": "NOTE"}})
