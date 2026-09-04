from typing import Literal

from pydantic import BaseModel, Field, field_validator


class AuthUser(BaseModel):
    id: int
    username: str
    role: Literal["admin", "user"]
    status: Literal["pending", "active", "disabled"]
    created_at: str
    approved_at: str | None = None


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=10, max_length=128)

    @field_validator("username")
    @classmethod
    def strip_username(cls, value: str) -> str:
        return value.strip()


class RegisterRequest(LoginRequest):
    pass


class AuthResponse(BaseModel):
    user: AuthUser


class RegisterResponse(BaseModel):
    user: AuthUser
    message: str


class UserListResponse(BaseModel):
    users: list[AuthUser]


class UserStatusRequest(BaseModel):
    status: Literal["active", "disabled"]
