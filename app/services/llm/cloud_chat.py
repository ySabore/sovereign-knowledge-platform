"""OpenAI and Anthropic chat completions for the grounded RAG path (sync HTTP)."""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.config import settings


def complete_openai_chat(*, api_key: str, base_url: str, model: str, user_prompt: str) -> str:
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload: dict[str, Any] = {
        "model": model,
        "temperature": 0.2,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    try:
        response = httpx.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=settings.cloud_llm_http_timeout_seconds,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"OpenAI request failed: {exc}") from exc
    data = response.json()
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("OpenAI returned no choices")
    msg = choices[0].get("message") or {}
    content = (msg.get("content") or "").strip()
    if not content:
        raise RuntimeError("OpenAI returned an empty message")
    return content


def complete_anthropic_chat(*, api_key: str, base_url: str, model: str, user_prompt: str) -> str:
    url = f"{base_url.rstrip('/')}/v1/messages"
    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": min(4096, settings.anthropic_max_output_tokens),
        "messages": [{"role": "user", "content": user_prompt}],
    }
    try:
        response = httpx.post(
            url,
            headers={
                "x-api-key": api_key,
                "anthropic-version": settings.anthropic_api_version,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=settings.cloud_llm_http_timeout_seconds,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        body = ""
        if exc.response is not None:
            try:
                body = exc.response.text[:500]
            except Exception:
                body = ""
        raise RuntimeError(f"Anthropic request failed: {exc} {body}") from exc
    data = response.json()
    blocks = data.get("content") or []
    parts: list[str] = []
    for block in blocks:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text") or "")
    content = "".join(parts).strip()
    if not content:
        raise RuntimeError("Anthropic returned an empty message")
    return content


async def stream_openai_chat_tokens(
    *,
    api_key: str,
    base_url: str,
    model: str,
    user_prompt: str,
) -> Any:
    """Async iterator of text fragments (async generator)."""
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload: dict[str, Any] = {
        "model": model,
        "temperature": 0.2,
        "messages": [{"role": "user", "content": user_prompt}],
        "stream": True,
    }
    async with httpx.AsyncClient(timeout=settings.cloud_llm_http_timeout_seconds) as client:
        async with client.stream(
            "POST",
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data = line[6:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                piece = delta.get("content")
                if piece:
                    yield piece


async def stream_anthropic_chat_tokens(
    *,
    api_key: str,
    base_url: str,
    model: str,
    user_prompt: str,
) -> Any:
    """Async iterator of text fragments (SSE)."""
    url = f"{base_url.rstrip('/')}/v1/messages"
    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": min(4096, settings.anthropic_max_output_tokens),
        "messages": [{"role": "user", "content": user_prompt}],
        "stream": True,
    }
    async with httpx.AsyncClient(timeout=settings.cloud_llm_http_timeout_seconds) as client:
        async with client.stream(
            "POST",
            url,
            headers={
                "x-api-key": api_key,
                "anthropic-version": settings.anthropic_api_version,
                "Content-Type": "application/json",
            },
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                raw = line[6:].strip()
                if not raw:
                    continue
                try:
                    ev = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if ev.get("type") == "content_block_delta":
                    delta = ev.get("delta") or {}
                    if delta.get("type") == "text_delta":
                        t = delta.get("text")
                        if t:
                            yield t
