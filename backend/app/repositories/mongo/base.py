"""MongoDB helpers shared by tenant-scoped repository implementations."""

from __future__ import annotations

from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.asynchronous.database import AsyncDatabase

from app.domain.errors import NotFound, TenantScopeError
from app.domain.models import TenantContext


class TenantScopedRepository:
    """Base class that injects one authenticated organization into every query."""

    def __init__(self, database: AsyncDatabase[Any], context: TenantContext) -> None:
        self.database = database
        self.context = context
        self._organization_id = self._to_object_id(context.organization_id)

    @staticmethod
    def _to_object_id(identifier: str) -> ObjectId:
        try:
            return ObjectId(identifier)
        except InvalidId as exc:
            raise NotFound("Resource not found") from exc

    @staticmethod
    def _session_options(session: AsyncClientSession | None) -> dict[str, Any]:
        return {} if session is None else {"session": session}

    def _scope(self, filter_document: dict[str, Any] | None = None) -> dict[str, Any]:
        """Add the authenticated organization and reject a contradictory caller scope."""
        scoped = {} if filter_document is None else dict(filter_document)
        supplied = scoped.get("organization_id")
        if supplied is not None and str(supplied) != str(self._organization_id):
            raise TenantScopeError("organization_id cannot override the authenticated tenant")
        scoped["organization_id"] = self._organization_id
        return scoped

    def _force_organization(self, document: dict[str, Any]) -> dict[str, Any]:
        """Overwrite any caller-provided tenant value before a database write."""
        forced = dict(document)
        forced["organization_id"] = self._organization_id
        return forced
