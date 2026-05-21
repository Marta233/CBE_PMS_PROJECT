"""
prompt_builder.py
Builds the LLM prompt with source tracking for each objective.
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
    return data["critical_target_objectile"]


def load_samples(unit: str = "", job_title: str = "") -> list:
    """Load sample objectives with source tracking."""
    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    samples_by_unit = data.get("samples_by_unit", {})

    unit_lower = unit.strip().lower()
    job_title_lower = job_title.strip().lower()

    matched_unit = None
    for unit_key in samples_by_unit:
        if unit_lower and (unit_key.lower() in unit_lower or unit_lower in unit_key.lower()):
            matched_unit = unit_key
            break

    if not matched_unit:
        return _get_all_samples_with_source(samples_by_unit)

    unit_data = samples_by_unit[matched_unit]

    matched_role = None
    for role_key in unit_data:
        if job_title_lower and (role_key.lower() in job_title_lower or job_title_lower in role_key.lower()):
            matched_role = role_key
            break

    if not matched_role:
        return _get_all_samples_with_source(samples_by_unit)

    # Add source to each sample
    samples = unit_data[matched_role][:8]
    for sample in samples:
        sample['source'] = f"Sample: {matched_unit} → {matched_role}"
    
    return samples


def _get_all_samples_with_source(samples_by_unit: dict) -> list:
    """Return all samples with source tracking."""
    all_samples = []
    for unit_key, unit_data in samples_by_unit.items():
        for role_key, role_samples in unit_data.items():
            for sample in role_samples[:3]:  # Limit per role
                sample_copy = sample.copy()
                sample_copy['source'] = f"Sample: {unit_key} → {role_key}"
                all_samples.append(sample_copy)
    return all_samples[:8]


def format_samples_for_prompt(samples: list) -> str:
    """Format sample objectives into readable prompt text with sources."""
    lines = []
    for i, s in enumerate(samples, 1):
        lines.append(
            f"  {i}. Objective : {s['objective']}\n"
            f"     Measure    : {s['measure']}  |  Target: {s['target']}\n"
            f"     Weight     : {s['weight_percent']}%  |  Category: {s['category']}\n"
            f"     Tracked by : {s['tracking_source']}  |  {s['time_frame']}\n"
            f"     SOURCE     : {s.get('source', 'Sample document')}"  # NEW
        )
    return "\n\n".join(lines)


# ── Context source extractors ───────────────────────────────────────────────

def extract_jd_sources(jd_context: str, job_title: str) -> list:
    """
    Parse JD context to extract potential objective sources.
    Returns list of responsibility areas that can become objectives.
    """
    sources = []
    
    # Extract key responsibilities from JD
    if "Responsibilities:" in jd_context:
        resp_section = jd_context.split("Responsibilities:")[1].split("\n\n")[0]
        responsibilities = [r.strip() for r in resp_section.split("\n") if r.strip() and len(r.strip()) > 20]
        
        for i, resp in enumerate(responsibilities[:5]):  # Top 5 responsibilities
            sources.append({
                "source_type": "JD",
                "content": resp[:200],
                "priority": i + 1
            })
    
    return sources


def extract_bsc_sources(bsc_context: str) -> list:
    """
    Parse BSC context to extract strategic objectives.
    """
    sources = []
    
    # Look for BSC perspectives
    perspectives = ["Financial", "Customer", "Internal Process", "Learning & Growth"]
    for perspective in perspectives:
        if perspective.lower() in bsc_context.lower():
            sources.append({
                "source_type": "BSC",
                "content": f"{perspective} perspective strategic objective",
                "perspective": perspective
            })
    
    return sources


def extract_los_sources(los_context: str) -> list:
    """
    Parse LOS context for line-of-sight alignment.
    """
    sources = []
    
    # Look for department/division objectives
    lines = los_context.split("\n")
    for line in lines[:10]:
        if any(word in line.lower() for word in ["objective", "goal", "target", "achieve", "improve"]):
            sources.append({
                "source_type": "LOS",
                "content": line[:200]
            })
    
    return sources


# ── Main builder ───────────────────────────────────────────────────────────

def build_prompt(context: dict, num_objectives: int) -> str:
    """
    Build the full LLM prompt with source tracking instructions.
    """
    query = context.get("query", "")
    jd_context = context.get("jd_context", "Not provided")
    bsc_context = context.get("bsc_context", "Not provided")
    los_context = context.get("los_context", "Not provided")

    # Extract unit from query
    unit = ""
    for line in query.splitlines():
        line = line.strip()
        if line.lower().startswith("unit:"):
            unit = line.split(":", 1)[-1].strip()
    
    # Load samples with sources
    samples = load_samples(unit=unit, job_title=query)
    formatted_samples = format_samples_for_prompt(samples)
    remaining = num_objectives - 1

    # Extract available sources from context
    jd_sources = extract_jd_sources(jd_context, query)
    bsc_sources = extract_bsc_sources(bsc_context)
    los_sources = extract_los_sources(los_context)

    # Format available sources for prompt
    available_sources = []
    if jd_sources:
        available_sources.append("### JD Responsibilities (Primary Source)")
        for s in jd_sources[:3]:
            available_sources.append(f"- Priority {s['priority']}: {s['content']}...")
    if bsc_sources:
        available_sources.append("\n### BSC Perspectives")
        for s in bsc_sources:
            available_sources.append(f"- {s['perspective']}: {s['content']}")
    if los_sources:
        available_sources.append("\n### LOS Strategic Goals")
        for s in los_sources[:3]:
            available_sources.append(f"- {s['content']}...")
    
    available_sources_text = "\n".join(available_sources) if available_sources else "No specific sources extracted."

    return f"""
You are an expert Performance Management System (PMS) for
Commercial Bank of Ethiopia (CBE), Which IS role base employee Object generation engine.

EMPLOYEE PROFILE
{query}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AVAILABLE SOURCES FOR OBJECTIVE GENERATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{available_sources_text}

JOB DESCRIPTION (Full Context)
{jd_context[:2000]}

BALANCED SCORECARD (BSC) CONTEXT
{bsc_context[:1500]}

LINE OF SIGHT (LOS)
{los_context[:1000]}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REAL SAMPLE OBJECTIVES FROM CBE PMS DOCUMENT
(Use as style and structure reference only — do NOT copy verbatim)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{formatted_samples}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR TASK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The first objective "Achieve team critical target" is already fixed with:
  weight_percent: 50, category: "Cannot Exceed", measure: "Various",
  target: "50% of manager's target", tracking_source: "System", time_frame: "Quarterly"
DO NOT include it in your output. It will be prepended automatically.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CBE PMS PLANNING PHASE — KEY PRINCIPLES (apply to every objective)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
A. CASCADING & ELIGIBILITY LOGIC
   • Objectives flow top-down: Corporate Strategy →  BSC → Department LOS →
     Individual PMP. Each objective must fit naturally into this hierarchy.
   • Each objective must be eligible for the employee's specific job title and position.
   • Avoid objectives that belong to a higher grade or a different functional unit.
B. WEIGHT DISTRIBUTION RULES
   • Total weight for all objectives (including the pre-fixed "Achieve team critical
     target" at 50%) must equal exactly 100%.
   • The {remaining} objectives you generate must therefore sum to exactly 50%.
   • Assign higher weights (15–20%) to core "Cannot Exceed" duties that directly
     drive financial or customer BSC results.
   • Assign lower weights (5–10%) to "Can Exceed" stretch objectives in Learning &
     Growth or Internal Process perspectives.
   • No single objective should exceed 20% weight unless it is the dominant KPI for
     that role (e.g., loan disbursement volume for a credit officer).
C. "CANNOT EXCEED" OBJECTIVES — CORE DUTIES
   • These are mandatory, contractual performance obligations tied to the employee's
     TOR and the unit's primary KPIs.
   • They must have a clearly defined numeric or percentage target that cannot be
     surpassed in rating (rating is capped at the target, no bonus for over-delivery).
   • Examples of "Cannot Exceed" areas: transaction volume, error rate, SLA compliance,
     report submission timeliness, customer complaint resolution rate, loan processing
     time, digital channel uptime contribution.
   • Success criteria (rating 1–5) must be defined in descending threshold bands, e.g.:
       5 = 100% of target achieved with zero errors
       4 = 90–99% of target
       3 = 80–89% of target
       2 = 70–79% of target
       1 = Below 70% of target
   • Use lookup values (System-tracked: BI/Data Warehouse extraction, or Manual:
     manager-verified with evidence attachment) to populate actual achievement.
D. "CAN EXCEED" OBJECTIVES — STRETCH GOALS
   • These reward employees for performance beyond the set target; the rating scale
     allows scores above the base threshold (over-achievement is recognized).
   • Use for innovation initiatives, process improvement, staff development activities,
     cross-functional project contributions, digital adoption targets, or any objective
     where exceeding the plan adds measurable value.
   • Examples: implementing a new digital service feature ahead of schedule, achieving
     a customer satisfaction score above the benchmark, completing an additional
     certification, reducing manual processing time beyond the target threshold.
   • Success criteria for "Can Exceed" should include an "Exceeds Expectations (5+)"
     band that rewards over-delivery, e.g.:
       5 = Achieved 110%+ of target / introduced additional improvement
       4 = Achieved 100–109% of target
       3 = Achieved 85–99% of target
       2 = Achieved 70–84% of target
       1 = Below 70% of target
   • At least {max(1, remaining // 3)} of the {remaining} objectives must be "Can Exceed"
     to balance accountability with motivation.
     
     
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR TASK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The first objective "Achieve team critical target" is already fixed with:
  weight_percent: 50, category: "Cannot Exceed", measure: "Various",
  target: "50% of manager's target", tracking_source: "System", time_frame: "Quarterly"
DO NOT include it in your output. It will be prepended automatically.

Generate exactly {remaining} additional SMART objectives.
All {remaining} objectives combined must have weights that sum to exactly 50.

IMPORTANT - SOURCE ATTRIBUTION:
For EACH objective you generate, you MUST specify which source it comes from:
- "JD"     = Directly from job description responsibilities
- "BSC"    = From Balanced Scorecard strategic objectives
- "LOS"    = From Line of Sight alignment
- "Sample" = Adapted from sample objectives (with significant modification)
- "LLM"    = AI generated based on common practices (use sparingly)

RULES
1.  SMART: Specific, Measurable, Achievable, Relevant, Time-bound.
3.  LOS: Each objective must trace back to the division/department line of sight to BSC.
4.  Role Fit: Match actual duties of the job title and grade.
5.  Weights: Must sum to exactly 50.
6.  Cannot Exceed: Core duties with capped rating — use for primary KPIs (see section D).
7.  Can Exceed: Stretch goals that reward over-delivery — use for innovation/improvement
    objectives (see section E). At least {max(1, remaining // 3)} objective(s) must be
    "Can Exceed".
8. Language: Use CBE institutional PMS style (action verbs, percentage targets,
    TOR references, quarterly framing).
11. No duplication: Every objective must be distinct in scope and measure.
12. Output: Return ONLY valid JSON. No markdown. No preamble.
13. All objectives are quarterly based.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REQUIRED JSON OUTPUT FORMAT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{{
  "objectives": [
    {{
      "objective": "Clear, action-oriented SMART statement",
      "measure": "Percentage | Number | Quality | Time | Various",
      "target": "Exact target value or threshold",
      "weight_percent": 10,
      "category": "Cannot Exceed | Can Exceed",
      "tracking_source": "System | Manual | Both",
      "time_frame": "Monthly | Quarterly | Annually",
      "source": "JD | BSC | LOS | Sample | LLM",
      "success_criteria": {{
        "5": "Description of rating-5 performance threshold",
        "4": "Description of rating-4 performance threshold",
        "3": "Description of rating-3 performance threshold",
        "2": "Description of rating-2 performance threshold",
        "1": "Description of rating-1 performance threshold"
      }},
      "lookup_value": "Brief description of the lookup value used for data tracking"
    }}
  ]
}}
"""