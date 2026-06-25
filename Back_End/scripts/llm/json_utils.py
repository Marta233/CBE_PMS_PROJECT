"""Extract and parse JSON objects from LLM text responses."""
from __future__ import annotations

import json
import re


def parse_llm_json(raw: str) -> dict:
    """
    Parse the first JSON object from an LLM response.

    Handles markdown fences, leading prose (e.g. "Here are the objectives:"),
    and trailing commentary after the JSON block.
    """
    text = raw.strip()
    if not text:
        raise json.JSONDecodeError("Empty LLM response", raw, 0)

    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()

    brace = text.find("{")
    if brace == -1:
        raise json.JSONDecodeError("No JSON object found in LLM response", text, 0)
    if brace > 0:
        text = text[brace:]

    obj, _ = json.JSONDecoder().raw_decode(text)
    if not isinstance(obj, dict):
        raise json.JSONDecodeError("Expected a JSON object", text, 0)
    return obj


def build_repair_prompt(raw_response: str, schema_example: str) -> tuple[str, str]:
    """Return (system, user) messages for a JSON repair attempt."""
    system = (
        "You repair malformed JSON from another model. "
        "Return ONLY a single valid JSON object — no markdown, no commentary."
    )
    user = (
        "The response below is invalid or incomplete JSON. "
        "Fix it to match the expected schema exactly.\n\n"
        f"MALFORMED RESPONSE:\n{raw_response}\n\n"
        f"EXPECTED SCHEMA EXAMPLE:\n{schema_example}"
    )
    return system, user
