"""Public anonymous vote (section 7, anonymous mode; D040). Lot 2 adds the two other modes."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime

from app.anonymity.detection import is_identifying
from app.core.config import Settings
from app.core.security import hash_ip
from app.domain.content import ColorKey
from app.domain.errors import RuleViolation
from app.domain.vote import (
    BallotQuotaFull,
    ContentChanged,
    PublicView,
    VersionClosed,
    VoteRecord,
)
from app.entitlements.checker import LimitReached
from app.repositories.mongo.store import MongoStore
from app.services.rate_limit import RateLimiter

# A whole room may share one public IP (NAT): the limit only stops scripted floods.
VOTES_PER_IP_PER_HOUR = 300
HOUR = 3600
VOTED_COOKIE_DAYS = 180

CLOSED = RuleViolation(
    409, "VERSION_CLOSED", "Cette consultation est close, votre réponse n'a pas été enregistrée."
)
ALREADY_VOTED = RuleViolation(409, "ALREADY_VOTED", "Votre vote a déjà été enregistré.")


def voted_cookie_name(version_id: str) -> str:
    return f"abq_v_{version_id}"


def rate_key_prefix(version_id: str) -> str:
    return f"vote:{version_id}:"


@dataclass(frozen=True)
class VoteInput:
    item_id: str
    color_key: ColorKey
    comment: str | None


@dataclass(frozen=True)
class VotedCookie:
    name: str
    value: str
    max_age: int


class VoteService:
    def __init__(self, store: MongoStore, settings: Settings, rate_limiter: RateLimiter) -> None:
        self.repository = store.public_vote()
        self.settings = settings
        self.rate_limiter = rate_limiter

    async def view(self, slug: str) -> PublicView:
        return await self.repository.find_by_slug(slug)

    async def submit(
        self,
        slug: str,
        version_id: str,
        votes: list[VoteInput],
        client_ip: str,
        cookies: dict[str, str],
    ) -> VotedCookie:
        if not votes:
            raise RuleViolation(400, "EMPTY_BALLOT", "Répondez à au moins un item avant d'envoyer.")
        if len({vote.item_id for vote in votes}) != len(votes):
            raise RuleViolation(400, "DUPLICATE_ITEM", "Un item ne peut recevoir qu'une réponse.")
        if voted_cookie_name(version_id) in cookies:
            raise ALREADY_VOTED

        key = rate_key_prefix(version_id) + hash_ip(
            client_ip, self.settings.IP_HASH_SALT.get_secret_value()
        )
        wait = await self.rate_limiter.retry_after(key, VOTES_PER_IP_PER_HOUR, HOUR)
        if wait is not None:
            raise RuleViolation(
                429, "RATE_LIMITED", "Trop d'envois depuis ce réseau. Réessayez plus tard."
            )
        await self.rate_limiter.record(key, HOUR)

        view = await self.repository.find_by_slug(slug)
        records = [
            VoteRecord(
                item_id=vote.item_id,
                color_key=vote.color_key,
                comment=vote.comment,
                comment_status=(
                    "flagged" if vote.comment and is_identifying(vote.comment) else "published"
                ),
            )
            for vote in votes
        ]
        now = datetime.now(UTC)
        try:
            await self.repository.submit_anonymous(
                view.organization_id,
                view.evaluation.id,
                version_id,
                view.max_ballots,
                records,
                now.strftime("%Y-%m-%d"),
            )
        except VersionClosed as exc:
            raise CLOSED from exc
        except BallotQuotaFull as exc:
            raise LimitReached("max_ballots_per_version") from exc
        except ContentChanged as exc:
            raise RuleViolation(
                409, "CONTENT_CHANGED", "Le questionnaire a changé : rechargez la page."
            ) from exc
        await self.repository.count_ballot_usage(view.organization_id, now.strftime("%Y-%m"))
        return VotedCookie(
            name=voted_cookie_name(version_id),
            value=secrets.token_urlsafe(16),  # random, carries nothing (D040)
            max_age=VOTED_COOKIE_DAYS * 24 * 3600,
        )
