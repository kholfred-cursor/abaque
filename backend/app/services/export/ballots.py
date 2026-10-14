"""Exports (section 12). Lot 1: export 2, ballots without segments.

Ballots are read only here (and in restitution), through BallotReaderPort, and every
output goes through app.anonymity first.
"""

from __future__ import annotations

import random
import re

from app.anonymity.threshold import BelowThreshold, check_global
from app.domain.content import scale_labels
from app.domain.errors import RuleViolation
from app.domain.models import TenantContext
from app.domain.ports import BallotReaderPort
from app.entitlements.checker import check_feature
from app.repositories.mongo.store import MongoStore
from app.services.csv_format import write_csv

BALLOTS_HEADER = (
    "ballot_ref",
    "item_position",
    "item_short_name",
    "color_key",
    "color_label",
    "comment",
)
NOT_EXPRESSED = "non exprimé"
_SYSTEM_RANDOM = random.SystemRandom()


def _file_part(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", value).strip("-") or "version"


class ExportService:
    def __init__(self, store: MongoStore, tenant: TenantContext) -> None:
        self.content = store.content(tenant)
        self.organizations = store.organizations(tenant)
        self.ballots: BallotReaderPort = store.ballot_reader(tenant)

    async def ballots_csv(self, version_id: str) -> tuple[str, bytes]:
        """Export 2: one line per ballot x item; never a segment, group, date or order."""
        check_feature(await self.organizations.get_entitlements(), "csv_export")
        content = await self.content.get_content(version_id)
        evaluation = await self.content.get_evaluation(content.version.evaluation_id)
        try:
            check_global(content.version.ballot_count, evaluation.anonymity_threshold)
        except BelowThreshold as exc:
            raise RuleViolation(
                409,
                "BELOW_THRESHOLD",
                f"Export indisponible : il faut au moins {evaluation.anonymity_threshold} "
                "réponses pour protéger l'anonymat.",
            ) from exc

        labels = scale_labels(evaluation.vote_preset, content.color_labels)
        items = [item for group in content.groups for item in group.items]
        ballots = list(await self.ballots.list_by_rand_key(version_id))
        # Fresh randomness at every generation: the order of the ballots AND the reference
        # given to each one are drawn independently, so nothing derives from rand_key,
        # from the ballot id or from a previous file.
        _SYSTEM_RANDOM.shuffle(ballots)
        numbers = list(range(1, len(ballots) + 1))
        _SYSTEM_RANDOM.shuffle(numbers)
        width = max(3, len(str(len(ballots))))

        rows: list[tuple[str, ...]] = []
        for ballot, number in zip(ballots, numbers, strict=True):
            reference = f"B{number:0{width}d}"
            for position, item in enumerate(items, start=1):
                vote = ballot.votes.get(item.id)
                if vote is None:
                    rows.append((reference, str(position), item.short_name, "", NOT_EXPRESSED, ""))
                    continue
                comment = vote.comment if vote.comment_status == "published" else None
                rows.append(
                    (
                        reference,
                        str(position),
                        item.short_name,
                        vote.color_key,
                        labels[vote.color_key],
                        comment or "",
                    )
                )
        await self.content.record_event(version_id, "export_ballots")
        filename = f"abaque_{evaluation.slug}_{_file_part(content.version.label)}_ballots.csv"
        return filename, write_csv(BALLOTS_HEADER, rows)
