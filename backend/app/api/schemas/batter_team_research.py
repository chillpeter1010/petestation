from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.api.schemas.common import ResponseMeta


class BatterTeamResearchResponse(BaseModel):
    meta: ResponseMeta
    team: str
    opponent_hand: str
    data_mode: str
    coverage: dict[str, Any] = Field(default_factory=dict)
    order_splits: list[dict[str, Any]] = Field(default_factory=list)
    hitters: list[dict[str, Any]] = Field(default_factory=list)
    position_coverage: list[dict[str, Any]] = Field(default_factory=list)
    lineup_prediction: dict[str, Any] = Field(default_factory=dict)
    scenarios: list[dict[str, Any]] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class BatterLineupScenarioResponse(BaseModel):
    meta: ResponseMeta
    team: str
    opponent_hand: str
    data_mode: str = "precomputed_lineup_scenarios"
    cache_status: Literal["current", "stale", "unavailable"] = "unavailable"
    generated_at: datetime | None = None
    model_version: str
    lineup_prediction: dict[str, Any] = Field(default_factory=dict)
    scenarios: list[dict[str, Any]] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
