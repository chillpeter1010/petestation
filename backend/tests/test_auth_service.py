from pathlib import Path
import sqlite3

import pytest

from app.services.auth_service import AuthServiceError, AuthStore, hash_password, verify_password
from app.core.ballpark_avatar import BallparkAvatarV1, default_ballpark_avatar


def test_password_hash_is_salted_and_verifiable() -> None:
    first = hash_password("a-secure-password")
    second = hash_password("a-secure-password")
    assert first != second
    assert verify_password("a-secure-password", first)
    assert not verify_password("wrong-password", first)


def test_registration_requires_approval_before_login(tmp_path: Path) -> None:
    store = AuthStore(tmp_path / "auth.sqlite3")
    pending = store.create_user("new_user", "a-secure-password", favorite_team_id=109)
    assert pending.status == "pending"
    assert pending.favorite_team_id == 109
    assert pending.as_dict()["favorite_team_code"] == "AZ"
    assert pending.avatar_setup_status == "pending"
    with pytest.raises(AuthServiceError, match="waiting"):
        store.authenticate("new_user", "a-secure-password")
    active = store.set_user_status(pending.id, "active", actor_user_id=999)
    assert active.status == "active"
    assert store.authenticate("NEW_USER", "a-secure-password").id == pending.id


def test_session_and_disable_flow(tmp_path: Path) -> None:
    store = AuthStore(tmp_path / "auth.sqlite3")
    admin = store.upsert_admin("site_admin", "a-secure-password")
    token, _ = store.create_session(admin.id, 14)
    assert store.user_for_session(token) == admin
    with pytest.raises(AuthServiceError, match="own administrator"):
        store.set_user_status(admin.id, "disabled", actor_user_id=admin.id)
    store.revoke_session(token)
    assert store.user_for_session(token) is None


def test_duplicate_usernames_are_case_insensitive(tmp_path: Path) -> None:
    store = AuthStore(tmp_path / "auth.sqlite3")
    store.create_user("Peter.User", "a-secure-password")
    with pytest.raises(AuthServiceError, match="already registered"):
        store.create_user("peter.user", "another-password")


def test_profile_supports_valid_team_and_default_avatar(tmp_path: Path) -> None:
    store = AuthStore(tmp_path / "auth.sqlite3")
    user = store.create_user("profile_user", "a-secure-password")
    updated = store.update_profile(user.id, favorite_team_id=147, avatar_setup_status="default")
    assert updated.favorite_team_id == 147
    assert updated.as_dict()["favorite_team_code"] == "NYY"
    assert updated.avatar_setup_status == "default"
    with pytest.raises(AuthServiceError, match="Unsupported MLB team"):
        store.update_profile(user.id, favorite_team_id=999, avatar_setup_status="default")


def test_existing_auth_database_is_migrated_without_losing_users(tmp_path: Path) -> None:
    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                approved_at TEXT
            );
            CREATE TABLE sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL
            );
            """
        )
        connection.execute(
            "INSERT INTO users(username, password_hash, role, status, created_at) VALUES (?, ?, 'user', 'pending', ?)",
            ("legacy_user", hash_password("a-secure-password"), "2026-10-31T00:00:00+00:00"),
        )
    store = AuthStore(path)
    migrated = store.list_users()[0]
    assert migrated.username == "legacy_user"
    assert migrated.favorite_team_id is None
    assert migrated.avatar_setup_status == "pending"
    assert migrated.avatar == default_ballpark_avatar()


def test_avatar_round_trip_and_corrupt_save_fallback_preserves_original(tmp_path: Path) -> None:
    path = tmp_path / "avatar.sqlite3"
    store = AuthStore(path)
    user = store.create_user("avatar_user", "a-secure-password", favorite_team_id=109)
    custom = BallparkAvatarV1(body_id="tone_4", uniform_id="neutral_away", palette_id="teal", number=27, bats="L", throws="R")
    saved = store.update_avatar(user.id, custom)
    assert saved.avatar == custom.model_dump()
    assert saved.favorite_team_id == 109
    assert saved.avatar_setup_status == "default"
    assert AuthStore(path).list_users()[0].avatar == custom.model_dump()

    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE users SET avatar_json = ? WHERE id = ?", ('{"avatar_version":999}', user.id))
    recovered = store.list_users()[0]
    assert recovered.avatar == default_ballpark_avatar()
    assert recovered.avatar_recovery_needed
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT avatar_json FROM users WHERE id = ?", (user.id,)).fetchone()[0] == '{"avatar_version":999}'
