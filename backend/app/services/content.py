"""Evaluations, versions and their content: the business rules of lot 1 (D035 to D043)."""

from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime
from typing import Any, Literal

from app.core.config import Settings
from app.domain.content import (
    COLOR_ORDER,
    LABEL_MAX,
    MAX_GROUPS_PER_VERSION,
    MAX_ITEMS_PER_VERSION,
    ColorKey,
    Evaluation,
    EvaluationCreate,
    GroupInput,
    ParticipationMode,
    TransitionAction,
    Version,
    VersionContent,
    VotePreset,
    as_inputs,
)
from app.domain.errors import (
    AnotherVersionOpen,
    ContentConflict,
    ContentLocked,
    InvalidTransition,
    RuleViolation,
)
from app.domain.models import TenantContext
from app.entitlements.checker import LimitReached, check_mode, get_limit
from app.repositories.mongo.content import QuotaFull, SlugTaken
from app.repositories.mongo.store import MongoStore
from app.services.csv_format import CsvImportError, items_csv, parse_items_csv

# No vowels-only ambiguity: no 0/o, 1/l (D036). 31^10 ≈ 8e14 possible slugs.
_SLUG_ALPHABET = "abcdefghijkmnpqrstuvwxyz23456789"
SLUG_LENGTH = 10
DEFAULT_GROUP = "Général"
TITLE_MAX = 300

LOCKED = RuleViolation(
    409,
    "CONTENT_LOCKED",
    "Le contenu de cette version est figé (elle a reçu des réponses ou elle est archivée). "
    "Dupliquez-la pour modifier les items.",
)
CONFLICT = RuleViolation(
    409,
    "CONTENT_CONFLICT",
    "Le contenu a été modifié ailleurs (autre onglet ?). Rechargez la page.",
)


def new_slug() -> str:
    return "".join(secrets.choice(_SLUG_ALPHABET) for _ in range(SLUG_LENGTH))


def _month() -> str:
    return datetime.now(UTC).strftime("%Y-%m")


def _safe_file_part(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", value).strip("-") or "version"


def _clean_labels(labels: dict[ColorKey, str]) -> dict[ColorKey, str]:
    cleaned: dict[ColorKey, str] = {}
    for key in COLOR_ORDER:
        value = (labels.get(key) or "").strip()
        if value:
            if len(value) > LABEL_MAX:
                raise RuleViolation(
                    400,
                    "INVALID_LABEL",
                    f"Un libellé d'échelle fait {LABEL_MAX} caractères au plus.",
                )
            cleaned[key] = value
    return cleaned


def _check_size(groups: list[GroupInput]) -> None:
    if len(groups) > MAX_GROUPS_PER_VERSION:
        raise RuleViolation(400, "TOO_MANY_GROUPS", f"{MAX_GROUPS_PER_VERSION} groupes au maximum.")
    if sum(len(group.items) for group in groups) > MAX_ITEMS_PER_VERSION:
        raise RuleViolation(400, "TOO_MANY_ITEMS", f"{MAX_ITEMS_PER_VERSION} items au maximum.")


class ContentService:
    def __init__(self, store: MongoStore, tenant: TenantContext, settings: Settings) -> None:
        self.repository = store.content(tenant)
        self.organizations = store.organizations(tenant)
        self.settings = settings

    # ── Evaluations ──────────────────────────────────────────────────────────

    async def list_all(self) -> list[tuple[Evaluation, list[Version]]]:
        return await self.repository.list_evaluations()

    async def get(self, evaluation_id: str) -> tuple[Evaluation, list[Version]]:
        evaluation = await self.repository.get_evaluation(evaluation_id)
        return evaluation, await self.repository.list_versions(evaluation_id)

    async def _create(
        self,
        data_without_slug: dict[str, Any],
        groups: list[GroupInput],
        labels: dict[ColorKey, str],
    ) -> tuple[Evaluation, Version]:
        entitlements = await self.organizations.get_entitlements()
        check_mode(entitlements, data_without_slug["participation_mode"])
        maximum = get_limit(entitlements, "max_active_evaluations")
        for _ in range(5):
            data = EvaluationCreate(slug=new_slug(), **data_without_slug)
            try:
                return await self.repository.create_evaluation(
                    data, "V1", groups, labels, _month(), maximum
                )
            except SlugTaken:
                continue
            except QuotaFull as exc:
                raise LimitReached("max_active_evaluations") from exc
        raise RuntimeError("could not draw a free public slug")  # pragma: no cover

    async def create(
        self,
        title: str,
        description: str | None,
        vote_preset: VotePreset,
        participation_mode: ParticipationMode,
    ) -> tuple[Evaluation, Version]:
        if participation_mode != "anonymous":  # D043
            raise RuleViolation(
                400,
                "MODE_NOT_AVAILABLE",
                "Seul le mode anonyme est disponible pour l'instant.",
            )
        return await self._create(
            {
                "title": title,
                "description": description,
                "participation_mode": participation_mode,
                "vote_preset": vote_preset,
            },
            [GroupInput(name=DEFAULT_GROUP)],
            {},
        )

    async def update(self, evaluation_id: str, changes: dict[str, Any]) -> Evaluation:
        evaluation = await self.repository.get_evaluation(evaluation_id)
        if (
            "anonymity_threshold" in changes
            and changes["anonymity_threshold"] < evaluation.anonymity_threshold
        ):
            raise RuleViolation(
                400, "THRESHOLD_DECREASE", "Le seuil d'anonymat ne peut être que relevé."
            )
        if (
            "vote_preset" in changes
            and changes["vote_preset"] != evaluation.vote_preset
            and await self.repository.evaluation_has_ballots(evaluation_id)
        ):
            raise RuleViolation(
                409,
                "PRESET_LOCKED",
                "L'échelle ne peut plus changer : des réponses ont déjà été reçues.",
            )
        if not changes:
            return evaluation
        return await self.repository.update_evaluation(evaluation_id, changes)

    async def delete(self, evaluation_id: str) -> None:
        await self.repository.delete_evaluation(evaluation_id)

    async def duplicate(self, evaluation_id: str) -> tuple[Evaluation, Version]:
        source, versions = await self.get(evaluation_id)
        content = await self.repository.get_content(versions[-1].id)
        suffix = " (copie)"
        return await self._create(
            {
                "title": source.title[: TITLE_MAX - len(suffix)] + suffix,
                "description": source.description,
                "participation_mode": source.participation_mode,
                "vote_preset": source.vote_preset,
                "intro_md": source.intro_md,
                "outro_md": source.outro_md,
                "show_vote_example": source.show_vote_example,
                "anonymity_threshold": source.anonymity_threshold,
            },
            as_inputs(content),
            content.color_labels,
        )

    # ── Versions ─────────────────────────────────────────────────────────────

    async def content(self, version_id: str) -> VersionContent:
        return await self.repository.get_content(version_id)

    async def save_content(
        self,
        version_id: str,
        revision: int,
        groups: list[GroupInput],
        color_labels: dict[ColorKey, str],
    ) -> VersionContent:
        _check_size(groups)
        try:
            return await self.repository.replace_content(
                version_id, revision, groups, _clean_labels(color_labels)
            )
        except ContentLocked as exc:
            raise LOCKED from exc
        except ContentConflict as exc:
            raise CONFLICT from exc

    async def duplicate_version(self, version_id: str) -> Version:
        return await self.repository.duplicate_version(version_id)

    async def transition(self, version_id: str, action: TransitionAction) -> Version:
        if action in ("open", "reopen"):
            content = await self.repository.get_content(version_id)
            if not any(group.items for group in content.groups):
                raise RuleViolation(
                    409, "NO_ITEMS", "Ajoutez au moins un item avant d'ouvrir le vote."
                )
        try:
            return await self.repository.transition(
                version_id, action, self.settings.credential_key_id
            )
        except InvalidTransition as exc:
            raise RuleViolation(
                409, "INVALID_TRANSITION", "Cette action n'est pas possible dans l'état actuel."
            ) from exc
        except AnotherVersionOpen as exc:
            raise RuleViolation(
                409,
                "ANOTHER_VERSION_OPEN",
                "Une autre version de cette évaluation est déjà ouverte. Clôturez-la d'abord.",
            ) from exc

    async def export_items(self, version_id: str) -> tuple[str, bytes]:
        content = await self.repository.get_content(version_id)
        evaluation = await self.repository.get_evaluation(content.version.evaluation_id)
        name = f"abaque_{evaluation.slug}_{_safe_file_part(content.version.label)}_items.csv"
        return name, items_csv(as_inputs(content))

    async def import_items(
        self,
        version_id: str,
        revision: int,
        text: str,
        mode: Literal["replace", "append"],
    ) -> VersionContent:
        try:
            imported = parse_items_csv(text)
        except CsvImportError as exc:
            raise RuleViolation(400, "CSV_INVALID", str(exc)) from exc
        current = await self.repository.get_content(version_id)
        if mode == "replace":
            groups = imported
        else:  # append: merge into existing groups of the same name, keep ids
            groups = [GroupInput.model_validate(group.model_dump()) for group in current.groups]
            by_name = {group.name: index for index, group in enumerate(groups)}
            for group in imported:
                if group.name in by_name:
                    existing = groups[by_name[group.name]]
                    groups[by_name[group.name]] = GroupInput(
                        id=existing.id, name=existing.name, items=[*existing.items, *group.items]
                    )
                else:
                    by_name[group.name] = len(groups)
                    groups.append(group)
        return await self.save_content(version_id, revision, groups, current.color_labels)
