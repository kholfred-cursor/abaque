"""Animator routes for evaluations, versions and their content. Lot 1."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.api.deps import ContentDep, ExportDep
from app.api.errors import responses
from app.domain.content import (
    COLOR_ORDER,
    ColorKey,
    Evaluation,
    GroupInput,
    ParticipationMode,
    TransitionAction,
    Version,
    VersionContent,
    VersionStatus,
    VotePreset,
    scale_labels,
)
from app.domain.errors import RuleViolation
from app.services.csv_format import MAX_IMPORT_CHARS

router = APIRouter(tags=["evaluations"])

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]
Markdown = Annotated[str, StringConstraints(max_length=10000)]
_CSV: dict[int | str, dict[str, Any]] = {
    200: {"content": {"text/csv": {"schema": {"type": "string"}}}}
}


class VersionSummary(BaseModel):
    id: str
    label: str
    status: VersionStatus
    ballot_count: int


class EvaluationSummary(BaseModel):
    id: str
    title: str
    slug: str
    participation_mode: ParticipationMode
    vote_preset: VotePreset
    created_at: datetime
    versions: list[VersionSummary]


class EvaluationDetail(EvaluationSummary):
    description: str | None
    intro_md: str | None
    outro_md: str | None
    show_vote_example: bool
    anonymity_threshold: int


class EvaluationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title
    description: Description | None = None
    vote_preset: VotePreset = "agreement"
    participation_mode: ParticipationMode = "anonymous"


class EvaluationUpdateRequest(BaseModel):
    """Only the fields sent are changed."""

    model_config = ConfigDict(extra="forbid")

    title: Title | None = None
    description: Description | None = None
    intro_md: Markdown | None = None
    outro_md: Markdown | None = None
    show_vote_example: bool | None = None
    vote_preset: VotePreset | None = None
    anonymity_threshold: int | None = Field(default=None, ge=3, le=50)


class ScaleEntry(BaseModel):
    key: ColorKey
    label: str


class ItemView(BaseModel):
    id: str
    short_name: str
    statement: str


class GroupView(BaseModel):
    id: str
    name: str
    items: list[ItemView]


class VersionDetail(VersionSummary):
    evaluation_id: str
    revision: int
    editable: bool


class VersionContentResponse(BaseModel):
    version: VersionDetail
    vote_preset: VotePreset
    groups: list[GroupView]
    color_labels: dict[ColorKey, str]
    scale: list[ScaleEntry]


class ContentSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision: int = Field(ge=0)
    groups: list[GroupInput]
    color_labels: dict[ColorKey, str] = Field(default_factory=dict)


class TransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: TransitionAction


class ItemsImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision: int = Field(ge=0)
    csv: str = Field(max_length=MAX_IMPORT_CHARS)
    mode: Literal["replace", "append"] = "replace"


def _version_summary(version: Version) -> VersionSummary:
    return VersionSummary(
        id=version.id, label=version.label, status=version.status, ballot_count=version.ballot_count
    )


def _summary(evaluation: Evaluation, versions: list[Version]) -> EvaluationSummary:
    return EvaluationSummary(
        id=evaluation.id,
        title=evaluation.title,
        slug=evaluation.slug,
        participation_mode=evaluation.participation_mode,
        vote_preset=evaluation.vote_preset,
        created_at=evaluation.created_at,
        versions=[_version_summary(version) for version in versions],
    )


def _detail(evaluation: Evaluation, versions: list[Version]) -> EvaluationDetail:
    return EvaluationDetail(
        **_summary(evaluation, versions).model_dump(),
        description=evaluation.description,
        intro_md=evaluation.intro_md,
        outro_md=evaluation.outro_md,
        show_vote_example=evaluation.show_vote_example,
        anonymity_threshold=evaluation.anonymity_threshold,
    )


async def _content_response(service: ContentDep, content: VersionContent) -> VersionContentResponse:
    version = content.version
    evaluation, _ = await service.get(version.evaluation_id)
    labels = scale_labels(evaluation.vote_preset, content.color_labels)
    return VersionContentResponse(
        version=VersionDetail(
            **_version_summary(version).model_dump(),
            evaluation_id=version.evaluation_id,
            revision=version.content_revision,
            editable=version.ballot_count == 0 and version.status != "archived",
        ),
        vote_preset=evaluation.vote_preset,
        groups=[
            GroupView(
                id=group.id,
                name=group.name,
                items=[ItemView(**item.model_dump()) for item in group.items],
            )
            for group in content.groups
        ],
        color_labels=content.color_labels,
        scale=[ScaleEntry(key=key, label=labels[key]) for key in COLOR_ORDER],
    )


# ── Evaluations ──────────────────────────────────────────────────────────────

_EVAL_ERRORS = responses(401, 403, 404)


@router.get("/evaluations", response_model=list[EvaluationSummary], responses=_EVAL_ERRORS)
async def list_evaluations(service: ContentDep) -> list[EvaluationSummary]:
    return [_summary(evaluation, versions) for evaluation, versions in await service.list_all()]


@router.post(
    "/evaluations",
    status_code=201,
    response_model=EvaluationDetail,
    responses=responses(400, 401, 403),
)
async def create_evaluation(body: EvaluationCreateRequest, service: ContentDep) -> EvaluationDetail:
    evaluation, version = await service.create(
        body.title, body.description, body.vote_preset, body.participation_mode
    )
    return _detail(evaluation, [version])


@router.get("/evaluations/{evaluation_id}", response_model=EvaluationDetail, responses=_EVAL_ERRORS)
async def get_evaluation(evaluation_id: str, service: ContentDep) -> EvaluationDetail:
    return _detail(*await service.get(evaluation_id))


@router.patch(
    "/evaluations/{evaluation_id}",
    response_model=EvaluationDetail,
    responses=responses(400, 401, 403, 404, 409),
)
async def update_evaluation(
    evaluation_id: str, body: EvaluationUpdateRequest, service: ContentDep
) -> EvaluationDetail:
    changes: dict[str, Any] = body.model_dump(exclude_unset=True)
    required = ("title", "show_vote_example", "vote_preset", "anonymity_threshold")
    if any(changes.get(key, "") is None for key in required):
        raise RuleViolation(400, "INVALID_FIELD", "Un champ obligatoire ne peut pas être vide.")
    await service.update(evaluation_id, changes)
    return _detail(*await service.get(evaluation_id))


@router.delete("/evaluations/{evaluation_id}", status_code=204, responses=_EVAL_ERRORS)
async def delete_evaluation(evaluation_id: str, service: ContentDep) -> Response:
    await service.delete(evaluation_id)
    return Response(status_code=204)


@router.post(
    "/evaluations/{evaluation_id}/duplicate",
    status_code=201,
    response_model=EvaluationDetail,
    responses=_EVAL_ERRORS,
)
async def duplicate_evaluation(evaluation_id: str, service: ContentDep) -> EvaluationDetail:
    evaluation, version = await service.duplicate(evaluation_id)
    return _detail(evaluation, [version])


# ── Versions ─────────────────────────────────────────────────────────────────


@router.get("/versions/{version_id}", response_model=VersionContentResponse, responses=_EVAL_ERRORS)
async def get_version(version_id: str, service: ContentDep) -> VersionContentResponse:
    return await _content_response(service, await service.content(version_id))


@router.put(
    "/versions/{version_id}/content",
    response_model=VersionContentResponse,
    responses=responses(400, 401, 403, 404, 409),
)
async def save_version_content(
    version_id: str, body: ContentSaveRequest, service: ContentDep
) -> VersionContentResponse:
    content = await service.save_content(version_id, body.revision, body.groups, body.color_labels)
    return await _content_response(service, content)


@router.post(
    "/versions/{version_id}/transitions",
    response_model=VersionSummary,
    responses=responses(401, 403, 404, 409),
)
async def transition_version(
    version_id: str, body: TransitionRequest, service: ContentDep
) -> VersionSummary:
    return _version_summary(await service.transition(version_id, body.action))


@router.post(
    "/versions/{version_id}/duplicate",
    status_code=201,
    response_model=VersionSummary,
    responses=_EVAL_ERRORS,
)
async def duplicate_version(version_id: str, service: ContentDep) -> VersionSummary:
    return _version_summary(await service.duplicate_version(version_id))


@router.get(
    "/versions/{version_id}/items.csv",
    response_class=Response,
    responses={**_EVAL_ERRORS, **_CSV},
)
async def export_items(version_id: str, service: ContentDep) -> Response:
    filename, content = await service.export_items(version_id)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/versions/{version_id}/items/import",
    response_model=VersionContentResponse,
    responses=responses(400, 401, 403, 404, 409),
)
async def import_items(
    version_id: str, body: ItemsImportRequest, service: ContentDep
) -> VersionContentResponse:
    content = await service.import_items(version_id, body.revision, body.csv, body.mode)
    return await _content_response(service, content)


@router.get(
    "/versions/{version_id}/exports/ballots.csv",
    response_class=Response,
    responses={**responses(400, 401, 403, 404, 409), **_CSV},
)
async def export_ballots(version_id: str, request: Request, service: ExportDep) -> Response:
    """Export 2: always on the whole version; any filter parameter is refused."""
    if request.query_params:
        raise RuleViolation(
            400, "FILTER_NOT_ALLOWED", "Cet export porte toujours sur l'ensemble de la version."
        )
    filename, content = await service.ballots_csv(version_id)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
