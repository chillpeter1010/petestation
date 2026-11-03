"""Versioned, brand-neutral Ballpark avatar appearance."""

from typing import Literal

from pydantic import BaseModel, Field


class BallparkAvatarV1(BaseModel):
    avatar_version: Literal[1] = 1
    body_id: Literal["tone_1", "tone_2", "tone_3", "tone_4"] = "tone_2"
    uniform_id: Literal["neutral_home", "neutral_away"] = "neutral_home"
    palette_id: Literal["orange", "teal", "slate"] = "orange"
    number: int | None = Field(default=None, ge=0, le=99)
    # unknown is retained only for backward compatibility with existing saves.
    bats: Literal["R", "L", "S", "unknown"] = "R"
    throws: Literal["R", "L", "S", "unknown"] = "R"


def default_ballpark_avatar() -> dict[str, object]:
    return BallparkAvatarV1().model_dump()
