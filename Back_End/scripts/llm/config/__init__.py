"""Employee profile parsing — used only to inject values into prompts, not to assign outputs."""

from .grade_bands import (
    CRITICAL_TARGET_WEIGHT,
    CRITICAL_TARGET_ROLE_LABEL,
    GRADE_GOAL_FOCUS,
    MAX_GOAL_ROWS,
    EmployeeProfile,
    parse_employee_query,
    resolve_grade_band,
)

__all__ = [
    "CRITICAL_TARGET_WEIGHT",
    "CRITICAL_TARGET_ROLE_LABEL",
    "GRADE_GOAL_FOCUS",
    "MAX_GOAL_ROWS",
    "EmployeeProfile",
    "parse_employee_query",
    "resolve_grade_band",
]
