"""
Grade-band lookups — Digital Banking Operationalize Document (Sep 2025).

Section 1: Critical target weight (fixed "Achieve team critical target").
Section 2: Remaining goal focus per grade band.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..sanitize import sanitize_user_field


# ── 1. Critical target weight ────────────────────────────────────────────────

CRITICAL_TARGET_WEIGHT: dict[str, int] = {
    "director": 80,
    "unit_manager": 70,
    "team_leader": 50,
    "senior_officer": 50,
    "digital_banking_officer": 50,
    "associate_officer_ii": 50,
    "associate_officer_i": 50,
    "banking_operation_officer": 40,
    "junior_officer_ii": 40,
    "junior_officer_i": 40,
}

CRITICAL_TARGET_ROLE_LABEL: dict[str, str] = {
    "director": "VP's",
    "unit_manager": "Director's",
    "team_leader": "Manager's",
    "senior_officer": "Manager's",
    "digital_banking_officer": "Manager's",
    "associate_officer_ii": "Manager's",
    "associate_officer_i": "Manager's",
    "banking_operation_officer": "Manager's",
    "junior_officer_ii": "Manager's",
    "junior_officer_i": "Manager's",
}

# W2 — primary channel metric weight by band
PRIMARY_CHANNEL_WEIGHT: dict[str, int] = {
    "director": 15,
    "unit_manager": 15,
    "team_leader": 15,
    "senior_officer": 20,
    "digital_banking_officer": 20,
    "associate_officer_ii": 20,
    "associate_officer_i": 20,
    "banking_operation_officer": 10,
    "junior_officer_ii": 10,
    "junior_officer_i": 10,
}

# ── 2. Remaining goal focus ───────────────────────────────────────────────────

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

MAX_GOAL_ROWS: dict[str, int] = {
    "director": 9,
    "unit_manager": 9,
    "team_leader": 7,
    "senior_officer": 10,
    "digital_banking_officer": 10,
    "associate_officer_ii": 9,
    "associate_officer_i": 11,
    "banking_operation_officer": 10,
    "junior_officer_ii": 10,
    "junior_officer_i": 10,
}

# Bands that should include document Quality + Time split rows
DOCUMENT_SPLIT_BANDS: frozenset[str] = frozenset({
    "senior_officer",
    "digital_banking_officer",
    "associate_officer_ii",
    "associate_officer_i",
    "banking_operation_officer",
    "junior_officer_ii",
    "junior_officer_i",
})

# Bands forbidden from proposal/BRD goals
NO_PROPOSAL_BANDS: frozenset[str] = frozenset({
    "banking_operation_officer",
    "junior_officer_ii",
    "junior_officer_i",
})


def resolve_grade_band(job_title: str, job_grade: int) -> str:
    """Map job title + numeric grade to the operationalize document grade band."""
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
    return "senior_officer"


@dataclass
class EmployeeProfile:
    division: str = ""
    department: str = ""
    unit: str = ""
    job_title: str = ""
    job_grade: int = 13
    grade_band: str = "senior_officer"
    critical_weight: int = 50
    remaining_weight: int = 50

    @property
    def query(self) -> str:
        return (
            f"Division: {self.division}\n"
            f"Department: {self.department}\n"
            f"Unit: {self.unit}\n"
            f"Job Title: {self.job_title}\n"
            f"Job Grade: {self.job_grade}"
        )


def parse_employee_query(query: str) -> EmployeeProfile:
    """Parse the multi-line query string used across the pipeline."""
    profile = EmployeeProfile()
    for line in query.splitlines():
        l = line.strip()
        ll = l.lower()
        if ll.startswith("unit:"):
            profile.unit = sanitize_user_field(l.split(":", 1)[-1])
        elif ll.startswith("job title:"):
            profile.job_title = sanitize_user_field(l.split(":", 1)[-1])
        elif ll.startswith("division:"):
            profile.division = sanitize_user_field(l.split(":", 1)[-1])
        elif ll.startswith("department:"):
            profile.department = sanitize_user_field(l.split(":", 1)[-1])
        elif ll.startswith("job grade:"):
            try:
                profile.job_grade = int(re.sub(r"[^0-9]", "", l.split(":", 1)[-1]))
            except ValueError:
                pass

    profile.grade_band = resolve_grade_band(profile.job_title, profile.job_grade)
    profile.critical_weight = CRITICAL_TARGET_WEIGHT[profile.grade_band]
    profile.remaining_weight = 100 - profile.critical_weight
    return profile
