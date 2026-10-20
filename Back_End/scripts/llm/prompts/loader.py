"""Load and render prompt templates from the prompts/ folder."""
from __future__ import annotations

import json
import re
from pathlib import Path

_PLACEHOLDER = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")

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


def fill_placeholders(template: str, **kwargs: str) -> str:
    """Replace known {placeholders}. Inserted values are literal, including braces."""
    def repl(match: re.Match) -> str:
        key = match.group(1)
        if key not in kwargs:
            raise KeyError(f"Prompt placeholder {{{key}}} has no value")
        return str(kwargs[key])

    return _PLACEHOLDER.sub(repl, template)


def render_template(name: str, **kwargs: str) -> str:
    """Load template and substitute {placeholders}."""
    return fill_placeholders(load_template(name), **kwargs)


def render_fragment(name: str, **kwargs: str) -> str:
    """Load fragment and substitute {placeholders}."""
    return fill_placeholders(load_fragment(name), **kwargs)


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
    return "\n\n".join(lines) if lines else (
        "  No style samples for this unit. Follow the job description, BSC, LOS, and the work plan only."
    )


def format_samples_for_step2(samples: list, limit: int = 4) -> str:
    """Step 2 style reference — measure and target from the matched unit only."""
    lines = []
    for i, s in enumerate(samples[:limit], 1):
        lines.append(
            f"  {i}. {s.get('objective', '')}\n"
            f"     measure: {s.get('measure', '')} | target: {s.get('target', '')}"
        )
    return "\n\n".join(lines) if lines else (
        "  No style samples for this unit. Follow the job description, BSC, LOS, and the work plan only."
    )


def step1_json_example(num_drafts: int) -> str:
    example = {
        "drafts": [
            {
                "draft_id": f"draft_{i + 1}",
                "objective": "SMART objective statement",
                "bsc_kpi": "Exact KPI from BSC context, or N/A when none measures this task",
                "bsc_strategic_objective": "Strategic objective from BSC context, or N/A",
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
    include_critical: bool = True,
) -> str:
    sample_non_critical = min(20, remaining_weight) if remaining_weight > 0 else 10
    draft = {
        "draft_id": "draft_1",
        "objective": "...",
        "measure": "Percentage",
        "target": "As per the source document",
        "weight_percent": sample_non_critical if include_critical else remaining_weight,
        "category": "Can Exceed",
        "tracking_source": "System",
        "time_frame": "Quarterly",
        "bsc_kpi": "...",
        "bsc_strategic_objective": "...",
        "los_alignment": "...",
        "source": "LLM",
    }
    if not include_critical:
        return json.dumps({"objectives": [draft], "weight_sum_check": 100}, indent=2)
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
            draft,
        ],
        "weight_sum_check": 100,
    }, indent=2)


def step3_json_example(
    critical_weight: int,
    remaining_weight: int,
    supervisor_target: str = "Manager's",
    include_critical: bool = True,
) -> str:
    if not include_critical:
        return json.dumps({
            "objectives": [
                {
                    "objective": "...",
                    "measure": "Percentage",
                    "target": "As per the source document",
                    "weight_percent": remaining_weight,
                    "category": "Can Exceed",
                    "tracking_source": "System",
                    "time_frame": "Quarterly",
                    "bsc_kpi": "...",
                    "bsc_strategic_objective": "...",
                    "los_alignment": "N/A",
                    "source": "LLM",
                    "appraisal_logic": {
                        "rating_5": "Exceptional — Exceeds 150% of plan",
                        "rating_4": "Above Expectations — Achieves 125–149.9% of plan",
                        "rating_3": "Meets Expectations — Achieves 100–124.9% of plan",
                        "rating_2": "Below Expectations — Achieves 65–99.9% of plan",
                        "rating_1": "Unsatisfactory — Achieves less than 65% of plan",
                    },
                }
            ],
            "total_weight": 100,
        }, indent=2)
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
