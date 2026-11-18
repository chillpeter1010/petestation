from datetime import date
from typing import Literal

from pydantic import BaseModel

from app.api.schemas.batter_zone_rates import BatterZoneRatesResponse


class ScoutTarget(BaseModel):
    u: float
    v: float
    zone: str
    swings: int
    located_swings: int


class PitchScoutResponse(BaseModel):
    contract_version: str = "pitch_scout_context_v1"
    mode: str = "historical_conditional_reference"
    before_date: date
    status: Literal["ready", "insufficient_history", "unavailable"]
    tier: str
    context_pitches: int
    swing_count: int
    swing_pct: float | None
    take_pct: float | None
    candidates: list[dict]
    target: ScoutTarget | None
    heatmap: BatterZoneRatesResponse
    source_version: str
