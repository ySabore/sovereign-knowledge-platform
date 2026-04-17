from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import settings
from app.logging_config import configure_logging
from app.limiter import limiter
from app.middleware import AuditMutationMiddleware, RequestIdMiddleware, SecurityHeadersMiddleware
from app.routers import api_chat, auth, billing, chat, connectors, documents, health, metrics, organizations, runtime_config, webhooks_clerk, webhooks_stripe

configure_logging()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.api_title,
        version=settings.api_version,
        description="Multi-tenant RAG API — authentication, organizations, workspaces, PDF ingestion, chat.",
        lifespan=lifespan,
    )
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    hosts = settings.trusted_host_list()
    if hosts:
        application.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts)

    application.add_middleware(RequestIdMiddleware)
    application.add_middleware(SecurityHeadersMiddleware)

    origins = settings.cors_origin_list()
    # Browsers forbid Access-Control-Allow-Origin: * together with credentials.
    allow_cred = "*" not in origins
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=allow_cred,
        allow_methods=settings.cors_methods_list(),
        allow_headers=settings.cors_headers_list(),
        expose_headers=["x-request-id"],
    )

    # SlowAPI middleware is required for limiter.exempt and global default_limits.
    application.add_middleware(SlowAPIMiddleware)
    # Innermost: observe final response + request.state (e.g. request_id) for HTTP mutation audit.
    application.add_middleware(AuditMutationMiddleware)

    application.include_router(runtime_config.router)
    application.include_router(health.router)
    application.include_router(auth.router)
    application.include_router(organizations.router)
    application.include_router(organizations.router_w)
    application.include_router(documents.router)
    application.include_router(chat.router)
    application.include_router(api_chat.router)
    application.include_router(connectors.router)
    application.include_router(metrics.router)
    application.include_router(webhooks_clerk.router)
    application.include_router(webhooks_stripe.router)
    application.include_router(billing.router)
    return application


app = create_app()
