"""Log successful mutating HTTP requests into audit_logs (org-scoped when path resolves)."""

from __future__ import annotations

import logging
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings
from app.database import SessionLocal
from app.models import AuditLog, AuditAction
from app.services.audit_actor import infer_actor_role
from app.services.audit_http_context import resolve_audit_org_workspace
from app.services.audit_request_user import get_user_for_audit_middleware

logger = logging.getLogger(__name__)

_MUTATING = frozenset({"POST", "PUT", "PATCH", "DELETE"})

_EXEMPT_PREFIXES = (
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/webhooks",
    "/auth/",
)


class AuditMutationMiddleware(BaseHTTPMiddleware):
    """After a successful mutating API call, append a row when org scope can be resolved."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Response]) -> Response:
        response = await call_next(request)
        if not settings.audit_http_middleware_enabled:
            return response
        if request.method not in _MUTATING:
            return response
        if response.status_code < 200 or response.status_code >= 300:
            return response
        path = request.url.path
        if not path.startswith("/") or path == "/":
            return response
        if any(path.startswith(p) for p in _EXEMPT_PREFIXES):
            return response

        db = SessionLocal()
        try:
            org_id, workspace_id = resolve_audit_org_workspace(db, path)
            if org_id is None:
                return response
            user = get_user_for_audit_middleware(db, request.headers.get("authorization"))
            actor_id = user.id if user is not None else None
            role: str | None = None
            if user is not None:
                role = infer_actor_role(db, user, organization_id=org_id, workspace_id=workspace_id)
            rid = getattr(request.state, "request_id", None) or request.headers.get("x-request-id")
            db.add(
                AuditLog(
                    actor_user_id=actor_id,
                    actor_role=role,
                    organization_id=org_id,
                    workspace_id=workspace_id,
                    action=AuditAction.api_http_mutation.value,
                    target_type="http_request",
                    target_id=None,
                    metadata_json={
                        "method": request.method,
                        "path": path,
                        "status_code": response.status_code,
                        "source": "http_middleware",
                        "request_id": rid,
                    },
                )
            )
            db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.warning("audit middleware: failed to persist: %s", exc)
            db.rollback()
        finally:
            db.close()

        return response
