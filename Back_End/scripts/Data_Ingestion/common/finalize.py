"""
finalize.py - the ONE place where parsed documents are mapped to the organisation
registry, validated and stamped, before anything is stored.

Loaders only read files. They return {"text", "metadata"} with names spelled however
the file spells them. finalize():

  1. fills blank scope fields from the upload form (only fields that make sense for the source)
  2. rejects a document whose file contradicts the form ("file says Card Banking, form says ...")
  3. expands a Work Plan unit cell such as "Both Merchant and Agent" into one document per unit
  4. maps division / department / unit to the canonical registry names
        - Work Plan: a blank department/division is derived from the unit
        - JD: a blank department is NEVER derived (it stays blank, with a warning)
        - JD whose unit is not in its stated department: kept EXACTLY as is, with a warning
  5. checks the schema (required fields per scope level, fiscal year for Work Plans)
  6. stamps provenance: scope_level, batch_id, ingested_at, ingested_by, source_file

It also provides identity_keys(), which says which batch an already-stored document belongs
to (using the same mapping), so a re-upload replaces exactly its own scope.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

from . import registry, schema
from .audit_store import utc_now

SOURCE_FOR_DOC_TYPE = {"BSC": "BSC", "JD": "JD", "LOS": "LOS", "WP": "WorkPlan"}

# Which scope fields a form value may fill / be compared with, per source.
FORM_FIELDS = {
    "BSC": ("division",),
    "LOS": ("division", "department"),
    "JD": ("division", "department", "unit"),
    "WorkPlan": ("division", "department", "unit"),
}
ORG_FIELDS = ("division", "department", "unit")


@dataclass
class Scope:
    """What the person chose on the upload form (all optional)."""
    division: str = ""
    department: str = ""
    unit: str = ""
    fiscal_year: str = ""

    @classmethod
    def from_form(cls, division="", department="", unit="", fiscal_year="") -> "Scope":
        return cls(*(str(v or "").strip() for v in (division, department, unit, fiscal_year)))

    def choices(self, name: str) -> list:
        """Values chosen for a field. The form may send several, joined with '|'
        (e.g. a JD file that covers many units). One value fills blanks; several are an allow-list."""
        return [x.strip() for x in str(getattr(self, name, "") or "").split("|") if x.strip()]


@dataclass
class FinalizeReport:
    accepted: list = field(default_factory=list)
    rejected: list = field(default_factory=list)       # [{reason, source, ... preview}]
    warnings: Counter = field(default_factory=Counter)  # message -> count
    mapped: Counter = field(default_factory=Counter)    # (field, old, new) -> count
    derived: Counter = field(default_factory=Counter)   # field -> count (filled from registry/form)
    expanded: int = 0                                   # extra documents created from "Both ..."

    def summary(self) -> dict:
        return {
            "accepted": len(self.accepted),
            "rejected": len(self.rejected),
            "expanded_extra_documents": self.expanded,
            "warnings": [{"message": m, "count": n} for m, n in self.warnings.most_common()],
            "renamed": [{"field": f, "from": o, "to": n, "count": c}
                        for (f, o, n), c in sorted(self.mapped.items())],
            "filled": dict(self.derived),
            "rejected_examples": self.rejected[:20],
        }


# ----------------------------------------------------------------- helpers
def _s(v) -> str:
    return str(v or "").strip()


def _is_multi(cell) -> bool:
    k = registry.loose_key(cell)
    return k == registry.MULTI_UNIT_PREFIX or k.startswith(registry.MULTI_UNIT_PREFIX + " ")


def _canon(fieldname: str, value: str, ctx: dict) -> Optional[str]:
    if fieldname == "division":
        return registry.canon_division(value)
    if fieldname == "department":
        return registry.canon_department(value, ctx.get("division") or None)
    return registry.canon_unit(value, ctx.get("department", ""), ctx.get("division") or None)


def _same(fieldname: str, a: str, b: str, ctx: dict) -> bool:
    ca, cb = _canon(fieldname, a, ctx), _canon(fieldname, b, ctx)
    if ca and cb:
        return ca == cb
    return registry.loose_key(a) == registry.loose_key(b)


def _canonicalise(meta: dict, src: str, scope: Optional[Scope]):
    """
    Returns (new_meta, problems, mapped, derived, keep_as_is).
    new_meta is None only when there are problems and the document cannot be kept.
    """
    scope = scope or Scope()
    m = dict(meta)
    problems: list = []
    mapped: Counter = Counter()
    derived: Counter = Counter()

    # 1-2. form values: fill blanks, detect contradictions
    ctx: dict = {}
    for f in ORG_FIELDS:
        opts = scope.choices(f) if f in FORM_FIELDS.get(src, ()) else []
        mine = _s(m.get(f))
        if len(opts) == 1:
            fv = opts[0]
            if not mine:
                m[f] = fv
                derived[f] += 1
            elif not _same(f, mine, fv, ctx):
                problems.append(f"the file says {f} '{mine}' but the upload form says '{fv}'")
        elif len(opts) > 1 and mine and not any(_same(f, mine, o, ctx) for o in opts):
            problems.append(f"the file says {f} '{mine}' which is not one of the selected: {', '.join(opts)}")
        ctx[f] = _canon(f, _s(m.get(f)), ctx) or _s(m.get(f)) if _s(m.get(f)) else ""
    if src == "WorkPlan" and scope.fiscal_year:
        mine_fy = _s(m.get("fiscal_year"))
        if not mine_fy:
            m["fiscal_year"] = scope.fiscal_year
            derived["fiscal_year"] += 1
        elif mine_fy != scope.fiscal_year:
            problems.append(f"the file says fiscal year '{mine_fy}' but the upload form says '{scope.fiscal_year}'")
    if problems:
        return None, problems, mapped, derived, False

    # 4. canonical mapping
    res = registry.resolve(m.get("division"), m.get("department"), m.get("unit"),
                           infer_department=src not in schema.NO_DEPARTMENT_INFERENCE)
    if res.problems:
        if src == "JD" and all("does not belong to department" in p for p in res.problems):
            return dict(meta), [], mapped, Counter(), True        # kept exactly as the file had it
        return None, list(res.problems), mapped, derived, False

    for f in ORG_FIELDS:
        new = getattr(res, f)
        old = _s(meta.get(f))
        if new:
            if old and old != new:
                mapped[(f, old, new)] += 1
            elif not _s(m.get(f)) and f in FORM_FIELDS.get(src, ()):
                derived[f] += 1
            m[f] = new
    if res.all_units:
        m["unit"] = ""
    return m, [], mapped, derived, False


def identity_keys(doc: dict) -> set:
    """
    Identity (replace key) of an already-stored or newly built document, computed with the same
    mapping as finalize(), so legacy spellings still match. A legacy Work Plan "Both" document
    answers with the keys of every unit it stands for.
    """
    m = dict(doc.get("metadata") or {})
    src = m.get("source")
    if src not in schema.SOURCE_SCOPES:
        return {("unknown", id(doc))}
    if src == "WorkPlan" and _is_multi(m.get("unit")):
        dept = registry.canon_department(m.get("department", "")) or _s(m.get("department"))
        units = registry.expand_units(m.get("unit"), dept, _s(m.get("division")) or None)
        keys = set()
        for u in units:
            clone = dict(m, unit=u)
            new_meta, *_ = _canonicalise(clone, src, None)
            keys.add(schema.replace_key({"text": "", "metadata": new_meta or clone}))
        if keys:
            return keys
    new_meta, problems, *_ = _canonicalise(m, src, None)
    return {schema.replace_key({"text": "", "metadata": new_meta or m})}


# ------------------------------------------------------------------- main
def finalize(docs: list, doc_type: str, scope: Optional[Scope] = None, *, batch_id: str,
             uploaded_by: str, source_file: str, now: Optional[str] = None) -> FinalizeReport:
    expected = SOURCE_FOR_DOC_TYPE[doc_type]
    now = now or utc_now()
    rep = FinalizeReport()

    def reject(reason: str, d: dict):
        m = (d.get("metadata") or {})
        rep.rejected.append({
            "reason": reason, "source": m.get("source"), "department": m.get("department"),
            "unit": m.get("unit"), "job_title": m.get("job_title"),
            "text_preview": _s(d.get("text"))[:80],
        })

    for d in docs:
        if not isinstance(d, dict) or "metadata" not in d:
            reject("not a {text, metadata} document", d if isinstance(d, dict) else {})
            continue
        meta = d["metadata"]
        src = meta.get("source")
        if src != expected:
            reject(f"document source '{src}' does not match the upload type {doc_type}", d)
            continue

        # 3. "Both ..." Work Plan unit cell -> one document per unit
        metas = [meta]
        if src == "WorkPlan" and _is_multi(meta.get("unit")):
            dept = _s(meta.get("department")) or (scope.choices("department")[0] if scope and len(scope.choices("department")) == 1 else "")
            dept = registry.canon_department(dept, _s(meta.get("division")) or None) or dept
            units = registry.expand_units(meta.get("unit"), dept, _s(meta.get("division")) or None)
            if not units:
                reject(f"cannot work out which units '{meta.get('unit')}' stands for "
                       f"in department '{dept}'", d)
                continue
            metas = [dict(meta, unit=u) for u in units]
            rep.expanded += len(units) - 1

        for mt in metas:
            new_meta, problems, mapped, derived, keep = _canonicalise(mt, src, scope)
            if new_meta is None:
                reject("; ".join(problems), d)
                continue
            new_meta["scope_level"] = schema.infer_scope_level({"metadata": new_meta})
            probe = {"text": d.get("text", ""), "metadata": new_meta}
            errors, warns = schema.check_doc(probe)
            if keep:
                warns = [f"kept unchanged: {w}" if "does not belong to department" in w else w
                         for w in warns]
            if errors:
                reject("; ".join(errors), d)
                continue
            for w in warns:
                rep.warnings[f"[{src}] {w}"] += 1
            rep.mapped.update(mapped)
            rep.derived.update(derived)
            new_meta.update(batch_id=batch_id, ingested_at=now, ingested_by=uploaded_by,
                            source_file=source_file)
            rep.accepted.append({"text": d.get("text", ""), "metadata": new_meta})
    return rep