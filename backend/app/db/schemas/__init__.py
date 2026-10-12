"""MongoDB $jsonSchema validators for all collections.

Every collection uses additionalProperties: false at every nesting level.
Schemas are applied by migrations.py via collMod in strict/error mode.
"""

from __future__ import annotations

from typing import Any

from app.db.schemas.admin_sessions import SCHEMA as admin_sessions_schema
from app.db.schemas.admins import SCHEMA as admins_schema
from app.db.schemas.auth_tokens import SCHEMA as auth_tokens_schema
from app.db.schemas.ballots import SCHEMA as ballots_schema
from app.db.schemas.color_labels import SCHEMA as color_labels_schema
from app.db.schemas.credential_uses import SCHEMA as credential_uses_schema
from app.db.schemas.email_logs import SCHEMA as email_logs_schema
from app.db.schemas.evaluations import SCHEMA as evaluations_schema
from app.db.schemas.general_answers import SCHEMA as general_answers_schema
from app.db.schemas.general_questions import SCHEMA as general_questions_schema
from app.db.schemas.glossary import SCHEMA as glossary_schema
from app.db.schemas.item_groups import SCHEMA as item_groups_schema
from app.db.schemas.items import SCHEMA as items_schema
from app.db.schemas.organizations import SCHEMA as organizations_schema
from app.db.schemas.participant_links import SCHEMA as participant_links_schema
from app.db.schemas.participants import SCHEMA as participants_schema
from app.db.schemas.segment_answers import SCHEMA as segment_answers_schema
from app.db.schemas.segment_questions import SCHEMA as segment_questions_schema
from app.db.schemas.version_events import SCHEMA as version_events_schema
from app.db.schemas.versions import SCHEMA as versions_schema
from app.db.schemas.votes import SCHEMA as votes_schema

ALL_SCHEMAS: dict[str, dict[str, Any]] = {
    "organizations": organizations_schema,
    "admins": admins_schema,
    "admin_sessions": admin_sessions_schema,
    "auth_tokens": auth_tokens_schema,
    "evaluations": evaluations_schema,
    "versions": versions_schema,
    "version_events": version_events_schema,
    "item_groups": item_groups_schema,
    "items": items_schema,
    "color_labels": color_labels_schema,
    "glossary": glossary_schema,
    "segment_questions": segment_questions_schema,
    "general_questions": general_questions_schema,
    "participants": participants_schema,
    "participant_links": participant_links_schema,
    "credential_uses": credential_uses_schema,
    "email_logs": email_logs_schema,
    "ballots": ballots_schema,
    "votes": votes_schema,
    "segment_answers": segment_answers_schema,
    "general_answers": general_answers_schema,
}

# Vote domain — strictest anonymity rules
VOTE_DOMAIN: frozenset[str] = frozenset({"ballots", "votes", "segment_answers", "general_answers"})

# Identity domain — never referenced from the vote domain
IDENTITY_DOMAIN: frozenset[str] = frozenset(
    {"participants", "participant_links", "credential_uses", "email_logs"}
)
