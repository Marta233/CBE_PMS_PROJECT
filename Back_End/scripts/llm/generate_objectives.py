"""
generate_objectives.py — runs the 3-step modular LLM pipeline.

  Step 1: draft objective text + BSC/LOS
  Step 2: weights, measures, targets, categories (model-generated)
  Step 3: appraisal_logic (model-generated)
"""

import json
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from config import GENERATED_OBJECTIVES_PATH, RETRIEVED_CONTEXT_PATH
from llm.pipeline import generate_objectives as run_pipeline


def generate(num_objectives: int = 5):
    if not RETRIEVED_CONTEXT_PATH.exists():
        raise FileNotFoundError(
            f"\nContext file not found: {RETRIEVED_CONTEXT_PATH}"
            f"\nRun first: python scripts/embedding/process_embeddings.py"
        )

    with open(RETRIEVED_CONTEXT_PATH, "r", encoding="utf-8") as f:
        context = json.load(f)

    print("\nContext loaded")
    print(f"   JD  : {len(context.get('jd_context', ''))} chars")
    print(f"   BSC : {len(context.get('bsc_context', ''))} chars")
    print(f"   LOS : {len(context.get('los_context', ''))} chars")

    print(f"\nRunning 3-step pipeline ({num_objectives} objectives incl. critical target)...")
    final_output = run_pipeline(context, num_objectives)

    meta = final_output.get("pipeline_meta", {})
    print(f"   Steps: {meta.get('steps_run', [])}")
    for w in meta.get("warnings", []):
        print(f"   WARNING: {w}")

    all_objectives = final_output["objectives"]
    total_weight = final_output["total_weight"]

    GENERATED_OBJECTIVES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(GENERATED_OBJECTIVES_PATH, "w", encoding="utf-8") as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 65)
    print("GENERATED OBJECTIVES")
    print("=" * 65)
    for i, obj in enumerate(all_objectives, 1):
        tag = "CRITICAL" if obj.get("category") == "Major Critical" else f"   [{i}]"
        print(f"\n{tag}  {obj.get('objective', '')}")
        print(f"         Measure  : {obj.get('measure', '')}  |  Target: {obj.get('target', '')}")
        print(f"         Weight   : {obj.get('weight_percent', '')}%  |  {obj.get('category', '')}")
        if obj.get("appraisal_logic"):
            print(f"         Appraisal: {obj['appraisal_logic'].get('rating_5', '')[:70]}...")

    print(f"\n{'=' * 65}")
    print(f"Total Weight: {total_weight}%")
    print(f"Saved: {GENERATED_OBJECTIVES_PATH}")
    return final_output


if __name__ == "__main__":
    generate(5)
