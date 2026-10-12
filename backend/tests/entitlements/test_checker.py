"""Unit tests for plan resolution and entitlement enforcement."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.entitlements.checker import (
    FeatureNotAllowed,
    LimitReached,
    check_feature,
    check_limit,
    check_mode,
    get_limit,
    resolve,
)


def test_trial_defaults_and_partial_override_are_resolved_without_mutating_the_plan() -> None:
    """Overrides apply to one resolved organization without changing shared defaults."""
    customized = resolve("trial", {"max_animators": 3})
    untouched = resolve("trial")

    assert customized.max_active_evaluations == 1
    assert customized.max_animators == 3
    assert customized.modes_allowed == ("anonymous",)
    assert untouched.max_animators == 1


def test_unlimited_limit_allows_any_current_count() -> None:
    """A None quota represents an unlimited plan capability."""
    entitlements = resolve("standard", {"max_animators": None})

    assert get_limit(entitlements, "max_animators") is None
    check_limit(entitlements, "max_animators", 1_000_000)


def test_limit_is_rejected_at_the_configured_boundary() -> None:
    """A limit is unavailable once its current count reaches the quota."""
    entitlements = resolve("trial")

    check_limit(entitlements, "max_animators", 0)
    with pytest.raises(LimitReached, match="Limite de votre offre atteinte"):
        check_limit(entitlements, "max_animators", 1)


def test_disabled_features_and_modes_are_rejected() -> None:
    """Trial cannot use invitation emails or authenticated participation modes."""
    entitlements = resolve("trial")

    with pytest.raises(FeatureNotAllowed):
        check_feature(entitlements, "email_invitations")
    with pytest.raises(FeatureNotAllowed):
        check_mode(entitlements, "auth_open")


def test_entitlements_module_has_no_database_or_web_framework_dependency() -> None:
    """The entitlement layer stays portable and pure Python."""
    directory = Path(__file__).parents[2] / "app" / "entitlements"
    source = "\n".join(path.read_text(encoding="utf-8") for path in directory.glob("*.py"))

    assert "pymongo" not in source
    assert "fastapi" not in source
