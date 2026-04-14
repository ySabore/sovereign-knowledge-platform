"""
Nango integration (Layer 6) — proxy requests to third-party APIs using Nango-managed OAuth.

Docs: https://nango.dev/docs/reference/api/proxy/get
All upstream paths are sent to: `{NANGO_HOST}/proxy{path}` with headers:
  Authorization: Bearer {NANGO_SECRET_KEY}
  Connection-Id: {connection_id}
  Provider-Config-Key: {provider_config_key}
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from app.config import settings
from app.services.text_cleaner import clean_text_for_ingestion

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class DocumentFetchResult:
    external_id: str
    name: str
    content: str
    url: str
    last_modified: datetime | None
    metadata: dict[str, Any]
    permissions: list[str] | None = None


def nango_configured() -> bool:
    return bool((settings.nango_secret_key or "").strip())


def canonical_connector_type(connector_type: str) -> str:
    """Map UI/seed aliases to internal fetch keys (must match branch labels below)."""
    ct = connector_type.strip().lower()
    aliases: dict[str, str] = {
        "gdrive": "google-drive",
        "googledrive": "google-drive",
    }
    return aliases.get(ct, ct)


def nango_provider_config_key(connector_type: str) -> str:
    """
    Value for Nango's Provider-Config-Key header — must match the integration id in Nango
    (Dashboard → Integrations). Pre-built Google Drive uses `google-drive`.
    """
    c = canonical_connector_type(connector_type)
    if c == "google-drive":
        return "google-drive"
    return c


def normalize_connector_type_for_storage(integration_id: str) -> str:
    """Persist canonical connector_type so sync + Nango keys stay aligned."""
    return canonical_connector_type(integration_id)


def _proxy_url(upstream_path: str) -> str:
    path = upstream_path if upstream_path.startswith("/") else f"/{upstream_path}"
    return f"{settings.nango_host.rstrip('/')}/proxy{path}"


def nango_proxy_request(
    method: str,
    *,
    connection_id: str,
    provider_config_key: str,
    upstream_path: str,
    params: dict[str, Any] | None = None,
    json_body: Any | None = None,
    extra_headers: dict[str, str] | None = None,
) -> httpx.Response:
    """Low-level Nango proxy call. `upstream_path` must start with `/` (e.g. `/wiki/rest/api/content`)."""
    if not nango_configured():
        raise RuntimeError("NANGO_SECRET_KEY is not set")
    url = _proxy_url(upstream_path)
    headers = {
        "Authorization": f"Bearer {settings.nango_secret_key.strip()}",
        "Connection-Id": connection_id.strip(),
        "Provider-Config-Key": provider_config_key.strip(),
    }
    if extra_headers:
        headers.update(extra_headers)
    timeout = settings.ollama_http_timeout_seconds
    with httpx.Client(timeout=timeout) as client:
        return client.request(method.upper(), url, params=params, json=json_body, headers=headers)


def nango_proxy_get_json(
    *,
    connection_id: str,
    provider_config_key: str,
    upstream_path: str,
    params: dict[str, Any] | None = None,
) -> Any:
    r = nango_proxy_request(
        "GET",
        connection_id=connection_id,
        provider_config_key=provider_config_key,
        upstream_path=upstream_path,
        params=params,
    )
    r.raise_for_status()
    return r.json()


def get_connect_ui_instructions(integration_id: str, connection_id: str) -> dict[str, str]:
    """
    Nango OAuth is normally started from the browser via `@nangohq/frontend`.
    Return a stable hint for API clients; the SPA should call `nango.auth()` / Connect UI.
    """
    return {
        "integration_id": integration_id,
        "connection_id": connection_id,
        "detail": "Open the Nango Connect UI from the frontend SDK; the API stores connection_id after OAuth.",
    }


def _parse_iso_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def fetch_documents(
    connector_type: str,
    connection_id: str,
    *,
    provider_config_key: str | None = None,
    cursor: str | None = None,
    connector_config: dict[str, Any] | None = None,
) -> tuple[list[DocumentFetchResult], str | None]:
    """
    Fetch remote documents through Nango. Provider-specific parsing; returns (results, next_cursor).

    `provider_config_key` defaults to `connector_type` (Nango unique integration key).
    """
    cfg = connector_config or {}
    ct = canonical_connector_type(connector_type)
    pkey = (provider_config_key or nango_provider_config_key(connector_type)).strip()

    if not nango_configured():
        logger.warning("NANGO_SECRET_KEY missing; fetch_documents returns empty")
        return [], None

    if ct == "confluence":
        return _fetch_confluence(connection_id, pkey, cursor, cfg)
    if ct == "google-drive":
        return _fetch_google_drive(connection_id, pkey, cursor, cfg)
    if ct == "notion":
        return _fetch_notion(connection_id, pkey, cursor, cfg)
    if ct == "github":
        return _fetch_github(connection_id, pkey, cursor, cfg)
    if ct == "jira":
        return _fetch_jira(connection_id, pkey, cursor, cfg)

    logger.warning("fetch_documents: unsupported connector_type=%s", ct)
    return [], None


def _fetch_confluence(
    connection_id: str,
    provider_config_key: str,
    cursor: str | None,
    cfg: dict[str, Any],
) -> tuple[list[DocumentFetchResult], str | None]:
    params: dict[str, Any] = {
        "type": "page",
        "expand": "body.storage,version",
        "limit": cfg.get("page_size", 25),
    }
    if cursor:
        params["start"] = int(cursor)
    data = nango_proxy_get_json(
        connection_id=connection_id,
        provider_config_key=provider_config_key,
        upstream_path="/wiki/rest/api/content",
        params=params,
    )
    results: list[DocumentFetchResult] = []
    for item in data.get("results") or []:
        body = (item.get("body") or {}).get("storage") or {}
        html = body.get("value") or ""
        text = clean_text_for_ingestion(html, strip_html=True)
        if not text:
            continue
        vid = item.get("id") or ""
        title = item.get("title") or "untitled"
        link = ""
        links = item.get("_links") or {}
        webui = links.get("webui") or ""
        base = cfg.get("site_base_url") or ""
        if base and webui:
            link = base.rstrip("/") + "/wiki" + webui if not webui.startswith("http") else webui
        ver = item.get("version") or {}
        when = _parse_iso_dt(ver.get("when"))
        results.append(
            DocumentFetchResult(
                external_id=str(vid),
                name=str(title)[:500],
                content=text,
                url=link or str(vid),
                last_modified=when,
                metadata={"confluence": item},
            )
        )
    next_cursor: str | None = None
    links = data.get("_links") or {}
    if links.get("next") and data.get("size"):
        start = int(cursor or 0) + int(data.get("size") or 0)
        next_cursor = str(start)
    return results, next_cursor


def _fetch_google_drive(
    connection_id: str,
    provider_config_key: str,
    cursor: str | None,
    cfg: dict[str, Any],
) -> tuple[list[DocumentFetchResult], str | None]:
    q = "mimeType contains 'application/vnd.google-apps.document' or mimeType contains 'text/plain'"
    params: dict[str, Any] = {"q": q, "pageSize": 10, "fields": "files(id,name,mimeType,modifiedTime,webViewLink),nextPageToken"}
    if cursor:
        params["pageToken"] = cursor
    data = nango_proxy_get_json(
        connection_id=connection_id,
        provider_config_key=provider_config_key,
        upstream_path="/drive/v3/files",
        params=params,
    )
    out: list[DocumentFetchResult] = []
    for f in data.get("files") or []:
        fid = f.get("id")
        if not fid:
            continue
        r = nango_proxy_request(
            "GET",
            connection_id=connection_id,
            provider_config_key=provider_config_key,
            upstream_path=f"/drive/v3/files/{fid}/export",
            params={"mimeType": "text/plain"},
        )
        r.raise_for_status()
        text = clean_text_for_ingestion(r.text, strip_html=False)
        out.append(
            DocumentFetchResult(
                external_id=str(fid),
                name=str(f.get("name") or fid)[:500],
                content=text,
                url=str(f.get("webViewLink") or fid),
                last_modified=_parse_iso_dt(f.get("modifiedTime")),
                metadata={"drive": f},
            )
        )
    return out, data.get("nextPageToken")


def _fetch_notion(
    connection_id: str,
    provider_config_key: str,
    cursor: str | None,
    cfg: dict[str, Any],
) -> tuple[list[DocumentFetchResult], str | None]:
    payload = {"page_size": cfg.get("page_size", 10)}
    if cursor:
        payload["start_cursor"] = cursor
    r = nango_proxy_request(
        "POST",
        connection_id=connection_id,
        provider_config_key=provider_config_key,
        upstream_path="/v1/search",
        json_body=payload,
        extra_headers={"Notion-Version": "2022-06-28"},
    )
    r.raise_for_status()
    data = r.json()
    out: list[DocumentFetchResult] = []
    for item in data.get("results") or []:
        if item.get("object") != "page":
            continue
        pid = item.get("id") or ""
        title = "untitled"
        for t in (item.get("properties") or {}).values():
            if isinstance(t, dict) and t.get("title"):
                title = "".join(x.get("plain_text", "") for x in t.get("title") or []) or title
                break
        out.append(
            DocumentFetchResult(
                external_id=str(pid),
                name=title[:500],
                content=clean_text_for_ingestion(str(item), strip_html=False)[:50_000],
                url=item.get("url") or pid,
                last_modified=None,
                metadata={"notion": item},
            )
        )
    return out, data.get("next_cursor")


def _fetch_github(
    connection_id: str,
    provider_config_key: str,
    cursor: str | None,
    cfg: dict[str, Any],
) -> tuple[list[DocumentFetchResult], str | None]:
    owner = cfg.get("owner") or ""
    repo = cfg.get("repo") or ""
    branch = cfg.get("branch") or "main"
    if not owner or not repo:
        logger.warning("github connector requires config.owner and config.repo")
        return [], None
    path = f"/repos/{owner}/{repo}/git/trees/{branch}"
    params = {"recursive": "1"} if not cursor else {}
    data = nango_proxy_get_json(
        connection_id=connection_id,
        provider_config_key=provider_config_key,
        upstream_path=path,
        params=params,
    )
    out: list[DocumentFetchResult] = []
    max_files = int(cfg.get("max_files", 15))
    for item in data.get("tree") or []:
        if len(out) >= max_files:
            break
        p = item.get("path") or ""
        if not p.endswith((".md", ".mdx", ".txt", ".rst")):
            continue
        if item.get("type") != "blob":
            continue
        raw = nango_proxy_get_json(
            connection_id=connection_id,
            provider_config_key=provider_config_key,
            upstream_path=f"/repos/{owner}/{repo}/contents/{p}",
            params={"ref": branch},
        )
        content = ""
        if isinstance(raw, dict) and raw.get("encoding") == "base64" and raw.get("content"):
            content = base64.b64decode(raw["content"]).decode("utf-8", errors="replace")
        text = clean_text_for_ingestion(content, strip_html=False)
        out.append(
            DocumentFetchResult(
                external_id=item.get("sha") or p,
                name=p.split("/")[-1][:500],
                content=text,
                url=raw.get("html_url") if isinstance(raw, dict) else p,
                last_modified=None,
                metadata={"github": {"path": p}},
            )
        )
    return out, None


def _fetch_jira(
    connection_id: str,
    provider_config_key: str,
    cursor: str | None,
    cfg: dict[str, Any],
) -> tuple[list[DocumentFetchResult], str | None]:
    project = cfg.get("jira_project") or cfg.get("project")
    jql = f'project = "{project}"' if project else "order by updated DESC"
    params: dict[str, Any] = {
        "jql": jql,
        "maxResults": 20,
        "fields": "summary,description,comment,updated",
    }
    if cursor:
        params["startAt"] = int(cursor)
    data = nango_proxy_get_json(
        connection_id=connection_id,
        provider_config_key=provider_config_key,
        upstream_path="/rest/api/3/search",
        params=params,
    )
    out: list[DocumentFetchResult] = []
    for issue in data.get("issues") or []:
        key = issue.get("key") or ""
        fields = issue.get("fields") or {}
        summary = fields.get("summary") or ""
        desc = fields.get("description")
        desc_text = ""
        if isinstance(desc, str):
            desc_text = desc
        elif isinstance(desc, dict):
            desc_text = str(desc)
        comments = fields.get("comment") or {}
        ctext = ""
        for c in comments.get("comments") or []:
            ctext += (c.get("body") or "") + "\n"
        text = clean_text_for_ingestion(f"{summary}\n\n{desc_text}\n\n{ctext}", strip_html=True)
        out.append(
            DocumentFetchResult(
                external_id=key,
                name=summary[:500] or key,
                content=text,
                url=key,
                last_modified=_parse_iso_dt(fields.get("updated")),
                metadata={"jira": issue},
            )
        )
    next_cursor: str | None = None
    total = int(data.get("startAt") or 0) + len(data.get("issues") or [])
    if data.get("total") is not None and total < int(data["total"]):
        next_cursor = str(total)
    return out, next_cursor


def get_permissions(
    connector_type: str,
    connection_id: str,
    document_external_id: str,
    *,
    provider_config_key: str | None = None,
    connector_config: dict[str, Any] | None = None,
) -> list[str]:
    """
    Return upstream user identifiers or emails that may read this document.
    Provider-specific; many APIs require extra scopes — stub returns [] until wired.
    """
    _ = (connector_type, connection_id, document_external_id, provider_config_key, connector_config)
    logger.info("get_permissions: not fully implemented for this provider; return []")
    return []
