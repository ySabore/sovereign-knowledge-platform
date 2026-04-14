"""Detect low-intent greetings / thanks so we skip RAG and answer conversationally."""

from __future__ import annotations

import re

CHITCHAT_REPLY = (
    "Hi — I’m here to answer questions using your workspace documents. "
    "Ask me anything about policies, procedures, or what’s in your indexed files."
)

_MAX_LEN_RAW = 56
_MAX_LEN_NORMALIZED = 48

_NON_WORD = re.compile(r"[^\w\s]+", re.UNICODE)
_WS = re.compile(r"\s+")

# Whole-message patterns after normalization (lowercase, punctuation → spaces).
_CHITCHAT = re.compile(
    r"""
    ^(
      (hi|hello|hey|howdy|hiya|yo|sup)(\s+(there|all|everyone|team|folks|guys))?
    | (good\s+(morning|afternoon|evening|night))(\s+(there|all|everyone|team|folks|guys))?
    | g\s*day
    | how\s+are\s+you
    | what(?:'s|s)\s+up
    | whats\s+up
    | thanks?(\s+you)?
    | thank\s+you
    | thx
    | ty
    | ok(?:ay)?
    | cheers
    | bye+
    | goodbye
    | ciao
    | (morning|afternoon|evening)(\s+(all|everyone))?
    )$
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _normalize(query: str) -> str:
    q = query.strip().lower()
    q = _NON_WORD.sub(" ", q)
    return _WS.sub(" ", q).strip()


def is_low_intent_chitchat(query: str) -> bool:
    """True when the user message is only a short greeting/thanks/etc. — not a document question."""
    q = query.strip()
    if not q or "\n" in q or "\r" in q:
        return False
    if len(q) > _MAX_LEN_RAW:
        return False
    if any(ch.isdigit() for ch in q):
        return False
    n = _normalize(q)
    if not n or len(n) > _MAX_LEN_NORMALIZED:
        return False
    return bool(_CHITCHAT.match(n))
