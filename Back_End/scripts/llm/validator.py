"""Non-fatal validation only — never rewrite model output."""
from __future__ import annotations

from .config.grade_bands import EmployeeProfile

WEIGHT_TOLERANCE = 0.01

APPRAISAL_FIELDS = ("rating_5", "rating_4", "rating_3", "rating_2", "rating_1")

REQUIRED_STRING_FIELDS = (
    "objective", "measure", "target", "category", "tracking_source", "time_frame",
)


def _coerce_weight(value) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip().rstrip("%"))
        except ValueError:
            return None
    return None


def _weights_close(total: float, expected: float) -> bool:
    return abs(total - expected) <= WEIGHT_TOLERANCE


def sum_weights(objectives: list[dict]) -> float:
    return round(sum(_coerce_weight(o.get("weight_percent")) or 0.0 for o in objectives), 4)


def normalize_objectives(objectives: list) -> tuple[list[dict], list[dict]]:
    """
    Coerce LLM output types and collect field-level errors.

    Returns (normalized_objectives, errors) where each error is
    {"index": int, "field": str, "message": str}.
    """
    errors: list[dict] = []
    normalized: list[dict] = []

    if not objectives:
        errors.append({"index": 0, "field": "objectives", "message": "No objectives returned."})
        return [], errors

    for i, raw in enumerate(objectives):
        if not isinstance(raw, dict):
            errors.append({"index": i, "field": "objective", "message": "Expected an object."})
            continue

        obj = dict(raw)
        weight = _coerce_weight(obj.get("weight_percent"))
        if weight is None:
            errors.append({
                "index": i,
                "field": "weight_percent",
                "message": f"Invalid weight_percent: {obj.get('weight_percent')!r}",
            })
        else:
            obj["weight_percent"] = round(weight, 2)

        for field in REQUIRED_STRING_FIELDS:
            val = obj.get(field)
            if val is None or (isinstance(val, str) and not val.strip()):
                errors.append({
                    "index": i,
                    "field": field,
                    "message": f"Missing or empty {field}.",
                })
            elif not isinstance(val, str):
                obj[field] = str(val)

        appraisal = obj.get("appraisal_logic")
        if appraisal is None:
            errors.append({
                "index": i,
                "field": "appraisal_logic",
                "message": "Missing appraisal_logic.",
            })
        elif not isinstance(appraisal, dict):
            errors.append({
                "index": i,
                "field": "appraisal_logic",
                "message": "appraisal_logic must be an object.",
            })
        else:
            appraisal = dict(appraisal)
            for field in APPRAISAL_FIELDS:
                val = appraisal.get(field)
                if val is None or (isinstance(val, str) and not val.strip()):
                    errors.append({
                        "index": i,
                        "field": f"appraisal_logic.{field}",
                        "message": f"Missing or empty {field}.",
                    })
                elif not isinstance(val, str):
                    appraisal[field] = str(val)
            obj["appraisal_logic"] = appraisal

        normalized.append(obj)

    return normalized, errors


def validate_objectives(objectives: list[dict], profile: EmployeeProfile) -> list[str]:
    """Return warnings about model output; Python does not fix weights or appraisal."""
    warnings: list[str] = []

    if not objectives:
        warnings.append("No objectives returned.")
        return warnings

    total = sum_weights(objectives)
    if not _weights_close(total, 100):
        warnings.append(f"Total weight is {total}% (expected 100%).")

    non_critical = [o for o in objectives if o.get("category") != "Major Critical"]
    nc_sum = sum_weights(non_critical)
    if not _weights_close(nc_sum, profile.remaining_weight):
        warnings.append(
            f"Non-critical weight sum is {nc_sum}% (expected {profile.remaining_weight}%)."
        )

    if objectives[0].get("category") != "Major Critical":
        warnings.append("First objective is not Major Critical (critical target).")

    kpis = [o.get("bsc_kpi", "") for o in objectives if o.get("bsc_kpi")]
    if len(kpis) != len(set(kpis)):
        warnings.append("Duplicate BSC KPIs detected.")

    for i, o in enumerate(objectives, 1):
        if not o.get("objective", "").strip():
            warnings.append(f"Objective {i} has empty text.")
        if not o.get("appraisal_logic"):
            warnings.append(f"Objective {i} missing appraisal_logic.")

    return warnings
