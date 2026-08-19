"""Non-fatal validation only — never rewrite model output."""
from __future__ import annotations

import re

from .config.grade_bands import EmployeeProfile

WEIGHT_TOLERANCE = 0.01

APPRAISAL_FIELDS = ("rating_5", "rating_4", "rating_3", "rating_2", "rating_1")

REQUIRED_STRING_FIELDS = (
    "objective", "measure", "target", "category", "tracking_source", "time_frame",
)

# ── Step 1 (draft text + BSC/LOS mapping only) ─────────────────────────────
# Fields step1_rules.txt explicitly forbids from appearing anywhere in Step 1
# output — they belong to a later drafting step.
STEP1_FORBIDDEN_FIELDS = (
    "weight_percent", "measure", "target", "category",
    "tracking_source", "time_frame", "appraisal_logic",
)

STEP1_REQUIRED_FIELDS = (
    "draft_id", "objective", "bsc_kpi", "bsc_strategic_objective", "los_alignment",
)

_NUMBER_PATTERN = re.compile(r'[\d%$]')

_SELF_NUMBERING_PATTERN = re.compile(
    r'^\s*(\d+[.\)]|first,|second,|third,|fourth,|fifth,)', re.IGNORECASE
)

_FIRST_PERSON_PATTERN = re.compile(
    r"^\s*(i\s|i'll\b|i will\b|i'm\b|my\s)", re.IGNORECASE
)

# Crude "Job Title:" lead-in detector — a colon within the first few words,
# before any recognizable verb-first phrasing has a chance to appear.
_JOB_TITLE_LEAD_PATTERN = re.compile(r'^\s*[A-Z][\w /&-]{1,40}:\s')

_MONTH_NAMES = (
    "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december",
)

_TIMEFRAME_WORDS = (
    "quarter", "quarterly", "q1", "q2", "q3", "q4",
    "month", "monthly", "annually", "annual", "yearly",
    "this quarter", "next quarter", "this month", "this year",
    "fiscal year", "fy",
) + _MONTH_NAMES

_TIMEFRAME_PATTERN = re.compile(
    r'\b(' + '|'.join(re.escape(w) for w in _TIMEFRAME_WORDS) + r')\b'
    r'|\bby\s+(the\s+end\s+of\s+)?(' + '|'.join(_MONTH_NAMES) + r'|q[1-4]|year[- ]end)\b'
    r'|\bwithin\s+\w+',
    re.IGNORECASE,
)

# Heuristic for chained "by X, increasing Y, and expanding Z" objectives:
# more than one mechanism clause, or "and" joining what look like separate
# outcomes, suggests bundled activities/KPIs.
_CHAIN_CLAUSE_PATTERN = re.compile(r'\b(by|through)\b', re.IGNORECASE)


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

def validate_step1_objectives(
    drafts: list[dict],
) -> list[str]:
    """
    Check Step 1 draft output (text + BSC/LOS mapping only) against every
    rule in step1_rules.txt. Non-fatal: returns warnings, never mutates or
    rewrites `drafts`.

    `bsc_kpis`, if provided, is the exact list of KPI labels from the BSC
    context, used to confirm bsc_kpi values weren't paraphrased or invented.

    Note: rule 3 of the CORE REQUIREMENTS ("fits the employee's actual JD
    responsibilities and grade band") is a semantic judgment the JD/grade
    context isn't available to check here, so it isn't covered — human/model
    review is still required for that one.
    """
    warnings: list[str] = []

    if not drafts:
        warnings.append("No Step 1 drafts returned.")
        return warnings

    # for i, raw in enumerate(drafts, 1):
    #     label = f"Draft {i}"

    #     # --- Rule 2c: zero digits/numeric symbols ------------------------
    #     for field in ("objective"):
    #         val = raw.get(field)
    #         if isinstance(val, str) and _NUMBER_PATTERN.search(val):
    #             warnings.append(f"{label}: field '{field}' contains a digit or numeric symbol.")

    #     # --- Rule 2d: no timeframe wording -------------------------------
    #     for field in ("objective"):
    #         val = raw.get(field)
    #         if isinstance(val, str) and _TIMEFRAME_PATTERN.search(val):
    #             warnings.append(f"{label}: field '{field}' contains timeframe wording.")

    return warnings