"""Domain errors translated to HTTP responses only by the API layer."""

from __future__ import annotations


class NotFound(Exception):  # noqa: N818
    """Raised for an absent resource or a resource outside the tenant scope."""


class TenantScopeError(ValueError):
    """Raised when a caller tries to override the authenticated organization scope."""


class AlreadyConsumed(Exception):  # noqa: N818
    """Raised when a single-use credential or token has already been consumed."""
