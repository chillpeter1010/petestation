from fastapi import APIRouter, HTTPException

from app.api.schemas.leverage import LeverageOverviewResponse, LeverageScenarioRequest, LeverageScenarioResponse
from app.services.leverage_lab_service import calculate_scenario, get_leverage_overview

router = APIRouter()


@router.get("/overview", response_model=LeverageOverviewResponse)
def read_leverage_overview(year: int = 2026) -> LeverageOverviewResponse:
    try:
        return LeverageOverviewResponse(**get_leverage_overview(year))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/calculator", response_model=LeverageScenarioResponse)
def read_leverage_calculator(request: LeverageScenarioRequest) -> LeverageScenarioResponse:
    try:
        return LeverageScenarioResponse(**calculate_scenario(request))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
