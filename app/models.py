from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OrgStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"


class OrgMembershipRole(str, enum.Enum):
    org_owner = "org_owner"
    member = "member"


class WorkspaceMemberRole(str, enum.Enum):
    workspace_admin = "workspace_admin"
    editor = "editor"
    member = "member"


class IngestionJobStatus(str, enum.Enum):
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class DocumentStatus(str, enum.Enum):
    uploaded = "uploaded"
    processing = "processing"
    indexed = "indexed"
    failed = "failed"


class ChatMessageRole(str, enum.Enum):
    system = "system"
    user = "user"
    assistant = "assistant"


class AuditAction(str, enum.Enum):
    organization_created = "organization_created"
    organization_updated = "organization_updated"
    organization_member_upserted = "organization_member_upserted"
    organization_member_removed = "organization_member_removed"
    workspace_created = "workspace_created"
    workspace_updated = "workspace_updated"
    workspace_member_upserted = "workspace_member_upserted"
    workspace_member_removed = "workspace_member_removed"
    organization_invite_sent = "organization_invite_sent"
    organization_invite_resent = "organization_invite_resent"
    organization_invite_revoked = "organization_invite_revoked"
    organization_invite_accepted = "organization_invite_accepted"
    organization_deleted = "organization_deleted"
    workspace_deleted = "workspace_deleted"
    document_deleted = "document_deleted"
    chat_session_deleted = "chat_session_deleted"
    connector_deleted = "connector_deleted"
    api_http_mutation = "api_http_mutation"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    clerk_user_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_platform_owner: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    org_memberships: Mapped[list[OrganizationMembership]] = relationship(back_populates="user")
    workspace_memberships: Mapped[list[WorkspaceMember]] = relationship(back_populates="user")
    created_documents: Mapped[list[Document]] = relationship(back_populates="created_by_user")
    chat_sessions: Mapped[list[ChatSession]] = relationship(back_populates="user")
    chat_messages: Mapped[list[ChatMessage]] = relationship(back_populates="user")
    audit_events: Mapped[list[AuditLog]] = relationship(back_populates="actor")


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    tenant_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default=OrgStatus.active.value)
    plan: Mapped[str] = mapped_column(
        String(32),
        default="free_trial",
        doc="free | starter | team | business | scale | admin — drives entitlements and rate limits",
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    billing_grace_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    clerk_organization_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    preferred_chat_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    preferred_chat_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    openai_api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    anthropic_api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    cohere_api_key_encrypted: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Fernet-encrypted Cohere API key for hosted Rerank (optional; overrides platform COHERE_API_KEY).",
    )
    openai_api_base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    anthropic_api_base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ollama_base_url: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        doc="Optional override for ANSWER_GENERATION_OLLAMA_BASE_URL (API must reach this host).",
    )
    retrieval_strategy: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        doc="heuristic | hybrid | rerank — rerank uses vector retrieval + Cohere when org or platform API key is set.",
    )
    allowed_connector_ids: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
        doc=(
            "Optional connector id allowlist for this org. "
            "Null/empty means all platform catalog connectors are available."
        ),
    )
    use_hosted_rerank: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="With heuristic/hybrid fetch, run Cohere Rerank instead of lexical heuristic when org or platform Cohere key is set.",
    )

    @property
    def openai_api_key_configured(self) -> bool:
        return bool((self.openai_api_key_encrypted or "").strip())

    @property
    def anthropic_api_key_configured(self) -> bool:
        return bool((self.anthropic_api_key_encrypted or "").strip())

    @property
    def cohere_api_key_configured(self) -> bool:
        return bool((self.cohere_api_key_encrypted or "").strip())

    memberships: Mapped[list[OrganizationMembership]] = relationship(back_populates="organization")
    workspaces: Mapped[list[Workspace]] = relationship(back_populates="organization")
    connector_registrations: Mapped[list["OrganizationConnector"]] = relationship(back_populates="organization")
    integration_connectors: Mapped[list["IntegrationConnector"]] = relationship(back_populates="organization")


class OrganizationConnector(Base):
    """Registered connector integrations per org (for plan limit: max connectors)."""

    __tablename__ = "organization_connectors"
    __table_args__ = (UniqueConstraint("organization_id", "integration_key", name="uq_org_connector_integration"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))
    integration_key: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    organization: Mapped[Organization] = relationship(back_populates="connector_registrations")


class IntegrationConnector(Base):
    """Nango-backed integration (Layer 5 Connector) — one row per org + connector_type."""

    __tablename__ = "connectors"
    __table_args__ = (UniqueConstraint("organization_id", "connector_type", name="uq_connectors_org_type"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))
    connector_type: Mapped[str] = mapped_column(String(128))
    nango_connection_id: Mapped[str] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    document_count: Mapped[int] = mapped_column(Integer, default=0)
    config: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    organization: Mapped[Organization] = relationship(back_populates="integration_connectors")
    documents: Mapped[list["Document"]] = relationship(back_populates="integration_connector")


class OrganizationMembership(Base):
    __tablename__ = "organization_memberships"
    __table_args__ = (UniqueConstraint("user_id", "organization_id", name="uq_user_org"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(32))  # OrgMembershipRole value
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="org_memberships")
    organization: Mapped[Organization] = relationship(back_populates="memberships")


class OrganizationInvite(Base):
    __tablename__ = "organization_invites"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    role: Mapped[str] = mapped_column(String(32), default=OrgMembershipRole.member.value)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    invite_token_hash: Mapped[str] = mapped_column(String(128), index=True)
    invited_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    accepted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    organization: Mapped[Organization] = relationship(back_populates="workspaces")
    members: Mapped[list[WorkspaceMember]] = relationship(back_populates="workspace")
    documents: Mapped[list[Document]] = relationship(back_populates="workspace")
    chat_sessions: Mapped[list[ChatSession]] = relationship(back_populates="workspace")
    query_logs: Mapped[list["QueryLog"]] = relationship(back_populates="workspace")


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id", name="uq_workspace_user"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(32))  # WorkspaceMemberRole value
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    workspace: Mapped[Workspace] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="workspace_memberships")


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=IngestionJobStatus.queued.value)
    source_filename: Mapped[str] = mapped_column(String(255))
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    documents: Mapped[list[Document]] = relationship(back_populates="ingestion_job")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"))
    ingestion_job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ingestion_jobs.id", ondelete="SET NULL"), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(128), default="application/pdf")
    storage_path: Mapped[str] = mapped_column(String(1024))
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_type: Mapped[str] = mapped_column(String(64), default="pdf-upload", index=True)
    external_id: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    ingestion_metadata: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    integration_connector_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("connectors.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(32), default=DocumentStatus.uploaded.value)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    workspace: Mapped[Workspace] = relationship(back_populates="documents")
    integration_connector: Mapped[IntegrationConnector | None] = relationship(back_populates="documents")
    created_by_user: Mapped[User | None] = relationship(back_populates="created_documents")
    ingestion_job: Mapped[IngestionJob | None] = relationship(back_populates="documents")
    chunks: Mapped[list[DocumentChunk]] = relationship(back_populates="document")
    permissions: Mapped[list["DocumentPermission"]] = relationship(back_populates="document")


class DocumentPermission(Base):
    """Per-document ACL synced from connectors (full RBAC) or created for uploads."""

    __tablename__ = "document_permissions"
    __table_args__ = (UniqueConstraint("document_id", "source", "external_id", name="uq_document_permission_source_ext"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"))
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    can_read: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[str] = mapped_column(String(64))
    external_id: Mapped[str] = mapped_column(String(512))
    connector_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    document: Mapped[Document] = relationship(back_populates="permissions")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"))
    chunk_index: Mapped[int] = mapped_column(Integer)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    document: Mapped[Document] = relationship(back_populates="chunks")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pinned: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    workspace: Mapped[Workspace] = relationship(back_populates="chat_sessions")
    user: Mapped[User | None] = relationship(back_populates="chat_sessions")
    messages: Mapped[list[ChatMessage]] = relationship(back_populates="session")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    role: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text)
    citations_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    feedback: Mapped[str | None] = mapped_column(String(16), nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(32), nullable=True)
    generation_mode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    generation_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    session: Mapped[ChatSession] = relationship(back_populates="messages")
    user: Mapped[User | None] = relationship(back_populates="chat_messages")


class QueryLog(Base):
    """Layer 5 Query model — audit trail for RAG turns (optional analytics)."""

    __tablename__ = "query_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    citations_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(16), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedback: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    workspace: Mapped[Workspace] = relationship(back_populates="query_logs")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    target_type: Mapped[str] = mapped_column(String(64))
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    metadata_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    actor: Mapped[User | None] = relationship(back_populates="audit_events")
