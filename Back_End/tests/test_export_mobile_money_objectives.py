"""Export Mobile Money objectives via the same /api/generate path as the UI."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.scripts.export_mobile_money_objectives import CASES, run_case

API_URL = "http://127.0.0.1:8000"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"


@pytest.mark.parametrize("case", CASES, ids=[c["job_title"] for c in CASES])
def test_export_mobile_money_objectives_csv(case: dict):
    """POST /api/generate like Performance Planning, then write downloadCSV-shaped output."""
    csv_path = run_case(case, API_URL)
    assert csv_path.exists()
    text = csv_path.read_text(encoding="utf-8-sig")
    assert case["job_title"] in text
    assert "Appraisal" in text
    assert "Rating 5 - Outstanding" in text
    assert (OUTPUT_DIR / csv_path.name).exists()
