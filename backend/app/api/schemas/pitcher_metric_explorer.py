from pydantic import BaseModel, Field


class PitcherMetricDefinition(BaseModel):
    key: str
    label: str
    category: str
    unit: str
    higher_is_better: bool | None = None
    description: str


class PitcherMetricExplorerRow(BaseModel):
    player_id: int
    name: str
    team: str
    role: str
    metrics: dict[str, float | None] = Field(default_factory=dict)


class PitcherMetricExplorerResponse(BaseModel):
    year: int
    available_years: list[int] = Field(default_factory=list)
    data_as_of: str | None = None
    metrics: list[PitcherMetricDefinition] = Field(default_factory=list)
    rows: list[PitcherMetricExplorerRow] = Field(default_factory=list)
    teams: list[str] = Field(default_factory=list)
    source_status: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
