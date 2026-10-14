"""Domain errors translated to HTTP responses only by the API layer."""

from __future__ import annotations


class NotFound(Exception):  # noqa: N818
    """Raised for an absent resource or a resource outside the tenant scope."""


class TenantScopeError(ValueError):
    """Raised when a caller tries to override the authenticated organization scope."""


class AlreadyConsumed(Exception):  # noqa: N818
    """Raised when a single-use credential or token has already been consumed."""


class EmailAlreadyRegistered(Exception):  # noqa: N818
    """Raised by signup when the (normalized) email already has an account."""


class InvalidTransition(Exception):  # noqa: N818
    """Raised when a version lifecycle action is not allowed from its current status."""


class AnotherVersionOpen(Exception):  # noqa: N818
    """Raised when opening a version while another version of the evaluation is open."""


class ContentLocked(Exception):  # noqa: N818
    """Raised when editing content of a version that has ballots or is archived."""


class ContentConflict(Exception):  # noqa: N818
    """Raised when the content was saved elsewhere since the editor loaded it."""


class RuleViolation(Exception):  # noqa: N818
    """A business rule refused the request; carries its HTTP status, code and message."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
