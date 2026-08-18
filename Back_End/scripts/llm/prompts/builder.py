"""Assemble targeted prompts for each pipeline step — rules are injected, model generates values."""

from __future__ import annotations



from ..config.grade_bands import (

    CRITICAL_TARGET_ROLE_LABEL,

    DOCUMENT_SPLIT_BANDS,

    GRADE_GOAL_FOCUS,

    NO_PROPOSAL_BANDS,

    PRIMARY_CHANNEL_WEIGHT,

    EmployeeProfile,

)

from ..sanitize import sanitize_user_field, wrap_context_block

from ..samples import load_samples

from .loader import (

    format_samples_for_step1,

    load_template,

    render_fragment,

    render_template,

    step1_json_example,

    step2_json_example,

    step3_json_example,

    to_json,

)





def _supervisor_label(profile: EmployeeProfile) -> str:

    return CRITICAL_TARGET_ROLE_LABEL.get(profile.grade_band, "Manager's")





def _fragment_kwargs(profile: EmployeeProfile) -> dict[str, str]:

    document_split_note = ""

    if profile.grade_band in DOCUMENT_SPLIT_BANDS:

        document_split_note = (

            "7. Document/report/proposal goals: create TWO separate drafts — one for "

            "Quality (accuracy/editing) and one for Time (deadline/TOR compliance). "

            "Assign measure, category, and weight in Step 2 only."

        )



    no_proposal_note = ""

    if profile.grade_band in NO_PROPOSAL_BANDS:

        no_proposal_note = (

            "8. Do NOT draft proposal initiation, BRD preparation, or strategic proposal goals."

        )



    return {

        "grade_band": profile.grade_band.replace("_", " ").title(),

        "critical_weight": str(profile.critical_weight),

        "remaining_weight": str(profile.remaining_weight),

        "supervisor_target": _supervisor_label(profile),

        "grade_focus": GRADE_GOAL_FOCUS.get(profile.grade_band, ""),

        "primary_channel_weight": str(PRIMARY_CHANNEL_WEIGHT.get(profile.grade_band, 15)),

        "document_split_note": document_split_note,

        "no_proposal_note": no_proposal_note,

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

        unit=sanitize_user_field(profile.unit) or "this unit",

        json_example=step1_json_example(num_drafts),

    )

    return load_template("system_base"), user





def build_step2_prompt(profile: EmployeeProfile, drafts: list[dict]) -> tuple[str, str]:

    """Step 2 — model assigns weights, measures, targets, categories."""

    fk = _fragment_kwargs(profile)



    user = render_template(

        "step2_assign_metrics",

        step2_rules=render_fragment("step2_rules", **fk),

        drafts_json=to_json({"drafts": drafts}),

        critical_weight=fk["critical_weight"],

        remaining_weight=fk["remaining_weight"],

        json_example=step2_json_example(

            profile.critical_weight,

            profile.remaining_weight,

            fk["supervisor_target"],

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

            fk["supervisor_target"],

        ),

    )

    return load_template("system_base"), user





def build_all_prompts(

    profile: EmployeeProfile,

    context: dict,

    num_objectives: int,

) -> dict[str, tuple[str, str]]:

    """Return step prompts for inspection (step 2/3 use placeholder prior-step data)."""

    num_drafts = max(1, num_objectives - 1)

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

    step2 = build_step2_prompt(profile, placeholder_drafts)



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

