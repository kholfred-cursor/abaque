"""Single entry point to the MongoDB repositories for the layers above.

The API and services receive a MongoStore and ask it for repositories, so they never
import pymongo or bson themselves (enforced by tests/architecture).
"""

from __future__ import annotations

from typing import Any

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from app.domain.models import TenantContext
from app.repositories.mongo.admins import AdminAuthRepository, AdminRepository
from app.repositories.mongo.auth_tokens import AuthTokenRepository
from app.repositories.mongo.content import ContentRepository
from app.repositories.mongo.organizations import (
    OrganizationProvisioningRepository,
    OrganizationRepository,
)
from app.repositories.mongo.sessions import AdminSessionRepository


class MongoStore:
    def __init__(self, client: AsyncMongoClient[Any], database: AsyncDatabase[Any]) -> None:
        self.client = client
        self.database = database

    # Outside any tenant scope (explicitly named, see lot0-04).
    def admin_auth(self) -> AdminAuthRepository:
        return AdminAuthRepository(self.database)

    def sessions(self) -> AdminSessionRepository:
        return AdminSessionRepository(self.database, self.client)

    def auth_tokens(self) -> AuthTokenRepository:
        return AuthTokenRepository(self.database)

    def provisioning(self) -> OrganizationProvisioningRepository:
        return OrganizationProvisioningRepository(self.database, self.client)

    # Tenant-scoped: require the context built by current_org.
    def organizations(self, tenant: TenantContext) -> OrganizationRepository:
        return OrganizationRepository(self.database, tenant)

    def admins(self, tenant: TenantContext) -> AdminRepository:
        return AdminRepository(self.database, tenant)

    def content(self, tenant: TenantContext) -> ContentRepository:
        return ContentRepository(self.database, self.client, tenant)
