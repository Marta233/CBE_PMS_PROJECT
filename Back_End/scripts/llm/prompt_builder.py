"""
prompt_builder.py  (v2)

Receives already-extracted context from process_embeddings.py / extractor.py:
    context = {
        "query"      : str  — raw query (Division, Job Title, Department, Unit, Grade)
        "jd_context" : str  — full JD text for the matched employee (one doc)
        "bsc_context": str  — top-k BSC KPI chunks joined by double newline
        "los_context": str  — LOS docs for the matched department joined by double newline
    }

Decision-factor hierarchy:
    1. BSC  — every objective anchored to a specific BSC KPI
    2. LOS  — each objective traces to the department LOS goal
    3. JD   — objective scoped to what this employee can own

Standards extracted from the CBE Digital Banking Operationalize Document:
    - Weight allocation per grade band (W1–W7)
    - Goal category rules (Major Critical / Cannot Exceed / Can Exceed)
    - Appraisal band tables for both category types
    - Document quality-time split rule
    - Grade-based goal focus
    - Target expression standards
"""
import re
import json
from pathlib import Path

BASE_DIR    = Path(__file__).resolve().parent.parent.parent
SAMPLE_PATH = BASE_DIR / "Data" / "sample" / "sample_objectives.json"


# ═══════════════════════════════════════════════════════════════════
# GRADE-BAND LOOKUP  (from operationalize document)
# ═══════════════════════════════════════════════════════════════════

# Critical target weight per grade band — extracted from DB0001–DB0058
CRITICAL_TARGET_WEIGHT: dict[str, int] = {
    "director"                 : 80,
    "unit_manager"             : 70,
    "team_leader"              : 50,
    "senior_officer"           : 50,   # JG-13
    "digital_banking_officer"  : 50,   # JG-12
    "associate_officer_ii"     : 50,   # JG-11
    "associate_officer_i"      : 50,   # JG-10
    "banking_operation_officer": 40,   # JG-9
    "junior_officer_ii"        : 40,   # JG-8
    "junior_officer_i"         : 40,   # JG-7
}

# Remaining weight distribution after critical target — from operationalize doc
# Describes what types of goals consume the remaining %, not specific numbers
GRADE_GOAL_FOCUS: dict[str, str] = {
    "director": (
        "strategic oversight, revenue generation, expense management, "
        "department compliance, stakeholder management, initiative delivery"
    ),
    "unit_manager": (
        "team performance oversight, non-interest income strategy, regulatory compliance, "
        "customer satisfaction, transaction volume, new functionalities, "
        "active user growth (primary channel metric — highest non-critical weight), "
        "3rd party productivity, document turnaround"
    ),
    "team_leader": (
        "operational execution oversight, zero-backlog production or delivery targets, "
        "materials and stock availability, report submission, stakeholder communication"
    ),
    "senior_officer": (
        "proposal initiation and analysis, document preparation and review (split into "
        "Quality + Time sub-goals), non-interest income proposals, new features and "
        "functionalities, fraud/product catalogue, active channel user acquisition "
        "(primary metric — 20% weight), strategic assessment documents"
    ),
    "digital_banking_officer": (
        "BRD and proposal preparation (Quality + Time splits), 3rd party operational "
        "monitoring, active channel user growth (20% weight), inactive user reduction, "
        "new functionalities, income or expense assessments, branding or customer feedback"
    ),
    "associate_officer_ii": (
        "UAT preparation and execution, new product or service idea initiation "
        "(Quality + Time splits), performance and fraud reporting, "
        "active channel user growth, customer preference analysis"
    ),
    "associate_officer_i": (
        "UAT execution, branch or user issue resolution, business idea initiation, "
        "performance and fraud reporting (Quality + Time splits), "
        "industry trend identification, active channel user growth"
    ),
    "banking_operation_officer": (
        "income or fee assessments (Quality + Time splits), use case and loophole "
        "identification, proposal drafting for new product ideas, UAT completion rate, "
        "performance report compilation, active channel user support — "
        "DO NOT include strategic oversight or income strategy"
    ),
    "junior_officer_ii": (
        "sales performance analysis (Quality + Time splits), compiled status reports, "
        "marketing activity execution, 3rd party and merchant visits, "
        "active channel user growth — "
        "DO NOT include proposal initiation or BRD preparation"
    ),
    "junior_officer_i": (
        "transaction performance analysis (Quality + Time splits), periodic 3rd party "
        "and merchant visits, transaction report compilation, channel penetration support, "
        "active channel user growth — "
        "DO NOT include proposal initiation or BRD preparation"
    ),
}

# Max goal rows per grade (from document analysis)
MAX_GOAL_ROWS: dict[str, int] = {
    "director"                 : 9,
    "unit_manager"             : 9,
    "team_leader"              : 7,
    "senior_officer"           : 10,
    "digital_banking_officer"  : 10,
    "associate_officer_ii"     : 9,
    "associate_officer_i"      : 11,
    "banking_operation_officer": 10,
    "junior_officer_ii"        : 10,
    "junior_officer_i"         : 10,
}


def _resolve_grade_band(job_title: str, job_grade: int) -> str:
    """Map job title + numeric grade to the correct grade band key."""
    t = job_title.lower()
    if "director" in t or "vice president" in t:
        return "director"
    if "unit manager" in t or ("manager" in t and job_grade >= 14):
        return "unit_manager"
    if "team leader" in t:
        return "team_leader"
    if job_grade == 13 or "senior" in t:
        return "senior_officer"
    if job_grade == 12:
        return "digital_banking_officer"
    if job_grade == 11:
        return "associate_officer_ii"
    if job_grade == 10:
        return "associate_officer_i"
    if job_grade == 9:
        return "banking_operation_officer"
    if job_grade == 8:
        return "junior_officer_ii"
    if job_grade <= 7:
        return "junior_officer_i"
    return "senior_officer"   # safe fallback


# ═══════════════════════════════════════════════════════════════════
# SAMPLE LOADERS  (unchanged)
# ═══════════════════════════════════════════════════════════════════

def load_samples(unit: str = "", job_title: str = "") -> list:
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


# ═══════════════════════════════════════════════════════════════════
# MAIN BUILDER
# ═══════════════════════════════════════════════════════════════════

def build_prompt(context: dict, num_objectives: int) -> str:
    """
    Build the full LLM prompt grounded in the CBE operationalize document.

    Parameters
    ----------
    context : dict
        Keys: query, jd_context, bsc_context, los_context.
    num_objectives : int
        Total objectives including the pre-fixed critical target.
        LLM generates (num_objectives - 1).
    """
    query       = context.get("query",       "").strip()
    jd_context  = context.get("jd_context",  "Not provided").strip()
    bsc_context = context.get("bsc_context", "Not provided").strip()
    los_context = context.get("los_context", "Not provided").strip()

    # ── Parse query fields ────────────────────────────────────────
    unit = job_title = division = department = ""
    job_grade = 13   # default fallback
    for line in query.splitlines():
        l = line.strip()
        ll = l.lower()
        if ll.startswith("unit:"):
            unit = l.split(":", 1)[-1].strip()
        elif ll.startswith("job title:"):
            job_title = l.split(":", 1)[-1].strip()
        elif ll.startswith("division:"):
            division = l.split(":", 1)[-1].strip()
        elif ll.startswith("department:"):
            department = l.split(":", 1)[-1].strip()
        elif ll.startswith("job grade:"):
            try:
                job_grade = int(re.sub(r"[^0-9]", "", l.split(":", 1)[-1]))
            except ValueError:
                pass

    # ── Resolve grade band and weights ───────────────────────────
    band           = _resolve_grade_band(job_title, job_grade)
    critical_wt    = CRITICAL_TARGET_WEIGHT[band]
    remaining_wt   = 100 - critical_wt
    remaining      = num_objectives - 1
    goal_focus     = GRADE_GOAL_FOCUS.get(band, "duties outlined in the JD")
    max_rows       = MAX_GOAL_ROWS.get(band, 10)

    # ── Samples ───────────────────────────────────────────────────
    samples           = load_samples(unit=unit, job_title=job_title)
    formatted_samples = format_samples_for_prompt(samples)

    return f"""You are a CBE Digital Banking PMS objective generation engine.
Your output will be loaded directly into the Oracle PMS system.
Generate objectives that match the exact standards of the CBE Digital Banking
Operationalize Document (September 2025).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EMPLOYEE PROFILE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{query}
Resolved grade band : {band.replace("_", " ").title()}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PRIORITY 1 — BSC CONTEXT  (anchor — every objective must cite one KPI)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{bsc_context}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PRIORITY 2 — LOS CONTEXT  (departmental mandate validator)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{los_context if los_context else "Not available — rely on BSC and JD only."}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PRIORITY 3 — JD CONTEXT  (individual scope and grade filter)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{jd_context}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SAMPLE OBJECTIVES  (style and structure reference — do NOT copy verbatim)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{formatted_samples}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FIXED OBJECTIVE — already set, do NOT include in your output
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Goal      : Achieve team critical target
  Measure   : Various (team performance against manager/director target)
  Target    : {critical_wt}% of {"Division" if band == "director" else "Director's" if band == "unit_manager" else "Manager's"} target
  Weight    : {critical_wt}%
  Category  : Major Critical
  Tracking  : System | Quarterly

Generate exactly {remaining} additional objectives.
Their weights must sum to exactly {remaining_wt}%.
Maximum total rows including quality/time splits: {max_rows - 1}.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION A — WEIGHT ALLOCATION RULES  (from operationalize document)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

W1. The fixed critical target carries {critical_wt}%. Your {remaining} objectives
    must fill the remaining {remaining_wt}% exactly. If the sum is not {remaining_wt},
    adjust Can Exceed goals proportionally before outputting.

W2. PRIMARY CHANNEL METRIC (active users / card activation / CBE-Birr users):
    This always receives the HIGHEST single weight among your generated objectives.
    Standard weight: 20% for JG-10 to JG-13 roles, 15% for Unit Manager,
    10% for JG-7 to JG-9 roles.
    Identify the primary channel metric from the BSC context and give it this weight.

W3. DOCUMENT / REPORT / PROPOSAL GOALS — MANDATORY QUALITY + TIME SPLIT:
    Any goal involving document preparation, BRD, assessment, proposal, or report
    MUST appear as TWO separate rows:
      Row A — Quality sub-goal : measure = "Quality"
               target = "One round review with minor editing"
               category = Cannot Exceed
      Row B — Time sub-goal   : measure = "Time"
               target = "As per TOR deadline" or "Monthly/Quarterly as per TOR"
               category = Can Exceed
    Weight split options (choose based on goal importance):
      High importance  → Quality 5%  + Time 5%
      Medium           → Quality 3%  + Time 2%
      Low              → Quality 2%  + Time 2%
    Never assign a single weight to a document goal.

W4. INCOME / REVENUE GOALS: weight 5% | category: Can Exceed
    Target: "As per quarterly action plan of 100%"

W5. NEW FEATURES / FUNCTIONALITIES: weight 3–5% | category: Can Exceed
    Target: "As per quarterly action plan of [N] new feature(s)"

W6. COMPLIANCE / REGULATORY / SECURITY: weight 1–2% | category: Cannot Exceed
    Target: "As per minimum standards & 100% compliance"
    Required for Unit Manager and above. Optional for lower grades.

W7. CUSTOMER SATISFACTION: weight 1–2% | category: Cannot Exceed
    Target: "As per the minimum standard of 80%"

W8. WEIGHT CHECK: Before outputting, sum all weight_percent values you generate.
    If the sum ≠ {remaining_wt}, this is an error. Fix it before responding.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION B — GOAL CATEGORIES  (from operationalize document)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Three categories exist. Each maps to a different appraisal rating scale:

MAJOR CRITICAL (pre-fixed only — do not use for generated objectives)
  The "Achieve team critical target" goal only.

CANNOT EXCEED
  Used for: compliance, document quality sub-goals, accuracy, operational
  obligations, inactive user reduction, UAT completion, SLA adherence.
  Rating scale (5 = best):
    5 — Meets Expectations    : Achieves 100% of target, full compliance
    4 — Nearly Meets          : Achieves 90–99.9% of target
    3 — Partially Meets       : Achieves 80–89.9% of target
    2 — Minimally Meets       : Achieves 66–79.9% of target
    1 — Unsatisfactory        : Achieves less than 65% of target
  For document quality goals specifically:
    5 → Documents ready after 1st review with minor or no editing
    4 → Minor editing needed after 2nd review
    3 → Minor editing needed after 3rd review
    2 → Significant editing after multiple reviews
    1 → Consistently poor quality

CAN EXCEED
  Used for: revenue, active user growth, features, 3rd party integrations,
  time-based document goals, marketing activities, merchant visits.
  Rating scale (5 = best):
    5 — Exceptional           : Exceeds 150% of plan
    4 — Above Expectations    : Achieves 125–149.9% of plan
    3 — Meets Expectations    : Achieves 100–124.9% of plan
    2 — Below Expectations    : Achieves 65–99.9% of plan
    1 — Unsatisfactory        : Achieves less than 65% of plan
  For time-based document goals specifically:
    5 → Action taken in ≤ 1 day of receiving
    4 → Action taken within 1–2 days
    3 → Action taken within 3 days
    2 → Action taken within 4–5 days
    1 → Action taken in more than 5 days
  For expense management goals (invert — lower is better):
    5 → Controllable expense < 95% of approved budget
    4 → Expense 96–99% of budget
    3 → Expense = 100% of budget
    2 → Expense 101–104% of budget
    1 → Expense > 105% of budget

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION C — GOAL FOCUS FOR THIS GRADE BAND
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Grade band: {band.replace("_", " ").title()} | Job Grade: {job_grade}

This role should focus on: {goal_focus}

Do NOT generate objectives that belong to a higher grade band.
Do NOT generate objectives for a different unit or channel.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION D — TARGET EXPRESSION STANDARDS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Use these exact target expressions from the operationalize document:

  • Quantitative channel targets (users, transactions, income):
      "As per quarterly action plan of 100%"
      (Do not invent a number if no unit plan value is in the BSC context.
       If an annual BSC target is present, divide by 4 for quarterly slice.)

  • Document quality sub-goals:
      "One round review with minor editing"

  • Document time sub-goals:
      "Quarterly as per the time stated on TOR"
      or "Monthly as per the time stated on TOR"

  • Compliance goals:
      "As per minimum standards & 100% compliance"

  • Customer satisfaction:
      "As per the minimum standard of 80%"

  • 3rd party productivity:
      "90% of productive 3rd party" or "As per action plan"

  • New features / functionalities:
      "As per the quarter action plan of [N] new feature(s)"

  • Expense management:
      "Max. of 95% of the approved budget" or "Not to exceed the approved budget"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION E — TRACKING SOURCE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  System — BI/DWH, CBS (T24/Finacle), Oracle EPM.
           Use for: user counts, transaction volume, revenue, error rates.
  Manual — Manager captures with attachment via Oracle self-service.
           Use for: document quality, project completion, training, assessments.
  Both   — System provides data, manager validates.
           Use for: 3rd party productivity, mixed KPIs.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MANDATORY GENERATION RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 1. Every objective must cite exactly one BSC KPI from the BSC context above.
 2. Every objective must trace to at least one LOS goal (or mark N/A).
 3. Every objective must be within this employee's JD responsibilities and grade.
 4. SMART format: action verb + measurable outcome + time-bound (quarterly).
 5. Weights of all generated objectives must sum to exactly {remaining_wt}.
 6. All objectives are quarterly unless the TOR specifies monthly frequency.
 7. No two objectives may share the same BSC KPI or the same measure.
 8. Document goals MUST be split into Quality + Time rows (see W3 above).
 9. Every objective must have a complete appraisal_logic block with the
    correct 5-band description from Section B. Match the category exactly.
10. No duplication in scope or measure across objectives.
11. Output ONLY valid JSON — no markdown fences, no preamble, no trailing text.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REQUIRED JSON OUTPUT FORMAT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{{
  "objectives": [
    {{
      "objective"        : "Action-oriented SMART statement scoped to {unit or 'this unit'}",
      "measure"          : "Percentage | Number | Quality | Time | Million birr | Various",
      "target"           : "Exact target expression from Section D above",
      "weight_percent"   : 10,
      "category"         : "Cannot Exceed | Can Exceed",
      "tracking_source"  : "System | Manual | Both",
      "time_frame"       : "Quarterly",
      "bsc_kpi"          : "Exact KPI name from the BSC block above",
      "bsc_strategic_objective" : "Exact Strategic Objective text from BSC block",
      "los_alignment"    : "One sentence — which LOS goal this traces to, or N/A",
      "source"           : "BSC | LOS | JD | Sample | LLM",
      "appraisal_logic"  : {{
        "rating_5" : "Condition for Meets Expectations or Exceptional (matches category)",
        "rating_4" : "Condition for Nearly Meets or Above Expectations",
        "rating_3" : "Condition for Partially Meets or Meets Expectations",
        "rating_2" : "Condition for Minimally Meets or Below Expectations",
        "rating_1" : "Condition for Unsatisfactory"
      }}
    }}
  ],
  "weight_sum_check": {remaining_wt},
  "grade_band"      : "{band}",
  "critical_target" : {{
    "objective"      : "Achieve team critical target",
    "measure"        : "Various",
    "target"         : "{critical_wt}% of {'Division' if band == 'director' else 'Director' + chr(39) + 's' if band == 'unit_manager' else 'Manager' + chr(39) + 's'} target",
    "weight_percent" : {critical_wt},
    "category"       : "Major Critical",
    "tracking_source": "System",
    "time_frame"     : "Quarterly"
  }}
}}
"""