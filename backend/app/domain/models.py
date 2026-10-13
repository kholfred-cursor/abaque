"""Database-agnostic Pydantic models exchanged through repository ports."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.entitlements.models import Entitlements

AdminRole = Literal["owner", "animator", "superadmin"]
OrganizationStatus = Literal["active", "suspended", "deleted"]
PlanCode = Literal["demo", "trial", "standard"]
UsageKey = Literal["evaluations", "ballots", "emails_sent"]


class TenantContext(BaseModel):
    """Authenticated organization scope, built from a validated access token only."""

    model_config = ConfigDict(frozen=True)

    organization_id: str
    admin_id: str
    role: AdminRole


class Organization(BaseModel):
    """One tenant organization and its resolved entitlements."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    slug: str
    plan_code: PlanCode
    status: OrganizationStatus
    entitlements: Entitlements
    usage: dict[str, dict[UsageKey, int]]
    trial_ends_at: datetime | None
    created_at: datetime


class Admin(BaseModel):
    """An animator, owner, or platform administrator."""

    model_config = ConfigDict(frozen=True)

    id: str
    organization_id: str | None
    email: str
    email_verified: bool
    password_hash: str
    role: AdminRole
    totp_secret_enc: str | None
    created_at: datetime


class OrganizationCreate(BaseModel):
    """Input for creating a trial or platform-managed organization."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(pattern=r"^[a-z0-9-]{2,60}$")
    plan_code: PlanCode = "trial"
    entitlement_overrides: dict[str, object] | None = None
    trial_ends_at: datetime | None = None


class AdminCreate(BaseModel):
    """Input for creating an owner or animator; tenant value is never trusted."""

    model_config = ConfigDict(frozen=True)

    email: str
    password_hash: str
    email_verified: bool = False
    organization_id: str | None = None
