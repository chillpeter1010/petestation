from typing import Any, Literal

from pydantic import BaseModel, Field

from app.api.schemas.common import BatterOption, ResponseMeta


class BatterPeriodOptionsResponse(BaseModel):
    meta: ResponseMeta
    years: list[int] = Field(default_factory=list)
    batters: list[BatterOption] = Field(default_factory=list)


class BatterPeriodMetric(BaseModel):
    key: str
    label: str
    group: Literal["sample", "production", "contact", "discipline", "tracking", "timing"]
    unit: Literal["count", "rate", "mph", "ft", "in", "pct"]
    delta_unit: Literal["count", "rate", "mph", "ft", "in", "pp"]
    period_a: int | float | None = None
    period_b: int | float | None = None
    delta: int | float | None = None
    denominator_label: str
    period_a_denominator: int
    period_b_denominator: int


class BatterPeriodWindow(BaseModel):
    label: str
    year: int
    start_date: str
    end_date: str
    pitches: int


class BatterPeriodComparisonResponse(BaseModel):
    meta: ResponseMeta
    batter: BatterOption | None = None
    periods: dict[str, BatterPeriodWindow]
    filters: dict[str, list[str]] = Field(default_factory=dict)
    metrics: list[BatterPeriodMetric] = Field(default_factory=list)
    heatmaps: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    bat_speed_domain: list[float] | None = None
    timing_reference: dict[str, dict[str, Any]] = Field(default_factory=dict)
    source_audit: dict[str, Any] = Field(default_factory=dict)
