"""Provisional default entitlements by plan code."""

from __future__ import annotations

from app.entitlements.models import Entitlements

# TODO tarifs: these MVP values must be replaced by the commercial catalogue.
PLAN_DEFAULTS: dict[str, Entitlements] = {
    "trial": Entitlements(
        max_active_evaluations=1,
        max_ballots_per_version=30,
        max_animators=1,
        modes_allowed=("anonymous",),
        pdf_export=True,
        csv_export=True,
        email_invitations=False,
        custom_branding=False,
        retention_months=1,
    ),
    "demo": Entitlements(
        max_active_evaluations=1,
        max_ballots_per_version=300,
        max_animators=1,
        modes_allowed=("anonymous",),
        pdf_export=True,
        csv_export=True,
        email_invitations=False,
        custom_branding=False,
        retention_months=1,
    ),
    "standard": Entitlements(
        max_active_evaluations=100,
        max_ballots_per_version=10_000,
        max_animators=20,
        modes_allowed=("anonymous", "auth_open", "auth_closed"),
        pdf_export=True,
        csv_export=True,
        email_invitations=True,
        custom_branding=True,
        retention_months=12,
    ),
}
