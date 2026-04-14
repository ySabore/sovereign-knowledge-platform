"""Lightweight query tweaks so retrieval matches indexed policy wording."""

from __future__ import annotations

import re


def normalize_for_retrieval(query: str) -> str:
    """
    Align colloquial product language with document text.

    Users often say "General chat" when they mean the Chats experience inside the General
    workspace; demo PDFs and policies say "General workspace".
    """
    q = query.strip()
    if not q:
        return q
    q = re.sub(r"\bgeneral\s+chat\b", "General workspace", q, flags=re.IGNORECASE)
    return q
