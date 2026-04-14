"""Normalize text for ingestion: HTML stripping, whitespace, light boilerplate removal."""

from __future__ import annotations

import re
from html.parser import HTMLParser

_HTML_TAG_RE = re.compile(r"<[^>]+>", re.DOTALL)
_MULTI_SPACE = re.compile(r"[ \t\r\f\v]+")
_BOILERPLATE_LINES = re.compile(
    r"^(cookie|privacy policy|terms of service|subscribe to our newsletter)\s*:?\s*$",
    re.IGNORECASE,
)


class _HTMLToText(HTMLParser):
    """Minimal HTML → text (no extra dependency)."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data:
            self._parts.append(data)

    def get_text(self) -> str:
        return "".join(self._parts)


def strip_html_tags(value: str) -> str:
    if not value or "<" not in value:
        return value
    parser = _HTMLToText()
    try:
        parser.feed(value)
        parser.close()
        out = parser.get_text()
    except Exception:
        out = _HTML_TAG_RE.sub(" ", value)
    return out


def normalize_whitespace(value: str) -> str:
    if not value:
        return ""
    lines = []
    for line in value.splitlines():
        line = _MULTI_SPACE.sub(" ", line).strip()
        if _BOILERPLATE_LINES.match(line):
            continue
        lines.append(line)
    text = "\n".join(lines)
    return _MULTI_SPACE.sub(" ", text).strip()


def clean_text_for_ingestion(value: str, *, strip_html: bool = True) -> str:
    """Strip HTML (if present), collapse whitespace, drop obvious boilerplate lines."""
    raw = value or ""
    if strip_html and ("<" in raw and ">" in raw):
        raw = strip_html_tags(raw)
    return normalize_whitespace(raw)
