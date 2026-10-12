"""MongoDB $jsonSchema validators for all collections.

Every collection uses additionalProperties: false at every nesting level.
Schemas are applied by migrations.py via collMod in strict/error mode.
"""

from __future__ import annotations

from typing import Any

from app.db.schemas import (
    admin_sessions,
    admins,
    auth_tokens,
    ballots,
    color_labels,
    credential_uses,
    email_logs,
    evaluations,
    general_answers,
    general_questions,
    glossary,
    item_groups,
    items,
    organizations,
    participant_links,
    participants,
    segment_answers,
    segment_questions,
    version_events,
    versions,
    votes,
)

ALL_SCHEMAS: dict[str, dict[str, Any]] = {
    "organizations": organizations.SCHEMA,
    "admins": admins.SCHEMA,
    "admin_sessions": admin_sessions.SCHEMA,
    "auth_tokens": auth_tokens.SCHEMA,
    "evaluations": evaluations.SCHEMA,
    "versions": versions.SCHEMA,
    "version_events": version_events.SCHEMA,
    "item_groups": item_groups.SCHEMA,
    "items": items.SCHEMA,
    "color_labels": color_labels.SCHEMA,
    "glossary": glossary.SCHEMA,
    "segment_questions": segment_questions.SCHEMA,
    "general_questions": general_questions.SCHEMA,
    "participants": participants.SCHEMA,
    "participant_links": participant_links.SCHEMA,
    "credential_uses": credential_uses.SCHEMA,
    "email_logs": email_logs.SCHEMA,
    "ballots": ballots.SCHEMA,
    "votes": votes.SCHEMA,
    "segment_answers": segment_answers.SCHEMA,
    "general_answers": general_answers.SCHEMA,
}

# Vote domain — strictest anonymity rules
VOTE_DOMAIN: frozenset[str] = frozenset({"ballots", "votes", "segment_answers", "general_answers"})

# Identity domain — never referenced from the vote domain
IDENTITY_DOMAIN: frozenset[str] = frozenset(
    {"participants", "participant_links", "credential_uses", "email_logs"}
)
