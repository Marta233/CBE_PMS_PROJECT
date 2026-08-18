from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from sqlalchemy.orm import Session

from .models import OrgUnit, Position, UnitGenerationRule, UnitType


@dataclass(frozen=True)
class DigitalBankingOrg:
    departments: List[str]
    units_by_department: Dict[str, List[str]]
    job_titles_by_unit: Dict[str, List[str]]


def _extract_ts_string_list(ts: str, key: str) -> List[str]:
    # Matches: 'Key': [ 'A', 'B', ... ],
    m = re.search(rf"{re.escape(key)}\s*:\s*\[(.*?)\]\s*,", ts, re.DOTALL)
    if not m:
        return []
    blob = m.group(1)
    return [s.strip() for s in re.findall(r"'([^']+)'", blob)]


def _extract_departments(ts: str) -> List[str]:
    # Matches: 'Digital Banking': [ ... ],
    m = re.search(r"'Digital Banking'\s*:\s*\[(.*?)\]\s*,\s*\n\};", ts, re.DOTALL)
    if not m:
        return []
    blob = m.group(1)
    return [s.strip() for s in re.findall(r"'([^']+)'", blob)]


def parse_digital_banking_org(frontend_types_path: Path) -> DigitalBankingOrg:
    ts = frontend_types_path.read_text(encoding="utf-8", errors="ignore")

    departments = _extract_departments(ts)

    units_by_department: Dict[str, List[str]] = {}
    for dept in departments:
        units_by_department[dept] = _extract_ts_string_list(ts, f"'{dept}'")

    # JOB_TITLES_BY_UNIT is large; for seeding we only need the unit keys and titles.
    job_titles_by_unit: Dict[str, List[str]] = {}
    m = re.search(r"export const JOB_TITLES_BY_UNIT:\s*Record<string,\s*string\[]>\s*=\s*\{(.*)\}\s*;\s*\n", ts, re.DOTALL)
    if m:
        body = m.group(1)
        # Find blocks like:  'Unit Name': [ 'Title 1', ... ],
        for _full_key, unit, arr in re.findall(r"('([^']+)')\s*:\s*\[(.*?)\]\s*,", body, re.DOTALL):
            titles = [s.strip() for s in re.findall(r"'([^']+)'", arr)]
            if titles:
                job_titles_by_unit[unit] = titles

    return DigitalBankingOrg(
        departments=departments,
        units_by_department=units_by_department,
        job_titles_by_unit=job_titles_by_unit,
    )


def seed_digital_banking(db: Session, frontend_types_path: Path) -> None:
    org = parse_digital_banking_org(frontend_types_path)

    # Division
    division = db.query(OrgUnit).filter(
        OrgUnit.unit_type == UnitType.division,
        OrgUnit.name == "Digital Banking",
    ).one_or_none()
    if division is None:
        division = OrgUnit(
            name="Digital Banking",
            parent_id=None,
            division="Digital Banking",
            department="",
            unit_type=UnitType.division,
        )
        db.add(division)
        db.flush()

    dept_units: Dict[str, OrgUnit] = {}
    for dept_name in org.departments:
        dept = db.query(OrgUnit).filter(
            OrgUnit.unit_type == UnitType.department,
            OrgUnit.name == dept_name,
            OrgUnit.division == "Digital Banking",
        ).one_or_none()
        if dept is None:
            dept = OrgUnit(
                name=dept_name,
                parent_id=division.id,
                division="Digital Banking",
                department=dept_name,
                unit_type=UnitType.department,
            )
            db.add(dept)
            db.flush()
        dept_units[dept_name] = dept

        for unit_name in org.units_by_department.get(dept_name, []):
            unit = db.query(OrgUnit).filter(
                OrgUnit.unit_type == UnitType.unit,
                OrgUnit.name == unit_name,
                OrgUnit.division == "Digital Banking",
                OrgUnit.department == dept_name,
            ).one_or_none()
            if unit is None:
                unit = OrgUnit(
                    name=unit_name,
                    parent_id=dept.id,
                    division="Digital Banking",
                    department=dept_name,
                    unit_type=UnitType.unit,
                )
                db.add(unit)
                db.flush()

            # Default generation rule (TODO in plan: config-driven)
            rule = db.query(UnitGenerationRule).filter(UnitGenerationRule.unit_id == unit.id).one_or_none()
            if rule is None:
                db.add(UnitGenerationRule(unit_id=unit.id, generation_scope="all_positions_in_unit"))

            # Seed positions (best-effort; grade levels not provided in TS)
            titles = org.job_titles_by_unit.get(unit_name) or org.job_titles_by_unit.get(dept_name) or []
            for title in titles:
                existing = db.query(Position).filter(Position.unit_id == unit.id, Position.title == title).one_or_none()
                if existing is None:
                    db.add(Position(unit_id=unit.id, title=title, grade_level=None))

