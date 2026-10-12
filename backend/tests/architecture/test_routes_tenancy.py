"""Block 6: tenant isolation, applied AUTOMATICALLY to every organization-scoped route.

Every route whose dependency tree contains `current_org` must have an entry in
RESOURCE_FACTORIES. A new route without one makes this test fail, so isolation is
tested by construction rather than by remembering to write a test.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from fastapi.dependencies.models import Dependant

from app.api.deps import current_org
from app.main import create_app
from tests.api_support import PASSWORD, Api

# A check receives the API (tenant A = api.organization, plus a tenant B) and the cookies
# of B's owner. It must prove that B never reaches A's data (404, or only B's own data).
Check = Callable[[Api, dict[str, str]], Awaitable[None]]


async def _organization_is_own(api: Api, b_cookies: dict[str, str]) -> None:
    response = await api.client.get(
        "/api/organization",
        params={"organization_id": api.organization.id},  # injected id must be ignored
        headers=api.cookie_header(abq_access=b_cookies["abq_access"]),
    )
    assert response.status_code == 200
    assert response.json()["id"] != api.organization.id


RESOURCE_FACTORIES: dict[tuple[str, str], Check] = {
    ("GET", "/api/organization"): _organization_is_own,
    # Lot 1+: routes with a resource id create it in tenant A, call it as B, expect 404.
}


def _depends_on(dependant: Dependant, target: Callable[..., Any]) -> bool:
    return any(dep.call is target or _depends_on(dep, target) for dep in dependant.dependencies)


def _flatten(routes: list[Any]) -> list[Any]:
    """FastAPI >= 0.143 keeps included routers lazily (_IncludedRouter); expand them.
    If FastAPI changes this again, test_tenant_routes_are_discovered fails loudly."""
    flat: list[Any] = []
    for route in routes:
        candidates = getattr(route, "effective_candidates", None)
        if callable(candidates):
            flat.extend(_flatten(candidates()))
        else:
            flat.append(route)
    return flat


def _tenant_routes() -> list[tuple[str, str]]:
    routes: list[tuple[str, str]] = []
    for route in _flatten(list(create_app().routes)):
        dependant = getattr(route, "dependant", None)
        if isinstance(dependant, Dependant) and _depends_on(dependant, current_org):
            routes.extend((method, str(route.path)) for method in sorted(route.methods or ()))
    return routes


TENANT_ROUTES = _tenant_routes()


def test_tenant_routes_are_discovered() -> None:
    """Guard: the dependency scan must find at least the organization route."""
    assert ("GET", "/api/organization") in TENANT_ROUTES


def test_every_tenant_route_declares_an_isolation_check() -> None:
    missing = [route for route in TENANT_ROUTES if route not in RESOURCE_FACTORIES]
    assert not missing, (
        f"Ajoute une usine dans RESOURCE_FACTORIES pour tester l'isolation de : {missing}"
    )


@pytest.mark.integration
@pytest.mark.parametrize("route", TENANT_ROUTES, ids=lambda r: f"{r[0]} {r[1]}")
async def test_tenant_b_never_reaches_tenant_a(api: Api, route: tuple[str, str]) -> None:
    _, b_email = await api.add_tenant("tenant-b")
    login = await api.client.post("/api/auth/login", json={"email": b_email, "password": PASSWORD})
    assert login.status_code == 200
    b_cookies = {
        h.split("=", 1)[0]: h.split(";", 1)[0].split("=", 1)[1]
        for h in login.headers.get_list("set-cookie")
    }
    await RESOURCE_FACTORIES[route](api, b_cookies)
