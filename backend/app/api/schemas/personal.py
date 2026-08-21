from pydantic import BaseModel, Field

from app.api.schemas.common import AnalysisResponse, ResponseMeta


class PersonalOverviewResponse(AnalysisResponse):
    pitcher_id: int
    selected_pitcher: dict[str, object] = Field(default_factory=dict)
    filters: dict[str, list[str]] = Field(default_factory=dict)

    @classmethod
    def empty(cls, year: int, pitcher_id: int) -> "PersonalOverviewResponse":
        return cls(meta=ResponseMeta(year=year), pitcher_id=pitcher_id)
