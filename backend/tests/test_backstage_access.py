import pytest
from fastapi import HTTPException, Request
from fastapi.routing import APIRoute

from app.api.dependencies.auth import require_backstage_admin
from app.main import app
from app.services.auth_service import UserRecord


def request_for(username: str | None, role: str = "user") -> Request:
    request = Request({"type": "http", "method": "GET", "path": "/api/admin/status", "headers": []})
    if username is not None:
        request.state.auth_user = UserRecord(
            id=1,
            username=username,
            role=role,
            status="active",
            created_at="2026-10-31T00:00:00+00:00",
            approved_at=None,
            favorite_team_id=None,
            avatar_setup_status="default",
        )
    return request


@pytest.mark.parametrize(
    ("username", "role", "expected_status"),
    [
        (None, "user", 401),
        ("visitor", "user", 403),
        ("peter1010", "user", 403),
        ("other_admin", "admin", 403),
        ("PETER1010", "admin", 403),
    ],
)
def test_backstage_denies_non_matching_identity(username: str | None, role: str, expected_status: int) -> None:
    with pytest.raises(HTTPException) as error:
        require_backstage_admin(request_for(username, role))
    assert error.value.status_code == expected_status


def test_backstage_accepts_exact_admin_identity() -> None:
    user = require_backstage_admin(request_for("peter1010", "admin"))
    assert user.username == "peter1010"


def test_every_admin_api_route_requires_backstage_identity() -> None:
    admin_routes = [route for route in app.routes if isinstance(route, APIRoute) and route.path.startswith("/api/admin/")]
    assert admin_routes
    assert all(
        any(dependency.call is require_backstage_admin for dependency in route.dependant.dependencies)
        for route in admin_routes
    )
