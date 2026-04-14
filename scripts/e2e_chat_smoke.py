from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.database import SessionLocal
from app.models import ChatMessage, ChatSession, Document, DocumentChunk
from app.services.chat import FALLBACK_NO_EVIDENCE

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_OWNER_EMAIL = "owner@example.com"
DEFAULT_OWNER_PASSWORD = "ChangeMeNow!"
DEFAULT_EVIDENCE_TEXT = (
    "Project Atlas retention period is 45 days. "
    "The escalation owner is Alice Example. "
    "Customer support hours are 9 AM to 5 PM Eastern on weekdays."
)
DEFAULT_HIT_QUESTION = "What is the Project Atlas retention period?"
DEFAULT_NO_HIT_QUESTION = "What is the office snack policy?"
REQUIRED_OPENAPI_PATHS = (
    "/config/public",
    "/documents/workspaces/{workspace_id}/upload",
    "/documents/workspaces/{workspace_id}/search",
    "/documents/ingestion-jobs/{job_id}",
    "/documents/{document_id}",
    "/chat/workspaces/{workspace_id}/sessions",
    "/chat/sessions/{session_id}/messages",
)


@dataclass(slots=True)
class SmokeConfig:
    base_url: str
    owner_email: str
    owner_password: str
    evidence_text: str
    hit_question: str
    no_hit_question: str
    timeout_seconds: float
    health_wait_seconds: float
    require_openapi_paths: bool
    skip_ollama_preflight: bool
    output_path: Path | None


class SmokePreflightError(RuntimeError):
    pass



def build_simple_pdf_bytes(lines: list[str]) -> bytes:
    def esc(value: str) -> str:
        return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    content_lines = ["BT", "/F1 12 Tf", "72 720 Td"]
    for index, line in enumerate(lines):
        if index == 0:
            content_lines.append(f"({esc(line)}) Tj")
        else:
            content_lines.append("0 -18 Td")
            content_lines.append(f"({esc(line)}) Tj")
    content_lines.append("ET")
    content_stream = "\n".join(content_lines).encode("utf-8")

    objects: list[bytes] = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    objects.append(
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
    )
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objects.append(
        b"<< /Length " + str(len(content_stream)).encode("ascii") + b" >>\nstream\n" + content_stream + b"\nendstream"
    )

    parts = [b"%PDF-1.4\n"]
    offsets = [0]
    for idx, obj in enumerate(objects, start=1):
        offsets.append(sum(len(part) for part in parts))
        parts.append(f"{idx} 0 obj\n".encode("ascii"))
        parts.append(obj)
        parts.append(b"\nendobj\n")

    xref_offset = sum(len(part) for part in parts)
    parts.append(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    parts.append(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        parts.append(f"{offset:010d} 00000 n \n".encode("ascii"))
    parts.append(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF"
        ).encode("ascii")
    )
    return b"".join(parts)



def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}



def parse_args() -> SmokeConfig:
    parser = argparse.ArgumentParser(
        description="Run the live end-to-end SKP chat smoke path as a repeatable pre-demo validation lane."
    )
    parser.add_argument("--base-url", default=os.getenv("SKP_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--owner-email", default=os.getenv("SKP_OWNER_EMAIL", DEFAULT_OWNER_EMAIL))
    parser.add_argument("--owner-password", default=os.getenv("SKP_OWNER_PASSWORD", DEFAULT_OWNER_PASSWORD))
    parser.add_argument("--evidence-text", default=os.getenv("SKP_SMOKE_EVIDENCE_TEXT", DEFAULT_EVIDENCE_TEXT))
    parser.add_argument("--hit-question", default=os.getenv("SKP_SMOKE_HIT_QUESTION", DEFAULT_HIT_QUESTION))
    parser.add_argument("--no-hit-question", default=os.getenv("SKP_SMOKE_NO_HIT_QUESTION", DEFAULT_NO_HIT_QUESTION))
    parser.add_argument("--timeout-seconds", type=float, default=float(os.getenv("SKP_SMOKE_TIMEOUT_SECONDS", "60")))
    parser.add_argument(
        "--health-wait-seconds",
        type=float,
        default=float(os.getenv("SKP_SMOKE_HEALTH_WAIT_SECONDS", "30")),
        help="How long to wait for /health to become ready before failing.",
    )
    parser.add_argument(
        "--skip-openapi-check",
        action="store_true",
        help="Skip verifying the required chat/document routes in /openapi.json.",
    )
    parser.add_argument(
        "--skip-ollama-preflight",
        action="store_true",
        help="Skip checking that Ollama is up and lists the configured embedding model (from app settings).",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path(os.getenv("SKP_SMOKE_OUTPUT_JSON")) if os.getenv("SKP_SMOKE_OUTPUT_JSON") else None,
        help="Optional path to also write the JSON result payload.",
    )
    args = parser.parse_args()
    return SmokeConfig(
        base_url=args.base_url.rstrip("/"),
        owner_email=args.owner_email,
        owner_password=args.owner_password,
        evidence_text=args.evidence_text,
        hit_question=args.hit_question,
        no_hit_question=args.no_hit_question,
        timeout_seconds=args.timeout_seconds,
        health_wait_seconds=args.health_wait_seconds,
        require_openapi_paths=not args.skip_openapi_check,
        skip_ollama_preflight=args.skip_ollama_preflight,
        output_path=args.output_json,
    )



def wait_for_health(client: httpx.Client, max_wait_seconds: float) -> dict[str, Any]:
    deadline = time.time() + max_wait_seconds
    last_error: str | None = None
    while time.time() < deadline:
        try:
            response = client.get("/health")
            response.raise_for_status()
            payload = response.json()
            if payload.get("status") != "ok":
                last_error = f"Unexpected health payload: {payload}"
            else:
                return payload
        except Exception as exc:  # pragma: no cover - exercised in live runs
            last_error = str(exc)
        time.sleep(1.0)
    raise SmokePreflightError(
        f"API never became healthy at {client.base_url} within {max_wait_seconds:.0f}s. Last error: {last_error}"
    )



def verify_ollama_embedding_model(timeout_seconds: float) -> dict[str, Any]:
    """Ensure Ollama is reachable and exposes the embedding model from app config (ingestion/search depend on it)."""
    base = settings.embedding_ollama_base_url.rstrip("/")
    model = settings.embedding_model.strip()
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.get(f"{base}/api/tags")
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        raise SmokePreflightError(
            f"Ollama not reachable at {base} (embedding model '{model}'): {exc}. "
            "Start Ollama and run: ollama pull " + model.split(":")[0]
        ) from exc

    models = payload.get("models") or []
    names: list[str] = []
    for row in models:
        name = row.get("name")
        if isinstance(name, str):
            names.append(name)

    base_name = model.split(":")[0]
    ok = any(
        n == model or n.startswith(base_name + ":") or n == base_name for n in names
    )
    if not ok:
        preview = ", ".join(names[:12])
        if len(names) > 12:
            preview += ", ..."
        raise SmokePreflightError(
            f"Ollama at {base} does not list embedding model '{model}'. "
            f"Available: {preview or '(none)'}. "
            f"Try: ollama pull {model}"
        )
    return {"ollama_base": base, "embedding_model": model, "model_count": len(names)}


def verify_openapi_paths(client: httpx.Client) -> list[str]:
    response = client.get("/openapi.json")
    response.raise_for_status()
    payload = response.json()
    paths = payload.get("paths", {})
    missing = [route for route in REQUIRED_OPENAPI_PATHS if route not in paths]
    if missing:
        raise SmokePreflightError(
            "Connected API is missing required ingestion/chat routes. "
            f"This often means a stale or wrong process is bound to the target port. Missing: {missing}"
        )
    return sorted(REQUIRED_OPENAPI_PATHS)



def run_smoke(config: SmokeConfig) -> dict[str, Any]:
    run_id = str(uuid.uuid4())[:8]
    org_slug = f"smoke-{run_id}"
    org_name = f"Smoke Org {run_id}"
    ws1_name = f"Evidence WS {run_id}"
    ws2_name = f"Isolation WS {run_id}"

    with httpx.Client(base_url=config.base_url, timeout=config.timeout_seconds) as client:
        health_payload = wait_for_health(client, config.health_wait_seconds)
        verified_paths = verify_openapi_paths(client) if config.require_openapi_paths else []
        ollama_preflight: dict[str, Any] | None = None
        if not config.skip_ollama_preflight:
            ollama_preflight = verify_ollama_embedding_model(min(15.0, config.timeout_seconds))

        login = client.post("/auth/login", json={"email": config.owner_email, "password": config.owner_password})
        login.raise_for_status()
        token = login.json()["access_token"]
        headers = auth_headers(token)

        org = client.post("/organizations", headers=headers, json={"name": org_name, "slug": org_slug})
        org.raise_for_status()
        org_id = org.json()["id"]

        ws1 = client.post(
            f"/workspaces/org/{org_id}",
            headers=headers,
            json={"name": ws1_name, "description": "workspace with indexed evidence"},
        )
        ws1.raise_for_status()
        ws1_id = ws1.json()["id"]

        ws2 = client.post(
            f"/workspaces/org/{org_id}",
            headers=headers,
            json={"name": ws2_name, "description": "workspace for isolation check"},
        )
        ws2.raise_for_status()
        ws2_id = ws2.json()["id"]

        pdf_bytes = build_simple_pdf_bytes(
            [
                "Sovereign Knowledge Platform smoke test document.",
                config.evidence_text,
                "This PDF exists only to prove ingestion, retrieval, chat citations, and workspace isolation.",
            ]
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            pdf_path = Path(tmp_dir) / "smoke-evidence.pdf"
            pdf_path.write_bytes(pdf_bytes)
            with pdf_path.open("rb") as handle:
                upload = client.post(
                    f"/documents/workspaces/{ws1_id}/upload",
                    headers=headers,
                    files={"file": (pdf_path.name, handle, "application/pdf")},
                )
            upload.raise_for_status()
            upload_payload = upload.json()

        search = client.post(
            f"/documents/workspaces/{ws1_id}/search",
            headers=headers,
            json={"query": config.hit_question, "top_k": 3},
        )
        search.raise_for_status()
        search_payload = search.json()
        if not search_payload["hits"]:
            raise AssertionError("Expected retrieval hits in evidence workspace")

        session1 = client.post(
            f"/chat/workspaces/{ws1_id}/sessions",
            headers=headers,
            json={"title": "Evidence session"},
        )
        session1.raise_for_status()
        session1_id = session1.json()["id"]

        hit_turn = client.post(
            f"/chat/sessions/{session1_id}/messages",
            headers=headers,
            json={"content": config.hit_question, "top_k": 3},
        )
        hit_turn.raise_for_status()
        hit_payload = hit_turn.json()

        no_hit_turn = client.post(
            f"/chat/sessions/{session1_id}/messages",
            headers=headers,
            json={"content": config.no_hit_question, "top_k": 3},
        )
        no_hit_turn.raise_for_status()
        no_hit_payload = no_hit_turn.json()

        session_detail = client.get(f"/chat/sessions/{session1_id}", headers=headers)
        session_detail.raise_for_status()
        session_detail_payload = session_detail.json()

        isolated_session = client.post(
            f"/chat/workspaces/{ws2_id}/sessions",
            headers=headers,
            json={"title": "Isolation session"},
        )
        isolated_session.raise_for_status()
        isolated_session_id = isolated_session.json()["id"]

        isolated_turn = client.post(
            f"/chat/sessions/{isolated_session_id}/messages",
            headers=headers,
            json={"content": config.hit_question, "top_k": 3},
        )
        isolated_turn.raise_for_status()
        isolated_payload = isolated_turn.json()

    hit_answer = hit_payload["assistant_message"]["content"]
    hit_citations = hit_payload["assistant_message"]["citations"]
    no_hit_answer = no_hit_payload["assistant_message"]["content"]
    isolated_answer = isolated_payload["assistant_message"]["content"]

    if not hit_citations:
        raise AssertionError(f"Expected citations for hit question, got none. Search payload: {json.dumps(search_payload, indent=2)}")
    if "45 days" not in hit_answer.lower() and "45 days" not in json.dumps(hit_citations).lower():
        raise AssertionError(f"Expected hit answer/citations to reference 45 days. Hit payload: {json.dumps(hit_payload, indent=2)}")
    if no_hit_answer != FALLBACK_NO_EVIDENCE:
        raise AssertionError(f"Expected no-hit fallback answer, got: {no_hit_answer}")
    if no_hit_payload["assistant_message"]["citations"]:
        raise AssertionError("Expected no citations for no-hit question")
    if isolated_answer != FALLBACK_NO_EVIDENCE:
        raise AssertionError(f"Expected isolated workspace fallback answer, got: {isolated_answer}")
    if isolated_payload["assistant_message"]["citations"]:
        raise AssertionError("Expected no citations for isolated workspace question")

    messages = session_detail_payload["messages"]
    roles = [message["role"] for message in messages]
    if roles != ["user", "assistant", "user", "assistant"]:
        raise AssertionError(f"Unexpected persisted message roles: {roles}")

    with SessionLocal() as db:
        db_session1 = db.get(ChatSession, session1_id)
        db_session2 = db.get(ChatSession, isolated_session_id)
        if db_session1 is None or db_session2 is None:
            raise AssertionError("Expected chat sessions to persist in database")
        ws1_message_count = db.query(ChatMessage).filter(ChatMessage.session_id == session1_id).count()
        ws2_message_count = db.query(ChatMessage).filter(ChatMessage.session_id == isolated_session_id).count()
        doc_count_ws1 = db.query(Document).filter(Document.workspace_id == ws1_id).count()
        chunk_count_ws1 = (
            db.query(DocumentChunk)
            .join(Document, Document.id == DocumentChunk.document_id)
            .filter(Document.workspace_id == ws1_id)
            .count()
        )
        chunk_count_ws2 = (
            db.query(DocumentChunk)
            .join(Document, Document.id == DocumentChunk.document_id)
            .filter(Document.workspace_id == ws2_id)
            .count()
        )
        if ws1_message_count != 4:
            raise AssertionError(f"Expected 4 persisted messages in evidence session, found {ws1_message_count}")
        if ws2_message_count != 2:
            raise AssertionError(f"Expected 2 persisted messages in isolation session, found {ws2_message_count}")
        if doc_count_ws1 != 1:
            raise AssertionError(f"Expected 1 document in evidence workspace, found {doc_count_ws1}")
        if chunk_count_ws1 < 1:
            raise AssertionError("Expected indexed chunks in evidence workspace")
        if chunk_count_ws2 != 0:
            raise AssertionError(f"Expected zero indexed chunks in isolation workspace, found {chunk_count_ws2}")

    return {
        "run_id": run_id,
        "base_url": config.base_url,
        "verified_health": health_payload,
        "verified_openapi_paths": verified_paths,
        "ollama_preflight": ollama_preflight,
        "org_id": org_id,
        "workspace_with_evidence_id": ws1_id,
        "isolated_workspace_id": ws2_id,
        "upload": upload_payload,
        "search_top_hit_score": search_payload["hits"][0]["score"],
        "search_hit_count": len(search_payload["hits"]),
        "chat_session_id": session1_id,
        "hit_question": config.hit_question,
        "hit_answer": hit_answer,
        "hit_citation_count": len(hit_citations),
        "no_hit_question": config.no_hit_question,
        "no_hit_answer": no_hit_answer,
        "isolated_answer": isolated_answer,
        "persisted_message_roles": roles,
        "db_checks": {
            "ws1_message_count": ws1_message_count,
            "ws2_message_count": ws2_message_count,
            "ws1_document_count": doc_count_ws1,
            "ws1_chunk_count": chunk_count_ws1,
            "ws2_chunk_count": chunk_count_ws2,
        },
        "verified_at_epoch": time.time(),
    }



def main() -> None:
    config = parse_args()
    try:
        result = run_smoke(config)
    except (SmokePreflightError, AssertionError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    result_json = json.dumps(result, indent=2)
    if config.output_path is not None:
        config.output_path.parent.mkdir(parents=True, exist_ok=True)
        config.output_path.write_text(result_json + "\n", encoding="utf-8")
    print(result_json)


if __name__ == "__main__":
    main()
