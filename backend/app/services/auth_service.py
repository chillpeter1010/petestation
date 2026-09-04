from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SESSION_BYTES = 32


class AuthServiceError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class UserRecord:
    id: int
    username: str
    role: str
    status: str
    created_at: str
    approved_at: str | None

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "status": self.status,
            "created_at": self.created_at,
            "approved_at": self.approved_at,
        }


class AuthStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode = WAL;
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('admin', 'user')),
                    status TEXT NOT NULL CHECK (status IN ('pending', 'active', 'disabled')),
                    created_at TEXT NOT NULL,
                    approved_at TEXT
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS sessions_user_id_idx ON sessions(user_id);
                CREATE INDEX IF NOT EXISTS sessions_expires_at_idx ON sessions(expires_at);
                """
            )

    def create_user(self, username: str, password: str, *, role: str = "user", status: str = "pending") -> UserRecord:
        clean_username = validate_username(username)
        validate_password(password)
        if role not in {"admin", "user"} or status not in {"pending", "active", "disabled"}:
            raise AuthServiceError("invalid_account", "Invalid account settings.")
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        approved_at = now if status == "active" else None
        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    "INSERT INTO users(username, password_hash, role, status, created_at, approved_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (clean_username, hash_password(password), role, status, now, approved_at),
                )
                row = connection.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
        except sqlite3.IntegrityError as exc:
            raise AuthServiceError("username_exists", "This username is already registered.") from exc
        return row_to_user(row)

    def upsert_admin(self, username: str, password: str) -> UserRecord:
        clean_username = validate_username(username)
        validate_password(password)
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        password_hash = hash_password(password)
        with self._connect() as connection:
            existing = connection.execute("SELECT id FROM users WHERE username = ?", (clean_username,)).fetchone()
            if existing:
                connection.execute(
                    "UPDATE users SET password_hash = ?, role = 'admin', status = 'active', approved_at = ? WHERE id = ?",
                    (password_hash, now, existing["id"]),
                )
                connection.execute("DELETE FROM sessions WHERE user_id = ?", (existing["id"],))
                row = connection.execute("SELECT * FROM users WHERE id = ?", (existing["id"],)).fetchone()
            else:
                cursor = connection.execute(
                    "INSERT INTO users(username, password_hash, role, status, created_at, approved_at) VALUES (?, ?, 'admin', 'active', ?, ?)",
                    (clean_username, password_hash, now, now),
                )
                row = connection.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return row_to_user(row)

    def authenticate(self, username: str, password: str) -> UserRecord:
        clean_username = username.strip()
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM users WHERE username = ?", (clean_username,)).fetchone()
        if row is None or not verify_password(password, row["password_hash"]):
            raise AuthServiceError("invalid_credentials", "Invalid username or password.")
        user = row_to_user(row)
        if user.status == "pending":
            raise AuthServiceError("pending_approval", "This account is waiting for administrator approval.")
        if user.status != "active":
            raise AuthServiceError("account_disabled", "This account is disabled.")
        return user

    def create_session(self, user_id: int, session_days: int) -> tuple[str, int]:
        raw_token = secrets.token_urlsafe(SESSION_BYTES)
        token_hash = digest_token(raw_token)
        now = int(datetime.now(timezone.utc).timestamp())
        expires_at = now + max(1, session_days) * 86_400
        with self._connect() as connection:
            connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
            connection.execute(
                "INSERT INTO sessions(token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (token_hash, user_id, now, expires_at),
            )
        return raw_token, expires_at

    def user_for_session(self, raw_token: str | None) -> UserRecord | None:
        if not raw_token:
            return None
        now = int(datetime.now(timezone.utc).timestamp())
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT users.* FROM sessions
                JOIN users ON users.id = sessions.user_id
                WHERE sessions.token_hash = ? AND sessions.expires_at > ? AND users.status = 'active'
                """,
                (digest_token(raw_token), now),
            ).fetchone()
        return row_to_user(row) if row else None

    def revoke_session(self, raw_token: str | None) -> None:
        if not raw_token:
            return
        with self._connect() as connection:
            connection.execute("DELETE FROM sessions WHERE token_hash = ?", (digest_token(raw_token),))

    def list_users(self) -> list[UserRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM users ORDER BY CASE status WHEN 'pending' THEN 0 WHEN 'active' THEN 1 ELSE 2 END, created_at DESC"
            ).fetchall()
        return [row_to_user(row) for row in rows]

    def set_user_status(self, user_id: int, status: str, *, actor_user_id: int) -> UserRecord:
        if status not in {"active", "disabled"}:
            raise AuthServiceError("invalid_status", "Invalid account status.")
        if user_id == actor_user_id and status == "disabled":
            raise AuthServiceError("cannot_disable_self", "You cannot disable your own administrator account.")
        approved_at = datetime.now(timezone.utc).isoformat(timespec="seconds") if status == "active" else None
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE users SET status = ?, approved_at = COALESCE(?, approved_at) WHERE id = ?",
                (status, approved_at, user_id),
            )
            if cursor.rowcount == 0:
                raise AuthServiceError("user_not_found", "Account not found.")
            if status == "disabled":
                connection.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return row_to_user(row)


def validate_username(username: str) -> str:
    clean = username.strip()
    if not 3 <= len(clean) <= 32 or not USERNAME_PATTERN.fullmatch(clean):
        raise AuthServiceError("invalid_username", "Username must be 3–32 characters using letters, numbers, dots, dashes, or underscores.")
    return clean


def validate_password(password: str) -> None:
    if not 10 <= len(password) <= 128:
        raise AuthServiceError("invalid_password", "Password must be 10–128 characters.")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${derived.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt_hex, expected_hex = encoded.split("$", 5)
        if algorithm != "scrypt":
            return False
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(bytes.fromhex(expected_hex)),
        )
        return hmac.compare_digest(actual, bytes.fromhex(expected_hex))
    except (ValueError, TypeError):
        return False


def digest_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def row_to_user(row: sqlite3.Row) -> UserRecord:
    return UserRecord(
        id=int(row["id"]),
        username=str(row["username"]),
        role=str(row["role"]),
        status=str(row["status"]),
        created_at=str(row["created_at"]),
        approved_at=str(row["approved_at"]) if row["approved_at"] else None,
    )
