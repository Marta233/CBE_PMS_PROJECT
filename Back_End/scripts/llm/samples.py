"""Load style-reference samples from sample_objectives.json."""
from __future__ import annotations

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SAMPLE_PATH = BASE_DIR / "Data" / "sample" / "sample_objectives.json"

# Fields assigned in Step 2 — omit from Step 1 style references.
_STEP2_FIELDS = frozenset({
    "measure", "target", "weight_percent", "category",
    "tracking_source", "time_frame", "appraisal_logic",
})


def _strip_step2_fields(sample: dict) -> dict:
    """Return a copy with only Step 1-relevant fields (objective text + BSC mapping)."""
    return {k: v for k, v in sample.items() if k not in _STEP2_FIELDS and k != "source"}


def load_samples(unit: str = "", job_title: str = "", *, for_step1: bool = False) -> list:
    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    samples_by_unit = data.get("samples_by_unit", {})
    unit_lower = unit.strip().lower()
    title_lower = job_title.strip().lower()
    matched_unit = next(
        (k for k in samples_by_unit
         if unit_lower and (k.lower() in unit_lower or unit_lower in k.lower())),
        None,
    )
    if not matched_unit:
        samples = _get_all_samples_with_source(samples_by_unit)
    else:
        unit_data = samples_by_unit[matched_unit]
        matched_role = next(
            (k for k in unit_data
             if title_lower and (k.lower() in title_lower or title_lower in k.lower())),
            None,
        )
        if not matched_role:
            samples = _get_all_samples_with_source(samples_by_unit)
        else:
            samples = unit_data[matched_role][:8]
            for s in samples:
                s["source"] = f"Sample: {matched_unit} → {matched_role}"

    if for_step1:
        return [_strip_step2_fields(s) for s in samples]
    return samples


def _get_all_samples_with_source(samples_by_unit: dict) -> list:
    out = []
    for uk, ud in samples_by_unit.items():
        for rk, rs in ud.items():
            for s in rs[:3]:
                sc = s.copy()
                sc["source"] = f"Sample: {uk} → {rk}"
                out.append(sc)
    return out[:8]
