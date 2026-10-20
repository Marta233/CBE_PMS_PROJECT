"""
Grade-band lookups.

Digital Banking uses the Sep 2025 operationalize cascade in
profiles/digital_banking.json. Any other division gets a neutral band
name and no forced critical-target row.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..profiles.policy import band_config, digital_banking_policy, is_digital_banking
from ..sanitize import sanitize_user_field


def _bands() -> dict:
    return digital_banking_policy()["bands"]


# Digital Banking tables, kept for callers that read the cascade directly.
CRITICAL_TARGET_WEIGHT: dict[str, int] = {
    name: int(row["critical_weight"]) for name, row in _bands().items()
}
CRITICAL_TARGET_ROLE_LABEL: dict[str, str] = {
    name: row["supervisor_target"] for name, row in _bands().items()
}
PRIMARY_CHANNEL_WEIGHT: dict[str, int] = {
    name: int(row["primary_channel_weight"]) for name, row in _bands().items()
}

GRADE_GOAL_FOCUS: dict[str, str] = {
    name: row["goal_focus"] for name, row in _bands().items()
}
MAX_GOAL_ROWS: dict[str, int] = {
    name: int(row["max_goal_rows"]) for name, row in _bands().items()
}
DOCUMENT_SPLIT_BANDS: frozenset[str] = frozenset(
    digital_banking_policy()["document_split_bands"]
)
NO_PROPOSAL_BANDS: frozenset[str] = frozenset(
    digital_banking_policy()["no_proposal_bands"]
)


def resolve_grade_band(job_title: str, job_grade: int, division: str = "") -> str:
    """Map job title + numeric grade to a band.

    Grade 12 is digital_banking_officer only for Digital Banking. Other
    divisions use the neutral name officer and do not inherit that cascade.
    """
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
        return "digital_banking_officer" if is_digital_banking(division) else "officer"
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


def draft_count(num_objectives: int, has_grade_policy: bool) -> int:
    """Digital Banking reserves one row for the critical-target objective."""
    reserved = 1 if has_grade_policy else 0
    return max(1, num_objectives - reserved)


@dataclass
class EmployeeProfile:
    division: str = ""
    department: str = ""
    unit: str = ""
    job_title: str = ""
    job_grade: int = 13
    grade_band: str = "senior_officer"
    critical_weight: int = 0
    remaining_weight: int = 100
    has_grade_policy: bool = False
    supervisor_target: str = "Manager's"

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

    profile.grade_band = resolve_grade_band(
        profile.job_title, profile.job_grade, profile.division
    )
    row = band_config(profile.grade_band) if is_digital_banking(profile.division) else None
    if row:
        profile.has_grade_policy = True
        profile.critical_weight = int(row["critical_weight"])
        profile.remaining_weight = 100 - profile.critical_weight
        profile.supervisor_target = row["supervisor_target"]
    else:
        profile.has_grade_policy = False
        profile.critical_weight = 0
        profile.remaining_weight = 100
        profile.supervisor_target = "Manager's"
    return profile
