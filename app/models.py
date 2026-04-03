from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

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


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    memberships: Mapped[list[OrganizationMembership]] = relationship(back_populates="organization")
    workspaces: Mapped[list[Workspace]] = relationship(back_populates="organization")


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
    status: Mapped[str] = mapped_column(String(32), default=DocumentStatus.uploaded.value)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    workspace: Mapped[Workspace] = relationship(back_populates="documents")
    created_by_user: Mapped[User | None] = relationship(back_populates="created_documents")
    ingestion_job: Mapped[IngestionJob | None] = relationship(back_populates="documents")
    chunks: Mapped[list[DocumentChunk]] = relationship(back_populates="document")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"))
    chunk_index: Mapped[int] = mapped_column(Integer)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    embedding: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    document: Mapped[Document] = relationship(back_populates="chunks")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    session: Mapped[ChatSession] = relationship(back_populates="messages")
    user: Mapped[User | None] = relationship(back_populates="chat_messages")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    target_type: Mapped[str] = mapped_column(String(64))
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    metadata_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    actor: Mapped[User | None] = relationship(back_populates="audit_events")
