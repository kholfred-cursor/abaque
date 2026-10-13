"""The authenticated tenant's organization and its resolved entitlements."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import organization_repository
from app.api.errors import responses
from app.entitlements.models import Entitlements
from app.repositories.mongo.organizations import OrganizationRepository

router = APIRouter(tags=["organization"])


class OrganizationResponse(BaseModel):
    id: str
    name: str
    slug: str
    plan_code: Literal["demo", "trial", "standard"]
    status: Literal["active", "suspended", "deleted"]
    entitlements: Entitlements


@router.get("/organization", response_model=OrganizationResponse, responses=responses(401, 403))
async def get_organization(
    repository: Annotated[OrganizationRepository, Depends(organization_repository)],
) -> OrganizationResponse:
    organization = await repository.get_current()
    return OrganizationResponse(
        id=organization.id,
        name=organization.name,
        slug=organization.slug,
        plan_code=organization.plan_code,
        status=organization.status,
        entitlements=organization.entitlements,
    )
