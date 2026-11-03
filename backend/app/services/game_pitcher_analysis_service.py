from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pandas as pd

from app.api.schemas.common import AnalysisResponse, MetricItem, ResponseMeta
from app.core.config import settings
from app.services.personal_service import (
    BALL_EVENTS,
    CALLED_STRIKE_EVENTS,
    ERROR_EVENTS,
    FOUL_EVENTS,
    HIT_EVENTS,
    IN_PLAY_EVENTS,
    OUT_EVENTS,
    SACRIFICE_EVENTS,
    STRIKEOUT_EVENTS,
    WALK_EVENTS,
    WHIFF_EVENTS,
    build_catcher_options,
    build_pitch_movement_summary,
    catcher_lookup_rows,
    clean_value,
    dataframe_to_table_payload,
    display_pitch_name,
    infer_pitcher_hand,
    load_personal_pitch_df,
)


PITCH_REPLAY_CONTRACT_VERSION = "pitch_trajectory_statcast_v1"
PITCH_REPLAY_PLATE_Y_FT = 17.0 / 12.0
PITCH_REPLAY_SAMPLE_POINTS = 31
PITCH_REPLAY_CLOSURE_LIMIT_IN = 3.0
PITCH_REPLAY_REQUIRED_FIELDS = (
    "release_pos_x",
    "release_pos_y",
    "release_pos_z",
    "vx0",
    "vy0",
    "vz0",
    "ax",
    "ay",
    "az",
)
from app.services.pitch_location_score_service import load_pitch_location_scores
from app.services.pitch_stuff_cache_service import load_pitch_stuff_scores
from app.services.player_archetype_practical_tag_service import get_practical_tags_for_pitcher
from app.services.player_archetype_slice3_service import CONTRACT_VERSION, slice3_roster_path
from app.services.stamina_lab_service import load_pitch_stamina_state


def _pitch_result_group(value: object) -> str:
    description = str(value or "").strip().lower()
    if description in CALLED_STRIKE_EVENTS:
        return "Called Strike"
    if description in WHIFF_EVENTS:
        return "Whiff"
    if description in FOUL_EVENTS:
        return "Foul"
    if description in IN_PLAY_EVENTS:
        return "In Play"
    if description in BALL_EVENTS:
        return "Ball"
    return "Other"


def _pa_result_group(value: object) -> str | None:
    event = str(value or "").strip().lower()
    if not event:
        return None
    if event in STRIKEOUT_EVENTS:
        return "Strikeout"
    if event in WALK_EVENTS:
        return "Walk"
    if event in HIT_EVENTS:
        return "Hit"
    if event in ERROR_EVENTS:
        return "Error"
    if event in SACRIFICE_EVENTS:
        return "Sacrifice"
    if event in OUT_EVENTS:
        return "Out"
    return "Other"


def _in_play_result_group(value: object) -> str | None:
    event = str(value or "").strip().lower()
    if not event:
        return None
    if event in HIT_EVENTS:
        return "Hit"
    if event in ERROR_EVENTS:
        return "Error"
    if event in SACRIFICE_EVENTS:
        return "Sacrifice"
    if event in OUT_EVENTS:
        return "Out"
    return "Other"


def _smallest_nonnegative_root(a: float, b: float, c: float, *, allow_zero: bool = False) -> float | None:
    epsilon = 1e-12
    minimum = -epsilon if allow_zero else epsilon
    if abs(a) < epsilon:
        if abs(b) < epsilon:
            return None
        root = -c / b
        return max(0.0, root) if root >= minimum else None
    discriminant = b * b - 4.0 * a * c
    if discriminant < -epsilon:
        return None
    root_term = math.sqrt(max(0.0, discriminant))
    roots = [(-b - root_term) / (2.0 * a), (-b + root_term) / (2.0 * a)]
    valid = [max(0.0, root) for root in roots if math.isfinite(root) and root >= minimum]
    return min(valid) if valid else None


def _finite_row_values(row: pd.Series, fields: tuple[str, ...]) -> tuple[dict[str, float], list[str]]:
    values: dict[str, float] = {}
    missing: list[str] = []
    for field in fields:
        value = pd.to_numeric(row.get(field), errors="coerce")
        if pd.isna(value) or not math.isfinite(float(value)):
            missing.append(field)
        else:
            values[field] = float(value)
    return values, missing


def build_pitch_trajectory(row: pd.Series) -> dict[str, Any]:
    """Build a release-to-plate path from Statcast's release and 50-foot states."""

    values, missing = _finite_row_values(row, PITCH_REPLAY_REQUIRED_FIELDS)
    if missing:
        return {
            "trajectory_status": "unavailable",
            "trajectory_reason": f"Missing required fields: {', '.join(missing)}",
            "flight_time_seconds": None,
            "closure_error_x_in": None,
            "closure_error_z_in": None,
            "trajectory_points": [],
        }

    release_to_50 = _smallest_nonnegative_root(
        -0.5 * values["ay"],
        values["vy0"],
        values["release_pos_y"] - 50.0,
        allow_zero=True,
    )
    fifty_to_plate = _smallest_nonnegative_root(
        0.5 * values["ay"],
        values["vy0"],
        50.0 - PITCH_REPLAY_PLATE_Y_FT,
    )
    if release_to_50 is None or fifty_to_plate is None:
        return {
            "trajectory_status": "unavailable",
            "trajectory_reason": "No physical positive-time root reaches the 50-foot state and plate plane.",
            "flight_time_seconds": None,
            "closure_error_x_in": None,
            "closure_error_z_in": None,
            "trajectory_points": [],
        }

    total_time = release_to_50 + fifty_to_plate
    release_vx = values["vx0"] - values["ax"] * release_to_50
    release_vy = values["vy0"] - values["ay"] * release_to_50
    release_vz = values["vz0"] - values["az"] * release_to_50
    points: list[dict[str, float]] = []
    for index in range(PITCH_REPLAY_SAMPLE_POINTS):
        progress = index / (PITCH_REPLAY_SAMPLE_POINTS - 1)
        time_value = total_time * progress
        points.append(
            {
                "progress": round(progress, 4),
                "time_seconds": round(time_value, 5),
                "x_ft": round(values["release_pos_x"] + release_vx * time_value + 0.5 * values["ax"] * time_value**2, 4),
                "y_ft": round(values["release_pos_y"] + release_vy * time_value + 0.5 * values["ay"] * time_value**2, 4),
                "z_ft": round(values["release_pos_z"] + release_vz * time_value + 0.5 * values["az"] * time_value**2, 4),
            }
        )

    plate_x = pd.to_numeric(row.get("plate_x"), errors="coerce")
    plate_z = pd.to_numeric(row.get("plate_z"), errors="coerce")
    if pd.isna(plate_x) or pd.isna(plate_z):
        status = "limited_trajectory"
        reason = "Observed plate location is unavailable, so trajectory closure cannot be verified."
        closure_x = None
        closure_z = None
    else:
        closure_x = abs(points[-1]["x_ft"] - float(plate_x)) * 12.0
        closure_z = abs(points[-1]["z_ft"] - float(plate_z)) * 12.0
        if max(closure_x, closure_z) > PITCH_REPLAY_CLOSURE_LIMIT_IN:
            status = "limited_trajectory"
            reason = f"Trajectory differs from the observed plate location by more than {PITCH_REPLAY_CLOSURE_LIMIT_IN:.0f} inches."
        else:
            status = "supported"
            reason = None

    return {
        "trajectory_status": status,
        "trajectory_reason": reason,
        "flight_time_seconds": round(total_time, 5),
        "closure_error_x_in": round(closure_x, 3) if closure_x is not None else None,
        "closure_error_z_in": round(closure_z, 3) if closure_z is not None else None,
        "trajectory_points": points,
    }


def build_game_pitch_replay_response(
    pitch_df: pd.DataFrame,
    *,
    year: int,
    game_pk: int,
    pitcher_id: int,
) -> AnalysisResponse:
    working = pitch_df.copy()
    if "game_pk" in working.columns:
        working = working[pd.to_numeric(working["game_pk"], errors="coerce").eq(int(game_pk))].copy()
    if "pitcher" in working.columns:
        working = working[pd.to_numeric(working["pitcher"], errors="coerce").eq(int(pitcher_id))].copy()
    if "pitch_type" in working.columns:
        pitch_types = working["pitch_type"].fillna("").astype(str).str.upper().str.strip()
        working = working[pitch_types.ne("") & pitch_types.ne("PO")].copy()

    if working.empty:
        return AnalysisResponse(
            meta=ResponseMeta(year=year, warnings=["No replay-eligible pitches were found for this pitcher and game."]),
            summary=[MetricItem(key="pitches", label="Pitches", value=0)],
            charts={
                "pitch_replay": [],
                "filter_options": {},
                "game_scope": {"game_pk": int(game_pk), "pitcher_id": int(pitcher_id)},
                "contract_version": PITCH_REPLAY_CONTRACT_VERSION,
            },
        )

    catcher_lookup = {row["catcher_id"]: row["catcher_name"] for row in catcher_lookup_rows(working, year=year)}
    if "fielder_2" in working.columns:
        catcher_ids = working["fielder_2"].map(lambda value: "" if pd.isna(value) else str(value).strip())
        working["catcher_name"] = catcher_ids.map(catcher_lookup)
    working["pitch_name"] = working["pitch_name"].map(display_pitch_name)
    working["pitch_result_group"] = working.get("description", pd.Series(index=working.index, dtype="object")).map(_pitch_result_group)
    working["pa_result_group"] = working.get("events", pd.Series(index=working.index, dtype="object")).map(_pa_result_group)
    working["in_play_result_group"] = working.get("events", pd.Series(index=working.index, dtype="object")).map(_in_play_result_group)

    scalar_columns = [
        "game_date", "game_pk", "pitcher", "batter", "at_bat_number", "pitch_number", "pitch_uid",
        "pitch_name", "pitch_type", "description", "events", "stand", "p_throws", "balls", "strikes",
        "bb_type", "fielder_2", "catcher_name", "release_speed", "release_extension", "release_pos_x",
        "release_pos_y", "release_pos_z", "plate_x", "plate_z", "sz_top", "sz_bot", "play_id", "video_url",
        "pitch_result_group", "in_play_result_group", "pa_result_group",
    ]
    rows: list[dict[str, Any]] = []
    for _, source_row in working.sort_values(["at_bat_number", "pitch_number"], kind="stable").iterrows():
        replay_row = {column: clean_value(source_row.get(column)) for column in scalar_columns if column in working.columns}
        replay_row.update(build_pitch_trajectory(source_row))
        rows.append(replay_row)

    statuses = pd.Series([row["trajectory_status"] for row in rows], dtype="object")
    pitch_names = sorted({str(value) for value in working["pitch_name"].dropna() if str(value).strip()})
    stands = sorted({str(value).upper() for value in working.get("stand", pd.Series(dtype="object")).dropna() if str(value).upper() in {"L", "R"}})
    counts = sorted(
        {
            f"{int(balls)}-{int(strikes)}"
            for balls, strikes in zip(
                pd.to_numeric(working.get("balls", pd.Series(dtype="float64")), errors="coerce"),
                pd.to_numeric(working.get("strikes", pd.Series(dtype="float64")), errors="coerce"),
            )
            if pd.notna(balls) and pd.notna(strikes)
        }
    )
    return AnalysisResponse(
        meta=ResponseMeta(
            year=year,
            warnings=[
                "Replay is a Statcast constant-acceleration reconstruction, not body motion capture or complete fluid physics.",
                "Release positions are back-projected to the 50-foot velocity/acceleration state before the path is sampled.",
            ],
        ),
        summary=[
            MetricItem(key="pitches", label="Pitches", value=len(rows)),
            MetricItem(key="supported_pitches", label="Supported", value=int(statuses.eq("supported").sum())),
            MetricItem(key="limited_pitches", label="Limited", value=int(statuses.eq("limited_trajectory").sum())),
            MetricItem(key="unavailable_pitches", label="Unavailable", value=int(statuses.eq("unavailable").sum())),
            MetricItem(key="pitcher_hand", label="Pitcher Hand", value=infer_pitcher_hand(working)),
        ],
        charts={
            "pitch_replay": rows,
            "filter_options": {
                "pitch_names": pitch_names,
                "catchers": build_catcher_options(working, year=year),
                "stands": stands,
                "counts": counts,
            },
            "game_scope": {"game_pk": int(game_pk), "pitcher_id": int(pitcher_id)},
            "contract_version": PITCH_REPLAY_CONTRACT_VERSION,
        },
    )


def get_game_pitch_replay(year: int, game_pk: int, pitcher_id: int) -> AnalysisResponse:
    return build_game_pitch_replay_response(
        load_personal_pitch_df(year=year, pitcher_id=pitcher_id, game_pk=game_pk),
        year=year,
        game_pk=game_pk,
        pitcher_id=pitcher_id,
    )


def build_game_pitch_shape_response(
    pitch_df: pd.DataFrame,
    *,
    year: int,
    game_pk: int,
    pitcher_id: int,
) -> AnalysisResponse:
    """Build one game-scoped payload shared by Movement and Release Point."""

    working = pitch_df.copy()
    if working.empty:
        return AnalysisResponse(
            meta=ResponseMeta(year=year, warnings=["No displayable pitches were found for this pitcher and game."]),
            summary=[MetricItem(key="pitches", label="Pitches", value=0)],
            charts={"pitch_shape_scatter": [], "filter_options": {}},
            tables={"movement_summary": dataframe_to_table_payload(pd.DataFrame()), "release_point_summary": dataframe_to_table_payload(pd.DataFrame())},
        )

    catcher_lookup = {row["catcher_id"]: row["catcher_name"] for row in catcher_lookup_rows(working, year=year)}
    if "fielder_2" in working.columns:
        catcher_ids = working["fielder_2"].map(lambda value: "" if pd.isna(value) else str(value).strip())
        working["catcher_name"] = catcher_ids.map(catcher_lookup)

    working["pitch_name"] = working["pitch_name"].map(display_pitch_name)
    working["h_break"] = pd.to_numeric(working.get("pfx_x"), errors="coerce") * -12.0
    working["v_break"] = pd.to_numeric(working.get("pfx_z"), errors="coerce") * 12.0
    working["release_pos_x_in"] = pd.to_numeric(working.get("release_pos_x"), errors="coerce") * 12.0
    working["release_pos_z_in"] = pd.to_numeric(working.get("release_pos_z"), errors="coerce") * 12.0
    working["pitch_result_group"] = working.get("description", pd.Series(index=working.index, dtype="object")).map(_pitch_result_group)
    working["pa_result_group"] = working.get("events", pd.Series(index=working.index, dtype="object")).map(_pa_result_group)
    working["in_play_result_group"] = working.get("events", pd.Series(index=working.index, dtype="object")).map(_in_play_result_group)

    row_columns = [
        "game_date", "game_pk", "pitcher", "at_bat_number", "pitch_number", "pitch_name", "pitch_type",
        "description", "events", "stand", "balls", "strikes", "bb_type", "fielder_2", "catcher_name",
        "plate_x", "plate_z", "h_break", "v_break", "release_pos_x", "release_pos_z",
        "release_pos_x_in", "release_pos_z_in", "release_extension", "release_speed", "arm_angle",
        "play_id", "video_url", "pitch_result_group", "in_play_result_group", "pa_result_group",
        "pitch_stuff_plus", "location_plus_pitch", "stamina_plus_trait", "stamina_expected_retention_delta",
        "stamina_expected_stuff_plus", "stamina_early_stuff_baseline", "stamina_reliability",
        "stamina_sample_label", "stamina_role",
    ]
    rows = dataframe_to_table_payload(working[[column for column in row_columns if column in working.columns]]).rows

    movement_summary = build_pitch_movement_summary(working)
    release_points = working.dropna(subset=["release_pos_x_in", "release_pos_z_in"]).copy()
    if release_points.empty:
        release_summary = pd.DataFrame()
    else:
        release_summary = (
            release_points.groupby("pitch_name", dropna=False)
            .agg(
                pitches=("pitch_name", "size"),
                release_pos_x_in=("release_pos_x_in", "mean"),
                release_pos_z_in=("release_pos_z_in", "mean"),
                release_extension=("release_extension", "mean") if "release_extension" in release_points.columns else ("pitch_name", "size"),
            )
            .reset_index()
            .sort_values("pitches", ascending=False)
        )

    pitch_names = sorted({str(value) for value in working["pitch_name"].dropna() if str(value).strip()})
    stands = sorted({str(value).upper() for value in working.get("stand", pd.Series(dtype="object")).dropna() if str(value).upper() in {"L", "R"}})
    counts = sorted(
        {
            f"{int(balls)}-{int(strikes)}"
            for balls, strikes in zip(
                pd.to_numeric(working.get("balls", pd.Series(dtype="float64")), errors="coerce"),
                pd.to_numeric(working.get("strikes", pd.Series(dtype="float64")), errors="coerce"),
            )
            if pd.notna(balls) and pd.notna(strikes)
        }
    )
    movement_count = int(working[["h_break", "v_break"]].notna().all(axis=1).sum())
    release_count = int(working[["release_pos_x_in", "release_pos_z_in"]].notna().all(axis=1).sum())
    return AnalysisResponse(
        meta=ResponseMeta(
            year=year,
            warnings=[
                "Movement and release-point values are descriptive for the selected game only.",
                "Release position uses the Statcast catcher-view horizontal coordinate and height above the ground.",
            ],
        ),
        summary=[
            MetricItem(key="pitches", label="Pitches", value=int(len(working))),
            MetricItem(key="pitcher_hand", label="Pitcher Hand", value=infer_pitcher_hand(working)),
            MetricItem(key="movement_pitches", label="Movement Pitches", value=movement_count),
            MetricItem(key="release_point_pitches", label="Release Point Pitches", value=release_count),
        ],
        charts={
            "pitch_shape_scatter": rows,
            "filter_options": {
                "pitch_names": pitch_names,
                "catchers": build_catcher_options(working, year=year),
                "stands": stands,
                "counts": counts,
            },
            "game_scope": {"game_pk": int(game_pk), "pitcher_id": int(pitcher_id)},
        },
        tables={
            "movement_summary": dataframe_to_table_payload(movement_summary),
            "release_point_summary": dataframe_to_table_payload(release_summary),
        },
    )


def get_game_pitch_shape(year: int, game_pk: int, pitcher_id: int) -> AnalysisResponse:
    pitch_df = load_personal_pitch_df(year=year, pitcher_id=pitcher_id, game_pk=game_pk)
    pitch_df = load_pitch_stamina_state(pitch_df, year=year, data_dir=settings.data_dir)
    if not pitch_df.empty:
        pitch_df["pitch_stuff_plus"] = load_pitch_stuff_scores(pitch_df).round(1)
        pitch_df["location_plus_pitch"] = load_pitch_location_scores(pitch_df).round(1)
    return build_game_pitch_shape_response(
        pitch_df,
        year=year,
        game_pk=game_pk,
        pitcher_id=pitcher_id,
    )


def _unavailable_payload(
    *,
    year: int,
    game_pk: int,
    pitcher_id: int,
    role: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "year": int(year),
        "game_pk": int(game_pk),
        "pitcher_id": int(pitcher_id),
        "role": role,
        "status": "unavailable",
        "support": {"pitches": 0, "label": "unavailable", "reliability": None},
        "tags": [],
        "version": CONTRACT_VERSION,
        "as_of": f"{int(year)} full-season snapshot",
        "time_scope": "full-season descriptive snapshot",
        "warnings": [reason],
    }


def _source_fingerprint(path: Path) -> str:
    stat = path.stat()
    return f"{path.name}:{stat.st_size}:{stat.st_mtime_ns}"


def _record_tags(record: pd.Series) -> list[dict[str, Any]]:
    tags: list[dict[str, Any]] = []
    for index in range(1, 5):
        label = record.get(f"tag_{index}")
        dimension = record.get(f"tag_{index}_dimension")
        if pd.isna(label) or not str(label).strip():
            continue
        dimension_value = str(dimension) if pd.notna(dimension) else "profile"
        if dimension_value == "primary_pair":
            continue
        tags.append(
            {
                "code": f"slice3_tag_{index}",
                "label": str(label),
                "kind": dimension_value,
                "description": f"Existing released Slice 3 {dimension_value.replace('_', ' ')} profile.",
                "evidence": {"dimension": dimension_value},
            }
        )
    return tags


def _record_support(record: pd.Series) -> dict[str, Any]:
    sample_size_value = pd.to_numeric(record.get("sample_size"), errors="coerce")
    reliability_value = pd.to_numeric(record.get("sample_reliability"), errors="coerce")
    support_value = record.get("support_status")
    sample_status_value = record.get("sample_status")
    support_status = str(support_value) if pd.notna(support_value) and str(support_value) else "unassigned"
    sample_status = str(sample_status_value) if pd.notna(sample_status_value) and str(sample_status_value) else "unknown"
    return {
        "pitches": int(sample_size_value) if pd.notna(sample_size_value) else 0,
        "label": support_status,
        "reliability": round(float(reliability_value), 3) if pd.notna(reliability_value) else None,
        "sample_status": sample_status,
    }


def _prior_tag_reference(roster: pd.DataFrame, *, year: int, pitcher_id: int, role: str) -> dict[str, Any] | None:
    candidates = roster[
        roster["year"].lt(int(year))
        & roster["population"].eq("pitcher")
        & roster["player_id"].eq(int(pitcher_id))
        & roster["role"].eq(role)
    ].sort_values("year", ascending=False)
    for _, record in candidates.iterrows():
        tags = _record_tags(record) + _practical_tag_items(
            year=int(record["year"]), pitcher_id=pitcher_id, role=role, data_dir=roster.attrs.get("data_dir")
        )
        if tags:
            reference_year = int(record["year"])
            return {
                "year": reference_year,
                "role": role,
                "support": _record_support(record),
                "tags": tags,
                "as_of": f"{reference_year} full-season snapshot",
            }
    return None


def _practical_tag_items(year: int, pitcher_id: int, role: str, data_dir: Path | str | None) -> list[dict[str, Any]]:
    return [
        {
            "code": str(item.get("code") or f"practical_{index}"),
            "label": str(item.get("label") or "Practical profile"),
            "kind": str(item.get("dimension") or "practical"),
            "description": str(item.get("description") or "Lab-first full-season descriptive profile."),
            "evidence": item.get("evidence") if isinstance(item.get("evidence"), dict) else {},
            "source": "practical_v1",
        }
        for index, item in enumerate(
            get_practical_tags_for_pitcher(year, pitcher_id, role, Path(data_dir) if data_dir else None), start=1
        )
    ]


def get_game_pitcher_tags(
    year: int,
    game_pk: int,
    pitcher_id: int,
    role: str,
    data_dir: Path = settings.data_dir,
) -> dict[str, Any]:
    """Return the existing released Slice 3 pitcher tags for a Game Center pitcher.

    These are full-season descriptive profiles.  The game-scoped route is only a
    convenient selector boundary; it must not imply that the tags were known as
    of the selected historical game.
    """

    normalized_role = str(role or "").upper()
    if normalized_role not in {"SP", "RP"}:
        return _unavailable_payload(
            year=year,
            game_pk=game_pk,
            pitcher_id=pitcher_id,
            role=normalized_role,
            reason="role must be SP or RP",
        )

    source_path = slice3_roster_path(Path(data_dir))
    if not source_path.exists():
        return _unavailable_payload(
            year=year,
            game_pk=game_pk,
            pitcher_id=pitcher_id,
            role=normalized_role,
            reason="the released Slice 3 pitcher-tag roster is unavailable",
        )

    roster = pd.read_parquet(source_path)
    roster.attrs["data_dir"] = str(Path(data_dir))
    row = roster[
        roster["year"].eq(int(year))
        & roster["population"].eq("pitcher")
        & roster["player_id"].eq(int(pitcher_id))
        & roster["role"].eq(normalized_role)
    ]
    current_practical_tags = _practical_tag_items(year, pitcher_id, normalized_role, Path(data_dir))
    reference = _prior_tag_reference(
        roster,
        year=year,
        pitcher_id=pitcher_id,
        role=normalized_role,
    )
    if row.empty:
        payload = _unavailable_payload(
            year=year,
            game_pk=game_pk,
            pitcher_id=pitcher_id,
            role=normalized_role,
            reason="this pitcher-season-role is not present in the released Slice 3 roster",
        )
        if current_practical_tags:
            payload["status"] = "review"
            payload["tags"] = current_practical_tags
            payload["warnings"].append("Only Lab-first practical tags are available for this pitcher-season-role.")
            reference = None
        payload["reference"] = reference
        payload["source_fingerprint"] = _source_fingerprint(source_path)
        if reference:
            payload["warnings"].append(
                f"Showing {reference['year']} only as a labeled same-role reference; it is not a current-season tag."
            )
        return payload

    record = row.iloc[0]
    core_tags = _record_tags(record)
    tags = core_tags + current_practical_tags
    support = _record_support(record)
    support_status = str(support["label"])
    warnings = [
        "Existing Slice 3 tags use the complete season and may include games after the selected historical game."
    ]
    if not tags:
        warnings.append("No released Slice 3 tag is assigned for this pitcher-season-role.")
        if reference:
            warnings.append(
                f"Showing {reference['year']} only as a labeled same-role reference; it is not a current-season tag."
            )

    return {
        "year": int(year),
        "game_pk": int(game_pk),
        "pitcher_id": int(pitcher_id),
        "role": normalized_role,
        "status": "review" if current_practical_tags and not core_tags else support_status,
        "support": support,
        "tags": tags,
        "reference": reference if not tags else None,
        "version": CONTRACT_VERSION,
        "as_of": f"{int(year)} full-season snapshot",
        "time_scope": "full-season descriptive snapshot",
        "source_fingerprint": _source_fingerprint(source_path),
        "warnings": warnings,
    }
