"""Evaluations, versions and their content (groups, items, scale labels). Lot 1."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ColorKey = Literal["++", "+", "~", "-", "--"]
COLOR_ORDER: tuple[ColorKey, ...] = ("++", "+", "~", "-", "--")
VotePreset = Literal["agreement", "score", "custom"]
ParticipationMode = Literal["anonymous", "auth_open", "auth_closed"]
VersionStatus = Literal["draft", "open", "closed", "archived"]
TransitionAction = Literal["open", "close", "reopen", "archive"]

# Labels of the two built-in presets; equal to docs/design/scale.json (tested).
PRESET_LABELS: dict[Literal["agreement", "score"], dict[ColorKey, str]] = {
    "agreement": {
        "++": "Tout à fait d'accord",
        "+": "Plutôt d'accord",
        "~": "Avis partagé, opinion mitigée",
        "-": "Plutôt pas d'accord",
        "--": "Pas du tout d'accord",
    },
    "score": {
        "++": "5 — Élevé",
        "+": "4 — Moyen",
        "~": "3 — Incertain / Mitigé",
        "-": "2 — Faible",
        "--": "1 — Très faible",
    },
}

# From -> allowed actions (D037). Archived is final.
TRANSITIONS: dict[TransitionAction, tuple[tuple[VersionStatus, ...], VersionStatus]] = {
    "open": (("draft",), "open"),
    "close": (("open",), "closed"),
    "reopen": (("closed",), "open"),
    "archive": (("draft", "closed"), "archived"),
}

SHORT_NAME_MAX = 50
STATEMENT_MAX = 2000
GROUP_NAME_MAX = 200
LABEL_MAX = 100
MAX_ITEMS_PER_VERSION = 500
MAX_GROUPS_PER_VERSION = 100


def scale_labels(preset: VotePreset, custom: dict[ColorKey, str]) -> dict[ColorKey, str]:
    """Labels shown to voters: the preset, or the custom labels completed by 'agreement'."""
    if preset == "custom":
        return {key: custom.get(key) or PRESET_LABELS["agreement"][key] for key in COLOR_ORDER}
    return dict(PRESET_LABELS[preset])


class Evaluation(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    description: str | None
    slug: str
    participation_mode: ParticipationMode
    vote_preset: VotePreset
    intro_md: str | None
    outro_md: str | None
    show_vote_example: bool
    anonymity_threshold: int
    created_at: datetime


class Version(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    evaluation_id: str
    label: str
    status: VersionStatus
    ballot_count: int
    content_revision: int
    closed_at: datetime | None


class Item(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    short_name: str
    statement: str


class ItemGroup(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    items: list[Item]


class VersionContent(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: Version
    groups: list[ItemGroup]
    color_labels: dict[ColorKey, str]


class ItemInput(BaseModel):
    """An item as sent by the editor; ``id`` keeps an existing item, None creates one."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    id: str | None = None
    short_name: str = Field(min_length=1, max_length=SHORT_NAME_MAX)
    statement: str = Field(min_length=1, max_length=STATEMENT_MAX)


class GroupInput(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    id: str | None = None
    name: str = Field(min_length=1, max_length=GROUP_NAME_MAX)
    items: list[ItemInput] = Field(default_factory=list, max_length=MAX_ITEMS_PER_VERSION)


class EvaluationCreate(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str
    description: str | None
    participation_mode: ParticipationMode
    vote_preset: VotePreset
    slug: str
    intro_md: str | None = None
    outro_md: str | None = None
    show_vote_example: bool = False
    anonymity_threshold: int = 3


def as_inputs(content: VersionContent) -> list[GroupInput]:
    """The content of a version as editor input without ids (used to copy it)."""
    return [
        GroupInput(
            name=group.name,
            items=[ItemInput(short_name=i.short_name, statement=i.statement) for i in group.items],
        )
        for group in content.groups
    ]
