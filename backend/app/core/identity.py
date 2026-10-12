"""Email normalization and identity types for credential fingerprinting.

This module is pure Python with a single external dependency (email-validator).
It is the ONLY place where email normalization happens.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from email_validator import EmailNotValidError, validate_email


class InvalidEmailError(ValueError):
    """Raised when an email address is syntactically invalid."""


@dataclass(frozen=True, slots=True)
class EmailIdentity:
    """An identity based on a normalized email address."""

    email: str

    def __post_init__(self) -> None:
        """Normalize email at construction time."""
        object.__setattr__(self, "email", normalize_email(self.email))

    @property
    def kind(self) -> str:
        return "email"

    @property
    def value(self) -> str:
        return self.email


@dataclass(frozen=True, slots=True)
class ParticipantIdentity:
    """An identity based on a participant_id (auth_closed without email)."""

    participant_id: str

    @property
    def kind(self) -> str:
        return "pid"

    @property
    def value(self) -> str:
        return self.participant_id


type Identity = EmailIdentity | ParticipantIdentity


def normalize_email(raw: str) -> str:
    """Normalize an email address for consistent comparison and storage.

    Steps:
    1. Unicode NFKC normalization
    2. Strip leading/trailing whitespace (including non-breaking spaces)
    3. Reject if internal whitespace is present
    4. Validate and normalize via email-validator (IDNA 2008, syntax check)
    5. Casefold local part + ascii domain from email-validator

    This function is the SOLE normalizer. Every code path that compares
    or stores an email must call this function.

    Raises InvalidEmailError on invalid input.
    Does NOT include the raw address in error messages.
    """
    normalized = unicodedata.normalize("NFKC", raw)

    stripped = normalized.strip()
    while stripped and unicodedata.category(stripped[0]).startswith("Z"):
        stripped = stripped[1:]
    while stripped and unicodedata.category(stripped[-1]).startswith("Z"):
        stripped = stripped[:-1]

    if not stripped:
        raise InvalidEmailError("L'adresse e-mail est vide.")

    for ch in stripped:
        if unicodedata.category(ch).startswith("Z") or ch in ("\t", "\n", "\r"):
            raise InvalidEmailError("L'adresse e-mail contient des espaces.")

    try:
        result = validate_email(stripped, check_deliverability=False)
    except EmailNotValidError as exc:
        raise InvalidEmailError("L'adresse e-mail n'est pas valide.") from exc

    # Casefold local part (NOT removing +tags or dots: see DECISIONS D023)
    local_part = result.local_part.casefold()
    domain = result.ascii_domain

    return f"{local_part}@{domain}"
