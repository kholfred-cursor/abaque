"""Pure entitlement resolution and guard functions."""

from __future__ import annotations

from typing import Any, Literal

from app.entitlements.models import Entitlements, ParticipationMode
from app.entitlements.plans import PLAN_DEFAULTS

LimitKey = Literal["max_active_evaluations", "max_ballots_per_version", "max_animators"]
FeatureKey = Literal["pdf_export", "csv_export", "email_invitations", "custom_branding"]


class LimitReached(Exception):  # noqa: N818
    """Raised when an organization has consumed its plan quota."""

    message = "Limite de votre offre atteinte"

    def __init__(self, key: LimitKey) -> None:
        super().__init__(self.message)
        self.key = key


class FeatureNotAllowed(Exception):  # noqa: N818
    """Raised when a plan does not allow a requested feature or mode."""

    message = "Fonctionnalité non disponible avec votre offre"

    def __init__(self, key: str) -> None:
        super().__init__(self.message)
        self.key = key


def resolve(plan_code: str, overrides: dict[str, Any] | None = None) -> Entitlements:
    """Resolve a plan and optional organization-specific entitlement overrides."""
    try:
        default = PLAN_DEFAULTS[plan_code]
    except KeyError as exc:
        raise ValueError("Unknown plan code") from exc
    values = default.model_dump()
    if overrides is not None:
        values.update(overrides)
    return Entitlements.model_validate(values)


def get_limit(entitlements: Entitlements, key: LimitKey) -> int | None:
    """Return a quota, where ``None`` represents an unlimited entitlement."""
    if key == "max_active_evaluations":
        return entitlements.max_active_evaluations
    if key == "max_ballots_per_version":
        return entitlements.max_ballots_per_version
    return entitlements.max_animators


def check_limit(entitlements: Entitlements, key: LimitKey, current: int) -> None:
    """Raise when the current count has reached the configured quota."""
    maximum = get_limit(entitlements, key)
    if maximum is not None and current >= maximum:
        raise LimitReached(key)


def check_feature(entitlements: Entitlements, key: FeatureKey) -> None:
    """Raise when a boolean plan feature is disabled."""
    if not getattr(entitlements, key):
        raise FeatureNotAllowed(key)


def check_mode(entitlements: Entitlements, mode: ParticipationMode) -> None:
    """Raise when a participation mode is not included in the plan."""
    if mode not in entitlements.modes_allowed:
        raise FeatureNotAllowed(mode)
