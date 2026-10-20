import json, sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import KNOWLEDGE_BASE_FILE

kb = json.loads(KNOWLEDGE_BASE_FILE.read_text(encoding="utf-8"))
print("total:", len(kb))
print(Counter(d["metadata"].get("source") for d in kb))
print("JD divisions :", Counter(d["metadata"].get("division") for d in kb if d["metadata"].get("source") == "JD").most_common(5))
print("LOS divisions:", Counter(d["metadata"].get("division") for d in kb if d["metadata"].get("source") == "LOS").most_common(5))
print("WP:", Counter((d["metadata"].get("department"), d["metadata"].get("unit")) for d in kb if d["metadata"].get("source") == "WorkPlan"))