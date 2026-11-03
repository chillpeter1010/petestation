from pathlib import Path

import pytest
from fastapi import Request, Response
from pydantic import ValidationError

import app.api.routes.auth as auth_routes
from app.api.schemas.auth import LoginRequest, RegisterRequest, UserProfileRequest
from app.services.auth_service import AuthStore


def test_registration_and_profile_bootstrap_round_trip(tmp_path: Path, monkeypatch) -> None:
    store = AuthStore(tmp_path / "auth.sqlite3")
    monkeypatch.setattr(auth_routes, "get_auth_store", lambda: store)

    registration = auth_routes.register(RegisterRequest(
        username="ballpark_user",
        password="a-secure-password",
        favorite_team_id=109,
    ))
    assert registration.user.favorite_team_code == "AZ"
    assert registration.user.avatar_setup_status == "pending"

    active_user = store.set_user_status(registration.user.id, "active", actor_user_id=999)
    response = Response()
    login = auth_routes.login(
        LoginRequest(username="ballpark_user", password="a-secure-password"),
        Request({"type": "http", "method": "POST", "path": "/api/auth/login", "headers": []}),
        response,
    )
    assert login.user.id == active_user.id
    assert "petehub_session=" in response.headers["set-cookie"]

    profile = auth_routes.update_profile(
        UserProfileRequest(favorite_team_id=147, avatar_setup_status="default"),
        active_user,
    )
    assert profile.user.favorite_team_code == "NYY"
    assert profile.user.avatar_setup_status == "default"

    cleared_team = auth_routes.update_profile(
        UserProfileRequest(favorite_team_id=None),
        store.list_users()[0],
    )
    assert cleared_team.user.favorite_team_id is None
    assert cleared_team.user.avatar_setup_status == "default"
    assert auth_routes.me(store.list_users()[0]).user.favorite_team_id is None


def test_registration_rejects_unknown_mlb_team(tmp_path: Path, monkeypatch) -> None:
    store = AuthStore(tmp_path / "auth.sqlite3")
    monkeypatch.setattr(auth_routes, "get_auth_store", lambda: store)

    with pytest.raises(ValidationError, match="Unsupported MLB team"):
        RegisterRequest(
            username="invalid_team_user",
            password="a-secure-password",
            favorite_team_id=999,
        )
