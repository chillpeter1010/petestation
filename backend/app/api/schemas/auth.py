from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.core.mlb_teams import MLB_TEAM_ID_TO_CODE
from app.core.ballpark_avatar import BallparkAvatarV1


class AuthUser(BaseModel):
    id: int
    username: str
    role: Literal["admin", "user"]
    status: Literal["pending", "active", "disabled"]
    created_at: str
    approved_at: str | None = None
    favorite_team_id: int | None = None
    favorite_team_code: str | None = None
    avatar_setup_status: Literal["pending", "default"] = "pending"
    avatar: BallparkAvatarV1 = Field(default_factory=BallparkAvatarV1)
    avatar_recovery_needed: bool = False


class AvatarUpdateRequest(BaseModel):
    avatar: BallparkAvatarV1


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=10, max_length=128)

    @field_validator("username")
    @classmethod
    def strip_username(cls, value: str) -> str:
        return value.strip()


class RegisterRequest(LoginRequest):
    favorite_team_id: int | None = None

    @field_validator("favorite_team_id")
    @classmethod
    def validate_favorite_team(cls, value: int | None) -> int | None:
        if value is not None and value not in MLB_TEAM_ID_TO_CODE:
            raise ValueError("Unsupported MLB team.")
        return value


class AuthResponse(BaseModel):
    user: AuthUser


class RegisterResponse(BaseModel):
    user: AuthUser
    message: str


class UserListResponse(BaseModel):
    users: list[AuthUser]


class UserStatusRequest(BaseModel):
    status: Literal["active", "disabled"]


class UserProfileRequest(BaseModel):
    favorite_team_id: int | None = None
    avatar_setup_status: Literal["pending", "default"] | None = None

    @field_validator("favorite_team_id")
    @classmethod
    def validate_favorite_team(cls, value: int | None) -> int | None:
        if value is not None and value not in MLB_TEAM_ID_TO_CODE:
            raise ValueError("Unsupported MLB team.")
        return value
