from typing import Literal

from pydantic import BaseModel


class PlayerBio(BaseModel):
    contract_version: Literal["player_bio_v1"] = "player_bio_v1"
    player_id: int
    name: str | None = None
    height_raw: str | None = None
    height_inches: float | None = None
    height_m: float | None = None
    weight_lb: float | None = None
    weight_kg: float | None = None
    bats: Literal["R", "L", "S"] | None = None
    throws: Literal["R", "L", "S"] | None = None
    source: str = "MLB StatsAPI People"
    source_url: str
    temporal_scope: str = "current_listed_bio_not_historical_measurement"
    retrieved_at: str | None = None
    last_attempt_at: str | None = None
    freshness: Literal["fresh", "stale", "unavailable"] = "unavailable"
    warning: str | None = None
