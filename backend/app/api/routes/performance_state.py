from fastapi import APIRouter, HTTPException

from app.api.schemas.performance_state import (
    PerformanceStateLeaderboardResponse,
    PerformanceStateOverviewResponse,
    PerformanceStateShadowResponse,
    PerformanceStateV2AuditResponse,
    PerformanceStateV2Slice14AuditResponse,
    PerformanceStateV2Slice15AuditResponse,
    PerformanceStateV2Slice16AuditResponse,
    PerformanceStateV2Slice17AuditResponse,
    PerformanceStateV2Slice18To20AuditResponse,
    PerformanceStateV2Slice21To22AuditResponse,
    PerformanceStateV2StrictReplayResponse,
    PerformanceStateV2LabResponse,
    PitcherPerformanceStatesResponse,
)
from app.services.performance_state_service import (
    get_performance_state_overview,
    get_pitcher_performance_states,
)
from app.services.performance_state_forecast_service import (
    get_performance_state_leaderboard,
    get_performance_state_shadow_audit,
)
from app.services.performance_state_v2_service import get_performance_state_v2_audit
from app.services.performance_state_v2_slice14_service import get_performance_state_v2_slice14_audit
from app.services.performance_state_v2_slice15_service import get_performance_state_v2_slice15_audit
from app.services.performance_state_v2_slice16_service import get_performance_state_v2_slice16_audit
from app.services.performance_state_v2_slice17_service import get_performance_state_v2_slice17_audit
from app.services.performance_state_v2_slice18_20_service import get_performance_state_v2_slice18_20_audit
from app.services.performance_state_v2_slice21_22_service import get_performance_state_v2_slice21_22_audit
from app.services.performance_state_v2_strict_replay_service import get_strict_2026_replay_audit
from app.services.performance_state_v2_lab_service import get_performance_state_v2_lab


router = APIRouter()


@router.get("/v2-audit", response_model=PerformanceStateV2AuditResponse)
def read_performance_state_v2_audit() -> PerformanceStateV2AuditResponse:
    try:
        return PerformanceStateV2AuditResponse(**get_performance_state_v2_audit())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/v2-slice14-audit", response_model=PerformanceStateV2Slice14AuditResponse)
def read_performance_state_v2_slice14_audit() -> PerformanceStateV2Slice14AuditResponse:
    try:
        return PerformanceStateV2Slice14AuditResponse(**get_performance_state_v2_slice14_audit())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/v2-slice15-audit", response_model=PerformanceStateV2Slice15AuditResponse)
def read_performance_state_v2_slice15_audit() -> PerformanceStateV2Slice15AuditResponse:
    try:
        return PerformanceStateV2Slice15AuditResponse(**get_performance_state_v2_slice15_audit())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/v2-slice16-audit", response_model=PerformanceStateV2Slice16AuditResponse)
def read_performance_state_v2_slice16_audit() -> PerformanceStateV2Slice16AuditResponse:
    try:
        return PerformanceStateV2Slice16AuditResponse(**get_performance_state_v2_slice16_audit())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/v2-slice17-audit", response_model=PerformanceStateV2Slice17AuditResponse)
def read_performance_state_v2_slice17_audit() -> PerformanceStateV2Slice17AuditResponse:
    try:
        return PerformanceStateV2Slice17AuditResponse(**get_performance_state_v2_slice17_audit())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/v2-slice18-20-audit", response_model=PerformanceStateV2Slice18To20AuditResponse)
def read_performance_state_v2_slice18_20_audit() -> PerformanceStateV2Slice18To20AuditResponse:
    try:
        return PerformanceStateV2Slice18To20AuditResponse(**get_performance_state_v2_slice18_20_audit())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/v2-slice21-22-audit", response_model=PerformanceStateV2Slice21To22AuditResponse)
def read_performance_state_v2_slice21_22_audit() -> PerformanceStateV2Slice21To22AuditResponse:
    try:
        return PerformanceStateV2Slice21To22AuditResponse(**get_performance_state_v2_slice21_22_audit())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/v2-strict-2026-replay", response_model=PerformanceStateV2StrictReplayResponse)
def read_strict_2026_replay() -> PerformanceStateV2StrictReplayResponse:
    try:
        return PerformanceStateV2StrictReplayResponse(**get_strict_2026_replay_audit())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/v2-lab", response_model=PerformanceStateV2LabResponse)
def read_performance_state_v2_lab(
    year: int = 2026,
    role: str = "SP",
    target: str = "process_collapse",
    minimum_forecasts: int = 1,
) -> PerformanceStateV2LabResponse:
    try:
        return PerformanceStateV2LabResponse(**get_performance_state_v2_lab(
            year=year,
            role=role,
            target=target,
            minimum_forecasts=minimum_forecasts,
        ))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/shadow", response_model=PerformanceStateShadowResponse)
def read_performance_state_shadow() -> PerformanceStateShadowResponse:
    try:
        return PerformanceStateShadowResponse(**get_performance_state_shadow_audit())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/leaderboard", response_model=PerformanceStateLeaderboardResponse)
def read_performance_state_leaderboard(
    year: int = 2026,
    role: str = "SP",
    target: str = "process_collapse",
    minimum_forecasts: int = 1,
) -> PerformanceStateLeaderboardResponse:
    try:
        return PerformanceStateLeaderboardResponse(**get_performance_state_leaderboard(
            year=year,
            role=role,
            target=target,
            minimum_forecasts=minimum_forecasts,
        ))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/overview", response_model=PerformanceStateOverviewResponse)
def read_performance_state_overview() -> PerformanceStateOverviewResponse:
    try:
        return PerformanceStateOverviewResponse(**get_performance_state_overview())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/player", response_model=PitcherPerformanceStatesResponse)
def read_pitcher_performance_states(
    year: int = 2026,
    pitcher_id: int = 0,
    role: str | None = None,
) -> PitcherPerformanceStatesResponse:
    try:
        return PitcherPerformanceStatesResponse(
            **get_pitcher_performance_states(year=year, pitcher_id=pitcher_id, role=role)
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
