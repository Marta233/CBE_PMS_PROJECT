"""
prompt_builder.py

Receives already-extracted context from process_embeddings.py / extractor.py:
    context = {
        "query"      : str  — raw query (Division, Job Title, Department, Unit, Grade)
        "jd_context" : str  — full JD text for the matched employee (one doc)
        "bsc_context": str  — top-k BSC KPI chunks joined by double newline
        "los_context": str  — LOS docs for the matched department joined by double newline
    }

Decision-factor hierarchy baked into the prompt:
    1. BSC  (highest) — every objective anchored to a specific BSC KPI
    2. LOS  (medium)  — each objective traces to the department LOS goal
    3. JD   (lowest)  — objective scoped to what this employee can own
"""

import json
from pathlib import Path

BASE_DIR    = Path(__file__).resolve().parent.parent.parent
SAMPLE_PATH = BASE_DIR / "Data" / "sample" / "sample_objectives.json"


# ── Sample loaders ─────────────────────────────────────────────────────────

def load_critical_target() -> dict:
    """Load the fixed 'Achieve team critical target' objective from the sample file."""
    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["critical_target_objective"]


def load_samples(unit: str = "", job_title: str = "") -> list:
    """Load sample objectives with source tracking."""
    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    samples_by_unit = data.get("samples_by_unit", {})
    unit_lower      = unit.strip().lower()
    title_lower     = job_title.strip().lower()

    matched_unit = next(
        (k for k in samples_by_unit
         if unit_lower and (k.lower() in unit_lower or unit_lower in k.lower())),
        None,
    )
    if not matched_unit:
        return _get_all_samples_with_source(samples_by_unit)

    unit_data    = samples_by_unit[matched_unit]
    matched_role = next(
        (k for k in unit_data
         if title_lower and (k.lower() in title_lower or title_lower in k.lower())),
        None,
    )
    if not matched_role:
        return _get_all_samples_with_source(samples_by_unit)

    samples = unit_data[matched_role][:8]
    for s in samples:
        s["source"] = f"Sample: {matched_unit} → {matched_role}"
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


def format_samples_for_prompt(samples: list) -> str:
    """Format sample objectives into readable prompt text with sources."""
    lines = []
    for i, s in enumerate(samples, 1):
        lines.append(
            f"  {i}. Objective : {s['objective']}\n"
            f"     Measure    : {s['measure']}  |  Target: {s['target']}\n"
            f"     Weight     : {s['weight_percent']}%  |  Category: {s['category']}\n"
            f"     Tracked by : {s['tracking_source']}  |  {s['time_frame']}\n"
            f"     SOURCE     : {s.get('source', 'Sample document')}"
        )
    return "\n\n".join(lines)


# ── Main builder ───────────────────────────────────────────────────────────

def build_prompt(context: dict, num_objectives: int) -> str:
    """
    Build the full LLM prompt from already-extracted context.

    Parameters
    ----------
    context : dict
        Keys: query, jd_context, bsc_context, los_context.
        All values are plain strings produced by process_embeddings.py.
    num_objectives : int
        Total objectives the employee should have (including the pre-fixed
        critical target). The LLM generates (num_objectives - 1).
    """
    query       = context.get("query",       "").strip()
    jd_context  = context.get("jd_context",  "Not provided").strip()
    bsc_context = context.get("bsc_context", "Not provided").strip()
    los_context = context.get("los_context", "Not provided").strip()

    # Parse unit + job title for sample matching
    unit = job_title = ""
    for line in query.splitlines():
        l = line.strip()
        if l.lower().startswith("unit:"):
            unit = l.split(":", 1)[-1].strip()
        elif l.lower().startswith("job title:"):
            job_title = l.split(":", 1)[-1].strip()

    samples           = load_samples(unit=unit, job_title=job_title)
    formatted_samples = format_samples_for_prompt(samples)
    remaining         = num_objectives - 1

    return f"""You are a role-based Performance Management System (PMS) objective generation
engine for Commercial Bank of Ethiopia (CBE), Digital Banking Division.

You receive three pre-extracted contexts — BSC, LOS, and JD — already filtered
and ranked for this specific employee. Apply them in strict priority order:

    PRIORITY 1 — BSC  : the Balanced Scorecard KPIs drive every objective.
                         Each objective MUST be anchored to one BSC KPI below.
    PRIORITY 2 — LOS  : the Line of Sight goals validate that the objective
                         belongs to this department's mandate.
    PRIORITY 3 — JD   : the Job Description scopes the objective to what this
                         employee can personally own, execute, and be rated on.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EMPLOYEE PROFILE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{query}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PRIORITY 1 — BSC CONTEXT  (highest decision factor)
Each block: Strategic Objective · KPI · Measurement unit · Target · Weight.
Higher BSC weight → higher individual objective weight.
Every objective you generate MUST be anchored to one KPI from this list.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{bsc_context}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PRIORITY 2 — LOS CONTEXT  (secondary decision factor)
Validate each objective against these department strategic goals.
Discard any objective that cannot trace to at least one goal here.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{los_context if los_context else "Not available for this department — rely on BSC and JD."}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PRIORITY 3 — JD CONTEXT  (tertiary decision factor)
Scope each objective to this employee's actual duties and grade.
Discard anything outside their TOR or above their grade level.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{jd_context}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SAMPLE OBJECTIVES  (style & structure reference — do NOT copy verbatim)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{formatted_samples}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FIXED OBJECTIVE — prepended automatically, do NOT include in your output
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"Achieve team critical target"
  weight_percent: 50 | category: Cannot Exceed | measure: Various
  target: 50% of manager's target | tracking_source: System | time_frame: Quarterly

Generate exactly {remaining} additional SMART objectives.
All {remaining} objectives combined must sum to exactly 50%.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CBE PMS PLANNING PHASE — KEY PRINCIPLES (apply to every objective)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

A. CASCADING & ELIGIBILITY LOGIC
   • Objectives flow top-down: Corporate Strategy → BSC → Department LOS →
     Individual PMP. Each objective must fit naturally into this hierarchy.
   • Every objective must be eligible for the employee's specific job title
     and position. Avoid objectives that belong to a higher grade or a
     different functional unit.
   • The BSC KPI is the starting point. The LOS confirms departmental
     ownership. The JD confirms individual ownership.

B. WEIGHT DISTRIBUTION RULES
   • Total weight across ALL objectives (including the pre-fixed critical
     target at 50%) must equal exactly 100%.
   • The {remaining} objectives you generate must therefore sum to exactly 50%.
   • Scale individual objective weight to BSC KPI weight:
       BSC KPI weight ≥ 10  →  objective weight 15–20%
       BSC KPI weight 5–9   →  objective weight 10–15%
       BSC KPI weight 1–4   →  objective weight 5–10%
   • Assign higher weights (15–20%) to core "Cannot Exceed" duties that
     directly drive revenue, volume, or customer KPI results.
   • Assign lower weights (5–10%) to "Can Exceed" stretch objectives in
     adoption, features, or process improvement KPIs.
   • No single objective should exceed 20% weight unless it is the dominant
     KPI for that role.

C. "CANNOT EXCEED" OBJECTIVES — CORE DUTIES
   • Mandatory, contractual performance obligations tied to the employee's
     TOR and the unit's primary KPIs.
   • Rating is capped at the target — no bonus for over-delivery.
   • Use for: transaction volume, revenue, error rate, SLA compliance,
     report timeliness, customer complaint resolution, uptime, user counts.
   • Success criteria (rating 1–5) in descending threshold bands:
       5 = 100% of target achieved
       4 = 90–99% of target
       3 = 80–89% of target
       2 = 70–79% of target
       1 = Below 70% of target
   • Lookup value must be extractable from System (BI/DWH/CBS/Oracle EPM)
     or Manual evidence (manager-verified with attachment).

D. "CAN EXCEED" OBJECTIVES — STRETCH GOALS
   • Reward employees for performance beyond the set target; over-delivery
     is recognized in the rating scale.
   • Use for: feature delivery, third-party integrations, new user
     recruitment, innovation, staff development, process improvement,
     digital adoption, cross-functional project contributions.
   • Success criteria include an over-delivery band:
       5 = Achieved 110%+ of target or delivered additional measurable value
       4 = Achieved 100–109% of target
       3 = Achieved 85–99% of target
       2 = Achieved 70–84% of target
       1 = Below 70% of target
   • At least {max(1, remaining // 3)} of the {remaining} objectives must
     be "Can Exceed" to balance accountability with motivation.

E. TRACKING SOURCE GUIDANCE
   • System  — auto-extracted from BI/Data Warehouse, CBS (Temenos/Finacle),
               or Oracle EPM. Use for volume, revenue, user counts, error
               rates, and any KPI with an automated data feed.
   • Manual  — manager captures progress with supporting evidence (attachment)
               via Oracle self-service. Use for qualitative, report-based,
               project-completion, or training objectives.
   • Both    — system supplies raw data, manager validates and adjusts. Use
               where automated data exists but managerial judgment is required.

F. APPRAISAL LOGIC PREREQUISITE
   • Before finalising each objective, confirm that a valid appraisal logic
     can be constructed: a lookup value that maps unambiguously to a 1–5
     rating scale using the success criteria defined above.
   • Objectives that cannot be rated objectively (no measurable lookup value)
     must not be included — replace them with a rateable alternative.
   • Prefer System-tracked objectives where possible; Manual is acceptable
     for qualitative KPIs with clear evidence criteria.

G. DYNAMIC GOAL CONSIDERATIONS
   • Set targets as quarterly slices of the annual BSC target.
   • Add target values cascaded from the annual target and distribute to the job title logically.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GENERATION RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  1. BSC-first: select the BSC KPI before writing the objective statement.
  2. LOS-validated: confirm the objective connects to a LOS goal (or note N/A).
  3. JD-scoped: confirm the employee's role can own and deliver the objective.
  4. SMART: Specific, Measurable, Achievable, Relevant, Time-bound.
  5. Weights sum to exactly 50.
  6. All objectives are quarterly.
  7. No two objectives share the same BSC KPI or measure.
  8. Use CBE institutional PMS language: action verbs, % or number targets,
     TOR references, quarterly framing.
  9. Every objective must have a rateable 1–5 appraisal logic with a clear
     lookup value (see principle F above).
 10. Source attribution: record which source drove each objective —
       "BSC"    = anchored to a BSC KPI
       "LOS"    = driven by a LOS strategic goal
       "JD"     = derived from a JD responsibility
       "Sample" = adapted from sample objectives (significantly modified)
       "LLM"    = AI-generated from common practice (use sparingly)
 11. No duplication: every objective must be distinct in scope and measure.
 12. Output: return ONLY valid JSON — no markdown, no preamble, no trailing text.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REQUIRED JSON OUTPUT FORMAT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{{
  "objectives": [
    {{
      "objective"              : "Clear, action-oriented SMART statement",
      "measure"                : "Million birr | Number | % | Thousand USD | Various",
      "target"                 : "Quarterly target derived from the BSC KPI annual target",
      "weight_percent"         : 10,
      "category"               : "Cannot Exceed | Can Exceed",
      "tracking_source"        : "System | Manual | Both",
      "time_frame"             : "Quarterly",
      "source"                 : "BSC | LOS | JD | Sample | LLM",
      "bsc_strategic_objective": "Exact Strategic Objective text from the BSC block above",
      "bsc_kpi"                : "Exact KPI name from the BSC block above",
      "los_alignment"          : "One sentence — which LOS goal this traces to, or N/A",
      "success_criteria": {{
        "5": "Rating-5 threshold description",
        "4": "Rating-4 threshold description",
        "3": "Rating-3 threshold description",
        "2": "Rating-2 threshold description",
        "1": "Rating-1 threshold description"
      }},
      "lookup_value": "Exact data source for actual achievement — e.g. BI Dashboard › Digital Transaction Volume"
    }}
  ]
}}
"""