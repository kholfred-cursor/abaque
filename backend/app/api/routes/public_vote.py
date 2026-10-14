"""Public vote routes, reached through /v/:slug. No session, no organization exposed."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.api.deps import SettingsDep, VoteDep
from app.api.errors import responses
from app.domain.content import COLOR_ORDER, ColorKey, scale_labels
from app.domain.vote import COMMENT_MAX
from app.services.vote import VoteInput, voted_cookie_name

router = APIRouter(prefix="/public", tags=["vote"])

Comment = Annotated[str, StringConstraints(strip_whitespace=True, max_length=COMMENT_MAX)]


class PublicScaleEntry(BaseModel):
    key: ColorKey
    label: str


class PublicItem(BaseModel):
    id: str
    short_name: str
    statement: str


class PublicGroup(BaseModel):
    id: str
    name: str
    items: list[PublicItem]


class PublicVersionResponse(BaseModel):
    """Everything the voting page needs; nothing about the organization or other versions."""

    title: str
    status: Literal["open", "closed"]
    version_id: str | None
    already_voted: bool
    intro_md: str | None
    outro_md: str | None
    show_vote_example: bool
    scale: list[PublicScaleEntry]
    groups: list[PublicGroup]


class VoteRequestItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str = Field(min_length=1, max_length=64)
    color_key: ColorKey
    comment: Comment | None = None


class BallotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version_id: str = Field(min_length=1, max_length=64)
    votes: list[VoteRequestItem] = Field(max_length=500)


class BallotAccepted(BaseModel):
    """Deliberately empty of any ballot id (section 7, step 5)."""

    status: Literal["recorded"]


@router.get("/v/{slug}", response_model=PublicVersionResponse, responses=responses(404))
async def get_public_version(
    slug: str, request: Request, service: VoteDep
) -> PublicVersionResponse:
    view = await service.view(slug)
    evaluation, content = view.evaluation, view.content
    if content is None:
        return PublicVersionResponse(
            title=evaluation.title,
            status="closed",
            version_id=None,
            already_voted=False,
            intro_md=None,
            outro_md=evaluation.outro_md,
            show_vote_example=False,
            scale=[],
            groups=[],
        )
    labels = scale_labels(evaluation.vote_preset, content.color_labels)
    version_id = content.version.id
    return PublicVersionResponse(
        title=evaluation.title,
        status="open",
        version_id=version_id,
        already_voted=voted_cookie_name(version_id) in request.cookies,
        intro_md=evaluation.intro_md,
        outro_md=evaluation.outro_md,
        show_vote_example=evaluation.show_vote_example,
        scale=[PublicScaleEntry(key=key, label=labels[key]) for key in COLOR_ORDER],
        groups=[
            PublicGroup(
                id=group.id,
                name=group.name,
                items=[PublicItem(**item.model_dump()) for item in group.items],
            )
            for group in content.groups
            if group.items
        ],
    )


@router.post(
    "/v/{slug}/ballots",
    status_code=201,
    response_model=BallotAccepted,
    responses=responses(400, 403, 404, 409, 429),
)
async def submit_ballot(
    slug: str,
    body: BallotRequest,
    request: Request,
    response: Response,
    service: VoteDep,
    settings: SettingsDep,
) -> BallotAccepted:
    client_ip = request.client.host if request.client else "unknown"
    cookie = await service.submit(
        slug,
        body.version_id,
        [
            VoteInput(item_id=vote.item_id, color_key=vote.color_key, comment=vote.comment or None)
            for vote in body.votes
        ],
        client_ip,
        dict(request.cookies),
    )
    response.set_cookie(
        cookie.name,
        cookie.value,
        max_age=cookie.max_age,
        path=f"/api/public/v/{slug}",
        httponly=True,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
    )
    return BallotAccepted(status="recorded")
