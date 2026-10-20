"""Load division grade policy, unit notes, and retrieval keyword signals from data files."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_DIR = Path(__file__).resolve().parent
_DIGITAL_BANKING = "Digital Banking"


def _org():
    try:
        from common import registry
    except ImportError:
        import sys
        ingestion = Path(__file__).resolve().parents[2] / "Data_Ingestion"
        if str(ingestion) not in sys.path:
            sys.path.insert(0, str(ingestion))
        from common import registry
    return registry


@lru_cache(maxsize=1)
def digital_banking_policy() -> dict:
    return json.loads((_DIR / "digital_banking.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _unit_notes() -> dict[str, str]:
    raw = json.loads((_DIR / "unit_notes.json").read_text(encoding="utf-8"))
    registry = _org()
    return {registry.loose_key(name): text for name, text in raw.items()}


@lru_cache(maxsize=1)
def retrieval_signals() -> dict:
    return json.loads((_DIR / "retrieval_signals.json").read_text(encoding="utf-8"))


def is_digital_banking(division: str) -> bool:
    canon = _org().canon_division(division)
    return canon == _DIGITAL_BANKING


def band_config(band: str) -> dict | None:
    return digital_banking_policy()["bands"].get(band)


def unit_note(unit: str) -> str:
    if not unit:
        return ""
    return _unit_notes().get(_org().loose_key(unit), "")


def sibling_unit_names(department: str, unit: str = "", division: str = "") -> list[str]:
    return _org().sibling_unit_names(department, unit, division or None)
