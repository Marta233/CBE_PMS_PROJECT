import json
from pathlib import Path
def load_samples():
    sample_path = Path("Data/sample/sample_objectives.json")

    with open(sample_path, "r", encoding="utf-8") as f:
        samples = json.load(f)

    return "\n".join(
        [f"{i+1}. {s['objective']}" for i, s in enumerate(samples)]
    )
def build_prompt(context: dict, num_objectives: int) -> str:
    samples = load_samples()

    return f"""
You are an AI-powered PMS assistant.

Generate {num_objectives} SMART objectives.

USER PROFILE:
{context['query']}

JOB DESCRIPTION:
{context['jd_context']}

BSC:
{context['bsc_context']}

LOS:
{context['los_context']}

SAMPLE OBJECTIVES:
{samples}
RULES:
1. Align to job role.
2. Align to BSC.
3. Align to LOS.
4. Follow SMART principle.
5. Include KPI.
6. Include measurement.
7. Return JSON only.
"""