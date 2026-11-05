from typing import Literal

from pydantic import BaseModel


class ZoneRate(BaseModel):
    numerator: int | float
    denominator: int | float
    value: float | None
    league_average: float | None = None
    raw_pr: float | None = None
    color_pr: float | None = None
    peer_count: int = 0
    benchmark_status: str = "unavailable"


class ZoneRateCell(BaseModel):
    id: str
    label: str
    region: Literal["zone", "outside"]
    bounds: tuple[float, float, float, float]
    pitches: int
    rates: dict[str, ZoneRate]


class BatterZoneRatesResponse(BaseModel):
    contract_version: str = "batter_zone_rates_v1"
    year: int
    batter_id: int
    pitcher_hand: Literal["All", "L", "R"]
    status: Literal["ready", "insufficient_pa", "no_data", "unavailable"]
    season_pa: int
    eligible: bool
    split_pitches: int
    located_pitches: int
    missing_location_pitches: int
    zone_height_fallback_pitches: int
    metrics: list[dict[str, str]]
    cells: list[ZoneRateCell]
    benchmark_status: str = "unavailable"
    benchmark_version: str | None = None
    benchmark_min_denominator: int = 10
    benchmark_min_peers: int = 5
    scope: str = "Selected regular season, vs pitcher hand; PA eligibility uses the whole season"

