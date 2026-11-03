from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

import app.api.routes.auth as auth_routes
import app.api.routes.teams as team_routes
import app.main as main_module
from app.services.active_roster_service import get_team_active_roster
from app.services.auth_service import AuthStore


def test_account_team_gate_and_private_response(tmp_path: Path, monkeypatch) -> None:
    store = AuthStore(tmp_path / "auth.sqlite3")
    monkeypatch.setattr(main_module, "get_auth_store", lambda: store)
    monkeypatch.setattr(auth_routes, "get_auth_store", lambda: store)

    source_calls = []

    def official_roster(url: str, timeout: int) -> dict[str, object]:
        source_calls.append(url)
        return {"roster": [{"person": {"id": 123, "fullName": "Test Player"}, "position": {"code": "1", "name": "Pitcher", "type": "Pitcher"}, "status": {"code": "A", "description": "Active"}}]}

    def roster_for_route(year: int, team_code: str, *, force_refresh: bool = False):
        return get_team_active_roster(
            year, team_code, data_dir=tmp_path, force_refresh=force_refresh,
            fetcher=official_roster, now=datetime(2026, 10, 31, 12, tzinfo=timezone.utc),
        )

    monkeypatch.setattr(team_routes, "get_team_active_roster", roster_for_route)

    with TestClient(main_module.app) as client:
        assert client.get("/api/teams/AZ/active-roster").status_code == 401
        assert client.patch("/api/auth/avatar", json={"avatar": {"avatar_version": 1}}).status_code == 401
        registration = client.post("/api/auth/register", json={"username": "gate_user", "password": "a-secure-password", "favorite_team_id": 109})
        assert registration.status_code == 201
        assert registration.json()["user"]["status"] == "pending"
        assert registration.headers["cache-control"] == "no-store"
        assert client.post("/api/auth/login", json={"username": "gate_user", "password": "a-secure-password"}).status_code == 403

        user_id = registration.json()["user"]["id"]
        store.set_user_status(user_id, "active", actor_user_id=999)
        login = client.post("/api/auth/login", json={"username": "gate_user", "password": "a-secure-password"})
        assert login.status_code == 200
        assert "httponly" in login.headers["set-cookie"].lower()
        assert "samesite=lax" in login.headers["set-cookie"].lower()
        assert login.headers["cache-control"] == "no-store"
        assert all(secret not in login.text.lower() for secret in ("a-secure-password", "password_hash", "petehub_session"))

        profile = client.patch("/api/auth/profile", json={"favorite_team_id": 147, "avatar_setup_status": "default"})
        assert profile.status_code == 200
        assert profile.json()["user"]["favorite_team_code"] == "NYY"
        assert client.get("/api/auth/me").json()["user"]["favorite_team_code"] == "NYY"
        assert client.get("/api/auth/me").headers["cache-control"] == "no-store"

        avatar = client.patch("/api/auth/avatar", json={"avatar": {"avatar_version": 1, "body_id": "tone_4", "number": 27}})
        assert avatar.status_code == 200
        assert avatar.json()["user"]["avatar"]["number"] == 27
        assert client.get("/api/auth/me").json()["user"]["avatar"]["body_id"] == "tone_4"
        assert client.patch("/api/auth/avatar", json={"avatar": {"avatar_version": 1, "number": 100}}).status_code == 422
        assert client.get("/api/auth/me").json()["user"]["avatar"]["number"] == 27

        roster = client.get("/api/teams/AZ/active-roster?year=2026")
        assert roster.status_code == 200
        assert roster.json()["contract_version"] == "official_active_roster_v1"
        assert roster.json()["freshness"] == "fresh"
        assert roster.json()["source_as_of"] is None
        assert [player["player_id"] for player in roster.json()["players"]] == [123]
        assert client.get("/api/teams/AZ/active-roster?year=2026").json()["freshness"] == "fresh"
        assert len(source_calls) == 1
        assert client.get("/api/admin/jobs/c5-check").status_code == 403

        store.set_user_status(user_id, "disabled", actor_user_id=999)
        assert client.get("/api/auth/me").status_code == 401
        assert client.get("/api/teams/AZ/active-roster").status_code == 401


def test_only_exact_admin_can_access_operations_api(tmp_path: Path, monkeypatch) -> None:
    store = AuthStore(tmp_path / "auth.sqlite3")
    monkeypatch.setattr(main_module, "get_auth_store", lambda: store)
    other_admin = store.create_user("other_admin", "a-secure-password", role="admin", status="active")
    backstage_admin = store.create_user("peter1010", "a-secure-password", role="admin", status="active")

    with TestClient(main_module.app) as client:
        other_token, _ = store.create_session(other_admin.id, 1)
        client.cookies.set("petehub_session", other_token)
        denied = client.get("/api/admin/jobs/c5-check")
        assert denied.status_code == 403
        assert denied.json() == {"detail": "Backstage access required."}
        assert denied.headers["cache-control"] == "no-store"

        backstage_token, _ = store.create_session(backstage_admin.id, 1)
        client.cookies.set("petehub_session", backstage_token)
        allowed = client.get("/api/admin/jobs/c5-check")
        assert allowed.status_code == 200
        assert allowed.json()["status"] == "not_found"
        assert allowed.headers["cache-control"] == "no-store"
