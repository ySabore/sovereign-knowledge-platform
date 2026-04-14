"""
Central application configuration.

All tunables are environment-driven (see `.env.example` and `docs/configuration.md`).
Import `settings` singleton only after env / working directory are set.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Server-side configuration (secrets and operational knobs)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
    )

    # --- Runtime identity ---
    environment: str = Field(default="development", description="development | staging | production")

    # --- Database ---
    database_url: str = "postgresql+psycopg://skp:skp@127.0.0.1:5433/skp"
    db_pool_size: int = Field(default=10, ge=1, le=100)
    db_max_overflow: int = Field(default=20, ge=0, le=200)
    db_pool_timeout_seconds: int = Field(default=30, ge=1, le=300, description="Seconds to wait for a connection from the pool")
    database_echo: bool = Field(default=False, description="Log SQL statements (dev/troubleshooting only)")

    # --- Redis ---
    redis_url: str = "redis://127.0.0.1:6380/0"
    redis_socket_timeout_seconds: float = Field(default=2.0, ge=0.5, le=30.0)

    # --- Auth / JWT ---
    jwt_secret: str = "dev-only-change-in-production"
    jwt_issuer: str = "sovereign-knowledge-platform"
    jwt_access_token_expire_minutes: int = Field(default=60, ge=1, le=10080)

    # --- Optional Clerk (RS256 session JWT; no Next.js required on the API) ---
    clerk_enabled: bool = Field(default=False, description="Accept Clerk session tokens in Authorization: Bearer")
    clerk_issuer: str = Field(
        default="",
        description="Clerk Frontend API URL, e.g. https://your-instance.clerk.accounts.dev",
    )
    clerk_audience: str = Field(
        default="",
        description="If set, verify JWT aud claim (often unset for default session tokens)",
    )
    clerk_jwt_leeway_seconds: int = Field(
        default=120,
        ge=0,
        le=600,
        description="Leeway for iat/nbf/exp when verifying Clerk JWTs (mitigates Docker VM vs host clock skew)",
    )

    # --- HTTP edge / CORS ---
    cors_origins: str = Field(
        default="*",
        description="Comma-separated browser origins, or * (disables credential cookies with browsers)",
    )
    cors_allow_methods: str = Field(default="*", description="Comma-separated methods or *")
    cors_allow_headers: str = Field(default="*", description="Comma-separated header names or *")
    trusted_hosts: str = Field(default="", description="Comma-separated Host values; empty disables TrustedHostMiddleware")

    # --- Logging ---
    log_level: str = Field(default="INFO", description="DEBUG|INFO|WARNING|ERROR|CRITICAL")
    log_json: bool = Field(default=False, description="Emit JSON lines for log aggregators")

    # --- Rate limiting (SlowAPI) ---
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = Field(default=120, ge=1, le=100000)
    rate_limit_redis_enabled: bool = Field(
        default=True,
        description="Use Redis (Upstash-compatible rediss://) for org plan tier limits on query/sync/admin routes",
    )

    # --- Stripe billing (optional) ---
    stripe_secret_key: str = Field(default="", description="sk_live_… or sk_test_…")
    stripe_webhook_secret: str = Field(default="", description="whsec_… for /webhooks/stripe")
    stripe_price_starter: str = Field(default="", description="price_… for Starter ($49/mo in dashboard)")
    stripe_price_team: str = Field(default="", description="price_… for Team")
    stripe_price_business: str = Field(default="", description="price_… for Business")
    stripe_price_scale: str = Field(default="", description="price_… for Scale")

    # --- Nango (connectors) ---
    nango_secret_key: str = Field(default="", description="Server secret for Nango Proxy API")
    nango_public_key: str = Field(
        default="",
        description="Publishable key for @nangohq/frontend (safe to expose via GET /config/public)",
    )
    nango_host: str = Field(default="https://api.nango.dev", description="Nango API base (proxy at /proxy/...)")

    # --- RBAC ---
    rbac_mode: str = Field(
        default="simple",
        description="simple = workspace/org-wide document access; full = DocumentPermission ACL required",
    )
    platform_owner_visible_org_slugs: str = Field(
        default="",
        description="Comma-separated organization slugs; if non-empty, platform owners only see these in GET /organizations/me (shell + overview)",
    )

    # --- Documents & ingestion ---
    document_storage_root: Path = Path("./data/documents")
    max_upload_size_mb: int = Field(default=50, ge=1, le=500, description="Maximum PDF upload size")
    ingestion_chunk_size: int = Field(default=1200, ge=100, le=50000)
    ingestion_chunk_overlap: int = Field(default=200, ge=0, le=10000)
    ingestion_target_tokens: int = Field(
        default=500,
        ge=200,
        le=2000,
        description="Target chunk size (~400–600 tokens); char budget = tokens × 4",
    )
    ingestion_overlap_ratio: float = Field(
        default=0.1,
        ge=0.0,
        le=0.4,
        description="Fraction of chunk_chars overlapped between windows (≈10%)",
    )
    embedding_batch_size: int = Field(default=32, ge=1, le=100, description="Chunks per embedding API call")
    embedding_batch_delay_seconds: float = Field(default=0.2, ge=0.0, le=5.0, description="Pause between batches")

    # --- Embeddings ---
    embedding_provider: str = "ollama"
    embedding_model: str = "nomic-embed-text"
    embedding_dimensions: int = Field(default=768, ge=1, le=16384)
    embedding_ollama_base_url: str = "http://127.0.0.1:11434"

    # --- Retrieval & chat ---
    retrieval_top_k: int = Field(default=5, ge=1, le=50)
    retrieval_candidate_k: int = Field(
        default=12,
        ge=1,
        le=50,
        description="Vector search pulls this many chunks before heuristic rerank (>= retrieval_top_k)",
    )
    rag_rerank_mode: str = Field(
        default="lexical_mmr",
        description="none | lexical_blend | lexical_mmr — heuristic rerank without extra models",
    )
    rag_lexical_weight: float = Field(
        default=0.25,
        ge=0.0,
        le=1.0,
        description="Blend: (1-w)*semantic_score + w*lexical_overlap",
    )
    rag_mmr_lambda: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="MMR tradeoff: higher = prefer relevance over diversity between chunks",
    )
    chat_min_citation_score: float = Field(
        default=0.30,
        ge=0.0,
        le=1.0,
        description="Min blended similarity on a top hit before chat answers (below ⇒ 'I don't know' fallback)",
    )
    chat_lexical_overlap_min: float = Field(
        default=0.10,
        ge=0.0,
        le=1.0,
        description="If all top hits are below chat_min_citation_score, still answer when query↔chunk token Jaccard ≥ this",
    )
    chat_citation_quote_max_chars: int = Field(default=400, ge=50, le=4000, description="Max chars per citation quote in responses")

    # --- Answer generation ---
    # Per-org: preferred_chat_provider / preferred_chat_model; cloud keys encrypted with ORG_LLM_FERNET_KEY.
    answer_generation_provider: str = Field(
        default="extractive",
        description="extractive | ollama | openai | anthropic",
    )
    answer_generation_model: str = "llama3.2"
    answer_generation_ollama_base_url: str = "http://127.0.0.1:11434"

    org_llm_fernet_key: str = Field(
        default="",
        description="Fernet key from Fernet.generate_key().decode(); required to store per-org OpenAI/Anthropic keys",
    )
    openai_api_key: str = Field(default="", description="Platform-wide OpenAI fallback when org has no stored key")
    anthropic_api_key: str = Field(default="", description="Platform-wide Anthropic fallback")
    openai_api_base: str = Field(default="https://api.openai.com/v1")
    anthropic_api_base: str = Field(default="https://api.anthropic.com")
    openai_default_chat_model: str = Field(default="gpt-4o-mini")
    anthropic_default_chat_model: str = Field(default="claude-3-5-haiku-20241022")
    anthropic_api_version: str = Field(default="2023-06-01")
    anthropic_max_output_tokens: int = Field(default=4096, ge=256, le=8192)
    cloud_llm_http_timeout_seconds: float = Field(default=120.0, ge=10.0, le=600.0)

    # --- Outbound HTTP (Ollama / embedding) ---
    ollama_http_timeout_seconds: float = Field(default=60.0, ge=5.0, le=600.0)

    # --- API metadata & feature bits ---
    api_title: str = "Sovereign Knowledge Platform API"
    api_version: str = "0.2.0"
    expose_public_config: bool = Field(
        default=True,
        description="If true, GET /config/public returns non-secret runtime options",
    )

    def cors_origin_list(self) -> list[str]:
        raw = self.cors_origins.strip()
        if raw == "*":
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]

    def cors_methods_list(self) -> list[str]:
        raw = self.cors_allow_methods.strip()
        if raw == "*":
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]

    def cors_headers_list(self) -> list[str]:
        raw = self.cors_allow_headers.strip()
        if raw == "*":
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]

    def trusted_host_list(self) -> list[str] | None:
        raw = self.trusted_hosts.strip()
        if not raw:
            return None
        return [h.strip() for h in raw.split(",") if h.strip()]

    def platform_owner_visible_org_slug_set(self) -> frozenset[str] | None:
        """If set, limits which organizations a platform owner sees in the app shell."""
        parts = [p.strip().lower() for p in self.platform_owner_visible_org_slugs.split(",") if p.strip()]
        return frozenset(parts) if parts else None

    @property
    def max_upload_size_bytes(self) -> int:
        return int(self.max_upload_size_mb) * 1024 * 1024

    def public_config(self) -> dict[str, Any]:
        """Safe subset for clients (no secrets)."""
        return {
            "environment": self.environment,
            "api_version": self.api_version,
            "embedding_provider": self.embedding_provider,
            "embedding_model": self.embedding_model,
            "embedding_dimensions": self.embedding_dimensions,
            "retrieval_top_k_default": self.retrieval_top_k,
            "retrieval_candidate_k_default": self.retrieval_candidate_k,
            "rag_rerank_mode": self.rag_rerank_mode,
            "rag_lexical_weight": self.rag_lexical_weight,
            "rag_mmr_lambda": self.rag_mmr_lambda,
            "rbac_mode": self.rbac_mode,
            "rate_limit_redis_enabled": self.rate_limit_redis_enabled,
            "chat_min_citation_score": self.chat_min_citation_score,
            "chat_lexical_overlap_min": self.chat_lexical_overlap_min,
            "answer_generation_provider": self.answer_generation_provider,
            "answer_generation_model": self.answer_generation_model,
            "max_upload_size_mb": self.max_upload_size_mb,
            "rate_limit_enabled": self.rate_limit_enabled,
            "nango_host": self.nango_host,
            "nango_public_key": (self.nango_public_key or "").strip(),
            "nango_configured": bool((self.nango_secret_key or "").strip()),
            "features": {
                "public_config_endpoint": self.expose_public_config,
                "clerk_sign_in": self.clerk_enabled and bool(self.clerk_issuer.strip()),
                "stripe_billing": bool((self.stripe_secret_key or "").strip().startswith(("sk_", "rk_"))),
                "nango_connect": bool((self.nango_public_key or "").strip()) and bool((self.nango_secret_key or "").strip()),
            },
        }


settings = Settings()
