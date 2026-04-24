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
    queries_used_month: int = 0
    connectors_used: int
    seats_used: int
    billing_grace_until: str | None = None


class BillingPlanTier(BaseModel):
    plan: str
    price_id: str | None = None
    price_display: str | None = None
    connectors_max: int
    seats_max: int
    queries_per_month: int
    queries_per_day: int
    queries_per_hour: int | None = None


class BillingPlansCatalogResponse(BaseModel):
    organization_id: UUID
    current_plan: str
    plans: list[BillingPlanTier]


class BillingInvoiceItem(BaseModel):
    invoice_id: str
    number: str | None = None
    status: str | None = None
    currency: str
    total_cents: int
    amount_due_cents: int
    amount_paid_cents: int
    created_at: str | None = None
    period_start_at: str | None = None
    period_end_at: str | None = None
    hosted_invoice_url: str | None = None
    invoice_pdf_url: str | None = None


class BillingInvoicesResponse(BaseModel):
    organization_id: UUID
    stripe_enabled: bool
    customer_id: str | None = None
    invoices: list[BillingInvoiceItem]
