from typing import Any

from pydantic import BaseModel, Field

from app.api.schemas.common import ResponseMeta, TablePayload


class ComparisonMetric(BaseModel):
    key: str
    label: str
    value: int | float | str | None = None
    formatted_value: str
    percentile: float | None = None
    higher_is_better: bool = True


class ComparisonPlayer(BaseModel):
    player_id: int
    display_name: str
    team: str
    role: str
    display_label: str
    meta: dict[str, Any] = Field(default_factory=dict)


class ComparisonOptionsResponse(BaseModel):
    meta: ResponseMeta
    years: list[int] = Field(default_factory=list)
    pitchers: list[ComparisonPlayer] = Field(default_factory=list)


class ComparisonOverviewResponse(BaseModel):
    meta: ResponseMeta
    players: dict[str, ComparisonPlayer | None]
    percentile_cards: dict[str, list[ComparisonMetric]]
    charts: dict[str, Any] = Field(default_factory=dict)
    tables: dict[str, TablePayload] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
