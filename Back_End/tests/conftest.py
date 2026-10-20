"""Put the backend packages on sys.path for tests run from Back_End/."""
from __future__ import annotations

import sys
from pathlib import Path

_BACK_END = Path(__file__).resolve().parents[1]
_SCRIPTS = _BACK_END / "scripts"
_INGESTION = _SCRIPTS / "Data_Ingestion"

for _path in (str(_BACK_END), str(_SCRIPTS), str(_INGESTION)):
    if _path not in sys.path:
        sys.path.insert(0, _path)
