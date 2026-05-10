"""Sanitize annotator-sourced text to prevent prompt injection.

All text from annotator responses that flows back through MCP tools
must be sanitized before being returned to the agent's context.

The sanitizer applies, in order:
  - Unicode NFKC normalization to fold lookalike codepoints to a canonical form
    (e.g. fullwidth digits and Cyrillic homoglyphs).
  - Stripping of zero-width characters and bidi/RTL override codepoints
    commonly used to hide text or visually spoof content.
  - Stripping of C0/C1 control characters except tab and newline.
  - Removal of XML/HTML-like tags so script-style payloads don't ride along.
  - Defanging of Markdown link / image syntax so URLs are not auto-clickable
    when the agent renders annotator text to a human.
  - Truncation to a fixed cap so a runaway response cannot crowd the context.
"""

import re
import unicodedata

MAX_RESPONSE_LENGTH = 500

_TAG_RE = re.compile(r"<[^>]*>")
# Zero-width spaces, bidi/RTL overrides, BOM, and other invisible formatters.
_INVISIBLE_RE = re.compile(
    "[​-‏‪-‮⁠-⁤﻿]"
)
# C0 controls except tab (\x09) and newline (\x0a); plus C1 controls (\x80-\x9f).
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


def sanitize_text(text: str) -> str:
    """Sanitize a single text string from annotator data."""
    if not isinstance(text, str):
        return str(text)

    text = unicodedata.normalize("NFKC", text)
    text = _INVISIBLE_RE.sub("", text)
    text = _CONTROL_RE.sub("", text)
    text = _TAG_RE.sub("", text)
    # Defang Markdown links / images (including nested-bracket variants) by
    # escaping the `(` that follows `]`, so URLs aren't auto-clickable when
    # the agent renders annotator text to a human.
    text = text.replace("](", "]\\(")

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


def sanitize_responses(responses: list[dict]) -> list[dict]:
    """Sanitize a list of raw response dicts from the job responses endpoint."""
    return [_sanitize_value(response) for response in responses]
