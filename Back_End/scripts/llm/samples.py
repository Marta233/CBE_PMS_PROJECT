"""Load style-reference samples from sample_objectives.json."""
from __future__ import annotations

import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SAMPLE_PATH = BASE_DIR / "Data" / "sample" / "sample_objectives.json"

# Fields assigned in Step 2 — omit from Step 1 style references.
_STEP2_FIELDS = frozenset({
    "measure", "target", "weight_percent", "category",
    "tracking_source", "time_frame", "appraisal_logic",
})


def _is_unit_key(key: str) -> bool:
    """Drop job-title fragments and numeric leftovers stored as unit names."""
    text = key.strip()
    lowered = text.lower()
    if not text or text.startswith("(") or re.fullmatch(r"\d+", text):
        return False
    if re.match(r"^\d+\s", text):
        return False
    if "officer" in lowered or "trainee" in lowered:
        return False
    return True


def _strip_step2_fields(sample: dict) -> dict:
    """Return a copy with only Step 1-relevant fields (objective text + BSC mapping)."""
    return {k: v for k, v in sample.items() if k not in _STEP2_FIELDS and k != "source"}


def _norm_phrase(text: str) -> str:
    text = text.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _best_match(keys: list[str], needle: str) -> str | None:
    """Longest role name that contains, or is contained in, the job title."""
    needle = needle.strip().lower()
    if not needle:
        return None
    hits = [key for key in keys if key.lower() in needle or needle in key.lower()]
    if not hits:
        return None
    return max(hits, key=len)


def _best_unit_match(keys: list[str], needle: str) -> str | None:
    """Match a stored unit without borrowing a longer unit that only shares a suffix.

    A stored name inside the employee unit wins (longest). Otherwise the employee
    unit must be the start of the stored name, so "Card Production" can use
    "Card Production and Distribution" while "Agent Management" does not use
    "Merchant and Agent Management".
    """
    query = _norm_phrase(needle)
    if not query:
        return None
    norms = [(key, _norm_phrase(key)) for key in keys]
    contained = [key for key, norm in norms if norm and f" {norm} " in f" {query} "]
    if contained:
        return max(contained, key=lambda key: len(_norm_phrase(key)))
    prefixes = [
        key for key, norm in norms
        if norm == query or norm.startswith(query + " ")
    ]
    if not prefixes:
        return None
    return max(prefixes, key=lambda key: len(_norm_phrase(key)))


def load_samples(unit: str = "", job_title: str = "", *, for_step1: bool = False) -> list:
    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    samples_by_unit = {
        key: value
        for key, value in data.get("samples_by_unit", {}).items()
        if _is_unit_key(key) and isinstance(value, dict)
    }
    matched_unit = _best_unit_match(list(samples_by_unit), unit)
    if not matched_unit:
        return []

    unit_data = samples_by_unit[matched_unit]
    matched_role = _best_match(list(unit_data), job_title)
    if matched_role and isinstance(unit_data.get(matched_role), list):
        samples = unit_data[matched_role][:8]
        source = f"Sample: {matched_unit} → {matched_role}"
    else:
        samples = []
        source = f"Sample: {matched_unit}"
        for rows in unit_data.values():
            if not isinstance(rows, list):
                continue
            samples.extend(rows[:2])
            if len(samples) >= 8:
                break
        samples = samples[:8]

    tagged = []
    for sample in samples:
        copied = dict(sample)
        copied["source"] = source
        tagged.append(copied)

    if for_step1:
        return [_strip_step2_fields(sample) for sample in tagged]
    return tagged
