"""Pure entitlement domain model."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ParticipationMode = Literal["anonymous", "auth_open", "auth_closed"]


class Entitlements(BaseModel):
    """Capabilities and quotas resolved for one organization."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_active_evaluations: int | None = Field(default=None, ge=0)
    max_ballots_per_version: int | None = Field(default=None, ge=0)
    max_animators: int | None = Field(default=None, ge=0)
    modes_allowed: tuple[ParticipationMode, ...]
    pdf_export: bool
    csv_export: bool
    email_invitations: bool
    custom_branding: bool
    retention_months: int | None = Field(default=None, ge=1)
