from pydantic import BaseModel, Field

from app.api.schemas.common import ResponseMeta


class HomeVideoRecommendation(BaseModel):
    game_pk: int
    game_date: str
    play_id: str
    video_url: str
    home_team: str
    away_team: str
    inning: int | None = None
    inning_half: str | None = None
    pitcher_name: str
    batter_name: str
    pitch_name: str | None = None
    event: str | None = None
    description: str
    wpa: float | None = None
    recommendation_source: str


class HomeRecommendationsResponse(BaseModel):
    meta: ResponseMeta
    latest_data_date: str | None = None
    videos: list[HomeVideoRecommendation] = Field(default_factory=list)
