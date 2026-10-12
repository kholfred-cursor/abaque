"""Repository protocols keeping the domain independent from MongoDB."""

from __future__ import annotations

from typing import Any, Protocol

from app.domain.models import Admin, AdminCreate, Organization, OrganizationCreate, UsageKey
from app.entitlements.models import Entitlements


class OrganizationProvisioningPort(Protocol):
    """Signup only: creates a tenant and its owner atomically, outside any tenant scope."""

    async def create_with_owner(
        self, organization: OrganizationCreate, owner: AdminCreate
    ) -> tuple[Organization, Admin]: ...


class OrganizationRepositoryPort(Protocol):
    """The authenticated tenant's own organization (lot 0)."""

    async def get_current(self, session: object | None = None) -> Organization: ...

    async def get_entitlements(self, session: object | None = None) -> Entitlements: ...

    async def increment_usage(
        self, month: str, key: UsageKey, increment: int, session: object | None = None
    ) -> None: ...


class AdminRepositoryPort(Protocol):
    """Organization-scoped administrator persistence operations."""

    async def get(self, admin_id: str, session: object | None = None) -> Admin: ...

    async def list(self, session: object | None = None) -> list[Admin]: ...

    async def create_animator(
        self,
        animator: AdminCreate,
        entitlements: Entitlements,
        session: object | None = None,
    ) -> Admin: ...


class AdminAuthRepositoryPort(Protocol):
    """Explicitly non-tenant-scoped operations used only by authentication."""

    async def find_by_email(self, email: str, session: object | None = None) -> Admin | None: ...

    async def create_owner(
        self, organization_id: str, owner: AdminCreate, session: object | None = None
    ) -> Admin: ...

    async def mark_email_verified(self, admin_id: str, session: object | None = None) -> Admin: ...

    async def set_password_hash(
        self, admin_id: str, password_hash: str, session: object | None = None
    ) -> Admin: ...


# ── Interfaces frozen at lot 0, implemented later (signatures only) ──
# Payloads are typed as Mapping/Any until their domain models arrive with each lot.


class AdminSessionRepositoryPort(Protocol):
    """Lot 0, block 4b: refresh-token sessions (lookup by token hash, outside tenant scope)."""

    async def create(
        self, admin_id: str, token_hash: str, session: object | None = None
    ) -> str: ...

    async def rotate(
        self, old_token_hash: str, new_token_hash: str, session: object | None = None
    ) -> str | None: ...

    async def revoke(self, token_hash: str, session: object | None = None) -> None: ...

    async def revoke_all_for_admin(self, admin_id: str, session: object | None = None) -> int: ...

    async def find_by_hash(self, token_hash: str, session: object | None = None) -> Any | None: ...

    async def mark_consumed(self, token_hash: str, session: object | None = None) -> bool: ...


class AuthTokenRepositoryPort(Protocol):
    """Lot 0, block 4b: single-use admin tokens (email verification, password reset)."""

    async def create(
        self, admin_id: str, purpose: str, token_hash: str, session: object | None = None
    ) -> None: ...

    async def consume(
        self, token_hash: str, purpose: str, session: object | None = None
    ) -> str | None: ...


class EvaluationRepositoryPort(Protocol):
    """Lot 1."""

    async def get(self, evaluation_id: str, session: object | None = None) -> Any: ...

    async def list(self, session: object | None = None) -> list[Any]: ...


class VersionRepositoryPort(Protocol):
    """Lot 1."""

    async def get(self, version_id: str, session: object | None = None) -> Any: ...


class ItemRepositoryPort(Protocol):
    """Lot 1."""

    async def list_for_version(
        self, version_id: str, session: object | None = None
    ) -> list[Any]: ...


class SegmentQuestionRepositoryPort(Protocol):
    """Lot 1."""

    async def list_for_version(
        self, version_id: str, session: object | None = None
    ) -> list[Any]: ...


class GeneralQuestionRepositoryPort(Protocol):
    """Lot 1."""

    async def list_for_version(
        self, version_id: str, session: object | None = None
    ) -> list[Any]: ...


class BallotWriterPort(Protocol):
    """Lot 2. The ONLY write path for ballots, called inside the vote transaction.

    No unit update or delete exists by design; only whole-version purge.
    """

    async def write_ballot(self, ballot: Any, session: object) -> None: ...

    async def purge_version(self, version_id: str, session: object | None = None) -> int: ...


class BallotReaderPort(Protocol):
    """Lot 2. Ballots are only ever returned sorted by rand_key (never by _id or natural order).

    Importable only by app.anonymity, app.services.restitution and app.services.export.
    """

    async def list_by_rand_key(
        self, version_id: str, session: object | None = None
    ) -> list[Any]: ...


class CredentialUseRepositoryPort(Protocol):
    """Lot 2. Consumption marker only: no read by fingerprint exists by design."""

    async def consume(
        self, version_id: str, fingerprint: str, key_id: str, day: str, session: object
    ) -> None: ...  # raises AlreadyConsumed

    async def purge_version(self, version_id: str, session: object | None = None) -> int: ...


class ParticipantRepositoryPort(Protocol):
    """Lot 3."""

    async def get(self, participant_id: str, session: object | None = None) -> Any: ...


class ParticipantLinkRepositoryPort(Protocol):
    """Lot 3. Magic links consumed by deletion (no used_at)."""

    async def consume(self, token_hash: str, session: object | None = None) -> Any | None: ...

    async def purge_version(self, version_id: str, session: object | None = None) -> int: ...
