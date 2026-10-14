"""Declarative MongoDB index definitions with stable names."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class IndexDefinition:
    """One MongoDB index, including the options that define its behavior."""

    collection: str
    name: str
    keys: tuple[tuple[str, int], ...]
    unique: bool = False
    partial_filter: dict[str, Any] | None = None
    expire_after_seconds: int | None = None

    def options(self) -> dict[str, Any]:
        """Return PyMongo options for this definition."""
        options: dict[str, Any] = {"name": self.name}
        if self.unique:
            options["unique"] = True
        if self.partial_filter is not None:
            options["partialFilterExpression"] = self.partial_filter
        if self.expire_after_seconds is not None:
            options["expireAfterSeconds"] = self.expire_after_seconds
        return options


_STRING_EXISTS: dict[str, Any] = {"$exists": True, "$type": "string"}


INDEXES: list[IndexDefinition] = [
    IndexDefinition("organizations", "uq_organizations_slug", (("slug", 1),), unique=True),
    IndexDefinition("admins", "uq_admins_email", (("email", 1),), unique=True),
    IndexDefinition(
        "admin_sessions", "uq_admin_sessions_token_hash", (("token_hash", 1),), unique=True
    ),
    IndexDefinition("auth_tokens", "uq_auth_tokens_token_hash", (("token_hash", 1),), unique=True),
    IndexDefinition(
        "participant_links", "uq_participant_links_token_hash", (("token_hash", 1),), unique=True
    ),
    IndexDefinition(
        "evaluations",
        "uq_evaluations_organization_id_slug",
        (("organization_id", 1), ("slug", 1)),
        unique=True,
    ),
    # Lot 1 (D036): the public link resolves a slug across the whole platform.
    IndexDefinition("evaluations", "uq_evaluations_slug", (("slug", 1),), unique=True),
    # Lot 1 (D037): at most one open version per evaluation, enforced by the database.
    IndexDefinition(
        "versions",
        "uq_versions_evaluation_id_open",
        (("evaluation_id", 1),),
        unique=True,
        partial_filter={"status": "open"},
    ),
    IndexDefinition(
        "color_labels",
        "uq_color_labels_version_id_color_key",
        (("version_id", 1), ("color_key", 1)),
        unique=True,
    ),
    IndexDefinition(
        "credential_uses",
        "uq_credential_uses_version_id_credential_fingerprint",
        (("version_id", 1), ("credential_fingerprint", 1)),
        unique=True,
    ),
    IndexDefinition(
        "votes", "uq_votes_ballot_id_item_id", (("ballot_id", 1), ("item_id", 1)), unique=True
    ),
    IndexDefinition(
        "segment_answers",
        "uq_segment_answers_ballot_id_question_id",
        (("ballot_id", 1), ("question_id", 1)),
        unique=True,
    ),
    IndexDefinition(
        "general_answers",
        "uq_general_answers_ballot_id_question_id",
        (("ballot_id", 1), ("question_id", 1)),
        unique=True,
    ),
    IndexDefinition(
        "participants",
        "uq_participants_version_id_email",
        (("version_id", 1), ("email", 1)),
        unique=True,
        partial_filter={"email": _STRING_EXISTS},
    ),
    IndexDefinition(
        "participants",
        "uq_participants_token_hash",
        (("token_hash", 1),),
        unique=True,
        partial_filter={"token_hash": _STRING_EXISTS},
    ),
    IndexDefinition(
        "auth_tokens", "ttl_auth_tokens_expires_at", (("expires_at", 1),), expire_after_seconds=0
    ),
    IndexDefinition(
        "participant_links",
        "ttl_participant_links_expires_at",
        (("expires_at", 1),),
        expire_after_seconds=0,
    ),
    IndexDefinition(
        "participant_links",
        "ix_participant_links_version_id_email_normalized",
        (("version_id", 1), ("email_normalized", 1)),
    ),
    IndexDefinition(
        "ballots", "ix_ballots_version_id_rand_key", (("version_id", 1), ("rand_key", 1))
    ),
    IndexDefinition("versions", "ix_versions_evaluation_id", (("evaluation_id", 1),)),
    IndexDefinition(
        "version_events", "ix_version_events_version_id_at", (("version_id", 1), ("at", 1))
    ),
    IndexDefinition(
        "item_groups",
        "ix_item_groups_version_id_position",
        (("version_id", 1), ("position", 1)),
    ),
    IndexDefinition("items", "ix_items_version_id_position", (("version_id", 1), ("position", 1))),
    IndexDefinition("admins", "ix_admins_organization_id", (("organization_id", 1),)),
    IndexDefinition("evaluations", "ix_evaluations_organization_id", (("organization_id", 1),)),
    IndexDefinition("versions", "ix_versions_organization_id", (("organization_id", 1),)),
    IndexDefinition(
        "version_events", "ix_version_events_organization_id", (("organization_id", 1),)
    ),
    IndexDefinition("item_groups", "ix_item_groups_organization_id", (("organization_id", 1),)),
    IndexDefinition("items", "ix_items_organization_id", (("organization_id", 1),)),
    IndexDefinition("color_labels", "ix_color_labels_organization_id", (("organization_id", 1),)),
    IndexDefinition("glossary", "ix_glossary_organization_id", (("organization_id", 1),)),
    IndexDefinition(
        "segment_questions", "ix_segment_questions_organization_id", (("organization_id", 1),)
    ),
    IndexDefinition(
        "general_questions", "ix_general_questions_organization_id", (("organization_id", 1),)
    ),
    IndexDefinition("participants", "ix_participants_organization_id", (("organization_id", 1),)),
    IndexDefinition(
        "participant_links", "ix_participant_links_organization_id", (("organization_id", 1),)
    ),
    IndexDefinition(
        "credential_uses", "ix_credential_uses_organization_id", (("organization_id", 1),)
    ),
    IndexDefinition("email_logs", "ix_email_logs_organization_id", (("organization_id", 1),)),
    IndexDefinition("ballots", "ix_ballots_organization_id", (("organization_id", 1),)),
    IndexDefinition("votes", "ix_votes_organization_id", (("organization_id", 1),)),
    IndexDefinition(
        "segment_answers", "ix_segment_answers_organization_id", (("organization_id", 1),)
    ),
    IndexDefinition(
        "general_answers", "ix_general_answers_organization_id", (("organization_id", 1),)
    ),
]
