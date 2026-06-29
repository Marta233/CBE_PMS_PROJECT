"""Load and render prompt templates from the prompts/ folder."""
from __future__ import annotations

import json
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent
FRAGMENTS_DIR = PROMPTS_DIR / "fragments"


def load_template(name: str) -> str:
    """Load a .txt template (supports nested paths like 'fragments/step2_rules')."""
    path = PROMPTS_DIR / f"{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    return path.read_text(encoding="utf-8")


def load_fragment(name: str) -> str:
    """Load a rules fragment from prompts/fragments/."""
    path = FRAGMENTS_DIR / f"{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt fragment not found: {path}")
    return path.read_text(encoding="utf-8")


def render_template(name: str, **kwargs: str) -> str:
    """Load template and substitute {placeholders}."""
    return load_template(name).format(**kwargs)


def render_fragment(name: str, **kwargs: str) -> str:
    """Load fragment and substitute {placeholders}."""
    return load_fragment(name).format(**kwargs)


def format_samples_for_step1(samples: list) -> str:
    """Step 1 style reference — objective text only, no Step 2 metric fields."""
    lines = []
    for i, s in enumerate(samples, 1):
        parts = [f"  {i}. {s.get('objective', '')}"]
        if s.get("kpi") or s.get("bsc_pillar"):
            parts.append(
                f"     BSC pillar: {s.get('bsc_pillar', '')} | KPI: {s.get('kpi', '')}"
            )
        if s.get("source"):
            parts.append(f"     ({s['source']})")
        lines.append("\n".join(parts))
    return "\n\n".join(lines) if lines else "  (none available)"


def step1_json_example(num_drafts: int) -> str:
    example = {
        "drafts": [
            {
                "draft_id": f"draft_{i + 1}",
                "objective": "SMART objective statement",
                "bsc_kpi": "Exact KPI from BSC context",
                "bsc_strategic_objective": "Strategic objective from BSC context",
                "los_alignment": "One sentence or N/A",
            }
            for i in range(min(2, num_drafts))
        ]
    }
    return json.dumps(example, indent=2)


def step2_json_example(
    critical_weight: int,
    remaining_weight: int,
    supervisor_target: str = "Manager's",
) -> str:
    sample_non_critical = min(20, remaining_weight) if remaining_weight > 0 else 10
    return json.dumps({
        "objectives": [
            {
                "draft_id": "critical",
                "objective": "Achieve team critical target",
                "measure": "Various",
                "target": f"{critical_weight}% of {supervisor_target} target",
                "weight_percent": critical_weight,
                "category": "Major Critical",
                "tracking_source": "System",
                "time_frame": "Quarterly",
                "bsc_kpi": "Team Critical Target",
                "bsc_strategic_objective": "...",
                "los_alignment": "N/A",
                "source": "Fixed",
            },
            {
                "draft_id": "draft_1",
                "objective": "...",
                "measure": "Percentage",
                "target": "As per quarterly action plan of 100%",
                "weight_percent": sample_non_critical,
                "category": "Can Exceed",
                "tracking_source": "System",
                "time_frame": "Quarterly",
                "bsc_kpi": "...",
                "bsc_strategic_objective": "...",
                "los_alignment": "...",
                "source": "LLM",
            },
        ],
        "weight_sum_check": 100,
    }, indent=2)


def step3_json_example(
    critical_weight: int,
    remaining_weight: int,
    supervisor_target: str = "Manager's",
) -> str:
    return json.dumps({
        "objectives": [
            {
                "objective": "Achieve team critical target",
                "measure": "Various",
                "target": f"{critical_weight}% of {supervisor_target} target",
                "weight_percent": critical_weight,
                "category": "Major Critical",
                "tracking_source": "System",
                "time_frame": "Quarterly",
                "bsc_kpi": "...",
                "bsc_strategic_objective": "...",
                "los_alignment": "N/A",
                "source": "Fixed",
                "appraisal_logic": {
                    "rating_5": "Meets Expectations — Achieves 100% or more",
                    "rating_4": "Nearly Meets — Achieves 90–99.9%",
                    "rating_3": "Partially Meets — Achieves 80–89.9%",
                    "rating_2": "Minimally Meets — Achieves 66–79.9%",
                    "rating_1": "Unsatisfactory — Achieves less than 65%",
                },
            }
        ],
        "total_weight": 100,
    }, indent=2)


def to_json(data: object) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)
