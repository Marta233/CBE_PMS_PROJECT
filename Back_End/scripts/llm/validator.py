"""Non-fatal validation only — never rewrite model output."""
from __future__ import annotations

import re

from .config.grade_bands import EmployeeProfile

WEIGHT_TOLERANCE = 0.01

APPRAISAL_FIELDS = ("rating_5", "rating_4", "rating_3", "rating_2", "rating_1")

REQUIRED_STRING_FIELDS = (
    "objective", "measure", "target", "category", "tracking_source", "time_frame",
)

# Values meaning "no BSC KPI genuinely fit this responsibility" (Rule 1
# in step1_rules.txt allows this — "otherwise set bsc_kpi to N/A"). These must NOT count as duplicates when several
# distinct, real JD responsibilities each lack a matching KPI.
def _is_placeholder_kpi(value: str | None) -> bool:
    v = (value or "").strip().lower()
    return v == "" or v.startswith("n/a") or v in ("none", "not applicable")

# ---------------------------------------------------------------------------
# Step 1 draft-level checks (run BEFORE weights/measures exist)
# ---------------------------------------------------------------------------

ACTIVITY_VERBS = (
    "implement", "install", "build", "develop", "deploy", "set up",
    "configure", "roll out", "introduce", "launch", "create a",
    "create an", "conduct a", "conduct an", "establish a", "establish an",
)

# Common English stopwords excluded so overlap isn't inflated by
# "the", "and", "to", etc. shared between any two sentences.
_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "of", "to", "for", "in", "on", "by",
    "with", "at", "from", "is", "are", "be", "as", "that", "this", "its",
})


def check_outcome_level(drafts: list[dict]) -> list[str]:
    """Flag drafts whose main verb describes an activity/tool, not an outcome (Rule 6)."""
    warnings: list[str] = []
    for i, d in enumerate(drafts, 1):
        text = (d.get("objective") or "").strip().lower()
        if not text:
            continue
        if any(text.startswith(v) or f" {v} " in f" {text} " for v in ACTIVITY_VERBS):
            warnings.append(
                f"Draft {i} looks activity-level, not outcome-level (Rule 6): {d.get('objective', '')!r}"
            )
    return warnings


def _word_set(text: str) -> set[str]:
    words = "".join(c if c.isalnum() else " " for c in text.lower()).split()
    return {w for w in words if w not in _STOPWORDS}


def check_duplicate_drafts(drafts: list[dict], threshold: float = 0.6) -> list[str]:
    """
    Flag draft pairs that likely describe the same underlying responsibility,
    even when worded with different verbs ("Enhance" vs "Improve" vs "Ensure")
    — Rule 7: no duplicate or overlapping drafts.

    This is a lightweight word-overlap heuristic (Jaccard similarity on
    content words). For higher precision, swap in cosine similarity from
    scripts/embedding instead of _word_set overlap — same call signature.
    """
    warnings: list[str] = []
    texts = [_word_set(d.get("objective") or "") for d in drafts]
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            a, b = texts[i], texts[j]
            if not a or not b:
                continue
            overlap = len(a & b) / len(a | b)
            if overlap >= threshold:
                warnings.append(
                    f"Draft {i + 1} and Draft {j + 1} look like duplicates (Rule 7, "
                    f"word overlap {overlap:.0%}): "
                    f"{drafts[i].get('objective', '')!r} vs {drafts[j].get('objective', '')!r}"
                )
    return warnings


def check_duplicate_bsc_kpi(drafts: list[dict]) -> list[str]:
    """
    Flag drafts that reuse the same REAL bsc_kpi — reusing a genuine KPI
    across two drafts almost always means they're the same underlying
    responsibility restated (Rule 7: no duplicate/overlapping drafts).
    Drafts marked "N/A" (Rule 1) are expected to repeat and are never
    flagged as duplicates against each other.
    """
    warnings: list[str] = []
    seen: dict[str, int] = {}
    for i, d in enumerate(drafts, 1):
        kpi = (d.get("bsc_kpi") or "").strip()
        if not kpi or _is_placeholder_kpi(kpi):
            continue
        kpi_lower = kpi.lower()
        if kpi_lower in seen:
            warnings.append(
                f"Draft {i} reuses the same BSC KPI as Draft {seen[kpi_lower]} "
                f"(Rule 7 — likely the same underlying responsibility): {kpi!r}"
            )
        else:
            seen[kpi_lower] = i
    return warnings


# ---------------------------------------------------------------------------
# Pattern-based checks for Rule 4 (SMART format / no second clause) and
# Rule 5 (no numbers or timeframe wording) — catch things word-overlap
# dedup misses, since the problem is usually internal to one sentence.
# ---------------------------------------------------------------------------

_BANNED_CONNECTOR_PHRASES = (
    "as well as", "in addition to", "while also", "coupled with",
)

# Verbs that, appearing after "and"/"," mid-sentence, signal a smuggled-in
# second outcome (Rule 4). Not exhaustive — extend as new real examples
# surface, the way "ensure"/"maintain"/"optimize" were added here.
_SECOND_CLAUSE_VERBS = (
    "ensure", "maintain", "improve", "reduce", "increase", "resolve",
    "optimize", "elevate", "strengthen", "enhance", "provide", "providing",
    "support", "supporting",
)


def check_compound_clause(drafts: list[dict]) -> list[str]:
    """
    Flag Step 1 drafts that smuggle in a second clause/outcome, per Rule 4:
      - a "by/through + verb-ing" mechanism clause
      - "and" (or a comma) introducing a second goal-type verb
      - an explicit banned connector phrase
    This is pattern-based, not a semantic check — it catches the common,
    mechanical forms of compounding, not every possible phrasing.
    """
    warnings: list[str] = []
    for i, d in enumerate(drafts, 1):
        text = d.get("objective") or ""
        low = text.lower()

        if re.search(r"\bby\s+\w+ing\b", low):
            warnings.append(
                f"Draft {i} has a 'by ...ing' mechanism clause (Rule 4 — no second clause): {text!r}"
            )
            continue

        flagged = False
        for phrase in _BANNED_CONNECTOR_PHRASES:
            if phrase in low:
                warnings.append(f"Draft {i} uses banned connector {phrase!r} (Rule 4): {text!r}")
                flagged = True
                break
        if flagged:
            continue

        second_verb_pattern = r"\b(and|,)\s+(" + "|".join(_SECOND_CLAUSE_VERBS) + r")\b"
        if re.search(second_verb_pattern, low):
            warnings.append(
                f"Draft {i} introduces a second outcome after 'and'/comma (Rule 4): {text!r}"
            )
    return warnings


MAX_OBJECTIVE_WORDS = 12


def check_word_count(drafts: list[dict], max_words: int = MAX_OBJECTIVE_WORDS) -> list[str]:
    """Flag drafts over the strict word limit (Rule 4). Hard cap, no exceptions."""
    warnings: list[str] = []
    for i, d in enumerate(drafts, 1):
        text = (d.get("objective") or "").strip()
        if not text:
            continue
        word_count = len(text.split())
        if word_count > max_words:
            warnings.append(
                f"Draft {i} is {word_count} words, exceeds the {max_words}-word "
                f"limit (Rule 4): {text!r}"
            )
    return warnings


# Any digit, or the %, $ symbols, anywhere in the objective text — Rule 5
# bans ALL numbers and numeric symbols in Step 1 (magnitude belongs to
# Step 2's target/weight_percent fields, not the objective sentence).
_FORBIDDEN_NUMBER_PATTERN = re.compile(r"\d|%|\$")


def check_forbidden_numbers(drafts: list[dict]) -> list[str]:
    """Flag any digit or numeric symbol in objective text (Rule 5)."""
    warnings: list[str] = []
    for i, d in enumerate(drafts, 1):
        text = d.get("objective") or ""
        if _FORBIDDEN_NUMBER_PATTERN.search(text):
            warnings.append(
                f"Draft {i} contains a number or numeric symbol — not allowed "
                f"in Step 1 (Rule 5): {text!r}"
            )
    return warnings


# Explicit calendar/cadence words and "within/by the next/end of ..." phrases —
# Rule 5 and Rule 9 both ban timeframe wording in Step 1 (time_frame is its
# own field, set later in Step 2).
_TIMEFRAME_WORDS = ("quarterly", "monthly", "annually", "yearly", "weekly", "daily")
_TIMEFRAME_PHRASES = (
    "this quarter", "this month", "this year", "next quarter", "next month",
    "next year", "within the next", "by the end of", "by end of",
    "by january", "by february", "by march", "by april", "by may", "by june",
    "by july", "by august", "by september", "by october", "by november", "by december",
)


def check_timeframe_wording(drafts: list[dict]) -> list[str]:
    """Flag calendar/cadence wording in objective text (Rule 5 / Rule 9)."""
    warnings: list[str] = []
    for i, d in enumerate(drafts, 1):
        text = d.get("objective") or ""
        low = text.lower()
        hit = next((w for w in _TIMEFRAME_WORDS if re.search(rf"\b{w}\b", low)), None)
        if not hit:
            hit = next((p for p in _TIMEFRAME_PHRASES if p in low), None)
        if hit:
            warnings.append(
                f"Draft {i} contains timeframe wording {hit!r} — not allowed "
                f"in Step 1 (Rule 5 / Rule 9): {text!r}"
            )
    return warnings


# Rule 8 — impersonal voice, always. No "I", "I'll", "I will", or a
# job-title lead-in ("As the Senior Officer, ...") before the action verb.
_PERSONAL_VOICE_PATTERN = re.compile(
    r"^(i\'ll|i will|i am|i\s|as (the|a|an)\b)", re.IGNORECASE
)


def check_impersonal_voice(drafts: list[dict]) -> list[str]:
    """Flag drafts starting in first person or with a job-title lead-in (Rule 8)."""
    warnings: list[str] = []
    for i, d in enumerate(drafts, 1):
        text = (d.get("objective") or "").strip()
        if not text:
            continue
        if _PERSONAL_VOICE_PATTERN.match(text):
            warnings.append(
                f"Draft {i} uses personal/job-title voice instead of starting "
                f"with an impersonal action verb (Rule 8): {text!r}"
            )
    return warnings


STEP1_REQUIRED_FIELDS = (
    "draft_id", "objective", "bsc_kpi", "bsc_strategic_objective", "los_alignment",
)
STEP2_REQUIRED_FIELDS = (
    "objective", "measure", "target", "category", "tracking_source", "time_frame",
    "bsc_kpi", "bsc_strategic_objective", "los_alignment",
)


def step1_schema_issues(drafts: list, num_drafts: int) -> list[str]:
    """Required Step 1 shape. Content-quality warnings are separate and may still ship."""
    if not isinstance(drafts, list):
        return ["Step 1 response has no drafts list."]
    if len(drafts) < num_drafts:
        return [f"Step 1 returned {len(drafts)} drafts, expected at least {num_drafts}."]
    issues: list[str] = []
    for i, draft in enumerate(drafts[:num_drafts], 1):
        if not isinstance(draft, dict):
            issues.append(f"Draft {i} is not an object.")
            continue
        for field in STEP1_REQUIRED_FIELDS:
            if not str(draft.get(field, "")).strip():
                issues.append(f"Draft {i} missing {field}.")
    return issues


def step2_schema_issues(objectives: list, num_objectives: int) -> list[str]:
    """Required Step 2 shape. A weight total other than 100% is not a schema failure."""
    if not isinstance(objectives, list):
        return ["Step 2 response has no objectives list."]
    if len(objectives) != num_objectives:
        return [f"Step 2 returned {len(objectives)} objectives, expected {num_objectives}."]
    issues: list[str] = []
    for i, obj in enumerate(objectives, 1):
        if not isinstance(obj, dict):
            issues.append(f"Objective {i} is not an object.")
            continue
        if _coerce_weight(obj.get("weight_percent")) is None:
            issues.append(f"Objective {i} missing a numeric weight_percent.")
        for field in STEP2_REQUIRED_FIELDS:
            if not str(obj.get(field, "")).strip():
                issues.append(f"Objective {i} missing {field}.")
    return issues


def validate_step1_drafts(drafts: list[dict]) -> list[str]:
    """Run all Step 1 draft-level checks and return a combined warning list."""
    if not drafts:
        return ["No drafts returned."]
    warnings: list[str] = []
    warnings.extend(check_outcome_level(drafts))          # Rule 6
    warnings.extend(check_duplicate_drafts(drafts))        # Rule 7
    warnings.extend(check_duplicate_bsc_kpi(drafts))       # Rule 1 / Rule 7
    warnings.extend(check_compound_clause(drafts))         # Rule 4
    warnings.extend(check_word_count(drafts))              # Rule 4
    warnings.extend(check_forbidden_numbers(drafts))       # Rule 5
    warnings.extend(check_timeframe_wording(drafts))       # Rule 5 / Rule 9
    warnings.extend(check_impersonal_voice(drafts))        # Rule 8
    return warnings


# ---------------------------------------------------------------------------
# Step 2 / Step 3 final-object-level checks (existing behavior, unchanged)
# ---------------------------------------------------------------------------


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

    kpis = [
        o.get("bsc_kpi", "") for o in objectives
        if o.get("bsc_kpi") and not _is_placeholder_kpi(o.get("bsc_kpi"))
    ]
    if len(kpis) != len(set(k.lower() for k in kpis)):
        warnings.append("Duplicate BSC KPIs detected.")

    # Safety net: re-check outcome-level and duplication on final objective
    # text too, in case Step 2 introduced or missed something from Step 1.
    warnings.extend(check_outcome_level(objectives))
    warnings.extend(check_duplicate_drafts(objectives))

    for i, o in enumerate(objectives, 1):
        if not o.get("objective", "").strip():
            warnings.append(f"Objective {i} has empty text.")
        if not o.get("appraisal_logic"):
            warnings.append(f"Objective {i} missing appraisal_logic.")

    return warnings