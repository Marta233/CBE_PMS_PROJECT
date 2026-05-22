"""
generate_objectives.py
Generates SMART performance objectives using retrieved context + LLM.

Flow:
  1. Load retrieved_context.json
  2. Build prompt (LLM generates num_objectives - 1 objectives, weight sum = 50)
  3. Prepend the fixed "Achieve team critical target" objective (weight=50, Cannot Exceed)
     loaded directly from sample_objectives.json — identical to the CBE PMS document
  4. Validate total weight == 100
  5. Save to generated_objectives.json
"""

from pathlib import Path
import json
import ollama

from .prompt_builder import build_prompt, load_critical_target

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def generate(num_objectives: int = 5):

    # ── 1. Load retrieved context ──────────────────────────────────────────
    context_path = BASE_DIR / "Data" / "processed" / "retrieved_context.json"

    if not context_path.exists():
        raise FileNotFoundError(
            f"\n❌ Context file not found: {context_path}"
            f"\n👉 Run first: python -m Back_End.scripts.embedding.process_embeddings"
        )

    with open(context_path, "r", encoding="utf-8") as f:
        context = json.load(f)

    print(f"\n✅ Context loaded")
    print(f"   JD  : {len(context.get('jd_context', ''))} chars")
    print(f"   BSC : {len(context.get('bsc_context', ''))} chars")
    print(f"   LOS : {len(context.get('los_context', ''))} chars")

    # ── 2. Load the fixed critical target from sample file ─────────────────
    critical_target = load_critical_target()
    print(f"\n📌 Fixed objective loaded: \"{critical_target['objective']}\"")
    print(f"   Weight: {critical_target['weight_percent']}%  |  Category: {critical_target['category']}")

    # ── 3. Build prompt ────────────────────────────────────────────────────
    prompt = build_prompt(context, num_objectives)
    print(f"\n📝 Prompt built ({len(prompt)} chars) — requesting {num_objectives - 1} objectives from LLM...")

    # ── 4. Call LLM ────────────────────────────────────────────────────────
    response = ollama.chat(
        model="llama3.2:1b",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a PMS expert for Commercial Bank of Ethiopia. "
                    "You ONLY output valid JSON. Never add explanations or markdown fences."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        options={
            "temperature": 0.3,
            "top_p": 0.9,
        }
    )

    raw_output = response["message"]["content"]

    # ── 5. Parse and validate LLM response ────────────────────────────────
    try:
        clean = raw_output.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        llm_result = json.loads(clean.strip())
        llm_objectives = llm_result.get("objectives", [])

        llm_weight_sum = sum(o.get("weight_percent", 0) for o in llm_objectives)
        print(f"\n✅ LLM returned {len(llm_objectives)} objectives  (weight sum: {llm_weight_sum}%)")

        if llm_weight_sum != 50:
            print(f"   ⚠️  Expected LLM weights to sum to 50%, got {llm_weight_sum}% — adjusting last item...")
            diff = 50 - llm_weight_sum
            if llm_objectives:
                llm_objectives[-1]["weight_percent"] += diff

    except json.JSONDecodeError as e:
        print(f"\n❌ LLM returned invalid JSON: {e}")
        print("   Raw output:\n", raw_output[:500])
        raise

    # ── 6. Prepend fixed critical target ───────────────────────────────────
    all_objectives = [critical_target] + llm_objectives

    # ── 7. Build final output ──────────────────────────────────────────────
    # Parse employee profile from context query
    profile = {}
    for line in context.get("query", "").splitlines():
        line = line.strip()
        if ":" in line:
            key, val = line.split(":", 1)
            profile[key.strip().lower().replace(" ", "_")] = val.strip()

    total_weight = sum(o.get("weight_percent", 0) for o in all_objectives)

    final_output = {
        "employee_profile": profile,
        "objectives": all_objectives,
        "total_weight": total_weight
    }

    if total_weight != 100:
        print(f"\n⚠️  Total weight is {total_weight}% (expected 100%)")
    else:
        print(f"\n✅ Total weight: {total_weight}%  ✓")

    # ── 8. Save ────────────────────────────────────────────────────────────
    save_path = BASE_DIR / "Data" / "processed" / "generated_objectives.json"
    save_path.parent.mkdir(parents=True, exist_ok=True)

    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)

    # ── 9. Print summary ───────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("GENERATED OBJECTIVES")
    print("=" * 65)
    for i, obj in enumerate(all_objectives, 1):
        tag = "📌 FIXED" if i == 1 else f"   [{i}]"
        print(f"\n{tag}  {obj.get('objective', '')}")
        print(f"         BSC      : {obj.get('bsc_pillar', '')}")
        print(f"         KPI      : {obj.get('kpi', '')}")
        print(f"         Measure  : {obj.get('measure', '')}  |  Target: {obj.get('target', '')}")
        print(f"         Weight   : {obj.get('weight_percent', '')}%  |  {obj.get('category', '')}")
        print(f"         Tracking : {obj.get('tracking_source', '')}  |  {obj.get('time_frame', '')}")

    print(f"\n{'=' * 65}")
    print(f"Total Weight: {total_weight}%")
    print(f"✅ Saved: {save_path}")

    return final_output
if __name__ == "__main__":
    generate(5)