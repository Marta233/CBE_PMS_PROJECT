"""
Read-only audit: how well does the current knowledge_base.json fit the
registry + schema?  Changes nothing.

    python scripts/check_kb_against_registry.py [path/to/knowledge_base.json]
"""
import collections as c
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()


def _find_up(name):
    """Walk up from this script until a folder containing `name` is found
    (also looks one level down, e.g. Back_End/Data_Ingestion)."""
    for base in HERE.parents:
        for cand in [base / name, *(s / name for s in (base.iterdir() if base.is_dir() else []) if s.is_dir())]:
            if (cand / "common" / "registry.py").is_file():
                return cand
    raise SystemExit(f"Could not find a '{name}' folder above {HERE}")


INGESTION = _find_up("Data_Ingestion")
ROOT = INGESTION.parent
sys.path.insert(0, str(INGESTION))
from common import registry, schema  # noqa: E402

def _default_kb():
    for base in HERE.parents:
        cand = base / "Data" / "documents" / "knowledge_base.json"
        if cand.is_file():
            return cand
    raise SystemExit("knowledge_base.json not found - pass its path as an argument")


kb_path = Path(sys.argv[1]) if len(sys.argv) > 1 else _default_kb()
kb = json.loads(Path(kb_path).read_text(encoding="utf-8"))
print(f"{kb_path}: {len(kb)} documents\n")

per_src = c.defaultdict(lambda: c.Counter())
renames = c.Counter()          # (field, old -> new)
problems = c.Counter()         # (source, message)
unconfirmed = c.Counter()
corrections = c.Counter()
collisions = c.defaultdict(set)

for d in kb:
    m = d["metadata"]; src = m["source"]
    res = registry.resolve(m.get("division"), m.get("department"), m.get("unit"), trust_unit=True)
    per_src[src]["docs"] += 1
    per_src[src]["resolvable" if res.ok else "NOT resolvable"] += 1
    for f in ("division", "department", "unit"):
        old, new = str(m.get(f) or ""), getattr(res, f)
        if old and new and old != new:
            renames[(f, old, new)] += 1
    for p in res.problems:
        problems[(src, p)] += 1
    for cmsg in res.corrected:
        corrections[(src, cmsg)] += 1
    for u in res.unconfirmed:
        unconfirmed[u] += 1
    collisions[(src, res.division, res.department, res.unit)].add(
        (m.get("division"), m.get("department"), m.get("unit")))

print("== Per source ==")
for s, cnt in per_src.items():
    print(f"  {s:9} {dict(cnt)}")

print("\n== Names that would be renamed to the canonical spelling ==")
for (f, old, new), n in sorted(renames.items()):
    print(f"  {n:>4}  {f:10} {old!r} -> {new!r}")

print("\n== Department corrected because the UNIT identifies it ==")
for (s_, msg), n in sorted(corrections.items()):
    print(f"  {n:>4}  [{s_}] {msg}")
if not corrections:
    print("  none")

print("\n== Cannot be placed (needs a registry entry or a data fix) ==")
for (s, msg), n in sorted(problems.items()):
    print(f"  {n:>4}  [{s}] {msg}")
if not problems:
    print("  none")

print("\n== Used but not yet business-confirmed ==")
for u, n in sorted(unconfirmed.items()):
    print(f"  {n:>4}  {u}")

print("\n== Replace-key size: documents per key under the NEW rule ==")
by_key = c.Counter()
for d in kb:
    m = d["metadata"]
    res = registry.resolve(m.get("division"), m.get("department"), m.get("unit"))
    probe = {"text": d["text"], "metadata": {**m, "division": res.division or m.get("division", ""),
             "department": res.department or m.get("department", ""),
             "unit": "" if res.all_units else (res.unit or m.get("unit", ""))}}
    if m["source"] in ("BSC",):
        probe["metadata"].update(department="", unit="")
    if m["source"] == "LOS":
        probe["metadata"]["unit"] = ""
    try:
        by_key[schema.replace_key(probe)] += 1
    except Exception as e:
        by_key[("ERR", str(e))] += 1
for k, n in sorted(by_key.items(), key=lambda x: str(x[0])):
    print(f"  {n:>4}  {k}")