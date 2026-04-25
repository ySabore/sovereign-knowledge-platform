from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserPublic(BaseModel):
    id: UUID
    email: str
    full_name: str | None
    is_platform_owner: bool
    org_ids_as_owner: list[UUID] = Field(
        default_factory=list,
        description="Organizations where this user is org_owner.",
    )
    org_ids_as_workspace_admin: list[UUID] = Field(
        default_factory=list,
        description="Organizations where this user is workspace_admin in at least one workspace.",
    )

    model_config = {"from_attributes": True}


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=128, description="URL-safe slug, lowercase recommended")
    preferred_chat_provider: str | None = Field(
        default=None,
        description="Optional initial value: extractive | ollama | openai | anthropic",
        max_length=32,
    )
    preferred_chat_model: str | None = Field(default=None, max_length=128)
    ollama_base_url: str | None = Field(
        default=None,
        max_length=512,
        description="Optional; API must reach this Ollama host when org uses ollama provider",
    )


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    status: str | None = Field(default=None, min_length=1, max_length=32)
    description: str | None = Field(default=None, max_length=16_000)
    preferred_chat_provider: str | None = Field(
        default=None,
        description="extractive | ollama | openai | anthropic | null/empty for platform default",
        max_length=32,
    )
    preferred_chat_model: str | None = Field(default=None, max_length=128)
    openai_api_key: str | None = Field(default=None, max_length=512, description="Write-only; platform owner only")
    anthropic_api_key: str | None = Field(default=None, max_length=512, description="Write-only; platform owner only")
    cohere_api_key: str | None = Field(
        default=None,
        max_length=512,
        description="Write-only; platform owner only — Cohere Rerank API key for this org",
    )
    openai_api_base_url: str | None = Field(default=None, max_length=512)
    anthropic_api_base_url: str | None = Field(default=None, max_length=512)
    ollama_base_url: str | None = Field(
        default=None,
        max_length=512,
        description="Override platform Ollama URL for this org (org owner may set)",
    )
    retrieval_strategy: str | None = Field(
        default=None,
        max_length=32,
        description="heuristic | hybrid | rerank — rerank uses Cohere when org or platform API key is set",
    )
    use_hosted_rerank: bool | None = Field(
        default=None,
        description="With heuristic/hybrid, use Cohere Rerank when org or platform API key is configured",
    )
    allowed_connector_ids: list[str] | None = Field(
        default=None,
        description="Optional connector id allowlist for this org; null/empty means all platform catalog connectors.",
    )


class OrganizationPublic(BaseModel):
    id: UUID
    name: str
    slug: str
    status: str
    plan: str = "free_trial"
    description: str | None = None
    preferred_chat_provider: str | None = None
    preferred_chat_model: str | None = None
    openai_api_key_configured: bool = False
    anthropic_api_key_configured: bool = False
    cohere_api_key_configured: bool = False
    openai_api_base_url: str | None = None
    anthropic_api_base_url: str | None = None
    ollama_base_url: str | None = None
    retrieval_strategy: str | None = None
    use_hosted_rerank: bool = False
    allowed_connector_ids: list[str] | None = None

    model_config = {"from_attributes": True}


class OrganizationOverviewStats(BaseModel):
    """Aggregate counts for org overview cards (any org member may read)."""

    member_count: int = Field(ge=0)
    document_count: int = Field(ge=0)


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None


class WorkspacePublic(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    description: str | None

    model_config = {"from_attributes": True}


class OrganizationMemberUpsert(BaseModel):
    email: EmailStr
    role: str = Field(default="member", min_length=1, max_length=32)


class OrganizationMemberPublic(BaseModel):
    user_id: UUID
    organization_id: UUID
    email: str
    full_name: str | None
    role: str


class OrganizationInviteCreate(BaseModel):
    email: EmailStr
    role: str = Field(default="member", min_length=1, max_length=32)


class OrganizationInvitePublic(BaseModel):
    id: UUID
    organization_id: UUID
    email: str
    role: str
    status: str
    expires_at: datetime
    accepted_at: datetime | None
    created_at: datetime


class OrganizationInviteIssueResponse(BaseModel):
    invite: OrganizationInvitePublic
    invite_token: str


class OrganizationInviteAcceptRequest(BaseModel):
    token: str = Field(min_length=8, max_length=512)


class WorkspaceMemberUpsert(BaseModel):
    email: EmailStr
    role: str = Field(default="member", min_length=1, max_length=32)


class WorkspaceMemberPublic(BaseModel):
    user_id: UUID
    workspace_id: UUID
    email: str
    full_name: str | None
    role: str


class DocumentChunkPublic(BaseModel):
    chunk_index: int
    page_number: int | None
    char_count: int
    content_preview: str


class DocumentIngestionResponse(BaseModel):
    ingestion_job_id: UUID
    document_id: UUID
    organization_id: UUID
    workspace_id: UUID
    filename: str
    status: str
    page_count: int
    chunk_count: int
    checksum_sha256: str
    storage_path: str
    chunks: list[DocumentChunkPublic]


class DocumentStatusResponse(BaseModel):
    """Snapshot of a workspace document for polling and ops (no chunk bodies)."""

    id: UUID
    organization_id: UUID
    workspace_id: UUID
    ingestion_job_id: UUID | None
    ingestion_job_status: str | None = None
    ingestion_job_error: str | None = None
    filename: str
    content_type: str
    status: str
    page_count: int | None
    chunk_count: int
    checksum_sha256: str | None
    created_at: datetime
    updated_at: datetime


class IngestionJobStatusResponse(BaseModel):
    """Ingestion job row plus linked document ids for the same workspace upload."""

    id: UUID
    organization_id: UUID
    workspace_id: UUID
    status: str
    source_filename: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    document_ids: list[UUID]


class RetrievalHitPublic(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_filename: str
    chunk_index: int
    page_number: int | None
    score: float
    content: str


class IngestTextRequest(BaseModel):
    """Connector / API ingestion of raw text (HTML supported — cleaned server-side)."""

    content: str = Field(min_length=1, max_length=2_000_000)
    name: str = Field(min_length=1, max_length=255)
    source_type: str = Field(min_length=1, max_length=64, description="e.g. confluence, google-drive, pdf-upload")
    external_id: str = Field(min_length=1, max_length=512, description="Stable id in the source system")
    source_url: str | None = Field(default=None, max_length=2048)
    metadata: dict | None = None
    permission_user_ids: list[UUID] | None = Field(
        default=None,
        description="If RBAC_MODE=full, restrict read to these users; omit for org-wide",
    )


class IngestTextResponse(BaseModel):
    document_id: UUID
    chunks_created: int


class RetrievalQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    top_k: int | None = Field(default=None, ge=1, le=20)


class RetrievalQueryResponse(BaseModel):
    workspace_id: UUID
    query: str
    top_k: int
    embedding_model: str
    answer: str
    hits: list[RetrievalHitPublic]


class ChatSessionCreateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)


class ChatSessionUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    pinned: bool | None = None


class ChatSessionPublic(BaseModel):
    id: UUID
    organization_id: UUID
    workspace_id: UUID
    user_id: UUID | None
    title: str | None
    pinned: bool
    created_at: datetime
    updated_at: datetime


class ChatCitationPublic(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_filename: str
    chunk_index: int
    page_number: int | None
    score: float
    quote: str


class ChatMessageCreateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=8000)
    top_k: int | None = Field(default=None, ge=1, le=20)


class ChatMessagePublic(BaseModel):
    id: UUID
    session_id: UUID
    user_id: UUID | None
    role: str
    content: str
    citations: list[ChatCitationPublic] = Field(default_factory=list)
    feedback: Literal["up", "down"] | None = None
    confidence: str | None = Field(default=None, description="high | medium | low (retrieval / model signal).")
    generation_mode: str | None = Field(default=None, description="e.g. ollama, extractive, chitchat.")
    generation_model: str | None = Field(default=None, description="Model label shown in UI, e.g. qwen3:32b.")
    created_at: datetime


class ChatMessageFeedbackRequest(BaseModel):
    feedback: Literal["up", "down"] | None = Field(
        default=None,
        description="Use `up` or `down`; pass null to clear existing feedback.",
    )


class ChatTurnResponse(BaseModel):
    session: ChatSessionPublic
    user_message: ChatMessagePublic
    assistant_message: ChatMessagePublic
    generation_mode: str = Field(
        description="Debug mode used for answer generation: ollama | ollama_fallback_extractive | extractive | no_evidence"
    )
    generation_model: str | None = Field(
        default=None,
        description="Debug model label used for answer generation (e.g., qwen3:32b, extractive).",
    )


class ChatSessionDetailResponse(BaseModel):
    session: ChatSessionPublic
    messages: list[ChatMessagePublic]
