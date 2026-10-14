from fastapi import APIRouter, HTTPException

from app.api.schemas.stamina import (
    StaminaGameStatesResponse,
    StaminaLeaderboardResponse,
    StaminaOverviewResponse,
    StaminaPhysicalStabilityResponse,
    StaminaCommandRetentionResponse,
    StaminaSlice18Result,
    StaminaResearchCurvesResponse,
    StaminaSeasonSummariesResponse,
    StaminaSlice13Result,
    StaminaSlice13AResult,
)
from app.services.physical_stability_service import get_physical_stability
from app.services.command_retention_service import get_command_retention, get_incremental_validation
from app.services.stamina_lab_service import (
    get_stamina_game_states,
    get_stamina_leaderboard,
    get_stamina_external_validation,
    get_stamina_season_bias_repair,
    get_stamina_overview,
    get_stamina_research_curves,
    get_stamina_season_summaries,
)

router = APIRouter()


@router.get("/overview", response_model=StaminaOverviewResponse)
def read_stamina_overview(year: int = 2026) -> StaminaOverviewResponse:
    try:
        return StaminaOverviewResponse(**get_stamina_overview(year))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/research-curves", response_model=StaminaResearchCurvesResponse)
def read_stamina_research_curves(year: int = 2026, pitcher_id: int = 0) -> StaminaResearchCurvesResponse:
    try:
        return StaminaResearchCurvesResponse(**get_stamina_research_curves(year, pitcher_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/game-states", response_model=StaminaGameStatesResponse)
def read_stamina_game_states(year: int = 2026, pitcher_id: int = 0) -> StaminaGameStatesResponse:
    try:
        return StaminaGameStatesResponse(**get_stamina_game_states(year, pitcher_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/physical-stability", response_model=StaminaPhysicalStabilityResponse)
def read_physical_stability(year: int = 2026, pitcher_id: int = 0) -> StaminaPhysicalStabilityResponse:
    try:
        return StaminaPhysicalStabilityResponse(**get_physical_stability(year, pitcher_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/command-retention", response_model=StaminaCommandRetentionResponse)
def read_command_retention(year: int = 2026, pitcher_id: int = 0) -> StaminaCommandRetentionResponse:
    try:
        return StaminaCommandRetentionResponse(**get_command_retention(year, pitcher_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/incremental-validation", response_model=StaminaSlice18Result)
def read_incremental_validation(year: int = 2026) -> StaminaSlice18Result:
    try:
        return StaminaSlice18Result(**get_incremental_validation(year))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/season-summaries", response_model=StaminaSeasonSummariesResponse)
def read_stamina_season_summaries(year: int = 2026) -> StaminaSeasonSummariesResponse:
    try:
        return StaminaSeasonSummariesResponse(**get_stamina_season_summaries(year))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/external-validation", response_model=StaminaSlice13Result)
def read_stamina_external_validation(year: int = 2026) -> StaminaSlice13Result:
    try:
        return StaminaSlice13Result(**get_stamina_external_validation(year))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/season-bias-repair", response_model=StaminaSlice13AResult)
def read_stamina_season_bias_repair(year: int = 2026) -> StaminaSlice13AResult:
    try:
        return StaminaSlice13AResult(**get_stamina_season_bias_repair(year))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/leaderboard", response_model=StaminaLeaderboardResponse)
def read_stamina_leaderboard(year: int = 2026) -> StaminaLeaderboardResponse:
    try:
        return StaminaLeaderboardResponse(**get_stamina_leaderboard(year))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
