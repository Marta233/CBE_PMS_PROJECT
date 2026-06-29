"""Sanitize untrusted text before embedding in LLM prompts."""
from __future__ import annotations

import re

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_EXCESS_NEWLINES = re.compile(r"\n{4,}")


def sanitize_user_field(value: str) -> str:
    """Sanitize a single user-supplied form field (single-line)."""
    if not value:
        return ""
    text = _CONTROL_CHARS.sub("", str(value))
    return " ".join(text.split()).strip()


def sanitize_context_text(value: str) -> str:
    """Sanitize retrieved document context (multi-line)."""
    if not value:
        return ""
    text = _CONTROL_CHARS.sub("", str(value))
    text = _EXCESS_NEWLINES.sub("\n\n\n", text)
    return text.strip()


def _escape_context_tags(text: str, tag: str) -> str:
    """Prevent untrusted content from closing an XML-style wrapper early."""
    pattern = re.compile(
        rf"</?{re.escape(tag)}>",
        flags=re.IGNORECASE,
    )
    return pattern.sub(lambda m: m.group(0).replace("<", "[").replace(">", "]"), text)


def wrap_context_block(tag: str, content: str, *, fallback: str = "") -> str:
    """Wrap retrieved or user context in explicit delimiters for the model."""
    text = sanitize_context_text(content) or fallback
    text = _escape_context_tags(text, tag)
    return f"<{tag}>\n{text}\n</{tag}>"
