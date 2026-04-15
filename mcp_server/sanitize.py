"""Sanitize annotator-sourced text to prevent prompt injection.

All text from annotator responses that flows back through MCP tools
must be sanitized before being returned to Claude's context.
"""

import re

MAX_RESPONSE_LENGTH = 500

_TAG_RE = re.compile(r"<[^>]*>")


def sanitize_text(text: str) -> str:
    """Sanitize a single text string from annotator data."""
    if not isinstance(text, str):
        return str(text)

    text = _TAG_RE.sub("", text)

    if len(text) > MAX_RESPONSE_LENGTH:
        text = text[:MAX_RESPONSE_LENGTH] + "..."

    return text.strip()


def _sanitize_value(value, _depth=0):
    """Recursively sanitize strings in dicts, lists, and plain values."""
    if _depth > 10:
        return sanitize_text(str(value))
    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, dict):
        return {k: _sanitize_value(v, _depth + 1) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(item, _depth + 1) for item in value]
    return value


def sanitize_results(results: list[dict]) -> list[dict]:
    """Sanitize a list of result dicts from the job results endpoint."""
    return [_sanitize_value(result) for result in results]
