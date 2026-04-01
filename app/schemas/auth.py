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

    model_config = {"from_attributes": True}


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=128, description="URL-safe slug, lowercase recommended")


class OrganizationPublic(BaseModel):
    id: UUID
    name: str
    slug: str
    status: str

    model_config = {"from_attributes": True}


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class WorkspacePublic(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    description: str | None

    model_config = {"from_attributes": True}
