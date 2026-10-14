"""Vote domain models: public view of a version and anonymous ballot records. Lot 1."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.domain.content import ColorKey, Evaluation, VersionContent

CommentStatus = Literal["published", "hidden", "flagged"]
COMMENT_MAX = 2000


class PublicView(BaseModel):
    """What the public link resolves to. The organization id never leaves the backend."""

    model_config = ConfigDict(frozen=True)

    organization_id: str
    evaluation: Evaluation
    content: VersionContent | None  # None: no open version
    max_ballots: int | None


class VoteRecord(BaseModel):
    """One answer as stored: no identity, no time (section 6.3)."""

    model_config = ConfigDict(frozen=True)

    item_id: str
    color_key: ColorKey
    comment: str | None
    comment_status: CommentStatus


class BallotRecord(BaseModel):
    """A ballot as read for an export: its votes by item id, nothing else."""

    model_config = ConfigDict(frozen=True)

    votes: dict[str, VoteRecord]


class VersionClosed(Exception):  # noqa: N818
    """The version is not open (closed, archived, or another version is now open)."""


class BallotQuotaFull(Exception):  # noqa: N818
    """max_ballots_per_version reached."""


class ContentChanged(Exception):  # noqa: N818
    """A vote references an item that is not in the version."""
