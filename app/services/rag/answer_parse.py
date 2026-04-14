"""Parse model output: confidence tags (spec Layer 3.2), rough token estimates."""

from __future__ import annotations

import re

# Trailing tag only (display text should not retain the tag).
_CONFIDENCE_TAIL = re.compile(
    r"\s*<confidence>\s*(high|medium|low)\s*</confidence>\s*$",
    re.IGNORECASE | re.DOTALL,
)


def estimate_tokens(text: str) -> int:
    """Rough token budget: ~4 characters per token (common heuristic)."""
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def extract_confidence_tag(text: str) -> tuple[str, str | None]:
    """
    If the model ended with <confidence>high|medium|low</confidence>, strip it and return the label.
    Otherwise return (text stripped, None).
    """
    raw = text.strip()
    m = _CONFIDENCE_TAIL.search(raw)
    if not m:
        return raw, None
    display = raw[: m.start()].strip()
    return display, m.group(1).lower()
