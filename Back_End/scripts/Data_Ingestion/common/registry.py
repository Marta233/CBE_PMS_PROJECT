"""
registry.py - the ONE place that knows what a division / department / unit is
called, who belongs to whom, and every spelling people use for them.

Loaders call this instead of keeping their own alias maps. Names are matched
"loosely" (case, spaces, '&' vs 'and', punctuation ignored) so
'Mobile &Internet Banking' == 'Mobile & Internet Banking' == 'mobile and internet banking'.
"""
from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

REGISTRY_PATH = Path(__file__).with_name("org_registry.json")

# A unit cell meaning "every unit of the department" (department-wide plan).
ALL_UNITS_TOKENS = {"all", "all units", "any"}
# A unit cell like "Both", "Both Merchant and Agent" names SEVERAL units of one
# department. It is not a unit and not the whole department: use expand_units().
MULTI_UNIT_PREFIX = "both"

_LOCK = threading.Lock()
_CACHE: dict = {}


def loose_key(value) -> str:
    """Normalise a name for comparison only (never stored)."""
    s = str(value or "").lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


@dataclass
class Resolution:
    """Result of resolving a (division, department, unit) triple."""
    division: str = ""
    department: str = ""
    unit: str = ""
    all_units: bool = False              # unit cell was 'All' -> department scope
    multi_units: list = field(default_factory=list)  # unit cell was 'Both ...' -> these units
    corrected: list = field(default_factory=list)    # fields changed because the unit says so
    problems: list = field(default_factory=list)
    inferred: list = field(default_factory=list)   # fields filled in by the registry
    unconfirmed: list = field(default_factory=list)  # entries not yet business-approved

    @property
    def ok(self) -> bool:
        return not self.problems


def _load() -> dict:
    with _LOCK:
        mtime = REGISTRY_PATH.stat().st_mtime
        if _CACHE.get("mtime") == mtime:
            return _CACHE["data"]
        raw = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        div_idx, dept_idx = {}, {}   # loose -> node ; dept_idx: loose -> [(div, dept)]
        for div in raw["divisions"]:
            for k in [div["name"], *div.get("aliases", [])]:
                div_idx[loose_key(k)] = div
            for dept in div.get("departments", []):
                for k in [dept["name"], *dept.get("aliases", [])]:
                    hits = dept_idx.setdefault(loose_key(k), [])
                    if not any(h[1] is dept for h in hits):   # aliases that collapse to one key
                        hits.append((div, dept))
        _CACHE.update(mtime=mtime, data={"raw": raw, "div": div_idx, "dept": dept_idx})
        return _CACHE["data"]


def reload() -> None:
    """Force a re-read (the file is also re-read automatically when it changes)."""
    with _LOCK:
        _CACHE.clear()


# ---------------------------------------------------------------- lookups
def _find_unit(dept: dict, name) -> Optional[dict]:
    k = loose_key(name)
    for u in dept.get("units", []):
        if k in {loose_key(u["name"]), *(loose_key(a) for a in u.get("aliases", []))}:
            return u
    return None


def canon_division(name) -> Optional[str]:
    node = _load()["div"].get(loose_key(name))
    return node["name"] if node else None


def canon_department(name, division=None) -> Optional[str]:
    hits = _load()["dept"].get(loose_key(name), [])
    if division:
        dn = canon_division(division)
        hits = [h for h in hits if h[0]["name"] == dn]
    return hits[0][1]["name"] if len(hits) == 1 else None


def canon_unit(name, department, division=None) -> Optional[str]:
    hits = _load()["dept"].get(loose_key(department), [])
    if division:
        dn = canon_division(division)
        hits = [h for h in hits if h[0]["name"] == dn]
    if len(hits) != 1:
        return None
    u = _find_unit(hits[0][1], name)
    return u["name"] if u else None


def department_of_unit(unit, division=None) -> Optional[tuple]:
    """(division, department) that owns this unit name, if exactly one does.
    Replaces the old UNIT_DEPARTMENT_MAP."""
    found = set()
    for div in _load()["raw"]["divisions"]:
        if division and canon_division(division) != div["name"]:
            continue
        for dept in div.get("departments", []):
            if _find_unit(dept, unit):
                found.add((div["name"], dept["name"]))
    return found.pop() if len(found) == 1 else None


def division_of_department(department) -> Optional[str]:
    hits = _load()["dept"].get(loose_key(department), [])
    divs = {h[0]["name"] for h in hits}
    return divs.pop() if len(divs) == 1 else None


# ---------------------------------------------------------------- main API
def expand_units(cell, department, division=None) -> list:
    """
    Turn a Work Plan 'Unit' cell into canonical unit names.
      'Agent'                    -> ['Agent Management']
      'Both Merchant and Agent'  -> ['Agent Management', 'Merchant Management']
      'Both' (names lost)        -> the department's "paired_units" from the registry
    Returns [] when nothing can be determined.
    """
    hits = _load()["dept"].get(loose_key(department), [])
    if division:
        dn = canon_division(division)
        hits = [h for h in hits if h[0]["name"] == dn]
    if len(hits) != 1:
        return []
    dept = hits[0][1]
    k = loose_key(cell)
    if not k:
        return []
    if not (k == MULTI_UNIT_PREFIX or k.startswith(MULTI_UNIT_PREFIX + " ")):
        u = _find_unit(dept, cell)
        return [u["name"]] if u else []
    rest = f" {k[len(MULTI_UNIT_PREFIX):].strip()} "
    found = []
    for u in dept.get("units", []):
        names = [loose_key(u["name"]), *(loose_key(a) for a in u.get("aliases", []))]
        if any(n and f" {n} " in rest for n in names):
            found.append(u["name"])
    if found:
        return found
    paired = dept.get("paired_units", [])
    return [u["name"] for u in dept.get("units", []) if u["name"] in paired]


def resolve(division="", department="", unit="", trust_unit=False, infer_department=True) -> Resolution:
    """
    Canonicalise a triple, filling the parent levels the registry can derive
    (unit -> department -> division) and reporting anything it cannot place.
    Blank inputs stay blank unless they can be derived safely.

    trust_unit=True: when the department given does not contain the unit but
    the unit belongs to exactly one other department, the UNIT wins and the
    department is corrected (recorded in .corrected). Used by the migration,
    because a unit name is more specific than a department label that was
    mis-inferred by a loader.

    infer_department=False: a blank department STAYS blank (never derived from
    the unit). Use it for sources whose departments must come from the file
    itself (JD). Work Plans keep the default, because their department is
    legitimately derived from the unit (e.g. Mobile Banking -> Mobile & Internet Banking).
    """
    r = Resolution()
    division, department, unit = (str(x or "").strip() for x in (division, department, unit))

    if unit and loose_key(unit) in ALL_UNITS_TOKENS:
        r.all_units, unit = True, ""
    elif unit and (loose_key(unit) == MULTI_UNIT_PREFIX or loose_key(unit).startswith(MULTI_UNIT_PREFIX + " ")):
        dep = canon_department(department, canon_division(division) if division else None) if department else ""
        r.multi_units = expand_units(unit, dep or department, division or None)
        r.problems.append(f"unit '{unit}' names several units {r.multi_units or '(unknown)'} - "
                          f"expand it into one document per unit")
        unit = ""

    # division
    if division:
        r.division = canon_division(division) or ""
        if not r.division:
            r.problems.append(f"unknown division '{division}'")

    # department
    if department:
        r.department = canon_department(department, r.division or None) or ""
        if not r.department:
            r.problems.append(f"unknown department '{department}'"
                              + (f" in division '{r.division}'" if r.division else ""))
    elif unit and infer_department:
        owner = department_of_unit(unit, r.division or None)
        if owner:
            r.division, r.department = owner
            r.inferred += ["division", "department"]

    # division from department
    if r.department and not r.division:
        d = division_of_department(r.department)
        if d:
            r.division = d
            r.inferred.append("division")

    # unit
    if unit and r.department:
        r.unit = canon_unit(unit, r.department, r.division or None) or ""
        if not r.unit and trust_unit:
            owner = department_of_unit(unit, r.division or None)
            if owner:
                r.corrected.append(f"department '{r.department}' -> '{owner[1]}' (unit '{unit}' belongs there)")
                r.division, r.department = owner
                r.unit = canon_unit(unit, r.department, r.division) or ""
        if not r.unit:
            r.problems.append(f"unit '{unit}' does not belong to department '{r.department}'")
    elif unit and not r.department and not r.problems and infer_department:
        r.problems.append(f"cannot place unit '{unit}' in any department")

    # unconfirmed (informational)
    for div in _load()["raw"]["divisions"]:
        if div["name"] != r.division:
            continue
        if not div.get("confirmed", True):
            r.unconfirmed.append(f"division {div['name']}")
        for dept in div.get("departments", []):
            if dept["name"] != r.department:
                continue
            if not dept.get("confirmed", True):
                r.unconfirmed.append(f"department {dept['name']}")
            u = _find_unit(dept, r.unit) if r.unit else None
            if u and not u.get("confirmed", True):
                r.unconfirmed.append(f"unit {u['name']}")
    return r


def list_tree() -> list:
    """Division -> department -> unit tree for upload dropdowns (GET /api/registry)."""
    out = []
    for div in _load()["raw"]["divisions"]:
        out.append({"division": div["name"], "departments": [
            {"department": d["name"], "units": [u["name"] for u in d.get("units", [])]}
            for d in div.get("departments", [])]})
    return out



# ---------------------------------------------------------------- text search
def _contains_words(haystack: str, needle: str) -> bool:
    """Whole-word containment on already loose-keyed strings."""
    return bool(needle) and f" {needle} " in f" {haystack} "


def _best(cands: list) -> Optional[str]:
    """cands = [(matched_key_length, canonical_name)] -> longest match if unambiguous."""
    if not cands:
        return None
    cands.sort(key=lambda c: -c[0])
    top = {c[1] for c in cands if c[0] == cands[0][0]}
    return top.pop() if len(top) == 1 else None


def find_division(text) -> Optional[str]:
    """Division named inside free text, e.g. sheet ' RBB 2025.2026' -> 'RBB'."""
    h = loose_key(text)
    cands = []
    for div in _load()["raw"]["divisions"]:
        for k in [div["name"], *div.get("aliases", [])]:
            lk = loose_key(k)
            if _contains_words(h, lk):
                cands.append((len(lk), div["name"]))
    return _best(cands)


def find_department(text, division=None) -> Optional[str]:
    """Department named inside free text (whole words, longest match wins)."""
    h = loose_key(text)
    dn = canon_division(division) if division else None
    cands = []
    for div in _load()["raw"]["divisions"]:
        if dn and div["name"] != dn:
            continue
        for dept in div.get("departments", []):
            for k in [dept["name"], *dept.get("aliases", [])]:
                lk = loose_key(k)
                if _contains_words(h, lk):
                    cands.append((len(lk), dept["name"]))
    return _best(cands)


def find_unit(text, department, division=None) -> Optional[str]:
    """Unit of `department` named inside free text."""
    h = loose_key(text)
    hits = _load()["dept"].get(loose_key(department), [])
    if division:
        dn = canon_division(division)
        hits = [x for x in hits if x[0]["name"] == dn]
    if len(hits) != 1:
        return None
    cands = []
    for u in hits[0][1].get("units", []):
        for k in [u["name"], *u.get("aliases", [])]:
            lk = loose_key(k)
            if _contains_words(h, lk):
                cands.append((len(lk), u["name"]))
    return _best(cands)


def find_unit_anywhere(text, division=None) -> Optional[tuple]:
    """
    (division, department, unit) of the unit whose name/alias appears as whole words in free
    text, when exactly one unit matches best. Loaders use it to fill a blank department from the
    unit the document names - it replaces the hard-coded keyword tables the loaders used to carry.
    """
    h = loose_key(text)
    if not h:
        return None
    dn = canon_division(division) if division else None
    cands = []
    for div in _load()["raw"]["divisions"]:
        if dn and div["name"] != dn:
            continue
        for dept in div.get("departments", []):
            for u in dept.get("units", []):
                for k in [u["name"], *u.get("aliases", [])]:
                    lk = loose_key(k)
                    if _contains_words(h, lk):
                        cands.append((len(lk), (div["name"], dept["name"], u["name"])))
    if not cands:
        return None
    cands.sort(key=lambda c: -c[0])
    top = {c[1] for c in cands if c[0] == cands[0][0]}
    return top.pop() if len(top) == 1 else None
