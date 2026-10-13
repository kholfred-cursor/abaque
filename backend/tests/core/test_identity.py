"""Tests for email normalization and typed identities (D023)."""

from __future__ import annotations

import pytest

from app.core.identity import (
    EmailIdentity,
    InvalidEmailError,
    ParticipantIdentity,
    normalize_email,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Alice@Example.COM", "alice@example.com"),
        ("  bob@example.com\u00a0", "bob@example.com"),
        ("\uff23\uff21\uff32\uff2f\uff2c@example.com", "carol@example.com"),
        ("dave+tag@example.com", "dave+tag@example.com"),
        ("e.v.e@example.com", "e.v.e@example.com"),
    ],
)
def test_normalize_email(raw: str, expected: str) -> None:
    """NFKC, outer whitespace stripped, local part casefolded, aliases kept."""
    assert normalize_email(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "a b@example.com", "a\tb@example.com", "not-an-email"])
def test_normalize_email_rejects_invalid_input(raw: str) -> None:
    """Empty, internal whitespace and invalid syntax are rejected."""
    with pytest.raises(InvalidEmailError):
        normalize_email(raw)


def test_invalid_email_error_never_echoes_the_address() -> None:
    """Error messages must not leak the submitted address."""
    with pytest.raises(InvalidEmailError) as error:
        normalize_email("secret.person@@example.com")
    assert "secret.person" not in str(error.value)


def test_identities_expose_kind_and_value() -> None:
    """EmailIdentity normalizes at construction; kinds never collide."""
    email = EmailIdentity("Alice@Example.com")
    participant = ParticipantIdentity("p-123")
    assert (email.kind, email.value) == ("email", "alice@example.com")
    assert (participant.kind, participant.value) == ("pid", "p-123")
