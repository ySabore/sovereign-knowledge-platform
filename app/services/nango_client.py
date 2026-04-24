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
import json
import logging
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from app.config import settings
from app.services.ingestion import extract_pages_from_upload
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
    try:
        r.raise_for_status()
    except httpx.HTTPStatusError as exc:
        body = (exc.response.text or "").strip().replace("\n", " ")
        body_preview = body[:500] if body else "<no response body>"
        raise RuntimeError(
            f"Nango proxy GET {upstream_path} failed ({exc.response.status_code}): {body_preview}"
        ) from exc
    return r.json()


def create_connect_session(
    *,
    allowed_integrations: list[str],
    tags: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Create a short-lived Nango Connect Session token.
    Docs: POST /connect/sessions
    """
    if not nango_configured():
        raise RuntimeError("NANGO_SECRET_KEY is not set")
    url = f"{settings.nango_host.rstrip('/')}/connect/sessions"
    payload: dict[str, Any] = {
        "allowed_integrations": [x.strip() for x in allowed_integrations if x and x.strip()],
    }
    if tags:
        payload["tags"] = {str(k).lower(): str(v) for k, v in tags.items() if v}
    timeout = settings.ollama_http_timeout_seconds
    with httpx.Client(timeout=timeout) as client:
        r = client.post(
            url,
            headers={
                "Authorization": f"Bearer {settings.nango_secret_key.strip()}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    try:
        r.raise_for_status()
    except httpx.HTTPStatusError as exc:
        body = (exc.response.text or "").strip().replace("\n", " ")
        body_preview = body[:500] if body else "<no response body>"
        raise RuntimeError(
            f"Nango connect session create failed ({exc.response.status_code}): {body_preview}"
        ) from exc
    data = r.json()
    if not isinstance(data, dict):
        raise RuntimeError("Invalid Nango connect session response payload")
    wrapped = data.get("data") if isinstance(data.get("data"), dict) else data
    if not isinstance(wrapped, dict) or not str(wrapped.get("token") or "").strip():
        raise RuntimeError("Nango connect session token missing in response")
    return wrapped


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


_DRIVE_FOLDER_MIME = "application/vnd.google-apps.folder"
_DRIVE_DOC_MIME = "application/vnd.google-apps.document"
_DRIVE_SHEET_MIME = "application/vnd.google-apps.spreadsheet"
_DRIVE_SLIDES_MIME = "application/vnd.google-apps.presentation"
_DRIVE_EXPORT_SPECS: dict[str, tuple[str, str]] = {
    _DRIVE_DOC_MIME: ("text/plain", ".txt"),
    _DRIVE_SHEET_MIME: (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xlsx",
    ),
    _DRIVE_SLIDES_MIME: (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".pptx",
    ),
}
_DRIVE_BINARY_SUPPORTED_MIME: set[str] = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "text/plain",
    "text/csv",
    "text/markdown",
    "text/html",
    "application/rtf",
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/tiff",
}
_DRIVE_CURSOR_PREFIX = "gdv2:"


def sanitize_drive_folder_ids(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for x in raw:
        s = str(x).strip()
        if not s or len(s) > 256:
            continue
        if all(c.isalnum() or c in "_-" for c in s):
            out.append(s)
    return out


def _drive_walk_encode(state: dict[str, Any]) -> str:
    blob = json.dumps(state, separators=(",", ":")).encode()
    return _DRIVE_CURSOR_PREFIX + base64.urlsafe_b64encode(blob).decode().rstrip("=")


def _drive_walk_decode(cursor: str) -> dict[str, Any] | None:
    if not cursor.startswith(_DRIVE_CURSOR_PREFIX):
        return None
    pad = "=" * (-(len(cursor) - len(_DRIVE_CURSOR_PREFIX)) % 4)
    try:
        raw = base64.urlsafe_b64decode((cursor[len(_DRIVE_CURSOR_PREFIX) :] + pad).encode())
        data = json.loads(raw.decode())
        return data if isinstance(data, dict) else None
    except (ValueError, json.JSONDecodeError, OSError):
        return None


def _drive_export_file(
    connection_id: str,
    provider_config_key: str,
    f: dict[str, Any],
) -> DocumentFetchResult:
    fid = str(f.get("id") or "")
    mime = str(f.get("mimeType") or "")
    name = str(f.get("name") or fid)[:500]
    url = str(f.get("webViewLink") or fid)
    when = _parse_iso_dt(f.get("modifiedTime"))
    text = ""
    if mime in _DRIVE_EXPORT_SPECS:
        export_mime, ext = _DRIVE_EXPORT_SPECS[mime]
        r = nango_proxy_request(
            "GET",
            connection_id=connection_id,
            provider_config_key=provider_config_key,
            upstream_path=f"/drive/v3/files/{fid}/export",
            params={"mimeType": export_mime},
        )
        r.raise_for_status()
        text = _extract_text_from_bytes_for_ingestion(r.content, f"{name}{ext}")
    elif mime in _DRIVE_BINARY_SUPPORTED_MIME:
        r = nango_proxy_request(
            "GET",
            connection_id=connection_id,
            provider_config_key=provider_config_key,
            upstream_path=f"/drive/v3/files/{fid}",
            params={"alt": "media"},
        )
        r.raise_for_status()
        text = _extract_text_from_bytes_for_ingestion(r.content, _drive_filename_for_binary(f))
    else:
        logger.info("drive skip unsupported mime=%s file_id=%s", mime, fid)
    return DocumentFetchResult(
        external_id=fid,
        name=name,
        content=text,
        url=url,
        last_modified=when,
        metadata={"drive": f},
    )


def _drive_filename_for_binary(f: dict[str, Any]) -> str:
    name = str(f.get("name") or f.get("id") or "drive-file")
    ext = str(f.get("fileExtension") or "").strip().lower()
    if ext and not name.lower().endswith(f".{ext}"):
        return f"{name}.{ext}"
    return name


def _extract_text_from_bytes_for_ingestion(raw: bytes, filename: str) -> str:
    safe_name = Path(filename).name or "drive-file"
    suffix = Path(safe_name).suffix or ".txt"
    with tempfile.NamedTemporaryFile(prefix="nango-drive-", suffix=suffix, delete=False) as tmp:
        tmp.write(raw)
        tmp_path = tmp.name
    try:
        pages = extract_pages_from_upload(tmp_path, safe_name)
        text = "\n\n".join((p.text or "").strip() for p in pages if (p.text or "").strip())
        if text.strip():
            return text
        if suffix == ".txt":
            return clean_text_for_ingestion(raw.decode("utf-8", errors="replace"), strip_html=False)
        return ""
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def _fetch_google_drive_folder_walk(
    connection_id: str,
    provider_config_key: str,
    cursor: str | None,
    cfg: dict[str, Any],
    folder_ids: list[str],
) -> tuple[list[DocumentFetchResult], str | None]:
    include_sub = bool(cfg.get("drive_include_subfolders", True))
    list_page_size = min(100, max(10, int(cfg.get("drive_list_page_size", 50))))
    batch_export = min(50, max(1, int(cfg.get("page_size", 10))))

    state: dict[str, Any]
    if cursor and (decoded := _drive_walk_decode(cursor)):
        state = decoded
    else:
        state = {
            "queue": list(folder_ids),
            "listed": [],
            "cur_folder": None,
            "list_token": None,
            "exports": [],
        }

    listed: set[str] = set(str(x) for x in (state.get("listed") or []) if x)
    queue: list[str] = [str(x) for x in (state.get("queue") or []) if x]
    exports: list[dict[str, Any]] = list(state.get("exports") or [])
    cur_folder: str | None = state.get("cur_folder")
    list_token: str | None = state.get("list_token")

    out: list[DocumentFetchResult] = []

    def persist() -> str:
        state.clear()
        state["queue"] = queue
        state["listed"] = sorted(listed)
        state["cur_folder"] = cur_folder
        state["list_token"] = list_token
        state["exports"] = exports
        return _drive_walk_encode(state)

    while len(out) < batch_export:
        while exports:
            fmeta = exports.pop(0)
            fid = fmeta.get("id")
            if not fid:
                continue
            try:
                doc = _drive_export_file(connection_id, provider_config_key, fmeta)
            except Exception as exc:
                logger.warning("drive export failed id=%s: %s", fid, exc)
                continue
            out.append(doc)
            if len(out) >= batch_export:
                return out, persist() if (queue or exports or cur_folder or list_token) else None

        while cur_folder is None and queue:
            nxt = queue.pop(0)
            if nxt in listed:
                continue
            cur_folder = nxt
            list_token = None
            break

        if cur_folder is None:
            return out, None

        q = f"'{cur_folder}' in parents and trashed = false"
        params: dict[str, Any] = {
            "q": q,
            "pageSize": list_page_size,
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
            "fields": "files(id,name,fileExtension,mimeType,modifiedTime,webViewLink),nextPageToken",
        }
        if list_token:
            params["pageToken"] = list_token
        data = nango_proxy_get_json(
            connection_id=connection_id,
            provider_config_key=provider_config_key,
            upstream_path="/drive/v3/files",
            params=params,
        )
        listed.add(cur_folder)
        for f in data.get("files") or []:
            mime = str(f.get("mimeType") or "")
            fid = f.get("id")
            if not fid:
                continue
            if mime == _DRIVE_FOLDER_MIME:
                if include_sub and str(fid) not in listed:
                    queue.append(str(fid))
            elif mime in _DRIVE_EXPORT_SPECS or mime in _DRIVE_BINARY_SUPPORTED_MIME:
                exports.append(dict(f))

        list_token = data.get("nextPageToken")
        if not list_token:
            cur_folder = None

        if not queue and not exports and cur_folder is None:
            return out, None

    return out, persist()


def _fetch_google_drive(
    connection_id: str,
    provider_config_key: str,
    cursor: str | None,
    cfg: dict[str, Any],
) -> tuple[list[DocumentFetchResult], str | None]:
    folder_ids = sanitize_drive_folder_ids(cfg.get("drive_folder_ids"))
    if folder_ids:
        return _fetch_google_drive_folder_walk(
            connection_id, provider_config_key, cursor, cfg, folder_ids
        )

    # Keep the query conservative for Drive v3; broad/contains predicates on mimeType
    # can trigger 400 in some tenant + proxy combinations.
    q = f"trashed = false and mimeType = '{_DRIVE_DOC_MIME}'"
    params: dict[str, Any] = {
        "q": q,
        "pageSize": int(cfg.get("page_size", 10)),
        "supportsAllDrives": "true",
        "includeItemsFromAllDrives": "true",
        "fields": "files(id,name,fileExtension,mimeType,modifiedTime,webViewLink),nextPageToken",
    }
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
        mime = str(f.get("mimeType") or "")
        if mime not in _DRIVE_EXPORT_SPECS and mime not in _DRIVE_BINARY_SUPPORTED_MIME:
            continue
        try:
            out.append(_drive_export_file(connection_id, provider_config_key, f))
        except Exception as exc:
            logger.warning("drive fetch skip id=%s name=%s err=%s", fid, f.get("name"), exc)
            continue
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
