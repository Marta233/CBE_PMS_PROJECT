"""
schema.py - what a knowledge-base document must look like, per source.

doc = {"text": "...", "metadata": {...}}
Scope level says WHERE in the hierarchy a document applies:
  division | department | unit | position
Each source may only use certain levels, and each level requires certain
fields (and forbids the lower ones). validate_doc() turns that into checks.
"""
from __future__ import annotations

import re

from . import registry

SCOPE_ORDER = ["division", "department", "unit", "position"]

# fields that MUST be filled at a level
REQUIRED = {
    "division":   ["division"],
    "department": ["division", "department"],
    "unit":       ["division", "department", "unit"],
    "position":   ["division", "department", "unit", "job_title"],
}
# fields that MUST be empty at a level
FORBIDDEN = {
    "division":   ["department", "unit", "job_title"],
    "department": ["unit", "job_title"],
    "unit":       ["job_title"],
    "position":   [],
}

# which scope levels each source may use
SOURCE_SCOPES = {
    "BSC":      {"division"},
    "LOS":      {"department"},
    "JD":       {"position"},
    "WorkPlan": {"division", "department", "unit"},   # unit today; others ready
}

# only these sources are versioned by fiscal year
FISCAL_YEAR_SOURCES = {"WorkPlan"}
FISCAL_YEAR_RE = re.compile(r"^\d{4}/\d{2}$")          # e.g. 2026/27


def infer_scope_level(doc: dict) -> str:
    """Scope of a document. Uses metadata['scope_level'] when present,
    otherwise derives it (needed for documents ingested before this schema)."""
    m = doc.get("metadata", {})
    if m.get("scope_level"):
        return m["scope_level"]
    src = m.get("source")
    if src in ("BSC",):
        return "division"
    if src == "LOS":
        return "department"
    if src == "JD":
        return "position"
    if src == "WorkPlan":
        unit = str(m.get("unit") or "").strip()
        if unit and registry.loose_key(unit) not in registry.ALL_UNITS_TOKENS:
            return "unit"           # incl. a legacy 'Both' cell, which validate_doc rejects
        return "department" if m.get("department") else "division"
    return ""


# Fields that are expected but whose absence only WARNS (the document is kept,
# and the blank is never guessed). JD files sometimes carry no department.
SOFT_REQUIRED = {"JD": {"department"}}

# Sources whose blank department must never be inferred from the unit.
NO_DEPARTMENT_INFERENCE = {"JD"}


def check_doc(doc: dict) -> tuple:
    """(errors, warnings). Errors block ingestion; warnings are reported only."""
    errors, warnings = [], []
    src = (doc.get("metadata") or {}).get("source")
    soft = SOFT_REQUIRED.get(src, set())
    for p in validate_doc(doc):
        field_ = p.split(" ")[1] if p.startswith("missing ") else ""
        # A JD whose unit is not in its stated department is reported, never "fixed".
        if field_ in soft or (src == "JD" and "does not belong to department" in p):
            warnings.append(p)
        else:
            errors.append(p)
    return errors, warnings


def validate_doc(doc: dict) -> list:
    """Return a list of problems (empty list = valid). See check_doc() for the
    errors/warnings split used at ingestion."""
    problems = []
    m = doc.get("metadata") or {}
    src = m.get("source")

    if not str(doc.get("text") or "").strip():
        problems.append("empty text")
    if src not in SOURCE_SCOPES:
        return problems + [f"unknown source '{src}'"]

    level = infer_scope_level(doc)
    if level not in SOURCE_SCOPES[src]:
        problems.append(f"{src} cannot have scope '{level}' (allowed: {sorted(SOURCE_SCOPES[src])})")
        return problems

    for f in REQUIRED[level]:
        if not str(m.get(f) or "").strip():
            problems.append(f"missing {f} (required at {level} scope)")
    for f in FORBIDDEN[level]:
        if str(m.get(f) or "").strip():
            problems.append(f"{f} must be empty at {level} scope (found '{m.get(f)}')")

    if src in FISCAL_YEAR_SOURCES:
        fy = str(m.get("fiscal_year") or "")
        if not FISCAL_YEAR_RE.match(fy):
            problems.append(f"fiscal_year '{fy}' must look like 2026/27")

    # names must be canonical and belong together
    res = registry.resolve(m.get("division"), m.get("department"), m.get("unit"),
                           infer_department=src not in NO_DEPARTMENT_INFERENCE)
    problems += res.problems
    for f in ("division", "department", "unit"):
        have, canon = str(m.get(f) or "").strip(), getattr(res, f)
        if have and canon and have != canon:
            problems.append(f"{f} '{have}' is not the canonical name '{canon}'")
    return problems


def replace_key(doc: dict) -> tuple:
    """
    Identity of the batch a document belongs to. Re-uploading a file deletes
    exactly the existing documents sharing its key - nothing wider.
      BSC  : division
      LOS  : division + department
      JD   : division + department + unit
      WP   : scope + division + department + unit + fiscal year
    """
    m = doc["metadata"]
    src = m["source"]
    base = (src, m.get("division", ""))
    if src == "BSC":
        return base
    if src == "LOS":
        return base + (m.get("department", ""),)
    if src == "JD":
        return base + (m.get("department", ""), m.get("unit", ""))
    if src == "WorkPlan":
        return (src, infer_scope_level(doc), m.get("division", ""), m.get("department", ""),
                m.get("unit", ""), m.get("fiscal_year", ""))
    raise ValueError(f"unknown source '{src}'")