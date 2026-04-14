from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class BillingCheckoutRequest(BaseModel):
    """Use a Price ID from the Stripe Dashboard (e.g. price_… for $49/mo Starter)."""

    price_id: str = Field(min_length=3, max_length=128)
    success_url: str = Field(min_length=8, description="https://… redirect after successful payment")
    cancel_url: str = Field(min_length=8, description="https://… if user cancels Checkout")


class BillingPortalRequest(BaseModel):
    return_url: str = Field(min_length=8, description="https://… return from Stripe Customer Portal")


class BillingCheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str


class BillingPortalResponse(BaseModel):
    portal_url: str


class BillingPlanResponse(BaseModel):
    organization_id: UUID
    plan: str
    subscription_status: str | None = None
    connectors_max: int
    seats_max: int
    queries_per_month: int
    queries_per_day: int
    queries_per_hour: int | None = None
    connectors_used: int
    seats_used: int
    billing_grace_until: str | None = None
