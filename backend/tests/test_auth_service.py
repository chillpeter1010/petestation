from pathlib import Path

import pytest

from app.services.auth_service import AuthServiceError, AuthStore, hash_password, verify_password


def test_password_hash_is_salted_and_verifiable() -> None:
    first = hash_password("a-secure-password")
    second = hash_password("a-secure-password")
    assert first != second
    assert verify_password("a-secure-password", first)
    assert not verify_password("wrong-password", first)


def test_registration_requires_approval_before_login(tmp_path: Path) -> None:
    store = AuthStore(tmp_path / "auth.sqlite3")
    pending = store.create_user("new_user", "a-secure-password")
    assert pending.status == "pending"
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
