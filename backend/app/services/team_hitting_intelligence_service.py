from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb

from app.api.schemas.common import ResponseMeta
from app.api.schemas.batter_swing_timing import SwingTimingLeaderboardRow
from app.api.schemas.teams import (
    TeamHitterIntelligenceRow,
    TeamHittingIntelligenceResponse,
    TeamHittingProfile,
    TeamPitchFamilyHitter,
    TeamPitchFamilyProfile,
)
from app.core.config import settings
from app.repositories.pitch_repository import get_season_duckdb_path
from app.services.batter_swing_timing_service import (
    TEAM_NAME_TO_CODE,
    get_batter_swing_timing,
)


PITCH_FAMILIES = (
    ("fastball", "Fastball"),
    ("breaking", "Breaking Ball"),
    ("offspeed", "Offspeed"),
)


def get_team_hitting_intelligence(
    year: int,
    team_id: str,
    data_dir: Path | None = None,
) -> TeamHittingIntelligenceResponse:
    team_code = team_id.strip().upper()
    if team_code not in set(TEAM_NAME_TO_CODE.values()):
        raise ValueError(f"Unsupported MLB team: {team_id}")

    root = Path(data_dir or settings.data_dir).resolve()
    event_metrics = _load_event_metrics(year, team_code, root)
    team_all = _timing(year, "all", team_code, root)
    league_all = _timing(year, "all", "All", root)
    versus_left = _timing(year, "all", team_code, root, pitcher_hand="L")
    versus_right = _timing(year, "all", team_code, root, pitcher_hand="R")
    left_by_player = {row.batter_id: row for row in versus_left.leaderboard}
    right_by_player = {row.batter_id: row for row in versus_right.leaderboard}

    hitters = [
        _hitter_row(
            row,
            event_metrics.get((row.batter_id, "all"), {}),
            left_by_player.get(row.batter_id),
            right_by_player.get(row.batter_id),
        )
        for row in team_all.leaderboard
    ]
    hitters.sort(key=lambda row: (-(row.plate_appearances or 0), -row.swings, row.name))

    families: list[TeamPitchFamilyProfile] = []
    warnings = [*team_all.warnings, *league_all.warnings]
    for family, label in PITCH_FAMILIES:
        team_response = _timing(year, family, team_code, root)
        league_response = _timing(year, family, "All", root)
        warnings.extend(team_response.warnings)
        warnings.extend(league_response.warnings)
        family_hitters = [
            TeamPitchFamilyHitter(
                batter_id=row.batter_id,
                name=row.name,
                swings=row.n_swings,
                miss_distance=row.miss_distance,
                perfect_pct=row.perfect_pct,
                on_time_pct=row.on_time_pct,
                whiff_pct=row.whiff_pct,
                run_value_per_100_swings=_event_value(
                    event_metrics, row.batter_id, family, "run_value_per_100_swings"
                ),
            )
            for row in team_response.leaderboard
        ]
        family_hitters.sort(key=lambda row: -row.swings)
        families.append(
            TeamPitchFamilyProfile(
                family=family,
                label=label,
                team=_profile(
                    team_response.league,
                    _event_value(event_metrics, 0, family, "run_value_per_100_swings"),
                ),
                league=_profile(league_response.league),
                hitters=family_hitters,
            )
        )

    return TeamHittingIntelligenceResponse(
        meta=ResponseMeta(
            year=year,
            data_updated_at=team_all.data_updated_at,
            warnings=list(dict.fromkeys(warnings)),
        ),
        team_id=team_code,
        hitters=hitters,
        lineup=hitters[:9],
        team_profile=_profile(
            team_all.league,
            _event_value(event_metrics, 0, "all", "run_value_per_100_swings"),
        ),
        league_profile=_profile(league_all.league),
        pitch_families=families,
        warnings=list(dict.fromkeys(warnings)),
    )


def _timing(
    year: int,
    pitch_group: str,
    batter_team: str,
    data_dir: Path,
    pitcher_hand: str = "All",
):
    return get_batter_swing_timing(
        year=year,
        pitch_group=pitch_group,
        pitcher_hand=pitcher_hand,
        batter_team=batter_team,
        minimum_swings=0,
        minimum_plate_appearances=5,
        data_dir=data_dir,
    )


def _profile(
    row: SwingTimingLeaderboardRow | None,
    run_value_per_100_swings: float | None = None,
) -> TeamHittingProfile:
    if row is None:
        return TeamHittingProfile()
    return TeamHittingProfile(
        swings=row.n_swings,
        miss_distance=row.miss_distance,
        flawed_pct=row.flawed_pct,
        perfect_pct=row.perfect_pct,
        whiff_pct=row.whiff_pct,
        contact_pct=_contact_pct(row.whiff_pct),
        competitive_pct=row.competitive_pct,
        tied_up_pct=row.tied_up_pct,
        centered_pct=row.centered_pct,
        flail_pct=row.flail_pct,
        late_pct=row.late_pct,
        on_time_pct=row.on_time_pct,
        early_pct=row.early_pct,
        over_pct=row.over_pct,
        lined_up_pct=row.lined_up_pct,
        under_pct=row.under_pct,
        run_value_per_100_swings=run_value_per_100_swings,
    )


def _hitter_row(
    row: SwingTimingLeaderboardRow,
    event: dict[str, Any],
    versus_left: SwingTimingLeaderboardRow | None,
    versus_right: SwingTimingLeaderboardRow | None,
) -> TeamHitterIntelligenceRow:
    return TeamHitterIntelligenceRow(
        **_profile(row, event.get("run_value_per_100_swings")).model_dump(),
        batter_id=row.batter_id,
        name=row.name,
        hand=row.batter_side,
        age=row.age,
        plate_appearances=row.plate_appearances,
        avg_bat_speed=event.get("avg_bat_speed"),
        platoon_edge=_platoon_edge(row.batter_side, versus_left, versus_right),
        sample_status=row.sample_status,
    )


def _contact_pct(whiff_pct: float | None) -> float | None:
    return round(100 - whiff_pct, 3) if whiff_pct is not None else None


def _platoon_edge(
    hand: str,
    versus_left: SwingTimingLeaderboardRow | None,
    versus_right: SwingTimingLeaderboardRow | None,
) -> float | None:
    left_contact = _contact_pct(versus_left.whiff_pct) if versus_left else None
    right_contact = _contact_pct(versus_right.whiff_pct) if versus_right else None
    if left_contact is None or right_contact is None:
        return None
    if hand == "L":
        return round(right_contact - left_contact, 2)
    if hand == "R":
        return round(left_contact - right_contact, 2)
    return round(abs(left_contact - right_contact), 2)


def _event_value(
    metrics: dict[tuple[int, str], dict[str, Any]],
    player_id: int,
    family: str,
    key: str,
) -> float | None:
    value = metrics.get((player_id, family), {}).get(key)
    return float(value) if value is not None else None


def _load_event_metrics(
    year: int,
    team_code: str,
    data_dir: Path,
) -> dict[tuple[int, str], dict[str, Any]]:
    path = get_season_duckdb_path(year, data_dir)
    if not path.exists():
        return {}
    try:
        with duckdb.connect(str(path), read_only=True) as conn:
            tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
            table = "pitches_enriched" if "pitches_enriched" in tables else ("pitches" if "pitches" in tables else "")
            if not table:
                return {}
            columns = {row[0] for row in conn.execute(f"DESCRIBE {table}").fetchall()}
            batter = "batter_id" if "batter_id" in columns else "batter"
            team = "batter_team" if "batter_team" in columns else "offense_team"
            exit_velocity = "launch_speed" if "launch_speed" in columns else "NULL"
            frame = conn.execute(
                f"""
                WITH tracked AS (
                    SELECT
                        CAST({batter} AS BIGINT) AS batter_id,
                        CASE
                            WHEN pitch_type IN ('FF', 'SI', 'FC') THEN 'fastball'
                            WHEN pitch_type IN ('SL', 'ST', 'CU', 'KC', 'SV') THEN 'breaking'
                            WHEN pitch_type IN ('CH', 'FS', 'FO') THEN 'offspeed'
                            ELSE 'other'
                        END AS family,
                        TRY_CAST(bat_speed AS DOUBLE) AS bat_speed,
                        TRY_CAST({exit_velocity} AS DOUBLE) AS exit_velocity,
                        TRY_CAST(delta_run_exp AS DOUBLE) AS run_value,
                        QUANTILE_CONT(TRY_CAST(bat_speed AS DOUBLE), 0.10)
                            OVER (PARTITION BY CAST({batter} AS BIGINT)) AS competitive_cutoff
                    FROM {table}
                    WHERE UPPER(TRIM(CAST({team} AS VARCHAR))) = ?
                      AND {batter} IS NOT NULL
                      AND bat_speed IS NOT NULL
                      AND COALESCE(description, '') NOT IN ('foul_bunt', 'missed_bunt', 'bunt_foul_tip')
                ),
                grouped AS (
                    SELECT batter_id, family, COUNT(*) AS swings,
                           AVG(CASE WHEN bat_speed >= competitive_cutoff
                                      OR (bat_speed >= 60 AND exit_velocity >= 90)
                                    THEN bat_speed END) AS avg_bat_speed,
                           100 * SUM(COALESCE(run_value, 0)) / NULLIF(COUNT(*), 0) AS rv100
                    FROM tracked GROUP BY batter_id, family
                    UNION ALL
                    SELECT batter_id, 'all', COUNT(*),
                           AVG(CASE WHEN bat_speed >= competitive_cutoff
                                      OR (bat_speed >= 60 AND exit_velocity >= 90)
                                    THEN bat_speed END),
                           100 * SUM(COALESCE(run_value, 0)) / NULLIF(COUNT(*), 0)
                    FROM tracked GROUP BY batter_id
                    UNION ALL
                    SELECT 0, family, COUNT(*), NULL,
                           100 * SUM(COALESCE(run_value, 0)) / NULLIF(COUNT(*), 0)
                    FROM tracked GROUP BY family
                    UNION ALL
                    SELECT 0, 'all', COUNT(*), NULL,
                           100 * SUM(COALESCE(run_value, 0)) / NULLIF(COUNT(*), 0)
                    FROM tracked
                )
                SELECT batter_id, family, swings, avg_bat_speed, rv100 FROM grouped
                """,
                [team_code],
            ).fetchall()
    except duckdb.Error:
        return {}
    return {
        (int(player_id), str(family)): {
            "swings": int(swings or 0),
            "avg_bat_speed": round(float(avg_bat_speed), 2) if avg_bat_speed is not None else None,
            "run_value_per_100_swings": round(float(rv100), 2) if rv100 is not None else None,
        }
        for player_id, family, swings, avg_bat_speed, rv100 in frame
    }
