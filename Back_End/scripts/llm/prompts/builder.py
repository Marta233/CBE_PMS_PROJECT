"""Assemble targeted prompts for each pipeline step — rules are injected, model generates values."""
from __future__ import annotations

from ..config.grade_bands import (
    DOCUMENT_SPLIT_BANDS,
    GRADE_GOAL_FOCUS,
    NO_PROPOSAL_BANDS,
    PRIMARY_CHANNEL_WEIGHT,
    EmployeeProfile,
)
from ..profiles.policy import sibling_unit_names, unit_note
from ..sanitize import sanitize_user_field, wrap_context_block
from ..samples import load_samples
from .loader import (
    format_samples_for_step1,
    format_samples_for_step2,
    load_template,
    render_fragment,
    render_template,
    step1_json_example,
    step2_json_example,
    step3_json_example,
    to_json,
)

WORK_PLAN_UNAVAILABLE = (
    "Work plan is not available for this unit. Do not invent work-plan activities."
)


def _domain_notes(profile: EmployeeProfile) -> str:
    return unit_note(profile.unit)


def _sibling_note(profile: EmployeeProfile) -> str:
    names = sibling_unit_names(profile.department, profile.unit, profile.division)
    if not names:
        return ""
    return " Do not draft objectives for these other units: " + ", ".join(names) + "."


def _grade_focus_block(profile: EmployeeProfile) -> str:
    if not profile.has_grade_policy:
        return ""
    focus = GRADE_GOAL_FOCUS.get(profile.grade_band, "")
    if not focus:
        return ""
    band = profile.grade_band.replace("_", " ").title()
    return (
        f"GRADE BAND GOAL FOCUS for {band}:\n{focus}\n\n"
        "The grade-focus line does not create a task. Draft a theme from it only "
        "when the work plan or the job description gives this role that work."
    )


def _critical_block(profile: EmployeeProfile) -> str:
    if not profile.has_grade_policy:
        return (
            "1. NO FIXED CRITICAL TARGET\n\n"
            "This division has no critical-target cascade. Do not add an "
            '"Achieve team critical target" objective. Every row comes from a Step 1 draft.'
        )
    return (
        "1. CRITICAL TARGET (fixed first objective — always output this row first)\n\n"
        f"This employee's resolved grade band: {profile.grade_band.replace('_', ' ').title()}\n"
        f"Critical target weight for this band: {profile.critical_weight}%\n"
        f"Remaining weight for all other objectives: {profile.remaining_weight}%\n\n"
        "The FIRST objective MUST always be:\n"
        "  objective      : Achieve team critical target\n"
        "  measure        : Various\n"
        f"  target         : {profile.critical_weight}% of {profile.supervisor_target} target\n"
        f"  weight_percent : {profile.critical_weight}\n"
        "  category       : Major Critical\n"
        "  tracking_source: System\n"
        "  time_frame     : Quarterly"
    )


def _weight_rule(profile: EmployeeProfile) -> str:
    if not profile.has_grade_policy:
        return "W1 — All objective weights must sum to exactly 100%."
    return (
        f"W1 — Critical target weight is fixed at {profile.critical_weight}%. "
        f"All other objectives must sum to exactly {profile.remaining_weight}%."
    )


def _core_duty_rule(profile: EmployeeProfile) -> str:
    if not profile.has_grade_policy:
        return (
            "W2 — The highest weight goes to this role's core duty as shown in the job description."
        )
    weight = PRIMARY_CHANNEL_WEIGHT.get(profile.grade_band, 15)
    return (
        f"W2 — Give the primary-channel weight ({weight}%) only when the job description "
        "shows this role owns that channel metric. Otherwise the highest non-critical weight "
        "goes to this role's core duty."
    )


def _policy_targets(profile: EmployeeProfile) -> str:
    if not profile.has_grade_policy:
        return ""
    return (
        "  • Quantitative channel targets     : \"As per quarterly action plan of 100%\"\n"
        "    Do not replace this with a figure copied from a work plan.\n"
        "    Do not invent the quarterly number the action plan does not define."
    )


def _fragment_kwargs(profile: EmployeeProfile) -> dict[str, str]:
    document_split_note = ""
    if profile.has_grade_policy and profile.grade_band in DOCUMENT_SPLIT_BANDS:
        document_split_note = (
            "Document/report/proposal goals: create TWO separate drafts — one for "
            "Quality (accuracy/editing) and one for Time (deadline/TOR compliance). "
            "Assign measure, category, and weight in Step 2 only."
        )

    no_proposal_note = ""
    if profile.has_grade_policy and profile.grade_band in NO_PROPOSAL_BANDS:
        no_proposal_note = (
            "Do NOT draft proposal initiation, BRD preparation, or strategic proposal goals."
        )

    return {
        "grade_band": profile.grade_band.replace("_", " ").title(),
        "critical_weight": str(profile.critical_weight),
        "remaining_weight": str(profile.remaining_weight),
        "supervisor_target": profile.supervisor_target,
        "document_split_note": document_split_note,
        "no_proposal_note": no_proposal_note,
        "grade_focus_block": _grade_focus_block(profile),
        "domain_notes": _domain_notes(profile),
        "sibling_note": _sibling_note(profile),
        "unit": sanitize_user_field(profile.unit) or "this unit",
        "critical_block": _critical_block(profile),
        "weight_rule": _weight_rule(profile),
        "core_duty_rule": _core_duty_rule(profile),
        "policy_targets": _policy_targets(profile),
    }


def build_step1_prompt(profile: EmployeeProfile, context: dict, num_drafts: int) -> tuple[str, str]:
    """Step 1 — draft SMART text + BSC/LOS mapping only."""
    fk = _fragment_kwargs(profile)
    samples = load_samples(unit=profile.unit, job_title=profile.job_title, for_step1=True)

    user = render_template(
        "step1_draft_objectives",
        query=wrap_context_block("employee_profile", profile.query),
        grade_band=fk["grade_band"],
        step1_rules=render_fragment("step1_rules", **fk),
        work_plan_context=wrap_context_block(
            "work_plan_context",
            context.get("work_plan_context", ""),
            fallback=WORK_PLAN_UNAVAILABLE,
        ),
        bsc_context=wrap_context_block(
            "bsc_context",
            context.get("bsc_context", ""),
            fallback="Not provided",
        ),
        los_context=wrap_context_block(
            "los_context",
            context.get("los_context", ""),
            fallback="Not available — use N/A.",
        ),
        jd_context=wrap_context_block(
            "jd_context",
            context.get("jd_context", ""),
            fallback="Not provided",
        ),
        formatted_samples=format_samples_for_step1(samples),
        num_drafts=str(num_drafts),
        unit=fk["unit"],
        draft_heading=(
            f"OUTPUT — exactly {num_drafts} drafts for {fk['unit']} (critical target excluded)"
            if profile.has_grade_policy
            else f"OUTPUT — exactly {num_drafts} drafts for {fk['unit']}"
        ),
        json_example=step1_json_example(num_drafts),
    )
    return load_template("system_base"), user


def build_step2_prompt(
    profile: EmployeeProfile,
    drafts: list[dict],
    jd_context: str = "",
) -> tuple[str, str]:
    """Step 2 — model assigns weights, measures, targets, categories."""
    fk = _fragment_kwargs(profile)
    samples = load_samples(unit=profile.unit, job_title=profile.job_title, for_step1=False)

    if profile.has_grade_policy:
        metrics_lead = (
            "You receive drafted objectives from Step 1. Assign weight_percent, measure, target,\n"
            "category, tracking_source, and time_frame to each draft AND add the fixed critical target.\n\n"
            "Apply ALL rules below. You must compute weights — do not leave them blank.\n"
            "The job description below is what this role performs. Use it when you choose\n"
            "the measure and which goal receives the largest non-critical weight.\n"
            "Do not copy monthly or quarterly figures from a work plan into the target."
        )
        output_requirements = (
            f"1. First objective = fixed critical target (Major Critical, {profile.critical_weight}%).\n"
            "2. Map each draft_id to a full objective row with all metric fields.\n"
            f"3. Non-critical weights must sum to exactly {profile.remaining_weight}%.\n"
            "4. Preserve draft objective text, bsc_kpi, bsc_strategic_objective, los_alignment."
        )
    else:
        metrics_lead = (
            "You receive drafted objectives from Step 1. Assign weight_percent, measure, target,\n"
            "category, tracking_source, and time_frame to each draft.\n"
            "Do not add an \"Achieve team critical target\" row.\n\n"
            "Apply ALL rules below. You must compute weights — do not leave them blank.\n"
            "The job description below is what this role performs.\n"
            "Do not copy monthly or quarterly figures from a work plan into the target."
        )
        output_requirements = (
            "1. Return one objective row per draft. Do not insert a critical-target row.\n"
            "2. Map each draft_id to a full objective row with all metric fields.\n"
            "3. Weights must sum to exactly 100%.\n"
            "4. Preserve draft objective text, bsc_kpi, bsc_strategic_objective, los_alignment."
        )

    user = render_template(
        "step2_assign_metrics",
        metrics_lead=metrics_lead,
        step2_rules=render_fragment("step2_rules", **fk),
        jd_context=wrap_context_block(
            "jd_context",
            jd_context,
            fallback="Not provided",
        ),
        formatted_samples=format_samples_for_step2(samples),
        drafts_json=to_json({"drafts": drafts}),
        output_requirements=output_requirements,
        json_example=step2_json_example(
            profile.critical_weight,
            profile.remaining_weight,
            profile.supervisor_target,
            include_critical=profile.has_grade_policy,
        ),
    )
    return load_template("system_base"), user


def build_step3_prompt(profile: EmployeeProfile, objectives: list[dict]) -> tuple[str, str]:
    """Step 3 — model writes appraisal_logic for every objective."""
    fk = _fragment_kwargs(profile)

    user = render_template(
        "step3_appraisal_logic",
        step3_rules=render_fragment("step3_rules", **fk),
        objectives_json=to_json({"objectives": objectives}),
        json_example=step3_json_example(
            profile.critical_weight,
            profile.remaining_weight,
            profile.supervisor_target,
            include_critical=profile.has_grade_policy,
        ),
    )
    return load_template("system_base"), user


def build_all_prompts(
    profile: EmployeeProfile,
    context: dict,
    num_objectives: int,
) -> dict[str, tuple[str, str]]:
    """Return step prompts for inspection (step 2/3 use placeholder prior-step data)."""
    from ..config.grade_bands import draft_count
    num_drafts = draft_count(num_objectives, profile.has_grade_policy)
    step1 = build_step1_prompt(profile, context, num_drafts)

    placeholder_drafts = [
        {
            "draft_id": f"draft_{i + 1}",
            "objective": f"(draft {i + 1} from step 1)",
            "bsc_kpi": "...",
            "bsc_strategic_objective": "...",
            "los_alignment": "N/A",
        }
        for i in range(num_drafts)
    ]
    step2 = build_step2_prompt(profile, placeholder_drafts, context.get("jd_context", ""))

    placeholder_objectives = [
        {
            "objective": "Achieve team critical target",
            "weight_percent": profile.critical_weight,
            "category": "Major Critical",
            "measure": "Various",
        },
        {
            "objective": "(objective from step 2)",
            "weight_percent": 10,
            "category": "Can Exceed",
            "measure": "Percentage",
        },
    ]
    step3 = build_step3_prompt(profile, placeholder_objectives)

    return {"step1_draft": step1, "step2_metrics": step2, "step3_appraisal": step3}
