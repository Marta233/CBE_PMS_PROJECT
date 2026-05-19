"""
prompt_builder.py
Builds the LLM prompt by:
  1. Loading sample objectives from Data/sample/sample_objectives.json
  2. Always injecting the fixed "Achieve team critical target" objective (50 weight, Cannot Exceed)
  3. Asking the LLM to generate only the REMAINING objectives (num_objectives - 1)
  4. Merging the fixed objective into the final output in generate_objectives.py
"""

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SAMPLE_PATH = BASE_DIR / "Data" / "sample" / "sample_objectives.json"


# ── Loaders ────────────────────────────────────────────────────────────────

def load_critical_target() -> dict:
    """Load the fixed 'Achieve team critical target' objective from the sample file."""
    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["critical_target_objective"]


import json

import json

def load_samples(unit: str = "",  job_title: str = "") -> list:
    """
    Current sample JSON structure:
    samples_by_unit -> unit -> job_title -> sample list

    Logic:
    1. Match unit
    2. Inside unit match job title
    3. If no match -> return all samples
    """

    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    samples_by_unit = data.get("samples_by_unit", {})

    unit_lower = unit.strip().lower()
    job_title_lower = job_title.strip().lower()

    # ---------------------------------------
    # Step 1: Match unit
    # ---------------------------------------
    matched_unit = None

    for unit_key in samples_by_unit:
        if unit_lower and (
            unit_key.lower() in unit_lower or unit_lower in unit_key.lower()
        ):
            matched_unit = unit_key
            break

    if not matched_unit:
        return _get_all_samples(samples_by_unit)

    unit_data = samples_by_unit[matched_unit]

    # ---------------------------------------
    # Step 2: Match job title inside unit
    # ---------------------------------------
    matched_role = None

    for role_key in unit_data:
        if job_title_lower and (
            role_key.lower() in job_title_lower or job_title_lower in role_key.lower()
        ):
            matched_role = role_key
            break

    if not matched_role:
        return _get_all_samples(samples_by_unit)

    return unit_data[matched_role][:8]


def _get_all_samples(samples_by_unit: dict) -> list:
    """
    Return all samples from all units and roles
    """
    all_samples = []

    for unit_data in samples_by_unit.values():
        for role_samples in unit_data.values():
            all_samples.extend(role_samples)

    return all_samples[:8]


def format_samples_for_prompt(samples: list) -> str:
    """Format sample objectives into readable prompt text."""
    lines = []
    for i, s in enumerate(samples, 1):
        lines.append(
            f"  {i}. Objective : {s['objective']}\n"
            f"     Measure    : {s['measure']}  |  Target: {s['target']}\n"
            f"     Weight     : {s['weight_percent']}%  |  Category: {s['category']}\n"
            f"     Tracked by : {s['tracking_source']}  |  {s['time_frame']}"
        )
    return "\n\n".join(lines)


# ── Main builder ───────────────────────────────────────────────────────────

def build_prompt(context: dict, num_objectives: int) -> str:
    """
    Build the full LLM prompt.

    IMPORTANT:
    - "Achieve team critical target" (weight=50, Cannot Exceed) is ALWAYS pre-filled.
    - LLM generates only (num_objectives - 1) additional objectives.
    - Remaining weights must sum to 50.
    """
    query = context.get("query", "")
    jd_context = context.get("jd_context", "Not provided")
    bsc_context = context.get("bsc_context", "Not provided")
    los_context = context.get("los_context", "Not provided")

    unit = ""
    for line in query.splitlines():
        line = line.strip()
        if line.lower().startswith("unit:"):
            unit = line.split(":", 1)[-1].strip()
    samples = load_samples(unit=unit, job_title=query)
    formatted_samples = format_samples_for_prompt(samples)
    remaining = num_objectives - 1

    return f"""
You are an expert Performance Management System (PMS) consultant for
Commercial Bank of Ethiopia (CBE), Digital Banking Division.

EMPLOYEE PROFILE
{query}

JOB DESCRIPTION
{jd_context}

BALANCED SCORECARD (BSC) CONTEXT
{bsc_context}

LINE OF SIGHT (LOS)
{los_context}

REAL SAMPLE OBJECTIVES FROM CBE PMS DOCUMENT
(Use as style and structure reference only — do NOT copy verbatim)
{formatted_samples}

YOUR TASK
The first objective "Achieve team critical target" is already fixed with:
  weight_percent: 50, category: "Cannot Exceed", measure: "Various",
  target: "50% of manager's target", tracking_source: "System"
DO NOT include it in your output. It will be prepended automatically.

Generate exactly {remaining} additional SMART objectives.
All {remaining} objectives combined must have weights that sum to exactly 50.

RULES
1. SMART: Specific, Measurable, Achievable, Relevant, Time-bound.
2. BSC: Spread across Financial | Customer | Internal Process | Learning & Growth.
3. LOS: Each objective must trace back to the division/department line of sight.
4. Role Fit: Match actual duties of the job title and grade.
5. Weights: Must sum to exactly 50.
6. Category: "Cannot Exceed" = core duty; "Can Exceed" = stretch goal.
7. Language: Use CBE institutional PMS style (action verbs, percentage targets, TOR references).
8. No duplication: Every objective must be distinct.
9. Output: Return ONLY valid JSON. No markdown. No preamble.
10. All objectives are quarterly based so all are quarterly tracked.

REQUIRED JSON OUTPUT FORMAT
{{
  "objectives": [
    {{
      "objective": "Clear, action-oriented SMART statement",
      "measure": "Percentage | Number | Quality | Time | Various",
      "target": "Exact target value or threshold",
      "weight_percent": 10,
      "category": "Cannot Exceed | Can Exceed",
      "tracking_source": "System | Manual | Both",
      "time_frame": "Monthly | Quarterly | Annually"
    }}
  ]
}}
"""