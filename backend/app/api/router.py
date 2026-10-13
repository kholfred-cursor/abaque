"""All business routes under /api, with CSRF protection applied router-wide."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import csrf_protect
from app.api.routes import account, auth, organization

api_router = APIRouter(prefix="/api", dependencies=[Depends(csrf_protect)])
api_router.include_router(auth.router)
api_router.include_router(account.router)
api_router.include_router(organization.router)
