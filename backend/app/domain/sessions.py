"""Domain model and error for administrator refresh sessions."""

from __future__ import annotations

from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict


class AdminSession(BaseModel):
    """One refresh-token session without raw MongoDB implementation values."""

    model_config = ConfigDict(frozen=True)

    id: str
    admin_id: str
    token_hash: str
    expires_at: datetime
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None
    consumed_at: datetime | None
    user_agent_hint: str | None


class SessionReuseDetected(Exception):  # noqa: N818
    """Raised when an already consumed refresh token is presented again."""

    def __init__(self, admin_id: str) -> None:
        super().__init__("Refresh token reuse detected")
        self.admin_id = admin_id


# A refresh token presented again within this window after its rotation is treated as a
# benign race (two tabs refreshing at once): the caller gets ConcurrentRotation and simply
# retries with the cookie set by the winning request. Beyond the window it is a replay
# (likely theft) and every session of the administrator is revoked (D029).
ROTATION_GRACE = timedelta(seconds=10)


class ConcurrentRotation(Exception):  # noqa: N818
    """Raised when a refresh token was rotated moments ago by a concurrent request."""
