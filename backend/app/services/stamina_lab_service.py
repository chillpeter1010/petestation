from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd

from app.core.config import settings
from app.repositories.pitch_repository import get_season_duckdb_path, resolve_pitch_table
from app.services.pitch_location_score_service import load_pitch_location_scores
from app.services.pitch_stuff_cache_service import load_pitch_stuff_scores


MODEL_VERSION = "stamina_observed_game_state_v1_1"
PITCH_KEY = ["game_pk", "at_bat_number", "pitch_number", "pitcher"]
CORE_COLUMNS = [*PITCH_KEY, "game_date", "inning", "pitcher_team"]
SOURCE_COLUMNS = [
    *PITCH_KEY, "pitch_uid", "game_date", "game_type", "pitch_type", "pitch_name", "batter", "player_name",
    "pitcher_team", "home_team", "away_team", "inning", "inning_topbot", "p_throws",
    "stand", "balls", "strikes", "n_thruorder_pitcher", "release_speed", "pfx_x", "pfx_z",
    "release_spin_rate", "spin_axis", "release_extension", "release_pos_x", "release_pos_z",
    "arm_angle", "plate_x", "plate_z", "sz_top", "sz_bot",
]
SP_BUCKETS = [(1, 20, "1–20"), (21, 40, "21–40"), (41, 60, "41–60"), (61, 80, "61–80"), (81, 100, "81–100"), (101, 10_000, "101+")]
RP_BUCKETS = [(1, 5, "1–5"), (6, 10, "6–10"), (11, 15, "11–15"), (16, 25, "16–25"), (26, 10_000, "26+")]
SP_SEASON_BUCKETS = [(0, 499, "0–499"), (500, 999, "500–999"), (1000, 1499, "1,000–1,499"), (1500, 1999, "1,500–1,999"), (2000, 100_000, "2,000+")]
RP_SEASON_BUCKETS = [(0, 199, "0–199"), (200, 399, "200–399"), (400, 599, "400–599"), (600, 799, "600–799"), (800, 100_000, "800+")]
PITCH_FAMILY_TYPES = {
    "Fastball": ("FF", "FA", "SI", "FC"),
    "Breaking": ("SL", "ST", "CU", "KC", "SV"),
    "Offspeed": ("CH", "FS", "FO"),
}
PITCH_FAMILY_BY_TYPE = {
    pitch_type: family
    for family, pitch_types in PITCH_FAMILY_TYPES.items()
    for pitch_type in pitch_types
}


def stamina_dataset_path(year: int, data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / f"stamina_lab_{int(year)}.parquet"


def stamina_meta_path(year: int, data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / f"stamina_lab_{int(year)}.json"


def stamina_v2_pitch_curve_path(year: int, data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / f"stamina_v2_pitch_curves_{int(year)}.parquet"


def stamina_v2_appearance_curve_path(year: int, data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / f"stamina_v2_appearance_curves_{int(year)}.parquet"


def stamina_v2_hierarchical_path(year: int, data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / f"stamina_v2_hierarchical_{int(year)}.parquet"


def stamina_v2_candidate_path(year: int, data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / f"stamina_v2_candidates_{int(year)}.parquet"


def stamina_v2_multisignal_path(year: int, data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / f"stamina_v2_multisignal_{int(year)}.parquet"


def stamina_game_state_path(year: int, data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / f"stamina_game_states_{int(year)}.parquet"


def stamina_game_state_window_path(year: int, data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / f"stamina_game_state_windows_{int(year)}.parquet"


def stamina_season_summary_path(year: int, data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / f"stamina_season_summaries_{int(year)}.parquet"


def stamina_external_validation_path(year: int, data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / f"stamina_external_validation_{int(year)}.json"


def stamina_adjusted_season_summary_path(year: int, data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / f"stamina_adjusted_season_summaries_{int(year)}.parquet"


def stamina_season_bias_repair_path(year: int, data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / f"stamina_season_bias_repair_{int(year)}.json"


def stamina_v2_archetype_path(year: int, data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / f"stamina_v2_archetypes_{int(year)}.parquet"


def stamina_cold_start_appearance_path(year: int, data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / f"stamina_cold_start_appearances_{int(year)}.parquet"


def stamina_cold_start_backtest_path(year: int, data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / f"stamina_cold_start_backtest_{int(year)}.parquet"


def stamina_single_season_candidate_path(year: int, data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / f"stamina_single_season_candidates_{int(year)}.parquet"


def stamina_cold_start_v2_development_path(year: int, data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / f"stamina_cold_start_v2_development_{int(year)}.parquet"


def stamina_cold_start_v2_audit_path(year: int, data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / f"stamina_cold_start_v2_audit_{int(year)}.parquet"


def refresh_stamina_dataset(year: int = 2026, data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    db_path = get_season_duckdb_path(year, root)
    if not db_path.exists():
        raise FileNotFoundError(f"Season database not found: {db_path}")

    frame, source_counts = _load_source(year, db_path)
    regular_rows = len(frame)
    for column in ["pitcher", "game_pk", "at_bat_number", "pitch_number", "inning"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["game_date"] = pd.to_datetime(frame["game_date"], errors="coerce")
    fallback_team = np.where(frame["inning_topbot"].eq("Top"), frame["home_team"], frame["away_team"])
    frame["pitcher_team"] = frame["pitcher_team"].fillna(pd.Series(fallback_team, index=frame.index)).replace("", pd.NA)

    core_valid = frame[CORE_COLUMNS].notna().all(axis=1)
    missing_core = int((~core_valid).sum())
    frame = frame.loc[core_valid].copy()
    duplicate_mask = frame.duplicated(PITCH_KEY, keep="last")
    duplicate_rows = int(duplicate_mask.sum())
    frame = frame.loc[~duplicate_mask].copy()
    frame[["pitcher", "game_pk", "at_bat_number", "pitch_number", "inning"]] = frame[
        ["pitcher", "game_pk", "at_bat_number", "pitch_number", "inning"]
    ].astype(int)
    frame = frame.sort_values(["game_date", "game_pk", "at_bat_number", "pitch_number", "pitcher"], kind="stable").reset_index(drop=True)

    appearances = (
        frame.groupby(["pitcher", "game_pk", "pitcher_team", "game_date"], as_index=False)
        .agg(first_sequence=("at_bat_number", "min"), pitches=("pitch_number", "size"))
    )
    first_pitch = (
        frame.assign(sequence=frame["at_bat_number"] * 1000 + frame["pitch_number"])
        .groupby(["pitcher", "game_pk", "pitcher_team", "game_date"], as_index=False)
        .agg(first_sequence=("sequence", "min"))
    )
    appearances = appearances.drop(columns="first_sequence").merge(
        first_pitch, on=["pitcher", "game_pk", "pitcher_team", "game_date"], how="left"
    )
    team_first = appearances.groupby(["game_pk", "pitcher_team"])["first_sequence"].transform("min")
    appearances["appearance_role"] = np.where(appearances["first_sequence"].eq(team_first), "SP", "RP")
    appearances = appearances.sort_values(["pitcher", "game_date", "game_pk"], kind="stable")
    appearances["previous_date"] = appearances.groupby("pitcher")["game_date"].shift(1)
    appearances["days_rest"] = (appearances["game_date"] - appearances["previous_date"]).dt.days.sub(1).clip(lower=0)
    appearances["appearance_number"] = appearances.groupby(["pitcher", "appearance_role"]).cumcount() + 1
    appearances["season_pitches_before"] = appearances.groupby(["pitcher", "appearance_role"])["pitches"].cumsum() - appearances["pitches"]
    appearances = _add_workload_history(appearances)

    frame = frame.merge(
        appearances[[
            "pitcher", "game_pk", "appearance_role", "days_rest", "appearance_number", "season_pitches_before",
            "all_role_appearance_number", "all_role_season_pitches_before", "previous_appearance_pitches",
            "workload_pitches_3d", "workload_pitches_7d", "workload_pitches_14d", "workload_pitches_28d",
            "workload_appearances_3d", "workload_appearances_7d", "workload_appearances_14d", "workload_appearances_28d",
            "back_to_back", "long_gap", "role_changed",
        ]],
        on=["pitcher", "game_pk"],
        how="left",
    )
    frame["appearance_pitch_number"] = frame.groupby(["pitcher", "game_pk"]).cumcount() + 1
    frame["inning_pitch_number"] = frame.groupby(["pitcher", "game_pk", "inning"]).cumcount() + 1
    frame["pitch_stuff_plus"] = load_pitch_stuff_scores(frame, root)
    frame["location_plus_pitch"] = load_pitch_location_scores(frame, root)
    frame["pitch_family"] = frame["pitch_type"].astype("string").str.upper().map(PITCH_FAMILY_BY_TYPE)

    meta = _build_overview(year, frame, appearances, source_counts, regular_rows, missing_core, duplicate_rows)
    meta["arm_angle_audit"] = _build_arm_angle_audit(frame)
    meta["slice1"] = _build_slice1(frame)
    meta["slice2"] = _build_slice2(frame, meta["slice1"])
    meta["slice3"] = _build_slice3(frame)
    meta["slice4"] = _build_slice4(frame, year, root)
    meta["slice5"] = _build_slice5(frame, year, root, meta["slice3"])
    frame, meta["slice6"] = _attach_stamina_state(frame, meta["slice5"], meta["slice3"])
    meta["slice7"] = _build_slice7(frame, meta["slice5"])
    pitch_curves, appearance_curves, meta["slice8"] = _build_slice8(frame, year, root)
    hierarchical, meta["slice9"] = _build_slice9(pitch_curves)
    candidates, meta["slice10"] = _build_slice10(pitch_curves, meta["slice7"], year, root)
    multisignal, meta["slice11"] = _build_slice11(frame, pitch_curves)
    reference_year = int(year - 1)
    reference_curve_path = stamina_v2_pitch_curve_path(reference_year, root)
    reference_source_path = stamina_dataset_path(reference_year, root)
    game_states = pd.DataFrame()
    game_state_windows = pd.DataFrame()
    if reference_curve_path.exists() and reference_source_path.exists():
        with duckdb.connect() as connection:
            reference_curves = connection.execute("SELECT * FROM read_parquet(?)", [str(reference_curve_path)]).fetchdf()
            reference_source = connection.execute(
                "SELECT pitcher, game_pk, game_date, appearance_role, appearance_pitch_number, "
                "player_name, pitcher_team, location_plus_pitch, release_speed "
                "FROM read_parquet(?) WHERE appearance_role = 'SP'",
                [str(reference_source_path)],
            ).fetchdf()
        game_states, game_state_windows, meta["slice11_game_state"] = _build_game_states(
            reference_curves, pitch_curves, reference_source, frame, reference_year, year
        )
    meta["source_modified_at"] = db_path.stat().st_mtime_ns
    output_path = stamina_dataset_path(year, root)
    meta_path = stamina_meta_path(year, root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = output_path.with_suffix(".tmp.parquet")
    with duckdb.connect() as connection:
        connection.register("stamina_cleaned", frame)
        target = str(temporary_output).replace("'", "''")
        connection.execute(f"COPY stamina_cleaned TO '{target}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        connection.unregister("stamina_cleaned")
    temporary_output.replace(output_path)
    _write_parquet_atomic(pitch_curves, stamina_v2_pitch_curve_path(year, root), "stamina_v2_pitch_curves")
    _write_parquet_atomic(appearance_curves, stamina_v2_appearance_curve_path(year, root), "stamina_v2_appearance_curves")
    _write_parquet_atomic(hierarchical, stamina_v2_hierarchical_path(year, root), "stamina_v2_hierarchical")
    _write_parquet_atomic(candidates, stamina_v2_candidate_path(year, root), "stamina_v2_candidates")
    _write_parquet_atomic(multisignal, stamina_v2_multisignal_path(year, root), "stamina_v2_multisignal")
    if len(game_states):
        _write_parquet_atomic(game_states, stamina_game_state_path(year, root), "stamina_game_states")
        _write_parquet_atomic(game_state_windows, stamina_game_state_window_path(year, root), "stamina_game_state_windows")
        season_summaries, meta["slice12"] = _build_season_summaries(game_states, year)
        _write_parquet_atomic(
            season_summaries, stamina_season_summary_path(year, root), "stamina_season_summaries"
        )
    temporary_meta = meta_path.with_suffix(".tmp")
    temporary_meta.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_meta.replace(meta_path)
    return meta


def _write_parquet_atomic(frame: pd.DataFrame, path: Path, relation_name: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp.parquet")
    with duckdb.connect() as connection:
        connection.register(relation_name, frame)
        target = str(temporary).replace("'", "''")
        connection.execute(f"COPY {relation_name} TO '{target}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        connection.unregister(relation_name)
    temporary.replace(path)


def get_stamina_overview(year: int = 2026, data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    meta_path = stamina_meta_path(year, root)
    if not meta_path.exists():
        raise FileNotFoundError(f"Stamina Slice 0 dataset has not been built for {year}.")
    payload = json.loads(meta_path.read_text(encoding="utf-8"))
    db_path = get_season_duckdb_path(year, root)
    if db_path.exists() and db_path.stat().st_mtime_ns > int(payload.get("source_modified_at") or 0):
        payload["dataset_status"] = "stale"
        payload.setdefault("warnings", []).append("The season pitch source changed after the Slice 0 dataset was generated. Rebuild before modeling.")
    from app.services.physical_stability_service import physical_contract_path

    physical_path = physical_contract_path(year, root)
    if physical_path.exists():
        physical = json.loads(physical_path.read_text(encoding="utf-8"))
        payload["slice15"] = physical.get("slice15")
        payload["slice16"] = physical.get("slice16")
    from app.services.command_retention_service import (
        command_contract_path,
        incremental_validation_path,
        product_integration_path,
    )

    command_path = command_contract_path(year, root)
    if command_path.exists():
        payload["slice17"] = json.loads(command_path.read_text(encoding="utf-8"))
    validation_path = incremental_validation_path(year, root)
    if validation_path.exists():
        payload["slice18"] = json.loads(validation_path.read_text(encoding="utf-8"))
    integration_path = product_integration_path(year, root)
    if integration_path.exists():
        payload["slice19"] = json.loads(integration_path.read_text(encoding="utf-8"))
    return payload


def refresh_stamina_slice11(year: int = 2026, data_dir: Path | None = None) -> dict[str, Any]:
    """Build Slice 11 from immutable Slice 8 and cleaned-pitch artifacts only."""
    root = Path(data_dir or settings.data_dir)
    dataset_path = stamina_dataset_path(year, root)
    curve_path = stamina_v2_pitch_curve_path(year, root)
    meta_path = stamina_meta_path(year, root)
    for path in [dataset_path, curve_path, meta_path]:
        if not path.exists():
            raise FileNotFoundError(f"Required Stamina artifact not found: {path}")
    source_columns = [
        *PITCH_KEY, "appearance_pitch_number", "player_name", "pitcher_team", "appearance_role", "pitch_type", "pitch_family",
        "release_speed", "pfx_x", "pfx_z", "release_spin_rate", "release_extension",
        "release_pos_x", "release_pos_z", "location_plus_pitch",
    ]
    with duckdb.connect() as connection:
        frame = connection.execute(
            f"SELECT {', '.join(source_columns)} FROM read_parquet(?) WHERE appearance_role = 'SP'",
            [str(dataset_path)],
        ).fetchdf()
        pitch_curves = connection.execute("SELECT * FROM read_parquet(?)", [str(curve_path)]).fetchdf()
    multisignal, slice11 = _build_slice11(frame, pitch_curves)
    _write_parquet_atomic(multisignal, stamina_v2_multisignal_path(year, root), "stamina_v2_multisignal")
    payload = json.loads(meta_path.read_text(encoding="utf-8"))
    payload["model_version"] = MODEL_VERSION
    payload["slice11"] = slice11
    temporary_meta = meta_path.with_suffix(".tmp")
    temporary_meta.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_meta.replace(meta_path)
    return slice11


def refresh_stamina_game_states(year: int = 2026, data_dir: Path | None = None) -> dict[str, Any]:
    """Build observed single-game and season-timeline Stamina+ without future-game targets."""
    root = Path(data_dir or settings.data_dir)
    reference_year = int(year - 1)
    required_paths = {
        "reference_curves": stamina_v2_pitch_curve_path(reference_year, root),
        "current_curves": stamina_v2_pitch_curve_path(year, root),
        "reference_source": stamina_dataset_path(reference_year, root),
        "current_source": stamina_dataset_path(year, root),
        "meta": stamina_meta_path(year, root),
    }
    for path in required_paths.values():
        if not path.exists():
            raise FileNotFoundError(f"Required Stamina artifact not found: {path}")
    source_columns = [
        "pitcher", "game_pk", "game_date", "appearance_role", "appearance_pitch_number",
        "player_name", "pitcher_team", "location_plus_pitch", "release_speed",
    ]
    with duckdb.connect() as connection:
        reference_curves = connection.execute(
            "SELECT * FROM read_parquet(?)", [str(required_paths["reference_curves"])]
        ).fetchdf()
        current_curves = connection.execute(
            "SELECT * FROM read_parquet(?)", [str(required_paths["current_curves"])]
        ).fetchdf()
        reference_source = connection.execute(
            f"SELECT {', '.join(source_columns)} FROM read_parquet(?) WHERE appearance_role = 'SP'",
            [str(required_paths["reference_source"])],
        ).fetchdf()
        current_source = connection.execute(
            f"SELECT {', '.join(source_columns)} FROM read_parquet(?) WHERE appearance_role = 'SP'",
            [str(required_paths["current_source"])],
        ).fetchdf()
    states, windows, result = _build_game_states(
        reference_curves, current_curves, reference_source, current_source, reference_year, year
    )
    _write_parquet_atomic(states, stamina_game_state_path(year, root), "stamina_game_states")
    _write_parquet_atomic(windows, stamina_game_state_window_path(year, root), "stamina_game_state_windows")
    season_summaries, slice12 = _build_season_summaries(states, year)
    _write_parquet_atomic(
        season_summaries, stamina_season_summary_path(year, root), "stamina_season_summaries"
    )
    payload = json.loads(required_paths["meta"].read_text(encoding="utf-8"))
    payload["model_version"] = MODEL_VERSION
    for obsolete in ["slice11_archetypes", "slice11_cold_start", "slice11_cold_start_v2"]:
        payload.pop(obsolete, None)
    payload["slice11_game_state"] = result
    payload["slice12"] = slice12
    temporary_meta = required_paths["meta"].with_suffix(".tmp")
    temporary_meta.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_meta.replace(required_paths["meta"])
    return result


def refresh_stamina_season_summaries(year: int = 2026, data_dir: Path | None = None) -> dict[str, Any]:
    """Build season observed-state summaries from the existing game-state artifact only."""
    root = Path(data_dir or settings.data_dir)
    state_path = stamina_game_state_path(year, root)
    meta_path = stamina_meta_path(year, root)
    for path in [state_path, meta_path]:
        if not path.exists():
            raise FileNotFoundError(f"Required Stamina artifact not found: {path}")
    with duckdb.connect() as connection:
        states = connection.execute("SELECT * FROM read_parquet(?)", [str(state_path)]).fetchdf()
    summaries, result = _build_season_summaries(states, year)
    _write_parquet_atomic(summaries, stamina_season_summary_path(year, root), "stamina_season_summaries")
    payload = json.loads(meta_path.read_text(encoding="utf-8"))
    payload["slice12"] = result
    temporary_meta = meta_path.with_suffix(".tmp")
    temporary_meta.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_meta.replace(meta_path)
    return result


def refresh_stamina_external_validation(year: int = 2026, data_dir: Path | None = None) -> dict[str, Any]:
    """Validate the frozen observed-state contracts across the two latest scored seasons."""
    root = Path(data_dir or settings.data_dir)
    validation_year = int(year - 1)
    required_paths = {
        "validation_meta": stamina_meta_path(validation_year, root),
        "test_meta": stamina_meta_path(year, root),
        "validation_states": stamina_game_state_path(validation_year, root),
        "test_states": stamina_game_state_path(year, root),
        "validation_summaries": stamina_season_summary_path(validation_year, root),
        "test_summaries": stamina_season_summary_path(year, root),
    }
    for path in required_paths.values():
        if not path.exists():
            raise FileNotFoundError(f"Required Stamina validation artifact not found: {path}")
    metas = {
        validation_year: json.loads(required_paths["validation_meta"].read_text(encoding="utf-8")),
        int(year): json.loads(required_paths["test_meta"].read_text(encoding="utf-8")),
    }
    with duckdb.connect() as connection:
        states = {
            validation_year: connection.execute(
                "SELECT * FROM read_parquet(?)", [str(required_paths["validation_states"])]
            ).fetchdf(),
            int(year): connection.execute(
                "SELECT * FROM read_parquet(?)", [str(required_paths["test_states"])]
            ).fetchdf(),
        }
        summaries = {
            validation_year: connection.execute(
                "SELECT * FROM read_parquet(?)", [str(required_paths["validation_summaries"])]
            ).fetchdf(),
            int(year): connection.execute(
                "SELECT * FROM read_parquet(?)", [str(required_paths["test_summaries"])]
            ).fetchdf(),
        }
    result = _build_external_validation(metas, states, summaries, validation_year, int(year))
    output_path = stamina_external_validation_path(year, root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(output_path)
    test_meta = metas[int(year)]
    test_meta["slice13"] = result
    meta_path = required_paths["test_meta"]
    temporary_meta = meta_path.with_suffix(".tmp")
    temporary_meta.write_text(json.dumps(test_meta, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_meta.replace(meta_path)
    return result


def refresh_stamina_season_bias_repair(year: int = 2026, data_dir: Path | None = None) -> dict[str, Any]:
    """Develop season ceiling correction on year-1 and evaluate once on the untouched requested year."""
    root = Path(data_dir or settings.data_dir)
    development_year = int(year - 1)
    external_path = stamina_external_validation_path(year, root)
    required = {
        season: {
            "states": stamina_game_state_path(season, root),
            "summaries": stamina_season_summary_path(season, root),
        }
        for season in [development_year, int(year)]
    }
    for paths in required.values():
        for path in paths.values():
            if not path.exists():
                raise FileNotFoundError(f"Required Stamina bias-repair artifact not found: {path}")
    if not external_path.exists():
        raise FileNotFoundError(f"Slice 13 external validation has not been built: {external_path}")
    with duckdb.connect() as connection:
        states = {
            season: connection.execute("SELECT * FROM read_parquet(?)", [str(paths["states"])]).fetchdf()
            for season, paths in required.items()
        }
        summaries = {
            season: connection.execute("SELECT * FROM read_parquet(?)", [str(paths["summaries"])]).fetchdf()
            for season, paths in required.items()
        }
    external_validation = json.loads(external_path.read_text(encoding="utf-8"))
    adjusted, result = _build_season_bias_repair(
        states, summaries, external_validation, development_year, int(year)
    )
    for season, frame in adjusted.groupby("season", sort=True):
        _write_parquet_atomic(
            frame.drop(columns="season").reset_index(drop=True),
            stamina_adjusted_season_summary_path(int(season), root),
            f"stamina_adjusted_season_summaries_{int(season)}",
        )
    result_path = stamina_season_bias_repair_path(year, root)
    temporary = result_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(result_path)
    meta_path = stamina_meta_path(year, root)
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["slice13a"] = result
    temporary_meta = meta_path.with_suffix(".tmp")
    temporary_meta.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_meta.replace(meta_path)
    return result


def refresh_stamina_archetypes(year: int = 2026, data_dir: Path | None = None) -> dict[str, Any]:
    """Build the 3×3 early-state diagnostic without rewriting Slices 0–11 artifacts."""
    root = Path(data_dir or settings.data_dir)
    dataset_path = stamina_dataset_path(year, root)
    multisignal_path = stamina_v2_multisignal_path(year, root)
    meta_path = stamina_meta_path(year, root)
    for path in [dataset_path, multisignal_path, meta_path]:
        if not path.exists():
            raise FileNotFoundError(f"Required Stamina artifact not found: {path}")
    with duckdb.connect() as connection:
        frame = connection.execute(
            "SELECT pitcher, game_pk, appearance_role, appearance_pitch_number, "
            "pitch_stuff_plus, location_plus_pitch FROM read_parquet(?) WHERE appearance_role = 'SP'",
            [str(dataset_path)],
        ).fetchdf()
        multisignal = connection.execute("SELECT * FROM read_parquet(?)", [str(multisignal_path)]).fetchdf()
    archetypes, result = _build_stamina_archetypes(frame, multisignal)
    _write_parquet_atomic(archetypes, stamina_v2_archetype_path(year, root), "stamina_v2_archetypes")
    payload = json.loads(meta_path.read_text(encoding="utf-8"))
    payload["model_version"] = MODEL_VERSION
    payload["slice11_archetypes"] = result
    temporary_meta = meta_path.with_suffix(".tmp")
    temporary_meta.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_meta.replace(meta_path)
    return result


def refresh_stamina_cold_start(year: int = 2026, data_dir: Path | None = None) -> dict[str, Any]:
    """Build cold-start single-season research artifacts from immutable seasonal inputs."""
    root = Path(data_dir or settings.data_dir)
    train_year = int(year - 1)
    required_paths = {
        "train_curves": stamina_v2_pitch_curve_path(train_year, root),
        "test_curves": stamina_v2_pitch_curve_path(year, root),
        "train_source": stamina_dataset_path(train_year, root),
        "test_source": stamina_dataset_path(year, root),
        "meta": stamina_meta_path(year, root),
    }
    for path in required_paths.values():
        if not path.exists():
            raise FileNotFoundError(f"Required Stamina artifact not found: {path}")
    source_columns = [
        "pitcher", "game_pk", "game_date", "appearance_role", "appearance_pitch_number",
        "player_name", "pitcher_team", "pitch_stuff_plus", "location_plus_pitch", "release_speed",
    ]
    with duckdb.connect() as connection:
        train_curves = connection.execute("SELECT * FROM read_parquet(?)", [str(required_paths["train_curves"])]).fetchdf()
        test_curves = connection.execute("SELECT * FROM read_parquet(?)", [str(required_paths["test_curves"])]).fetchdf()
        train_source = connection.execute(
            f"SELECT {', '.join(source_columns)} FROM read_parquet(?) WHERE appearance_role = 'SP'",
            [str(required_paths["train_source"])],
        ).fetchdf()
        test_source = connection.execute(
            f"SELECT {', '.join(source_columns)} FROM read_parquet(?) WHERE appearance_role = 'SP'",
            [str(required_paths["test_source"])],
        ).fetchdf()
    appearances, backtest, candidates, result = _build_cold_start_research(
        train_curves, test_curves, train_source, test_source, train_year, year
    )
    _write_parquet_atomic(appearances, stamina_cold_start_appearance_path(year, root), "stamina_cold_start_appearances")
    _write_parquet_atomic(backtest, stamina_cold_start_backtest_path(year, root), "stamina_cold_start_backtest")
    _write_parquet_atomic(candidates, stamina_single_season_candidate_path(year, root), "stamina_single_season_candidates")
    payload = json.loads(required_paths["meta"].read_text(encoding="utf-8"))
    payload["model_version"] = MODEL_VERSION
    payload["slice11_cold_start"] = result
    temporary_meta = required_paths["meta"].with_suffix(".tmp")
    temporary_meta.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_meta.replace(required_paths["meta"])
    return result


def refresh_stamina_cold_start_v2(year: int = 2026, data_dir: Path | None = None) -> dict[str, Any]:
    """Calibrate cold-start shrinkage on cross-fitted prior-year pseudo-rookies, then audit the next year."""
    root = Path(data_dir or settings.data_dir)
    development_year = int(year - 1)
    required_paths = {
        "development_curves": stamina_v2_pitch_curve_path(development_year, root),
        "audit_curves": stamina_v2_pitch_curve_path(year, root),
        "development_source": stamina_dataset_path(development_year, root),
        "audit_source": stamina_dataset_path(year, root),
        "meta": stamina_meta_path(year, root),
    }
    for path in required_paths.values():
        if not path.exists():
            raise FileNotFoundError(f"Required Stamina artifact not found: {path}")
    source_columns = [
        "pitcher", "game_pk", "game_date", "appearance_role", "appearance_pitch_number",
        "player_name", "pitcher_team", "pitch_stuff_plus", "location_plus_pitch", "release_speed",
    ]
    with duckdb.connect() as connection:
        development_curves = connection.execute(
            "SELECT * FROM read_parquet(?)", [str(required_paths["development_curves"])]
        ).fetchdf()
        audit_curves = connection.execute("SELECT * FROM read_parquet(?)", [str(required_paths["audit_curves"])]).fetchdf()
        development_source = connection.execute(
            f"SELECT {', '.join(source_columns)} FROM read_parquet(?) WHERE appearance_role = 'SP'",
            [str(required_paths["development_source"])],
        ).fetchdf()
        audit_source = connection.execute(
            f"SELECT {', '.join(source_columns)} FROM read_parquet(?) WHERE appearance_role = 'SP'",
            [str(required_paths["audit_source"])],
        ).fetchdf()
    development, audit, result = _build_cold_start_v2(
        development_curves, audit_curves, development_source, audit_source, development_year, year
    )
    _write_parquet_atomic(
        development, stamina_cold_start_v2_development_path(development_year, root), "stamina_cold_start_v2_development"
    )
    _write_parquet_atomic(audit, stamina_cold_start_v2_audit_path(year, root), "stamina_cold_start_v2_audit")
    payload = json.loads(required_paths["meta"].read_text(encoding="utf-8"))
    payload["model_version"] = MODEL_VERSION
    payload["slice11_cold_start_v2"] = result
    temporary_meta = required_paths["meta"].with_suffix(".tmp")
    temporary_meta.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_meta.replace(required_paths["meta"])
    return result


def get_stamina_research_curves(
    year: int,
    pitcher_id: int,
    data_dir: Path | None = None,
) -> dict[str, Any]:
    path = stamina_v2_multisignal_path(year, data_dir)
    if not path.exists():
        raise FileNotFoundError(f"Stamina Slice 11 artifact has not been built for {year}.")
    with duckdb.connect() as connection:
        rows = connection.execute(
            "SELECT * FROM read_parquet(?) WHERE pitcher = ? ORDER BY game_date DESC, game_pk, \"order\", pitch_family",
            [str(path), int(pitcher_id)],
        ).fetchdf()
    if rows.empty:
        raise ValueError(f"Pitcher {pitcher_id} has no Slice 11 research curves for {year}.")
    games = (
        rows.groupby(["game_pk", "game_date"], as_index=False)
        .agg(total_pitches=("appearance_total_pitches", "max"))
        .sort_values(["game_date", "game_pk"], ascending=[False, False])
    )
    value_columns = [
        "stuff_delta", "velocity_delta", "spin_delta", "movement_drift_inches",
        "release_point_drift_inches", "extension_delta", "location_delta", "usage_pct", "usage_delta_pp",
    ]
    records = rows.to_dict(orient="records")
    for record in records:
        record["game_date"] = pd.Timestamp(record["game_date"]).date().isoformat()
        for column in value_columns:
            if pd.isna(record.get(column)):
                record[column] = None
    return {
        "year": int(year), "publication_status": "research_only", "pitcher_id": int(pitcher_id),
        "pitcher_name": str(rows["pitcher_name"].dropna().iloc[0]) if rows["pitcher_name"].notna().any() else str(pitcher_id),
        "team": str(rows["team"].dropna().iloc[-1]) if rows["team"].notna().any() else "",
        "games": [
            {"game_pk": int(row.game_pk), "game_date": pd.Timestamp(row.game_date).date().isoformat(), "total_pitches": int(row.total_pitches)}
            for row in games.itertuples(index=False)
        ],
        "curves": records,
        "warnings": [
            "These are descriptive within-game deviations, not a Stamina+ score or next-start forecast.",
            "A missing value means the exact pitch type lacked three early reference pitches; it is never replaced with zero.",
        ],
    }


def get_stamina_game_states(
    year: int,
    pitcher_id: int,
    data_dir: Path | None = None,
) -> dict[str, Any]:
    state_path = stamina_game_state_path(year, data_dir)
    window_path = stamina_game_state_window_path(year, data_dir)
    for path in [state_path, window_path]:
        if not path.exists():
            raise FileNotFoundError(f"Observed Stamina state artifact has not been built for {year}: {path}")
    with duckdb.connect() as connection:
        states = connection.execute(
            "SELECT * FROM read_parquet(?) WHERE pitcher = ? ORDER BY game_date, game_pk, scope",
            [str(state_path), int(pitcher_id)],
        ).fetchdf()
        windows = connection.execute(
            "SELECT * FROM read_parquet(?) WHERE pitcher = ? ORDER BY game_date, game_pk, scope, \"order\"",
            [str(window_path), int(pitcher_id)],
        ).fetchdf()
    if states.empty:
        raise ValueError(f"Pitcher {pitcher_id} has no observed Stamina states for {year}.")
    nullable_columns = [
        "raw_retention", "posterior_retention", "stamina_plus", "ci_low", "ci_high",
        "reliability", "rolling_3", "rolling_5", "velocity_delta", "early_stuff", "early_velocity",
        "observed_mix_retention", "fixed_mix_coverage", "early_baseline_reliability",
    ]
    state_records = states.to_dict(orient="records")
    for record in state_records:
        record["game_date"] = pd.Timestamp(record["game_date"]).date().isoformat()
        for column in nullable_columns:
            if pd.isna(record.get(column)):
                record[column] = None
    window_records = windows.to_dict(orient="records")
    for record in window_records:
        record["game_date"] = pd.Timestamp(record["game_date"]).date().isoformat()
        for column in ["retention", "velocity_delta"]:
            if pd.isna(record.get(column)):
                record[column] = None
    return {
        "year": int(year), "publication_status": "observed_state", "pitcher_id": int(pitcher_id),
        "pitcher_name": str(states["pitcher_name"].dropna().iloc[-1]),
        "team": str(states["team"].dropna().iloc[-1]), "states": state_records, "windows": window_records,
        "warnings": [
            "Game Stamina+ summarizes observed in-game Stuff+ retention relative to the prior-season expectation; it does not predict the next start.",
            "Scores with low reliability or missing family support remain visibly uncertain instead of being filled with zero.",
            "Depth is reported separately because leaving a game early can reflect performance, strategy, injury or pitch limits.",
        ],
    }


def get_stamina_season_summaries(
    year: int,
    data_dir: Path | None = None,
) -> dict[str, Any]:
    summary_path = stamina_season_summary_path(year, data_dir)
    if not summary_path.exists():
        raise FileNotFoundError(f"Observed Stamina season summary has not been built for {year}: {summary_path}")
    with duckdb.connect() as connection:
        rows = connection.execute(
            "SELECT * FROM read_parquet(?) ORDER BY scope, qualified DESC, stamina_plus DESC NULLS LAST, pitcher_name",
            [str(summary_path)],
        ).fetchdf()
    nullable_columns = [
        "raw_stamina_plus", "unweighted_stamina_plus", "stamina_plus", "ci_low", "ci_high",
        "reliability", "mean_game_reliability", "average_pitches", "rank",
    ]
    records = rows.to_dict(orient="records")
    for record in records:
        for column in nullable_columns:
            if pd.isna(record.get(column)):
                record[column] = None
    return {
        "year": int(year),
        "publication_status": "research_only",
        "contract_version": "stamina_observed_season_state_v1_1",
        "rows": records,
        "warnings": [
            "Season Stamina+ summarizes observed starts in the selected season; it is not a permanent trait or next-start forecast.",
            "Only qualified rows receive a rank. Family scores remain null when season support or season reliability is insufficient.",
        ],
    }


def get_stamina_external_validation(
    year: int,
    data_dir: Path | None = None,
) -> dict[str, Any]:
    path = stamina_external_validation_path(year, data_dir)
    if not path.exists():
        raise FileNotFoundError(f"Stamina external validation has not been built for {year}: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def get_stamina_season_bias_repair(
    year: int,
    data_dir: Path | None = None,
) -> dict[str, Any]:
    path = stamina_season_bias_repair_path(year, data_dir)
    if not path.exists():
        raise FileNotFoundError(f"Stamina season bias repair has not been built for {year}: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def get_stamina_leaderboard(
    year: int,
    data_dir: Path | None = None,
) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    summary_path = stamina_adjusted_season_summary_path(year, root)
    audit_path = stamina_season_bias_repair_path(year, root)
    meta_path = stamina_meta_path(year, root)
    for path in [summary_path, audit_path, meta_path]:
        if not path.exists():
            raise FileNotFoundError(f"Required Stamina leaderboard artifact not found: {path}")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if not audit.get("leaderboard_release_eligible") or int(audit.get("test_year") or 0) != int(year):
        raise ValueError(f"Stamina leaderboard is not release-eligible for {year}.")
    with duckdb.connect() as connection:
        frame = connection.execute("SELECT * FROM read_parquet(?)", [str(summary_path)]).fetchdf()
    overall = frame[
        frame["scope"].eq("Overall") & frame["adjusted_qualified"].fillna(False)
    ].copy()
    family = frame[
        frame["scope"].isin(["Fastball", "Breaking", "Offspeed"])
        & frame["adjusted_qualified"].fillna(False)
    ].pivot_table(
        index="pitcher", columns="scope", values="adjusted_stamina_plus", aggfunc="first"
    ).reset_index()
    rows = overall.merge(family, on="pitcher", how="left", validate="one_to_one")
    research_scores = pd.DataFrame(columns=[
        "pitcher", "quality_game_stamina_plus", "physical_stability_plus", "command_retention_plus"
    ])
    from app.services.command_retention_service import command_game_path
    from app.services.physical_stability_service import physical_game_path

    quality_path = stamina_game_state_path(year, root)
    physical_path = physical_game_path(year, root)
    command_path = command_game_path(year, root)
    if quality_path.exists() and physical_path.exists() and command_path.exists():
        with duckdb.connect() as connection:
            research_scores = connection.execute(
                """
                WITH quality AS (
                    SELECT pitcher, count(DISTINCT game_pk) AS games,
                           avg(stamina_plus) AS quality_game_stamina_plus
                    FROM read_parquet(?)
                    WHERE scope = 'Overall' AND eligible AND stamina_plus IS NOT NULL
                    GROUP BY pitcher HAVING count(DISTINCT game_pk) >= 10
                ), physical AS (
                    SELECT pitcher, count(DISTINCT game_pk) AS games,
                           avg(physical_stability_plus) AS physical_stability_plus
                    FROM read_parquet(?)
                    WHERE eligible AND physical_stability_plus IS NOT NULL
                    GROUP BY pitcher HAVING count(DISTINCT game_pk) >= 10
                ), command AS (
                    SELECT pitcher, count(DISTINCT game_pk) AS games,
                           avg(command_retention_plus) AS command_retention_plus
                    FROM read_parquet(?)
                    WHERE scope = 'Overall' AND eligible AND command_retention_plus IS NOT NULL
                    GROUP BY pitcher HAVING count(DISTINCT game_pk) >= 10
                )
                SELECT coalesce(quality.pitcher, physical.pitcher, command.pitcher) AS pitcher,
                       quality.quality_game_stamina_plus,
                       physical.physical_stability_plus, command.command_retention_plus
                FROM quality
                FULL OUTER JOIN physical USING (pitcher)
                FULL OUTER JOIN command USING (pitcher)
                """,
                [str(quality_path), str(physical_path), str(command_path)],
            ).fetchdf()
    rows = rows.merge(research_scores, on="pitcher", how="left", validate="one_to_one")
    rows = rows.sort_values(["adjusted_rank", "pitcher_name"], kind="stable")
    records = []
    for row in rows.itertuples(index=False):
        records.append({
            "rank": int(row.adjusted_rank),
            "pitcher_id": int(row.pitcher),
            "name": str(row.pitcher_name),
            "team": str(row.team),
            "starts": int(row.total_starts),
            "eligible_games": int(row.eligible_games),
            "average_pitches": round(float(row.average_pitches), 1),
            "fastball_stamina_plus": _nullable_round(getattr(row, "Fastball", np.nan), 1),
            "breaking_stamina_plus": _nullable_round(getattr(row, "Breaking", np.nan), 1),
            "offspeed_stamina_plus": _nullable_round(getattr(row, "Offspeed", np.nan), 1),
            "ci_low": round(float(row.adjusted_ci_low), 1),
            "ci_high": round(float(row.adjusted_ci_high), 1),
            "reliability": round(float(row.adjusted_reliability), 3),
            "stamina_plus": round(float(row.adjusted_stamina_plus), 1),
            "quality_game_stamina_plus": _nullable_round(row.quality_game_stamina_plus, 1),
            "physical_stability_plus": _nullable_round(row.physical_stability_plus, 1),
            "command_retention_plus": _nullable_round(row.command_retention_plus, 1),
        })
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    return {
        "year": int(year),
        "data_as_of": meta.get("data_as_of"),
        "publication_status": "validated_observed_state",
        "contract_version": "stamina_observed_season_leaderboard_v1_1",
        "correction_version": str(audit.get("contract_version") or ""),
        "development_year": int(audit["development_year"]),
        "test_year": int(audit["test_year"]),
        "rows": records,
        "warnings": [
            "Observed Season Stamina+ summarizes quality-neutral in-season retention; it is not physiology or a next-start forecast.",
            "Only 2026 is an untouched external season for correction v1.1.",
            "Family scores remain blank when that family does not meet its own adjusted reliability and support thresholds.",
            "Q-Stm+, Phy-Stb+, and Cmd-Ret+ are separate research-only means of at least 10 eligible game states; they do not change the official Stamina+ rank.",
        ],
    }


def _nullable_round(value: Any, digits: int) -> float | None:
    return None if pd.isna(value) else round(float(value), digits)


def get_stamina_cold_start_pitcher(
    year: int,
    pitcher_id: int,
    data_dir: Path | None = None,
) -> dict[str, Any]:
    appearance_path = stamina_cold_start_appearance_path(year, data_dir)
    candidate_path = stamina_single_season_candidate_path(year, data_dir)
    if not appearance_path.exists():
        raise FileNotFoundError(f"Stamina cold-start artifact has not been built for {year}.")
    with duckdb.connect() as connection:
        rows = connection.execute(
            "SELECT * FROM read_parquet(?) WHERE pitcher = ? ORDER BY game_date, game_pk",
            [str(appearance_path), int(pitcher_id)],
        ).fetchdf()
        candidate = pd.DataFrame()
        if candidate_path.exists():
            candidate = connection.execute(
                "SELECT * FROM read_parquet(?) WHERE pitcher = ?", [str(candidate_path), int(pitcher_id)]
            ).fetchdf()
    if rows.empty:
        raise ValueError(f"Pitcher {pitcher_id} has no cold-start research appearances for {year}.")
    nullable_columns = [
        "early_stuff", "early_location", "early_velocity", "game_retention", "raw_retention_delta",
        "observed_late_stuff", "expected_late_stuff", "velocity_delta", "location_delta", "late_pitches",
        "observation_weight",
    ]
    appearances = rows.to_dict(orient="records")
    for row in appearances:
        row["game_date"] = pd.Timestamp(row["game_date"]).date().isoformat()
        for column in nullable_columns:
            if pd.isna(row.get(column)):
                row[column] = None
    candidate_record = None
    if not candidate.empty:
        candidate_record = candidate.iloc[0].to_dict()
        for key, value in list(candidate_record.items()):
            if pd.isna(value):
                candidate_record[key] = None
    return {
        "year": int(year), "publication_status": "research_only" if candidate_record is None else "provisional_candidate",
        "pitcher_id": int(pitcher_id),
        "pitcher_name": str(rows["pitcher_name"].dropna().iloc[-1]) if rows["pitcher_name"].notna().any() else str(pitcher_id),
        "team": str(rows["team"].dropna().iloc[-1]) if rows["team"].notna().any() else "",
        "candidate": candidate_record, "appearances": appearances,
        "warnings": [
            "Game Retention is the observed 61–80-pitch quality minus its 2025-trained conditional expectation.",
            "A missing Game Retention means the start did not provide at least five eligible pitches in the target window.",
            "No single-season Stamina+ is returned unless a pseudo-rookie checkpoint passes every release gate.",
        ],
    }


def load_pitch_stamina_state(
    frame: pd.DataFrame,
    year: int,
    data_dir: Path | None = None,
) -> pd.DataFrame:
    result = frame.copy()
    state_columns = [
        "stamina_plus_trait", "stamina_expected_retention_delta", "stamina_expected_stuff_plus",
        "stamina_early_stuff_baseline", "stamina_reliability", "stamina_sample_label",
        "stamina_role", "pitch_stuff_plus", "location_plus_pitch",
    ]
    path = stamina_dataset_path(year, data_dir)
    required = set(PITCH_KEY)
    if result.empty or not path.exists() or not required.issubset(result.columns):
        for column in state_columns:
            if column not in result.columns:
                result[column] = pd.NA
        return result
    pitchers = pd.to_numeric(result["pitcher"], errors="coerce").dropna().astype(int).unique().tolist()
    if not pitchers:
        return result
    placeholders = ", ".join("?" for _ in pitchers)
    selected = [*PITCH_KEY, *state_columns]
    with duckdb.connect() as connection:
        available = {
            row[0]
            for row in connection.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(path)]).fetchall()
        }
        if not set(selected).issubset(available):
            for column in state_columns:
                if column not in result.columns:
                    result[column] = pd.NA
            return result
        state = connection.execute(
            f"SELECT {', '.join(selected)} FROM read_parquet(?) WHERE CAST(pitcher AS BIGINT) IN ({placeholders})",
            [str(path), *pitchers],
        ).fetchdf()
    for column in PITCH_KEY:
        result[column] = pd.to_numeric(result[column], errors="coerce").astype("Int64")
        state[column] = pd.to_numeric(state[column], errors="coerce").astype("Int64")
    existing_state = [column for column in state_columns if column in result.columns]
    if existing_state:
        result = result.drop(columns=existing_state)
    return result.merge(state, on=PITCH_KEY, how="left", validate="many_to_one")


def _load_source(year: int, db_path: Path) -> tuple[pd.DataFrame, dict[str, int]]:
    with duckdb.connect(str(db_path), read_only=True) as connection:
        tables = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
        table = resolve_pitch_table(tables)
        if not table:
            raise ValueError(f"No pitch source table is available for {year}.")
        available = {row[1] for row in connection.execute(f"PRAGMA table_info('{table}')").fetchall()}
        required = set(PITCH_KEY) | {"game_date", "game_type", "inning", "inning_topbot", "home_team", "away_team"}
        missing = sorted(required - available)
        if missing:
            raise ValueError(f"Pitch source is missing Stamina Slice 0 columns: {', '.join(missing)}")
        total_rows = int(connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0])
        regular_rows = int(connection.execute(f"SELECT count(*) FROM {table} WHERE game_type = 'R'").fetchone()[0])
        expressions = [column if column in available else f"NULL AS {column}" for column in SOURCE_COLUMNS]
        frame = connection.execute(
            f"SELECT {', '.join(expressions)} FROM {table} WHERE game_type = 'R'"
        ).fetchdf()
    return frame, {"source_rows": total_rows, "non_regular_rows": total_rows - regular_rows}


def _add_workload_history(appearances: pd.DataFrame) -> pd.DataFrame:
    result = appearances.sort_values(["pitcher", "game_date", "game_pk"], kind="stable").copy()
    numeric_columns = [
        "all_role_appearance_number", "all_role_season_pitches_before", "previous_appearance_pitches",
        "workload_pitches_3d", "workload_pitches_7d", "workload_pitches_14d", "workload_pitches_28d",
        "workload_appearances_3d", "workload_appearances_7d", "workload_appearances_14d", "workload_appearances_28d",
        "back_to_back", "long_gap", "role_changed",
    ]
    for column in numeric_columns:
        result[column] = 0
    for _, group in result.groupby("pitcher", sort=False):
        indices = group.index.to_numpy()
        dates = pd.to_datetime(group["game_date"], errors="coerce").to_numpy(dtype="datetime64[D]")
        pitches = pd.to_numeric(group["pitches"], errors="coerce").fillna(0).to_numpy(dtype="int64")
        roles = group["appearance_role"].astype(str).to_numpy()
        for position, index in enumerate(indices):
            result.at[index, "all_role_appearance_number"] = position + 1
            result.at[index, "all_role_season_pitches_before"] = int(pitches[:position].sum())
            result.at[index, "previous_appearance_pitches"] = int(pitches[position - 1]) if position else 0
            if position:
                days_ago = (dates[position] - dates[:position]).astype("timedelta64[D]").astype(int)
                for window in [3, 7, 14, 28]:
                    included = (days_ago >= 0) & (days_ago <= window)
                    result.at[index, f"workload_pitches_{window}d"] = int(pitches[:position][included].sum())
                    result.at[index, f"workload_appearances_{window}d"] = int(included.sum())
                result.at[index, "role_changed"] = int(roles[position - 1] != roles[position])
            days_rest = pd.to_numeric(pd.Series([group.iloc[position]["days_rest"]]), errors="coerce").iloc[0]
            result.at[index, "back_to_back"] = int(pd.notna(days_rest) and float(days_rest) == 0)
            result.at[index, "long_gap"] = int(pd.notna(days_rest) and float(days_rest) >= 14)
    integer_columns = [column for column in numeric_columns if column != "all_role_appearance_number"]
    result[integer_columns] = result[integer_columns].fillna(0).astype(int)
    result["all_role_appearance_number"] = result["all_role_appearance_number"].astype(int)
    return result


def _build_overview(
    year: int,
    frame: pd.DataFrame,
    appearances: pd.DataFrame,
    source_counts: dict[str, int],
    regular_rows: int,
    missing_core: int,
    duplicate_rows: int,
) -> dict[str, Any]:
    dual_ids = set(
        appearances.groupby("pitcher")["appearance_role"].nunique().loc[lambda values: values > 1].index.astype(int)
    )
    cleaning = [
        _cleaning_step("regular_season", "Regular-season scope", source_counts["source_rows"], regular_rows, source_counts["non_regular_rows"], "ready", "Spring training, postseason and other game types are excluded."),
        _cleaning_step("core_identity", "Valid pitch identity", regular_rows, regular_rows - missing_core, missing_core, "ready", "Requires pitcher, game, plate appearance, pitch number, date, inning and pitching team."),
        _cleaning_step("deduplicate", "Unique pitch key", regular_rows - missing_core, len(frame), duplicate_rows, "ready", "Keeps one row per game, plate appearance, pitch number and pitcher."),
        _cleaning_step("role_split", "Appearance-level SP/RP role", len(frame), len(frame), 0, "ready", "The first pitcher used by each team is SP; every later pitcher is RP. Dual-role pitchers remain in both groups."),
    ]
    roles = []
    coverage = []
    for role in ["SP", "RP"]:
        role_frame = frame[frame["appearance_role"].eq(role)]
        role_appearances = appearances[appearances["appearance_role"].eq(role)]
        stuff = int(role_frame["pitch_stuff_plus"].notna().sum())
        location = int(role_frame["location_plus_pitch"].notna().sum())
        both = int((role_frame["pitch_stuff_plus"].notna() & role_frame["location_plus_pitch"].notna()).sum())
        roles.append({
            "role": role,
            "pitches": int(len(role_frame)),
            "appearances": int(len(role_appearances)),
            "pitchers": int(role_appearances["pitcher"].nunique()),
            "dual_role_pitchers": int(role_appearances["pitcher"].isin(dual_ids).groupby(role_appearances["pitcher"]).any().sum()),
        })
        coverage.append({
            "role": role,
            "pitches": int(len(role_frame)),
            "stuff_scored": stuff,
            "stuff_coverage_pct": _pct(stuff, len(role_frame)),
            "location_scored": location,
            "location_coverage_pct": _pct(location, len(role_frame)),
            "both_scored": both,
            "both_coverage_pct": _pct(both, len(role_frame)),
        })

    pitch_buckets = []
    for role, buckets in [("SP", SP_BUCKETS), ("RP", RP_BUCKETS)]:
        role_frame = frame[frame["appearance_role"].eq(role)]
        for low, high, label in buckets:
            sample = role_frame[role_frame["appearance_pitch_number"].between(low, high)]
            pitch_buckets.append({
                "role": role,
                "bucket": label,
                "pitches": int(len(sample)),
                "appearances": int(sample[["pitcher", "game_pk"]].drop_duplicates().shape[0]),
                "pitchers": int(sample["pitcher"].nunique()),
                "stuff_coverage_pct": _pct(sample["pitch_stuff_plus"].notna().sum(), len(sample)),
                "location_coverage_pct": _pct(sample["location_plus_pitch"].notna().sum(), len(sample)),
            })

    feature_specs = [
        ("Quality", "Stuff+", ["pitch_stuff_plus"], "Primary pitch-quality outcome."),
        ("Quality", "Location+", ["location_plus_pitch"], "Primary command-quality outcome."),
        ("Shape", "Velocity", ["release_speed"], "Within-pitcher, within-pitch-type velocity retention."),
        ("Shape", "Movement", ["pfx_x", "pfx_z"], "Horizontal and vertical movement stability."),
        ("Shape", "Spin", ["release_spin_rate", "spin_axis"], "Spin magnitude and direction stability."),
        ("Mechanics", "Release geometry", ["release_pos_x", "release_pos_z", "release_extension"], "Release-point drift and dispersion."),
        ("Mechanics", "Arm angle", ["arm_angle"], "Coverage loss is concentrated in complete Statcast date batches; excluded from the Slice 1 primary model."),
        ("Context", "Count and matchup", ["balls", "strikes", "stand", "p_throws"], "Controls pitch intent and handedness."),
        ("Context", "Times through order", ["n_thruorder_pitcher"], "Separates continuous workload from batter familiarity."),
        ("Workload", "Pitch sequence", ["appearance_pitch_number", "inning_pitch_number"], "Cleaned within-appearance and within-inning workload."),
        ("Workload", "Recovery", ["days_rest", "all_role_season_pitches_before", "workload_pitches_7d", "workload_pitches_28d"], "Strictly lagged rest, rolling load and cross-role cumulative workload prepared at appearance level."),
    ]
    feature_audit = []
    for group, feature, columns, note in feature_specs:
        valid = frame[columns].notna().all(axis=1).sum()
        coverage_pct = _pct(valid, len(frame))
        feature_audit.append({
            "group": group,
            "feature": feature,
            "status": "ready" if coverage_pct >= 95 else "partial" if coverage_pct > 0 else "missing",
            "coverage_pct": coverage_pct,
            "note": note,
        })
    feature_audit.extend([
        {"group": "External context", "feature": "Park and venue proxy", "status": "ready", "coverage_pct": _pct(frame[["home_team", "away_team"]].notna().all(axis=1).sum(), len(frame)), "note": "Home and away team identify venue context; explicit park factors belong in Slice 1."},
        {"group": "External context", "feature": "Weather and travel", "status": "missing", "coverage_pct": 0.0, "note": "Not present in the local pitch source; omitted and disclosed in the Slice 1 primary model."},
    ])

    warnings = [
        "Slice 5 publishes a validated role-specific Stuff+ retention Stamina+; Slice 6 keeps the fixed trait separate from the pitch-count expected path and observed pitch noise.",
        "Bullpen warm-up pitches, private health data, soreness, sleep and off-day throwing are not observable in public Statcast data.",
        "Slice 2 reduces observed informative removal, but unmeasured manager intent and health can still affect who remains observable at high pitch counts.",
    ]
    return {
        "year": int(year),
        "data_as_of": frame["game_date"].max().date().isoformat() if len(frame) else None,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset_status": "current" if coverage and min(row["both_coverage_pct"] for row in coverage) >= 95.0 else "partial",
        "model_version": MODEL_VERSION,
        "dataset_rows": int(len(frame)),
        "appearances": int(len(appearances)),
        "pitchers": int(frame["pitcher"].nunique()),
        "dual_role_pitchers": int(len(dual_ids)),
        "cleaning": cleaning,
        "roles": roles,
        "coverage": coverage,
        "pitch_buckets": pitch_buckets,
        "feature_audit": feature_audit,
        "hypotheses": _hypotheses(),
        "warnings": warnings,
    }


def _cleaning_step(key: str, label: str, input_rows: int, output_rows: int, removed_rows: int, status: str, note: str) -> dict[str, Any]:
    return {"key": key, "label": label, "input_rows": int(input_rows), "output_rows": int(output_rows), "removed_rows": int(removed_rows), "status": status, "note": note}


def _pct(numerator: int | float, denominator: int | float) -> float:
    return round(float(numerator) / float(denominator) * 100.0, 1) if denominator else 0.0


def _build_arm_angle_audit(frame: pd.DataFrame) -> dict[str, Any]:
    dates = frame.assign(_date=frame["game_date"].dt.date).groupby("_date", as_index=False).agg(
        pitches=("pitcher", "size"),
        arm_scored=("arm_angle", "count"),
    )
    dates["coverage_pct"] = dates["arm_scored"].div(dates["pitches"]).mul(100.0)
    zero_dates = dates.loc[dates["arm_scored"].eq(0), "_date"].astype(str).tolist()
    physical = ["release_speed", "pfx_x", "pfx_z", "release_pos_x", "release_pos_z", "release_extension"]
    missing = frame[frame["arm_angle"].isna()]
    otherwise_trackable = int(missing[physical].notna().all(axis=1).sum())
    return {
        "coverage_pct": _pct(frame["arm_angle"].notna().sum(), len(frame)),
        "missing_pitches": int(frame["arm_angle"].isna().sum()),
        "otherwise_trackable_missing": otherwise_trackable,
        "dates": int(len(dates)),
        "zero_coverage_dates": zero_dates,
        "zero_coverage_date_count": int(len(zero_dates)),
        "pattern": "date_batch",
        "note": "Missingness is concentrated in complete game-date batches while other physical tracking remains present; it is not pitcher-specific. Arm angle is excluded from the Slice 1 primary model.",
    }


def _build_slice1(frame: pd.DataFrame) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for role in ["SP", "RP"]:
        sample = frame[
            frame["appearance_role"].eq(role)
            & frame["pitch_stuff_plus"].notna()
            & frame["location_plus_pitch"].notna()
            & frame["pitch_type"].notna()
            & frame["batter"].notna()
        ].copy()
        if len(sample) < 500:
            diagnostics.append({"role": role, "status": "insufficient", "pitches": int(len(sample))})
            continue
        pitch_buckets = SP_BUCKETS if role == "SP" else RP_BUCKETS
        season_buckets = SP_SEASON_BUCKETS if role == "SP" else RP_SEASON_BUCKETS
        sample["pitch_bucket"] = _assign_bucket(sample["appearance_pitch_number"], pitch_buckets)
        sample["season_bucket"] = _assign_bucket(sample["season_pitches_before"], season_buckets)
        sample = sample.dropna(subset=["pitch_bucket", "season_bucket"]).copy()
        design, effect_columns = _slice1_design(sample, pitch_buckets, season_buckets)
        group_pitch = pd.factorize(sample["pitcher"].astype(str) + "|" + sample["pitch_type"].astype(str), sort=True)[0]
        group_batter = pd.factorize(pd.to_numeric(sample["batter"], errors="coerce").fillna(-1).astype(int), sort=True)[0]
        cluster = pd.factorize(sample["pitcher"].astype(str) + "|" + sample["game_pk"].astype(str), sort=True)[0]
        transformed_x = _two_way_residualize(design.to_numpy(dtype="float64"), group_pitch, group_batter)
        role_diagnostics: dict[str, Any] = {
            "role": role,
            "status": "ready",
            "pitches": int(len(sample)),
            "appearances": int(sample[["pitcher", "game_pk"]].drop_duplicates().shape[0]),
            "pitchers": int(sample["pitcher"].nunique()),
            "clusters": int(np.unique(cluster).size),
            "fixed_effects": ["pitcher × pitch type", "batter"],
            "controls": ["count", "handedness matchup", "times through order", "inning group", "home venue", "calendar trend"],
            "outcomes": {},
        }
        for outcome, label in [("pitch_stuff_plus", "Stuff+"), ("location_plus_pitch", "Location+")]:
            y = pd.to_numeric(sample[outcome], errors="coerce").to_numpy(dtype="float64")
            transformed_y = _two_way_residualize(y[:, None], group_pitch, group_batter)[:, 0]
            beta, standard_errors, r_squared = _cluster_ols(transformed_x, transformed_y, cluster)
            role_diagnostics["outcomes"][outcome] = {"within_r_squared": round(r_squared, 4)}
            for dimension, buckets, column_prefix in [
                ("appearance_pitch_count", pitch_buckets, "pitch_bucket"),
                ("season_workload", season_buckets, "season_bucket"),
            ]:
                for order, (_, _, bucket) in enumerate(buckets):
                    rows = sample[sample[column_prefix].eq(bucket)]
                    column = effect_columns.get((column_prefix, bucket))
                    estimate = 0.0 if order == 0 else float(beta[design.columns.get_loc(column)])
                    se = 0.0 if order == 0 else float(standard_errors[design.columns.get_loc(column)])
                    results.append({
                        "role": role,
                        "dimension": dimension,
                        "outcome": outcome,
                        "outcome_label": label,
                        "bucket": bucket,
                        "order": order,
                        "reference": order == 0,
                        "adjusted_delta": round(estimate, 3),
                        "ci_low": round(estimate - 1.96 * se, 3),
                        "ci_high": round(estimate + 1.96 * se, 3),
                        "standard_error": round(se, 4),
                        "raw_mean": round(float(rows[outcome].mean()), 2),
                        "pitches": int(len(rows)),
                        "appearances": int(rows[["pitcher", "game_pk"]].drop_duplicates().shape[0]),
                        "pitchers": int(rows["pitcher"].nunique()),
                    })
        diagnostics.append(role_diagnostics)
    summaries = []
    for role in ["SP", "RP"]:
        for dimension in ["appearance_pitch_count", "season_workload"]:
            for outcome, label in [("pitch_stuff_plus", "Stuff+"), ("location_plus_pitch", "Location+")]:
                points = [row for row in results if row["role"] == role and row["dimension"] == dimension and row["outcome"] == outcome]
                if not points:
                    continue
                terminal = max(points, key=lambda row: row["order"])
                direction = "decline" if terminal["ci_high"] < 0 else "increase" if terminal["ci_low"] > 0 else "inconclusive"
                summaries.append({
                    "role": role,
                    "dimension": dimension,
                    "outcome": outcome,
                    "outcome_label": label,
                    "reference_bucket": min(points, key=lambda row: row["order"])["bucket"],
                    "terminal_bucket": terminal["bucket"],
                    "adjusted_delta": terminal["adjusted_delta"],
                    "ci_low": terminal["ci_low"],
                    "ci_high": terminal["ci_high"],
                    "direction": direction,
                })
    return {
        "status": "ready" if results else "insufficient",
        "method": "Two-way fixed-effects OLS with pitcher-by-pitch-type and batter effects; appearance-clustered 95% confidence intervals.",
        "interpretation": "Adjusted deltas are Plus points relative to the first bucket, not a published Stamina+ score. These Slice 1 curves remain uncorrected; compare them with Slice 2 below.",
        "points": results,
        "summaries": summaries,
        "diagnostics": diagnostics,
        "warnings": [
            "High pitch-count observations are selected survivors; use the Slice 2 paired and weighted sensitivity estimates below.",
            "Weather and travel are unavailable in the local source and are omitted from this primary model.",
            "Arm angle is excluded because missingness occurs in complete date batches rather than at random.",
        ],
    }


def _assign_bucket(values: pd.Series, buckets: list[tuple[int, int, str]]) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    result = pd.Series(pd.NA, index=values.index, dtype="object")
    for low, high, label in buckets:
        result.loc[numeric.between(low, high)] = label
    return result


def _slice1_design(
    sample: pd.DataFrame,
    pitch_buckets: list[tuple[int, int, str]],
    season_buckets: list[tuple[int, int, str]],
) -> tuple[pd.DataFrame, dict[tuple[str, str], str]]:
    categories = pd.DataFrame(index=sample.index)
    categories["pitch_bucket"] = pd.Categorical(sample["pitch_bucket"], categories=[item[2] for item in pitch_buckets], ordered=True)
    categories["season_bucket"] = pd.Categorical(sample["season_bucket"], categories=[item[2] for item in season_buckets], ordered=True)
    categories["count"] = sample["balls"].fillna(-1).astype(str) + "-" + sample["strikes"].fillna(-1).astype(str)
    categories["matchup"] = sample["p_throws"].fillna("U").astype(str) + "-" + sample["stand"].fillna("U").astype(str)
    categories["tto"] = pd.to_numeric(sample["n_thruorder_pitcher"], errors="coerce").fillna(0).clip(0, 4).astype(int).astype(str)
    categories["inning_group"] = pd.cut(pd.to_numeric(sample["inning"], errors="coerce"), bins=[0, 3, 6, 9, np.inf], labels=["1-3", "4-6", "7-9", "10+"]).astype("object").fillna("unknown")
    categories["venue"] = sample["home_team"].fillna("unknown").astype(str)
    parts: list[pd.DataFrame] = []
    effect_columns: dict[tuple[str, str], str] = {}
    for column in categories.columns:
        dummies = pd.get_dummies(categories[column], prefix=column, dtype="float64")
        ordered_columns = list(dummies.columns)
        if ordered_columns:
            dummies = dummies.drop(columns=ordered_columns[0])
        parts.append(dummies)
        if column in {"pitch_bucket", "season_bucket"}:
            for bucket in categories[column].cat.categories:
                name = f"{column}_{bucket}"
                if name in dummies.columns:
                    effect_columns[(column, str(bucket))] = name
    day = (sample["game_date"] - sample["game_date"].min()).dt.days.astype(float)
    scale = max(float(day.max()), 1.0)
    calendar = pd.DataFrame({"calendar": day / scale, "calendar_sq": (day / scale) ** 2}, index=sample.index)
    parts.append(calendar)
    design = pd.concat(parts, axis=1)
    design = design.loc[:, design.nunique(dropna=False).gt(1)]
    return design, effect_columns


def _two_way_residualize(values: np.ndarray, first_group: np.ndarray, second_group: np.ndarray) -> np.ndarray:
    residual = np.asarray(values, dtype="float64").copy()
    for _ in range(8):
        previous = residual.copy()
        for groups in [first_group, second_group]:
            counts = np.bincount(groups).astype("float64")
            sums = np.zeros((len(counts), residual.shape[1]), dtype="float64")
            np.add.at(sums, groups, residual)
            residual -= (sums / counts[:, None])[groups]
        if np.max(np.abs(residual - previous)) < 1e-7:
            break
    return residual


def _cluster_ols(x: np.ndarray, y: np.ndarray, clusters: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    xtx_inverse = np.linalg.pinv(x.T @ x, rcond=1e-10)
    beta = xtx_inverse @ (x.T @ y)
    residual = y - x @ beta
    cluster_count = int(np.max(clusters)) + 1
    scores = np.zeros((cluster_count, x.shape[1]), dtype="float64")
    np.add.at(scores, clusters, x * residual[:, None])
    covariance = xtx_inverse @ (scores.T @ scores) @ xtx_inverse
    if cluster_count > 1 and len(y) > x.shape[1]:
        covariance *= cluster_count / (cluster_count - 1) * (len(y) - 1) / (len(y) - x.shape[1])
    standard_errors = np.sqrt(np.clip(np.diag(covariance), 0.0, None))
    denominator = float(np.sum((y - y.mean()) ** 2))
    r_squared = 1.0 - float(np.sum(residual**2)) / denominator if denominator > 0 else 0.0
    return beta, standard_errors, r_squared


def _build_slice2(frame: pd.DataFrame, slice1: dict[str, Any]) -> dict[str, Any]:
    appearance_results: list[dict[str, Any]] = []
    selection_models: list[dict[str, Any]] = []
    tto_results: list[dict[str, Any]] = []
    season_results: list[dict[str, Any]] = []
    for role in ["SP", "RP"]:
        buckets = SP_BUCKETS if role == "SP" else RP_BUCKETS
        role_frame = frame[
            frame["appearance_role"].eq(role)
            & frame["pitch_stuff_plus"].notna()
            & frame["location_plus_pitch"].notna()
        ].copy()
        role_frame["analysis_bucket"] = _assign_bucket(role_frame["appearance_pitch_number"], buckets)
        grouped = (
            role_frame.dropna(subset=["analysis_bucket"])
            .groupby(["pitcher", "game_pk", "analysis_bucket"], as_index=False)
            .agg(
                pitch_stuff_plus=("pitch_stuff_plus", "mean"),
                location_plus_pitch=("location_plus_pitch", "mean"),
                release_speed=("release_speed", "mean"),
                modal_tto=("n_thruorder_pitcher", lambda values: pd.to_numeric(values, errors="coerce").median()),
                pitches=("pitcher", "size"),
                days_rest=("days_rest", "first"),
                season_pitches_before=("season_pitches_before", "first"),
                appearance_number=("appearance_number", "first"),
                game_date=("game_date", "first"),
            )
        )
        baseline_label = buckets[0][2]
        baseline = grouped[grouped["analysis_bucket"].eq(baseline_label)].copy()
        total_pitches = role_frame.groupby(["pitcher", "game_pk"])["appearance_pitch_number"].max().rename("total_pitches")
        baseline = baseline.merge(total_pitches, on=["pitcher", "game_pk"], how="left")
        baseline = baseline.sort_values(["pitcher", "game_date", "game_pk"], kind="stable")
        baseline["prior_avg_pitches"] = baseline.groupby("pitcher")["total_pitches"].transform(
            lambda values: values.shift(1).expanding().mean()
        )
        baseline["prior_avg_pitches"] = baseline["prior_avg_pitches"].fillna(baseline["total_pitches"].median())
        for order, (low, _, bucket) in enumerate(buckets[1:], start=1):
            target = grouped[grouped["analysis_bucket"].eq(bucket)].copy()
            target_keys = pd.MultiIndex.from_frame(target[["pitcher", "game_pk"]])
            model_frame = baseline.copy()
            model_frame["reached"] = pd.MultiIndex.from_frame(model_frame[["pitcher", "game_pk"]]).isin(target_keys).astype(int)
            probabilities, diagnostic = _cross_fitted_reach_probability(model_frame)
            model_frame["probability"] = probabilities
            marginal = float(model_frame["reached"].mean())
            reached = model_frame[model_frame["reached"].eq(1)].copy()
            if reached.empty:
                diagnostic.update({
                    "role": role,
                    "bucket": bucket,
                    "at_risk_appearances": int(len(model_frame)),
                    "reached_appearances": 0,
                    "marginal_reach_pct": 0.0,
                    "effective_sample_size": 0.0,
                    "max_weight": 0.0,
                })
                selection_models.append(diagnostic)
                continue
            reached_keys = pd.MultiIndex.from_frame(reached[["pitcher", "game_pk"]])
            # Each target window is a separate missing-observation problem relative to
            # the common first-window cohort.  Do not multiply probabilities across
            # targets: P(reach 101+) already includes survival through earlier windows.
            direct_weight = np.clip(marginal / reached["probability"].clip(0.03, 0.97), 0.1, 10.0)
            current_weights = pd.Series(direct_weight.to_numpy(dtype="float64"), index=reached_keys)
            current_weights = current_weights.clip(upper=float(current_weights.quantile(0.99)))
            diagnostic.update({
                "role": role,
                "bucket": bucket,
                "at_risk_appearances": int(len(model_frame)),
                "reached_appearances": int(len(reached)),
                "marginal_reach_pct": round(marginal * 100.0, 1),
                "effective_sample_size": round(_effective_sample_size(current_weights.to_numpy()), 1),
                "max_weight": round(float(current_weights.max()), 3),
            })
            selection_models.append(diagnostic)
            paired = reached[["pitcher", "game_pk", "pitch_stuff_plus", "location_plus_pitch"]].merge(
                target[["pitcher", "game_pk", "pitch_stuff_plus", "location_plus_pitch", "modal_tto", "pitches"]],
                on=["pitcher", "game_pk"],
                how="inner",
                suffixes=("_base", "_target"),
            )
            paired_weights = current_weights.reindex(pd.MultiIndex.from_frame(paired[["pitcher", "game_pk"]])).to_numpy(dtype="float64")
            for outcome, label in [("pitch_stuff_plus", "Stuff+"), ("location_plus_pitch", "Location+")]:
                differences = paired[f"{outcome}_target"].to_numpy(dtype="float64") - paired[f"{outcome}_base"].to_numpy(dtype="float64")
                unweighted, unweighted_se = _clustered_weighted_mean(differences, np.ones(len(paired)), paired["pitcher"].to_numpy())
                weighted, weighted_se = _clustered_weighted_mean(differences, paired_weights, paired["pitcher"].to_numpy())
                appearance_results.append({
                    "role": role,
                    "outcome": outcome,
                    "outcome_label": label,
                    "reference_bucket": baseline_label,
                    "target_bucket": bucket,
                    "order": order,
                    "appearances": int(len(paired)),
                    "pitchers": int(paired["pitcher"].nunique()),
                    "unweighted_delta": round(unweighted, 3),
                    "unweighted_ci_low": round(unweighted - 1.96 * unweighted_se, 3),
                    "unweighted_ci_high": round(unweighted + 1.96 * unweighted_se, 3),
                    "weighted_delta": round(weighted, 3),
                    "weighted_ci_low": round(weighted - 1.96 * weighted_se, 3),
                    "weighted_ci_high": round(weighted + 1.96 * weighted_se, 3),
                })
                for tto_label, mask in [
                    ("TTO ≤ 3", pd.to_numeric(paired["modal_tto"], errors="coerce").le(3)),
                    ("TTO 4+", pd.to_numeric(paired["modal_tto"], errors="coerce").gt(3)),
                ]:
                    if int(mask.sum()) < 30:
                        continue
                    value, se = _clustered_weighted_mean(differences[mask], paired_weights[mask], paired.loc[mask, "pitcher"].to_numpy())
                    tto_results.append({
                        "role": role, "outcome": outcome, "outcome_label": label, "target_bucket": bucket,
                        "tto": tto_label, "appearances": int(mask.sum()), "pitchers": int(paired.loc[mask, "pitcher"].nunique()),
                        "weighted_delta": round(value, 3), "ci_low": round(value - 1.96 * se, 3), "ci_high": round(value + 1.96 * se, 3),
                    })
        season_results.extend(_season_fixed_cohort(role_frame, role))
    extreme_comparison = []
    for role in ["SP", "RP"]:
        for outcome in ["pitch_stuff_plus", "location_plus_pitch"]:
            primary = [row for row in slice1.get("summaries", []) if row["role"] == role and row["dimension"] == "appearance_pitch_count" and row["outcome"] == outcome]
            corrected = [row for row in appearance_results if row["role"] == role and row["outcome"] == outcome]
            if primary and corrected:
                extreme = max(corrected, key=lambda row: row["order"])
                extreme_comparison.append({
                    "role": role, "outcome": outcome, "outcome_label": extreme["outcome_label"],
                    "slice1_adjusted_delta": primary[0]["adjusted_delta"],
                    "survivor_paired_delta": extreme["unweighted_delta"],
                    "weighted_paired_delta": extreme["weighted_delta"],
                    "target_bucket": extreme["target_bucket"],
                })
    return {
        "status": "ready",
        "method": "Fixed-window within-appearance pairing plus cross-fitted stabilized inverse-probability-of-observation weights; uncertainty clustered by pitcher.",
        "appearance_results": appearance_results,
        "season_fixed_cohort": season_results,
        "selection_models": selection_models,
        "tto_sensitivity": tto_results,
        "extreme_comparison": extreme_comparison,
        "warnings": [
            "Weighting reduces observed selection on early quality and workload history but cannot recover unmeasured manager intent, health, bullpen state or warm-up information.",
            "The fixed-cohort estimates describe pitchers who reached the target window; they are not league-wide causal effects.",
            "Any extreme window with weak propensity discrimination or low effective sample size remains research-only.",
        ],
    }


def _build_slice3(frame: pd.DataFrame) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    priors: list[dict[str, Any]] = []
    validations: list[dict[str, Any]] = []
    identity = _pitcher_role_identity(frame)
    for role in ["SP", "RP"]:
        buckets = SP_BUCKETS if role == "SP" else RP_BUCKETS
        unit_pitches = 20.0 if role == "SP" else 5.0
        minimum_appearances = 8 if role == "SP" else 12
        role_frame = frame[
            frame["appearance_role"].eq(role)
            & frame["pitch_stuff_plus"].notna()
            & frame["location_plus_pitch"].notna()
            & frame["pitch_type"].notna()
        ].copy()
        observations = _pitcher_retention_observations(role_frame, buckets, unit_pitches)
        for outcome, label in [("pitch_stuff_plus", "Stuff+"), ("location_plus_pitch", "Location+")]:
            sample = observations[observations["outcome"].eq(outcome)].copy()
            raw_estimates: list[dict[str, Any]] = []
            for pitcher, group in sample.groupby("pitcher", sort=False):
                appearances = int(group["game_pk"].nunique())
                target_windows = int(group["target_bucket"].nunique())
                if appearances < minimum_appearances or target_windows < 2:
                    continue
                slope, standard_error = _weighted_slope_with_clustered_se(group)
                raw_estimates.append({
                    "pitcher_id": int(pitcher),
                    "raw_slope": slope,
                    "standard_error": max(standard_error, 0.05),
                    "appearances": appearances,
                    "observations": int(len(group)),
                    "matched_pitches": int(group["matched_pitches"].sum()),
                    "target_windows": target_windows,
                })
            if not raw_estimates:
                continue
            raw = pd.DataFrame(raw_estimates)
            variances = raw["standard_error"].to_numpy(dtype="float64") ** 2
            estimates = raw["raw_slope"].to_numpy(dtype="float64")
            fixed_weights = 1.0 / variances
            fixed_mean = float(np.sum(fixed_weights * estimates) / np.sum(fixed_weights))
            q_value = float(np.sum(fixed_weights * (estimates - fixed_mean) ** 2))
            c_value = float(np.sum(fixed_weights) - np.sum(fixed_weights**2) / np.sum(fixed_weights))
            tau_squared = max(0.0, (q_value - (len(raw) - 1)) / c_value) if c_value > 0 else 0.0
            random_weights = 1.0 / (variances + tau_squared)
            league_mean = float(np.sum(random_weights * estimates) / np.sum(random_weights))
            prior_scale = float(np.sqrt(tau_squared))
            priors.append({
                "role": role,
                "outcome": outcome,
                "outcome_label": label,
                "unit_pitches": int(unit_pitches),
                "candidate_pitchers": int(role_frame["pitcher"].nunique()),
                "eligible_pitchers": int(len(raw)),
                "minimum_appearances": minimum_appearances,
                "league_slope": round(league_mean, 3),
                "between_pitcher_sd": round(prior_scale, 3),
            })
            role_rows = []
            for item in raw.to_dict(orient="records"):
                sampling_variance = float(item["standard_error"]) ** 2
                if tau_squared <= 1e-12:
                    posterior = league_mean
                    posterior_se = float(np.sqrt(1.0 / np.sum(fixed_weights)))
                    reliability = 0.0
                else:
                    posterior_variance = 1.0 / (1.0 / sampling_variance + 1.0 / tau_squared)
                    posterior = posterior_variance * (float(item["raw_slope"]) / sampling_variance + league_mean / tau_squared)
                    posterior_se = float(np.sqrt(posterior_variance))
                    reliability = tau_squared / (tau_squared + sampling_variance)
                ci_low = posterior - 1.96 * posterior_se
                ci_high = posterior + 1.96 * posterior_se
                if ci_low > league_mean:
                    band = "above_average"
                elif ci_high < league_mean:
                    band = "below_average"
                else:
                    band = "indistinguishable"
                reliability_label = "strong" if reliability >= 0.60 else "moderate" if reliability >= 0.35 else "limited"
                pitcher_id = int(item["pitcher_id"])
                person = identity.get((pitcher_id, role), {})
                role_rows.append({
                    "pitcher_id": pitcher_id,
                    "pitcher_name": person.get("pitcher_name") or f"Pitcher {pitcher_id}",
                    "team": person.get("team") or "",
                    "role": role,
                    "outcome": outcome,
                    "outcome_label": label,
                    "unit_pitches": int(unit_pitches),
                    "raw_slope": round(float(item["raw_slope"]), 3),
                    "standard_error": round(float(item["standard_error"]), 4),
                    "posterior_slope": round(posterior, 3),
                    "ci_low": round(ci_low, 3),
                    "ci_high": round(ci_high, 3),
                    "reliability": round(reliability, 3),
                    "reliability_label": reliability_label,
                    "retention_band": band,
                    "appearances": int(item["appearances"]),
                    "observations": int(item["observations"]),
                    "matched_pitches": int(item["matched_pitches"]),
                    "target_windows": int(item["target_windows"]),
                })
            role_rows.sort(key=lambda item: item["posterior_slope"], reverse=True)
            for rank, item in enumerate(role_rows, start=1):
                item["rank"] = rank
            rows.extend(role_rows)
            validations.append(_split_half_validation(sample, raw["pitcher_id"].astype(int).tolist(), role, outcome, label, minimum_appearances))
    return {
        "status": "ready" if rows else "insufficient",
        "method": "Pitch-type-matched within-appearance retention slopes with Slice 2 observation weights, followed by empirical-Bayes random-effects shrinkage.",
        "leaderboard": rows,
        "priors": priors,
        "split_half_validation": validations,
        "warnings": [
            "Posterior slope is a research estimate of Plus-point change per workload unit (20 pitches for SP, 5 for RP), not Stamina+.",
            "Pitch-type matching reduces repertoire sequencing bias; count, intent and unmeasured health or manager decisions can still confound an individual estimate.",
            "Limited-reliability rows should not be used to rank pitchers, and weak split-half correlation blocks publication of a production score.",
        ],
    }


def _pitcher_retention_observations(
    frame: pd.DataFrame,
    buckets: list[tuple[int, int, str]],
    unit_pitches: float,
) -> pd.DataFrame:
    working = frame.copy()
    working["analysis_bucket"] = _assign_bucket(working["appearance_pitch_number"], buckets)
    working = working.dropna(subset=["analysis_bucket"])
    overall = working.groupby(["pitcher", "game_pk", "analysis_bucket"], as_index=False).agg(
        pitch_stuff_plus=("pitch_stuff_plus", "mean"), location_plus_pitch=("location_plus_pitch", "mean"),
        release_speed=("release_speed", "mean"), days_rest=("days_rest", "first"),
        season_pitches_before=("season_pitches_before", "first"), appearance_number=("appearance_number", "first"),
        game_date=("game_date", "first"), total_pitches=("appearance_pitch_number", "max"),
    )
    pitch_type = working.groupby(["pitcher", "game_pk", "analysis_bucket", "pitch_type"], as_index=False).agg(
        pitch_stuff_plus=("pitch_stuff_plus", "mean"), location_plus_pitch=("location_plus_pitch", "mean"),
        pitch_number=("appearance_pitch_number", "mean"), pitches=("pitcher", "size"),
        appearance_number=("appearance_number", "first"),
    )
    baseline_label = buckets[0][2]
    baseline = overall[overall["analysis_bucket"].eq(baseline_label)].copy()
    baseline = baseline.sort_values(["pitcher", "game_date", "game_pk"], kind="stable")
    baseline["prior_avg_pitches"] = baseline.groupby("pitcher")["total_pitches"].transform(lambda values: values.shift(1).expanding().mean())
    baseline["prior_avg_pitches"] = baseline["prior_avg_pitches"].fillna(baseline["total_pitches"].median())
    baseline_pitch_type = pitch_type[pitch_type["analysis_bucket"].eq(baseline_label)].copy()
    records: list[pd.DataFrame] = []
    for _, _, bucket in buckets[1:]:
        target_overall = overall[overall["analysis_bucket"].eq(bucket)]
        target_keys = pd.MultiIndex.from_frame(target_overall[["pitcher", "game_pk"]])
        model_frame = baseline.copy()
        model_frame["reached"] = pd.MultiIndex.from_frame(model_frame[["pitcher", "game_pk"]]).isin(target_keys).astype(int)
        probabilities, _ = _cross_fitted_reach_probability(model_frame)
        model_frame["probability"] = probabilities
        marginal = float(model_frame["reached"].mean())
        reached = model_frame[model_frame["reached"].eq(1)]
        if reached.empty:
            continue
        direct_weight = np.clip(marginal / reached["probability"].clip(0.03, 0.97), 0.1, 10.0)
        weight_by_key = pd.Series(
            direct_weight.to_numpy(dtype="float64"),
            index=pd.MultiIndex.from_frame(reached[["pitcher", "game_pk"]]),
        )
        weight_by_key = weight_by_key.clip(upper=float(weight_by_key.quantile(0.99)))
        target_pitch_type = pitch_type[pitch_type["analysis_bucket"].eq(bucket)]
        paired = baseline_pitch_type.merge(
            target_pitch_type,
            on=["pitcher", "game_pk", "pitch_type"],
            suffixes=("_base", "_target"),
        )
        if paired.empty:
            continue
        paired["match_weight"] = np.minimum(paired["pitches_base"], paired["pitches_target"]).clip(lower=1)
        paired["pitch_distance_weighted"] = (
            paired["pitch_number_target"] - paired["pitch_number_base"]
        ) * paired["match_weight"]
        for outcome in ["pitch_stuff_plus", "location_plus_pitch"]:
            paired["delta_weighted"] = (
                paired[f"{outcome}_target"] - paired[f"{outcome}_base"]
            ) * paired["match_weight"]
            aggregated = paired.groupby(["pitcher", "game_pk"], as_index=False).agg(
                delta_sum=("delta_weighted", "sum"), distance_sum=("pitch_distance_weighted", "sum"),
                matched_pitches=("match_weight", "sum"), appearance_number=("appearance_number_target", "first"),
            )
            aggregated["delta"] = aggregated["delta_sum"] / aggregated["matched_pitches"]
            aggregated["workload_units"] = aggregated["distance_sum"] / aggregated["matched_pitches"] / unit_pitches
            keys = pd.MultiIndex.from_frame(aggregated[["pitcher", "game_pk"]])
            aggregated["observation_weight"] = weight_by_key.reindex(keys).to_numpy(dtype="float64")
            aggregated["outcome"] = outcome
            aggregated["target_bucket"] = bucket
            records.append(aggregated[[
                "pitcher", "game_pk", "appearance_number", "outcome", "target_bucket", "delta",
                "workload_units", "observation_weight", "matched_pitches",
            ]])
    return pd.concat(records, ignore_index=True) if records else pd.DataFrame(columns=[
        "pitcher", "game_pk", "appearance_number", "outcome", "target_bucket", "delta",
        "workload_units", "observation_weight", "matched_pitches",
    ])


def _weighted_slope_with_clustered_se(frame: pd.DataFrame) -> tuple[float, float]:
    x = frame["workload_units"].to_numpy(dtype="float64")
    y = frame["delta"].to_numpy(dtype="float64")
    selection = frame["observation_weight"].to_numpy(dtype="float64")
    match_precision = np.sqrt(frame["matched_pitches"].to_numpy(dtype="float64")).clip(1.0, 4.0)
    weights = selection * match_precision
    denominator = float(np.sum(weights * x**2))
    if denominator <= 0:
        return 0.0, float("inf")
    slope = float(np.sum(weights * x * y) / denominator)
    residual = y - slope * x
    scores = pd.Series(weights * x * residual).groupby(frame["game_pk"].to_numpy()).sum().to_numpy(dtype="float64")
    variance = float(np.sum(scores**2) / denominator**2)
    if len(scores) > 1:
        variance *= len(scores) / (len(scores) - 1)
    return slope, float(np.sqrt(max(variance, 0.0)))


def _split_half_validation(
    sample: pd.DataFrame,
    pitcher_ids: list[int],
    role: str,
    outcome: str,
    outcome_label: str,
    minimum_appearances: int,
) -> dict[str, Any]:
    pairs = []
    minimum_half = max(4, minimum_appearances // 2)
    for pitcher_id in pitcher_ids:
        pitcher = sample[sample["pitcher"].eq(pitcher_id)].copy()
        midpoint = float(pitcher["appearance_number"].median())
        halves = [pitcher[pitcher["appearance_number"].le(midpoint)], pitcher[pitcher["appearance_number"].gt(midpoint)]]
        if any(int(half["game_pk"].nunique()) < minimum_half for half in halves):
            continue
        first, _ = _weighted_slope_with_clustered_se(halves[0])
        second, _ = _weighted_slope_with_clustered_se(halves[1])
        pairs.append((first, second))
    if len(pairs) >= 3:
        pair_frame = pd.DataFrame(pairs, columns=["first", "second"])
        correlation = float(pair_frame["first"].rank().corr(pair_frame["second"].rank()))
        mae = float((pair_frame["first"] - pair_frame["second"]).abs().mean())
    else:
        correlation, mae = float("nan"), float("nan")
    status = "stable" if np.isfinite(correlation) and correlation >= 0.50 else "partial" if np.isfinite(correlation) and correlation >= 0.25 else "weak"
    return {
        "role": role, "outcome": outcome, "outcome_label": outcome_label, "pitchers": int(len(pairs)),
        "spearman_correlation": round(correlation, 3) if np.isfinite(correlation) else None,
        "mean_absolute_difference": round(mae, 3) if np.isfinite(mae) else None,
        "status": status,
    }


def _pitcher_role_identity(frame: pd.DataFrame) -> dict[tuple[int, str], dict[str, str]]:
    ordered = frame.sort_values(["game_date", "game_pk"], kind="stable")
    result: dict[tuple[int, str], dict[str, str]] = {}
    for (pitcher, role), group in ordered.groupby(["pitcher", "appearance_role"], sort=False):
        names = group["player_name"].dropna().astype(str).str.strip()
        names = names[~names.str.match(r"^(pitcher|player)\s+\d+$", case=False, na=False) & names.ne("")]
        teams = group["pitcher_team"].dropna().astype(str).str.strip()
        name = names.iloc[-1] if not names.empty else ""
        if "," in name:
            last, first = [part.strip() for part in name.split(",", 1)]
            name = f"{first} {last}".strip()
        result[(int(pitcher), str(role))] = {
            "pitcher_name": name,
            "team": teams.iloc[-1] if not teams.empty else "",
        }
    return result


def _build_slice5(
    frame: pd.DataFrame,
    year: int,
    data_dir: Path,
    current_slice3: dict[str, Any],
) -> dict[str, Any]:
    prior_year = int(year) - 1
    prior_path = stamina_meta_path(prior_year, data_dir)
    base = {
        "status": "unavailable",
        "publication_status": "research_only",
        "method": (
            "Season-centered Stuff+ retention slopes combined across seasons with inverse-variance weighting, "
            "then partially pooled within SP and RP and calibrated to a role-specific 100-centered scale."
        ),
        "train_year": prior_year,
        "test_year": int(year),
        "leaderboard": [],
        "season_leaderboard": [],
        "priors": [],
        "season_priors": [],
        "validations": [],
        "warnings": [],
    }
    if not prior_path.exists():
        base["warnings"] = [f"Missing {prior_path.name}; two-season Stamina+ cannot be estimated."]
        return base
    prior_payload = json.loads(prior_path.read_text(encoding="utf-8"))
    prior_slice3 = prior_payload.get("slice3") or {}
    if prior_slice3.get("status") != "ready" or current_slice3.get("status") != "ready":
        base["warnings"] = ["Both seasons need completed Slice 3 pitcher retention estimates."]
        return base

    identity = _pitcher_role_identity(frame)
    coverage = min(_stuff_coverage(prior_payload), _stuff_coverage({"coverage": _build_coverage(frame)}))
    validations = [
        _validate_retention_trait(prior_slice3, current_slice3, role, prior_year, int(year), coverage)
        for role in ["SP", "RP"]
    ]
    validation_by_role = {row["role"]: row for row in validations}
    season_leaderboard: list[dict[str, Any]] = []
    season_priors: list[dict[str, Any]] = []
    for season, slice3 in [(prior_year, prior_slice3), (int(year), current_slice3)]:
        season_rows, season_summary = _build_season_stamina_scores(slice3, season)
        season_leaderboard.extend(season_rows)
        season_priors.extend(season_summary)
    leaderboard: list[dict[str, Any]] = []
    priors: list[dict[str, Any]] = []
    for role in ["SP", "RP"]:
        season_rows: list[dict[str, Any]] = []
        for season, slice3 in [(prior_year, prior_slice3), (int(year), current_slice3)]:
            prior = _slice3_prior(slice3, role)
            if not prior:
                continue
            for row in slice3.get("leaderboard", []):
                if row.get("role") != role or row.get("outcome") != "pitch_stuff_plus":
                    continue
                standard_error = _slice3_raw_standard_error(row, prior)
                if not np.isfinite(standard_error) or standard_error <= 0:
                    continue
                season_rows.append({
                    "season": season,
                    "pitcher_id": int(row["pitcher_id"]),
                    "centered_raw": float(row["raw_slope"]) - float(prior["league_slope"]),
                    "standard_error": standard_error,
                    "season_reliability": float(row.get("reliability") or 0),
                    "appearances": int(row.get("appearances") or 0),
                    "matched_pitches": int(row.get("matched_pitches") or 0),
                    "pitcher_name": str(row.get("pitcher_name") or ""),
                    "team": str(row.get("team") or ""),
                })
        if not season_rows:
            continue
        season_frame = pd.DataFrame(season_rows)
        pooled_rows: list[dict[str, Any]] = []
        for pitcher_id, group in season_frame.groupby("pitcher_id", sort=False):
            weights = 1.0 / np.square(group["standard_error"].to_numpy(dtype="float64"))
            centered = group["centered_raw"].to_numpy(dtype="float64")
            pooled_rows.append({
                "pitcher_id": int(pitcher_id),
                "raw_advantage": float(np.average(centered, weights=weights)),
                "standard_error": float(np.sqrt(1.0 / weights.sum())),
                "seasons": int(group["season"].nunique()),
                "minimum_season_reliability": float(group["season_reliability"].min()),
                "appearances": int(group["appearances"].sum()),
                "matched_pitches": int(group["matched_pitches"].sum()),
                "pitcher_name": str(group.sort_values("season").iloc[-1]["pitcher_name"]),
                "team": str(group.sort_values("season").iloc[-1]["team"]),
            })
        pooled = pd.DataFrame(pooled_rows)
        league_mean, tau_squared = _random_effects_prior(
            pooled["raw_advantage"].to_numpy(dtype="float64"),
            np.square(pooled["standard_error"].to_numpy(dtype="float64")),
        )
        between_sd = float(np.sqrt(tau_squared))
        priors.append({
            "role": role,
            "unit_pitches": 20 if role == "SP" else 5,
            "pitchers": int(len(pooled)),
            "two_season_pitchers": int(pooled["seasons"].eq(2).sum()),
            "league_center": round(league_mean, 4),
            "between_pitcher_sd": round(between_sd, 4),
        })
        role_rows: list[dict[str, Any]] = []
        for item in pooled.to_dict(orient="records"):
            sampling_variance = float(item["standard_error"]) ** 2
            if tau_squared <= 1e-12:
                posterior, posterior_se, reliability = league_mean, float(item["standard_error"]), 0.0
            else:
                posterior_variance = 1.0 / (1.0 / sampling_variance + 1.0 / tau_squared)
                posterior = posterior_variance * (
                    float(item["raw_advantage"]) / sampling_variance + league_mean / tau_squared
                )
                posterior_se = float(np.sqrt(posterior_variance))
                reliability = tau_squared / (tau_squared + sampling_variance)
            scale = between_sd if between_sd > 1e-9 else 1.0
            stamina_plus = 100.0 + 10.0 * (posterior - league_mean) / scale
            score_se = 10.0 * posterior_se / scale
            seasons = int(item["seasons"])
            sample_label = (
                "qualified"
                if seasons == 2 and float(item["minimum_season_reliability"]) >= 0.35
                else "limited" if seasons == 2 else "provisional"
            )
            pitcher_id = int(item["pitcher_id"])
            person = identity.get((pitcher_id, role), {})
            role_rows.append({
                "rank": 0,
                "pitcher_id": pitcher_id,
                "pitcher_name": person.get("pitcher_name") or item["pitcher_name"] or f"Pitcher {pitcher_id}",
                "team": person.get("team") or item["team"] or "",
                "role": role,
                "unit_pitches": 20 if role == "SP" else 5,
                "stamina_plus": round(stamina_plus, 1),
                "ci_low": round(stamina_plus - 1.96 * score_se, 1),
                "ci_high": round(stamina_plus + 1.96 * score_se, 1),
                "retention_advantage": round(posterior - league_mean, 3),
                "raw_advantage": round(float(item["raw_advantage"]), 3),
                "reliability": round(reliability, 3),
                "reliability_label": "strong" if reliability >= 0.60 else "moderate" if reliability >= 0.35 else "limited",
                "sample_label": sample_label,
                "seasons": seasons,
                "appearances": int(item["appearances"]),
                "matched_pitches": int(item["matched_pitches"]),
                "publication_status": validation_by_role[role]["status"],
            })
        role_rows.sort(key=lambda row: row["stamina_plus"], reverse=True)
        for rank, row in enumerate(role_rows, start=1):
            row["rank"] = rank
        leaderboard.extend(role_rows)

    validated_roles = [row for row in validations if row["status"] == "validated"]
    base.update({
        "status": "ready" if leaderboard else "insufficient",
        "publication_status": "validated" if len(validated_roles) == 2 else "research_only",
        "leaderboard": leaderboard,
        "season_leaderboard": season_leaderboard,
        "priors": priors,
        "season_priors": season_priors,
        "validations": validations,
        "warnings": [
            "Stamina+ measures role-specific Stuff+ retention, not durability, injury risk or next-appearance readiness.",
            "Location+ and public workload variables remain diagnostic only because they did not pass repeatability or predictive-gain gates.",
            "Provisional rows have only one eligible season; limited rows have two seasons but low signal reliability.",
        ],
    })
    return base


def _build_season_stamina_scores(
    slice3: dict[str, Any],
    season: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    scores: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    validations = {
        (row.get("role"), row.get("outcome")): row
        for row in slice3.get("split_half_validation", [])
    }
    for role in ["SP", "RP"]:
        prior = _slice3_prior(slice3, role)
        if not prior:
            continue
        league_slope = float(prior["league_slope"])
        between_sd = float(prior["between_pitcher_sd"])
        if between_sd <= 1e-9:
            continue
        validation = validations.get((role, "pitch_stuff_plus"), {})
        summaries.append({
            "season": int(season),
            "role": role,
            "unit_pitches": int(prior["unit_pitches"]),
            "eligible_pitchers": int(prior["eligible_pitchers"]),
            "league_slope": round(league_slope, 3),
            "between_pitcher_sd": round(between_sd, 3),
            "split_half_spearman": validation.get("spearman_correlation"),
            "split_half_status": validation.get("status") or "unavailable",
        })
        role_scores: list[dict[str, Any]] = []
        for row in slice3.get("leaderboard", []):
            if row.get("role") != role or row.get("outcome") != "pitch_stuff_plus":
                continue
            posterior = float(row["posterior_slope"])
            stamina_plus = 100.0 + 10.0 * (posterior - league_slope) / between_sd
            reliability = float(row.get("reliability") or 0)
            role_scores.append({
                "rank": 0,
                "pitcher_id": int(row["pitcher_id"]),
                "pitcher_name": str(row.get("pitcher_name") or f"Pitcher {row['pitcher_id']}"),
                "team": str(row.get("team") or ""),
                "role": role,
                "unit_pitches": int(prior["unit_pitches"]),
                "stamina_plus": round(stamina_plus, 1),
                "ci_low": round(100.0 + 10.0 * (float(row["ci_low"]) - league_slope) / between_sd, 1),
                "ci_high": round(100.0 + 10.0 * (float(row["ci_high"]) - league_slope) / between_sd, 1),
                "retention_advantage": round(posterior - league_slope, 3),
                "raw_advantage": round(float(row["raw_slope"]) - league_slope, 3),
                "reliability": round(reliability, 3),
                "reliability_label": str(row.get("reliability_label") or "limited"),
                "sample_label": "qualified" if reliability >= 0.35 else "limited",
                "seasons": 1,
                "season": int(season),
                "score_scope": "season",
                "appearances": int(row.get("appearances") or 0),
                "matched_pitches": int(row.get("matched_pitches") or 0),
                "publication_status": "season_estimate",
            })
        role_scores.sort(key=lambda item: item["stamina_plus"], reverse=True)
        for rank, row in enumerate(role_scores, start=1):
            row["rank"] = rank
        scores.extend(role_scores)
    return scores, summaries


def _build_coverage(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    for role, group in frame.groupby("appearance_role"):
        rows.append({
            "role": str(role),
            "stuff_coverage_pct": round(float(group["pitch_stuff_plus"].notna().mean() * 100), 1),
        })
    return rows


def _stuff_coverage(payload: dict[str, Any]) -> float:
    values = [
        float(row.get("stuff_coverage_pct") or 0)
        for row in payload.get("coverage", [])
        if row.get("role") in {"SP", "RP"}
    ]
    return min(values) if values else 0.0


def _slice3_prior(slice3: dict[str, Any], role: str) -> dict[str, Any] | None:
    return next((
        row for row in slice3.get("priors", [])
        if row.get("role") == role and row.get("outcome") == "pitch_stuff_plus"
    ), None)


def _slice3_raw_standard_error(row: dict[str, Any], prior: dict[str, Any]) -> float:
    explicit = row.get("standard_error")
    if explicit is not None and np.isfinite(float(explicit)) and float(explicit) > 0:
        return float(explicit)
    reliability = float(row.get("reliability") or 0)
    tau = float(prior.get("between_pitcher_sd") or 0)
    if reliability > 1e-6 and tau > 0:
        return float(np.sqrt(tau * tau * (1.0 - reliability) / reliability))
    posterior_se = abs(float(row.get("ci_high") or 0) - float(row.get("ci_low") or 0)) / (2 * 1.96)
    return max(posterior_se, 0.05)


def _random_effects_prior(estimates: np.ndarray, variances: np.ndarray) -> tuple[float, float]:
    fixed_weights = 1.0 / np.clip(variances, 1e-9, None)
    fixed_mean = float(np.sum(fixed_weights * estimates) / np.sum(fixed_weights))
    q_value = float(np.sum(fixed_weights * np.square(estimates - fixed_mean)))
    c_value = float(np.sum(fixed_weights) - np.sum(np.square(fixed_weights)) / np.sum(fixed_weights))
    tau_squared = max(0.0, (q_value - (len(estimates) - 1)) / c_value) if c_value > 0 else 0.0
    random_weights = 1.0 / (variances + tau_squared)
    return float(np.sum(random_weights * estimates) / np.sum(random_weights)), tau_squared


def _validate_retention_trait(
    prior_slice3: dict[str, Any],
    current_slice3: dict[str, Any],
    role: str,
    train_year: int,
    test_year: int,
    coverage_pct: float,
) -> dict[str, Any]:
    prior = _slice3_prior(prior_slice3, role)
    current = _slice3_prior(current_slice3, role)
    if not prior or not current:
        return {
            "role": role, "train_year": train_year, "test_year": test_year, "status": "insufficient",
            "common_pitchers": 0, "reliable_pitchers": 0, "source_coverage_pct": round(coverage_pct, 1),
            "gates": {"coverage": coverage_pct >= 95, "sample": False, "rank": False, "rmse": False},
        }
    left = pd.DataFrame([
        row for row in prior_slice3.get("leaderboard", [])
        if row.get("role") == role and row.get("outcome") == "pitch_stuff_plus"
    ])
    right = pd.DataFrame([
        row for row in current_slice3.get("leaderboard", [])
        if row.get("role") == role and row.get("outcome") == "pitch_stuff_plus"
    ])
    if left.empty or right.empty:
        return {
            "role": role, "train_year": train_year, "test_year": test_year, "status": "insufficient",
            "common_pitchers": 0, "reliable_pitchers": 0, "source_coverage_pct": round(coverage_pct, 1),
            "gates": {"coverage": coverage_pct >= 95, "sample": False, "rank": False, "rmse": False},
        }
    joined = left.merge(right, on="pitcher_id", suffixes=("_train", "_test"))
    train = joined["posterior_slope_train"].astype(float) - float(prior["league_slope"])
    test = joined["raw_slope_test"].astype(float) - float(current["league_slope"])
    spearman = float(train.rank().corr(test.rank())) if len(joined) >= 3 else float("nan")
    pearson = float(train.corr(test)) if len(joined) >= 3 else float("nan")
    errors = test - train
    rmse = float(np.sqrt(np.mean(np.square(errors)))) if len(joined) else float("nan")
    baseline_rmse = float(np.sqrt(np.mean(np.square(test)))) if len(joined) else float("nan")
    improvement = 100.0 * (baseline_rmse - rmse) / baseline_rmse if baseline_rmse > 0 else float("nan")
    reliable = joined[
        joined["reliability_train"].astype(float).ge(0.35)
        & joined["reliability_test"].astype(float).ge(0.35)
    ]
    if len(joined) >= 3 and float(np.var(train)) > 1e-12:
        calibration_slope, calibration_intercept = np.polyfit(train, test, 1)
    else:
        calibration_slope, calibration_intercept = float("nan"), float("nan")
    gates = {
        "coverage": coverage_pct >= 95.0,
        "sample": len(joined) >= 50,
        "rank": np.isfinite(spearman) and spearman >= 0.40,
        "rmse": np.isfinite(improvement) and improvement > 0.0,
    }
    return {
        "role": role,
        "train_year": train_year,
        "test_year": test_year,
        "status": "validated" if all(gates.values()) else "research_only",
        "common_pitchers": int(len(joined)),
        "reliable_pitchers": int(len(reliable)),
        "source_coverage_pct": round(coverage_pct, 1),
        "spearman_correlation": round(spearman, 3) if np.isfinite(spearman) else None,
        "pearson_correlation": round(pearson, 3) if np.isfinite(pearson) else None,
        "rmse": round(rmse, 3) if np.isfinite(rmse) else None,
        "baseline_rmse": round(baseline_rmse, 3) if np.isfinite(baseline_rmse) else None,
        "rmse_improvement_pct": round(improvement, 2) if np.isfinite(improvement) else None,
        "mae": round(float(np.mean(np.abs(errors))), 3) if len(joined) else None,
        "calibration_slope": round(float(calibration_slope), 3) if np.isfinite(calibration_slope) else None,
        "calibration_intercept": round(float(calibration_intercept), 3) if np.isfinite(calibration_intercept) else None,
        "gates": gates,
    }


def _attach_stamina_state(
    frame: pd.DataFrame,
    slice5: dict[str, Any],
    current_slice3: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    result = frame.copy()
    numeric_columns = [
        "stamina_plus_trait", "stamina_expected_retention_delta", "stamina_expected_stuff_plus",
        "stamina_early_stuff_baseline", "stamina_reliability",
    ]
    text_columns = ["stamina_sample_label", "stamina_role"]
    for column in numeric_columns:
        result[column] = np.nan
    for column in text_columns:
        result[column] = pd.NA
    if slice5.get("status") != "ready" or not slice5.get("leaderboard"):
        return result, {
            "status": "unavailable",
            "method": "No validated two-season Stamina+ trait was available for per-pitch state caching.",
            "pitch_rows": int(len(result)),
            "trait_rows": 0,
            "expected_rows": 0,
            "trait_coverage_pct": 0.0,
            "expected_coverage_pct": 0.0,
            "warnings": ["Per-pitch state requires a completed Slice 5 model."],
        }

    scores = pd.DataFrame(slice5["leaderboard"])[[
        "pitcher_id", "role", "stamina_plus", "retention_advantage", "reliability", "sample_label",
    ]].rename(columns={
        "pitcher_id": "pitcher",
        "role": "appearance_role",
        "stamina_plus": "stamina_plus_trait",
        "reliability": "stamina_reliability",
        "sample_label": "stamina_sample_label",
    })
    result = result.drop(columns=["stamina_plus_trait", "stamina_reliability", "stamina_sample_label"])
    result = result.merge(scores, on=["pitcher", "appearance_role"], how="left", validate="many_to_one")
    result["stamina_role"] = result["appearance_role"]

    league_slopes = {
        row["role"]: float(row["league_slope"])
        for row in current_slice3.get("priors", [])
        if row.get("outcome") == "pitch_stuff_plus"
    }
    unit_by_role = {"SP": 20.0, "RP": 5.0}
    baseline_end_by_role = {"SP": 20.0, "RP": 5.0}
    league = result["appearance_role"].map(league_slopes).astype("float64")
    unit = result["appearance_role"].map(unit_by_role).astype("float64")
    baseline_end = result["appearance_role"].map(baseline_end_by_role).astype("float64")
    pitch_number = pd.to_numeric(result["appearance_pitch_number"], errors="coerce")
    workload_units = ((pitch_number - baseline_end).clip(lower=0) / unit).fillna(0.0)
    absolute_slope = league + pd.to_numeric(result["retention_advantage"], errors="coerce")
    result["stamina_expected_retention_delta"] = absolute_slope * workload_units

    baseline_mask = pitch_number.le(baseline_end) & result["pitch_stuff_plus"].notna() & result["pitch_type"].notna()
    baseline = (
        result.loc[baseline_mask]
        .groupby(["pitcher", "game_pk", "pitch_type"])["pitch_stuff_plus"]
        .mean()
    )
    baseline_keys = pd.MultiIndex.from_frame(result[["pitcher", "game_pk", "pitch_type"]])
    result["stamina_early_stuff_baseline"] = baseline.reindex(baseline_keys).to_numpy(dtype="float64")
    result["stamina_expected_stuff_plus"] = (
        result["stamina_early_stuff_baseline"] + result["stamina_expected_retention_delta"]
    )
    result = result.drop(columns="retention_advantage")
    trait_rows = int(result["stamina_plus_trait"].notna().sum())
    expected_rows = int(result["stamina_expected_stuff_plus"].notna().sum())
    total = int(len(result))
    return result, {
        "status": "current",
        "method": (
            "Cached pitch state joins the fixed pitcher-role Stamina+ trait to each pitch and applies the current-role "
            "league slope plus the pitcher's two-season retention advantage after the SP 1–20 or RP 1–5 reference window."
        ),
        "pitch_rows": total,
        "trait_rows": trait_rows,
        "expected_rows": expected_rows,
        "trait_coverage_pct": round(trait_rows / total * 100, 1) if total else 0.0,
        "expected_coverage_pct": round(expected_rows / total * 100, 1) if total else 0.0,
        "warnings": [
            "Observed pitch Stuff+ is noisy; its gap from expected Stuff+ is not a causal fatigue estimate.",
            "Expected Stuff+ is unavailable when that pitch type has no early-window baseline in the appearance.",
            "The fixed Stamina+ trait does not change pitch by pitch; only the expected retention path changes with pitch count.",
        ],
    }


def _build_slice7(frame: pd.DataFrame, slice5: dict[str, Any]) -> dict[str, Any]:
    sample = frame[frame["appearance_role"].eq("SP")].copy()
    sample["pitch_family"] = sample["pitch_type"].astype("string").str.upper().map(PITCH_FAMILY_BY_TYPE)
    pitch_number = pd.to_numeric(sample["appearance_pitch_number"], errors="coerce")
    sample["window"] = np.where(pitch_number.le(20), "early", "late")
    mapped = sample[sample["pitch_family"].notna()].copy()
    early_total = int(mapped["window"].eq("early").sum())
    late_total = int(mapped["window"].eq("late").sum())

    family_coverage = []
    for family, pitch_types in PITCH_FAMILY_TYPES.items():
        family_frame = mapped[mapped["pitch_family"].eq(family)]
        early = family_frame[family_frame["window"].eq("early")]
        late = family_frame[family_frame["window"].eq("late")]
        early_share = _pct(len(early), early_total)
        late_share = _pct(len(late), late_total)
        family_coverage.append({
            "family": family,
            "pitch_types": list(pitch_types),
            "pitches": int(len(family_frame)),
            "appearances": int(family_frame[["pitcher", "game_pk"]].drop_duplicates().shape[0]),
            "pitchers": int(family_frame["pitcher"].nunique()),
            "stuff_coverage_pct": _pct(family_frame["pitch_stuff_plus"].notna().sum(), len(family_frame)),
            "velocity_coverage_pct": _pct(family_frame["release_speed"].notna().sum(), len(family_frame)),
            "early_pitches": int(len(early)),
            "late_pitches": int(len(late)),
            "early_usage_pct": early_share,
            "late_usage_pct": late_share,
            "late_usage_delta_pp": round(late_share - early_share, 1),
        })

    raw_types = sample["pitch_type"].astype("string").str.upper()
    unclassified = (
        raw_types[sample["pitch_family"].isna() & raw_types.notna()]
        .value_counts()
        .rename_axis("pitch_type")
        .reset_index(name="pitches")
    )
    unclassified_rows = [
        {"pitch_type": str(row.pitch_type), "pitches": int(row.pitches)}
        for row in unclassified.itertuples(index=False)
    ]
    missing_audit = [
        {
            "key": "unclassified_family",
            "label": "Unclassified pitch family",
            "pitches": int(sample["pitch_family"].isna().sum()),
            "pct": _pct(sample["pitch_family"].isna().sum(), len(sample)),
        },
        {
            "key": "missing_stuff",
            "label": "Missing Stuff+ among classified pitches",
            "pitches": int(mapped["pitch_stuff_plus"].isna().sum()),
            "pct": _pct(mapped["pitch_stuff_plus"].isna().sum(), len(mapped)),
        },
        {
            "key": "missing_velocity",
            "label": "Missing velocity among classified pitches",
            "pitches": int(mapped["release_speed"].isna().sum()),
            "pct": _pct(mapped["release_speed"].isna().sum(), len(mapped)),
        },
    ]

    bias_correlations: list[dict[str, Any]] = []
    ceiling_bands: list[dict[str, Any]] = []
    pitcher_rows = 0
    trait_rows = [row for row in slice5.get("leaderboard", []) if row.get("role") == "SP"]
    if trait_rows and not mapped.empty:
        pitcher = mapped.groupby("pitcher", as_index=False).agg(
            mean_stuff=("pitch_stuff_plus", "mean"),
            mean_velocity=("release_speed", "mean"),
        )
        early = mapped[mapped["window"].eq("early")].groupby("pitcher", as_index=False).agg(
            early_stuff=("pitch_stuff_plus", "mean"),
            early_velocity=("release_speed", "mean"),
        )
        late = mapped[mapped["window"].eq("late")].groupby("pitcher", as_index=False).agg(
            late_stuff=("pitch_stuff_plus", "mean"),
        )
        scores = pd.DataFrame(trait_rows)[["pitcher_id", "stamina_plus"]].rename(columns={"pitcher_id": "pitcher"})
        audit = pitcher.merge(early, on="pitcher", how="inner").merge(late, on="pitcher", how="inner").merge(
            scores, on="pitcher", how="inner", validate="one_to_one"
        )
        audit["naive_late_minus_early"] = audit["late_stuff"] - audit["early_stuff"]
        pitcher_rows = int(len(audit))
        correlation_specs = [
            ("mean_stuff_vs_v1", "Mean Stuff+ vs v1 Stamina+", "mean_stuff", "stamina_plus"),
            ("mean_velocity_vs_v1", "Mean velocity vs v1 Stamina+", "mean_velocity", "stamina_plus"),
            ("early_stuff_vs_v1", "Early Stuff+ vs v1 Stamina+", "early_stuff", "stamina_plus"),
            ("early_velocity_vs_v1", "Early velocity vs v1 Stamina+", "early_velocity", "stamina_plus"),
            ("early_stuff_vs_naive_delta", "Early Stuff+ vs naïve late − early", "early_stuff", "naive_late_minus_early"),
        ]
        for key, label, left, right in correlation_specs:
            valid = audit[[left, right]].dropna()
            correlation = float(valid[left].rank().corr(valid[right].rank())) if len(valid) >= 3 else float("nan")
            bias_correlations.append({
                "key": key,
                "label": label,
                "pitchers": int(len(valid)),
                "spearman": round(correlation, 3) if np.isfinite(correlation) else None,
            })
        if audit["early_stuff"].nunique() >= 4:
            audit["ceiling_band"] = pd.qcut(
                audit["early_stuff"].rank(method="first"),
                4,
                labels=["Q1 lowest", "Q2", "Q3", "Q4 highest"],
            )
            for label, group in audit.groupby("ceiling_band", observed=True):
                ceiling_bands.append({
                    "band": str(label),
                    "pitchers": int(len(group)),
                    "early_stuff": round(float(group["early_stuff"].mean()), 2),
                    "late_stuff": round(float(group["late_stuff"].mean()), 2),
                    "naive_delta": round(float(group["naive_late_minus_early"].mean()), 2),
                    "mean_stamina_plus": round(float(group["stamina_plus"].mean()), 1),
                })

    targets = [
        {
            "key": "family_late_quality",
            "label": "Primary family target",
            "definition": "Late-appearance context-adjusted Stuff+ conditional on observed early quality, estimated within exact pitch type before family aggregation.",
            "purpose": "Avoid using raw late − early as the target, which mechanically couples the estimate to an unusually high or low early baseline.",
        },
        {
            "key": "overall_fixed_repertoire",
            "label": "Overall target",
            "definition": "Combine family estimates with a preregistered prior-season repertoire weight, or first-20-pitch weight when no prior season is available.",
            "purpose": "Prevent late-game pitch selection from rewarding a pitcher for abandoning a declining family.",
        },
        {
            "key": "missingness",
            "label": "Missing-data rule",
            "definition": "Unsupported pitcher-family estimates remain null; no family, pitch, or score is imputed as zero.",
            "purpose": "Keep sparse Offspeed and unclassified-pitch uncertainty visible.",
        },
    ]
    release_gates = [
        {"key": "source_coverage", "scope": "overall", "threshold": "classified Stuff+ coverage ≥ 95%"},
        {"key": "holdout_sample", "scope": "overall", "threshold": "at least 50 common SP in the 2025 → 2026 holdout"},
        {"key": "holdout_skill", "scope": "overall", "threshold": "Spearman ≥ 0.40 and RMSE improvement > 0% versus the train mean"},
        {"key": "calibration", "scope": "overall", "threshold": "holdout calibration slope 0.80–1.20"},
        {"key": "ceiling_neutrality", "scope": "overall", "threshold": "|residual Spearman| ≤ 0.10 versus early Stuff+ and early velocity"},
        {"key": "family_support", "scope": "each family", "threshold": "at least 40 common SP and cross-season Spearman ≥ 0.30"},
        {"key": "family_coverage", "scope": "each family", "threshold": "Stuff+ coverage ≥ 90%; otherwise retain null/unavailable"},
    ]
    classified_pct = _pct(len(mapped), len(sample))
    stuff_pct = _pct(mapped["pitch_stuff_plus"].notna().sum(), len(mapped))
    return {
        "status": "ready" if pitcher_rows >= 3 else "partial",
        "contract_version": "stamina_v2_slice7_preregistered_v1",
        "scope": "Starting-pitcher audit only; v1 scores and Slices 0–6 remain unchanged.",
        "method": "A fixed pitch-family taxonomy audits classified coverage, early/late repertoire selection, v1 ceiling association and regression to the mean before any v2 model is trained.",
        "classified_pitches": int(len(mapped)),
        "classified_coverage_pct": classified_pct,
        "classified_stuff_coverage_pct": stuff_pct,
        "pitchers_with_v1_audit": pitcher_rows,
        "family_coverage": family_coverage,
        "unclassified_pitch_types": unclassified_rows,
        "missing_audit": missing_audit,
        "bias_correlations": bias_correlations,
        "ceiling_bands": ceiling_bands,
        "targets": targets,
        "release_gates": release_gates,
        "warnings": [
            "FO is explicitly classified as Offspeed.",
            "Early/late summaries are descriptive diagnostics, not context-adjusted v2 estimates.",
            "A negative association with v1 Stamina+ may mix regression to the mean, a Stuff+ ceiling, pacing and real retention; Slice 9 must compare preregistered challengers rather than hide it in a black box.",
            "Overlapping trailing MA5 curves belong to Slice 8 display and feature extraction only; they are not independent inference samples.",
        ],
    }


def _context_adjust_stuff(frame: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    sample = frame.dropna(subset=["pitch_stuff_plus", "pitch_type"]).copy()
    if sample.empty:
        sample["context_adjusted_stuff"] = pd.Series(dtype="float64")
        return sample, 0.0
    sample["pitch_type"] = sample["pitch_type"].astype(str).str.upper()
    categories = pd.DataFrame(index=sample.index)
    categories["count"] = sample["balls"].fillna(-1).astype(str) + "-" + sample["strikes"].fillna(-1).astype(str)
    categories["matchup"] = sample["p_throws"].fillna("U").astype(str) + "-" + sample["stand"].fillna("U").astype(str)
    categories["tto"] = pd.to_numeric(sample["n_thruorder_pitcher"], errors="coerce").fillna(0).clip(0, 4).astype(int).astype(str)
    categories["inning"] = pd.cut(
        pd.to_numeric(sample["inning"], errors="coerce"),
        bins=[0, 3, 6, 9, np.inf], labels=["1-3", "4-6", "7-9", "10+"],
    ).astype("object").fillna("unknown")
    categories["park"] = sample["home_team"].fillna("unknown").astype(str)
    design = pd.get_dummies(categories, drop_first=True, dtype="float64")
    dates = pd.to_datetime(sample["game_date"], errors="coerce")
    calendar = (dates - dates.min()).dt.days.astype(float)
    design["calendar"] = calendar.div(max(float(calendar.max()), 1.0)).fillna(0.0)
    for column in design.columns:
        design[column] = design[column] - design[column].groupby(sample["pitch_type"]).transform("mean")
    design = design.loc[:, design.std().gt(1e-10)]
    outcome = pd.to_numeric(sample["pitch_stuff_plus"], errors="coerce")
    pitch_mean = outcome.groupby(sample["pitch_type"]).transform("mean")
    centered = outcome - pitch_mean
    x = design.to_numpy(dtype="float64")
    beta = np.linalg.lstsq(x, centered.to_numpy(dtype="float64"), rcond=None)[0] if x.shape[1] else np.array([])
    context_component = x @ beta if len(beta) else np.zeros(len(sample), dtype="float64")
    sample["context_adjusted_stuff"] = outcome.to_numpy(dtype="float64") - context_component
    denominator = float(np.sum(np.square(centered.to_numpy(dtype="float64"))))
    residual = centered.to_numpy(dtype="float64") - context_component
    r_squared = 1.0 - float(np.sum(np.square(residual))) / denominator if denominator > 0 else 0.0
    return sample, r_squared


def _slice8_selection_weights(frame: pd.DataFrame) -> pd.DataFrame:
    appearance = frame.groupby(["pitcher", "game_pk"], as_index=False).agg(
        pitch_stuff_plus=("pitch_stuff_plus", "mean"),
        location_plus_pitch=("location_plus_pitch", "mean"),
        release_speed=("release_speed", "mean"),
        days_rest=("days_rest", "first"),
        season_pitches_before=("season_pitches_before", "first"),
        appearance_number=("appearance_number", "first"),
        game_date=("game_date", "first"),
        total_pitches=("appearance_pitch_number", "max"),
    ).sort_values(["pitcher", "game_date", "game_pk"], kind="stable")
    appearance["prior_avg_pitches"] = appearance.groupby("pitcher")["total_pitches"].transform(
        lambda values: values.shift(1).expanding().mean()
    )
    appearance["prior_avg_pitches"] = appearance["prior_avg_pitches"].fillna(appearance["total_pitches"].median())
    rows = []
    for order, (low, _, bucket) in enumerate(SP_BUCKETS):
        if order == 0:
            weights = np.ones(len(appearance), dtype="float64")
            reached = np.ones(len(appearance), dtype=bool)
        else:
            model_frame = appearance.copy()
            model_frame["reached"] = model_frame["total_pitches"].ge(low).astype(int)
            probabilities, _ = _cross_fitted_reach_probability(model_frame)
            marginal = float(model_frame["reached"].mean())
            reached = model_frame["reached"].eq(1).to_numpy()
            weights = np.clip(marginal / probabilities, 0.1, 10.0)
            if reached.any():
                cap = float(np.quantile(weights[reached], 0.99))
                weights = np.minimum(weights, cap)
        selected = appearance.loc[reached, ["pitcher", "game_pk"]].copy()
        selected["analysis_bucket"] = bucket
        selected["observation_weight"] = weights[reached]
        rows.append(selected)
    return pd.concat(rows, ignore_index=True)


def _prior_family_weights(year: int, data_dir: Path) -> pd.DataFrame:
    path = stamina_dataset_path(year - 1, data_dir)
    if not path.exists():
        return pd.DataFrame(columns=["pitcher", "pitch_family", "fixed_weight"])
    with duckdb.connect() as connection:
        prior = connection.execute(
            "SELECT pitcher, upper(pitch_type) AS pitch_type FROM read_parquet(?) "
            "WHERE appearance_role = 'SP' AND pitch_type IS NOT NULL",
            [str(path)],
        ).fetchdf()
    prior["pitch_family"] = prior["pitch_type"].map(PITCH_FAMILY_BY_TYPE)
    counts = prior.dropna(subset=["pitch_family"]).groupby(["pitcher", "pitch_family"], as_index=False).size()
    counts["fixed_weight"] = counts["size"] / counts.groupby("pitcher")["size"].transform("sum")
    return counts[["pitcher", "pitch_family", "fixed_weight"]]


def _weighted_curve_mean(group: pd.DataFrame, column: str) -> float | None:
    values = pd.to_numeric(group[column], errors="coerce")
    weights = pd.to_numeric(group["curve_weight"], errors="coerce")
    valid = values.notna() & weights.notna() & weights.gt(0)
    return float(np.average(values[valid], weights=weights[valid])) if valid.any() else None


def _build_slice8(
    frame: pd.DataFrame,
    year: int,
    data_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    starters = frame[frame["appearance_role"].eq("SP") & frame["pitch_family"].notna()].copy()
    pitch_curves, context_r_squared = _context_adjust_stuff(starters)
    pitch_curves = pitch_curves.sort_values(
        ["pitcher", "game_date", "game_pk", "appearance_pitch_number"], kind="stable"
    ).copy()
    pitch_curves["analysis_bucket"] = _assign_bucket(pitch_curves["appearance_pitch_number"], SP_BUCKETS)
    pitch_curves["family_pitch_number"] = pitch_curves.groupby(
        ["pitcher", "game_pk", "pitch_family"]
    ).cumcount() + 1
    pitch_curves["trailing_ma5"] = (
        pitch_curves.groupby(["pitcher", "game_pk", "pitch_family"], sort=False)["context_adjusted_stuff"]
        .rolling(5, min_periods=5).mean().reset_index(level=[0, 1, 2], drop=True)
    )
    baseline = (
        pitch_curves[pd.to_numeric(pitch_curves["appearance_pitch_number"], errors="coerce").le(20)]
        .groupby(["pitcher", "game_pk", "pitch_type"])["context_adjusted_stuff"].mean()
    )
    velocity_baseline = (
        pitch_curves[pd.to_numeric(pitch_curves["appearance_pitch_number"], errors="coerce").le(20)]
        .groupby(["pitcher", "game_pk", "pitch_type"])["release_speed"].mean()
    )
    baseline_keys = pd.MultiIndex.from_frame(pitch_curves[["pitcher", "game_pk", "pitch_type"]])
    pitch_curves["early_pitch_type_baseline"] = baseline.reindex(baseline_keys).to_numpy(dtype="float64")
    pitch_curves["early_pitch_type_velocity"] = velocity_baseline.reindex(baseline_keys).to_numpy(dtype="float64")
    selection_weights = _slice8_selection_weights(starters)
    pitch_curves = pitch_curves.merge(
        selection_weights, on=["pitcher", "game_pk", "analysis_bucket"], how="left", validate="many_to_one"
    )
    pitch_curves["observation_weight"] = pitch_curves["observation_weight"].fillna(1.0)

    family_curves = pitch_curves.groupby(
        ["pitcher", "game_pk", "game_date", "pitch_family", "analysis_bucket"], as_index=False
    ).agg(
        pitches=("pitcher", "size"),
        raw_stuff=("pitch_stuff_plus", "mean"),
        adjusted_stuff=("context_adjusted_stuff", "mean"),
        trailing_ma5=("trailing_ma5", "mean"),
        observation_weight=("observation_weight", "first"),
    )
    bucket_order = {bucket: order for order, (_, _, bucket) in enumerate(SP_BUCKETS)}
    family_curves["order"] = family_curves["analysis_bucket"].map(bucket_order).astype(int)
    prior_weights = _prior_family_weights(year, data_dir)
    prior_lookup = {
        int(pitcher): dict(zip(group["pitch_family"], group["fixed_weight"]))
        for pitcher, group in prior_weights.groupby("pitcher")
    }
    early_counts = (
        pitch_curves[pd.to_numeric(pitch_curves["appearance_pitch_number"], errors="coerce").le(20)]
        .groupby(["pitcher", "game_pk", "pitch_family"], as_index=False).size()
    )
    early_counts["fixed_weight"] = early_counts["size"] / early_counts.groupby(["pitcher", "game_pk"])["size"].transform("sum")
    early_lookup = {
        (int(pitcher), int(game_pk)): dict(zip(group["pitch_family"], group["fixed_weight"]))
        for (pitcher, game_pk), group in early_counts.groupby(["pitcher", "game_pk"])
    }
    family_curves["fixed_weight"] = np.nan
    family_curves["weight_source"] = pd.NA
    overall_rows: list[dict[str, Any]] = []
    for (pitcher, game_pk), group in family_curves.groupby(["pitcher", "game_pk"], sort=False):
        weights = prior_lookup.get(int(pitcher))
        source = "prior_season" if weights else "appearance_first_20"
        weights = weights or early_lookup.get((int(pitcher), int(game_pk)), {})
        mask = (family_curves["pitcher"].eq(pitcher) & family_curves["game_pk"].eq(game_pk))
        family_curves.loc[mask, "fixed_weight"] = family_curves.loc[mask, "pitch_family"].map(weights)
        family_curves.loc[mask, "weight_source"] = source
        carried: dict[str, dict[str, float | None]] = {}
        for order, bucket in enumerate([item[2] for item in SP_BUCKETS]):
            bucket_rows = group[group["analysis_bucket"].eq(bucket)]
            if bucket_rows.empty:
                continue
            for row in bucket_rows.itertuples(index=False):
                carried[str(row.pitch_family)] = {
                    "adjusted_stuff": float(row.adjusted_stuff),
                    "raw_stuff": float(row.raw_stuff),
                    "trailing_ma5": float(row.trailing_ma5) if pd.notna(row.trailing_ma5) else None,
                }
            required = {family: weight for family, weight in weights.items() if float(weight) > 0}
            available = bool(required) and all(family in carried for family in required)
            adjusted = sum(float(weight) * float(carried[family]["adjusted_stuff"]) for family, weight in required.items()) if available else None
            raw = sum(float(weight) * float(carried[family]["raw_stuff"]) for family, weight in required.items()) if available else None
            ma5_available = available and all(carried[family]["trailing_ma5"] is not None for family in required)
            ma5 = sum(float(weight) * float(carried[family]["trailing_ma5"]) for family, weight in required.items()) if ma5_available else None
            overall_rows.append({
                "pitcher": int(pitcher), "game_pk": int(game_pk),
                "game_date": group["game_date"].iloc[0], "pitch_family": "Overall",
                "analysis_bucket": bucket, "order": order,
                "pitches": int(bucket_rows["pitches"].sum()),
                "raw_stuff": raw, "adjusted_stuff": adjusted, "trailing_ma5": ma5,
                "observation_weight": float(bucket_rows["observation_weight"].mean()) if len(bucket_rows) else 1.0,
                "fixed_weight": 1.0, "weight_source": source,
            })
    overall = pd.DataFrame(overall_rows)
    appearance_curves = pd.concat([family_curves, overall], ignore_index=True, sort=False)
    appearance_curves["curve_weight"] = appearance_curves["pitches"].clip(lower=1) * appearance_curves["observation_weight"].clip(lower=0.1)

    family_audit = []
    for family in PITCH_FAMILY_TYPES:
        family_frame = pitch_curves[pitch_curves["pitch_family"].eq(family)]
        ma5_rows = int(family_frame["trailing_ma5"].notna().sum())
        family_audit.append({
            "family": family, "pitches": int(len(family_frame)),
            "appearances": int(family_frame[["pitcher", "game_pk"]].drop_duplicates().shape[0]),
            "pitchers": int(family_frame["pitcher"].nunique()), "ma5_rows": ma5_rows,
            "ma5_coverage_pct": _pct(ma5_rows, len(family_frame)),
        })
    league_curves = []
    for (family, bucket), group in appearance_curves.groupby(["pitch_family", "analysis_bucket"], sort=False):
        adjusted = _weighted_curve_mean(group, "adjusted_stuff")
        raw = _weighted_curve_mean(group, "raw_stuff")
        ma5 = _weighted_curve_mean(group, "trailing_ma5")
        league_curves.append({
            "family": str(family), "bucket": str(bucket), "order": int(bucket_order[str(bucket)]),
            "pitches": int(group["pitches"].sum()),
            "appearances": int(group[["pitcher", "game_pk"]].drop_duplicates().shape[0]),
            "pitchers": int(group["pitcher"].nunique()),
            "adjusted_stuff": round(adjusted, 3) if adjusted is not None else None,
            "raw_stuff": round(raw, 3) if raw is not None else None,
            "trailing_ma5": round(ma5, 3) if ma5 is not None else None,
            "fixed_weight_coverage_pct": _pct(group["adjusted_stuff"].notna().sum(), len(group)) if family == "Overall" else None,
        })
    pitch_columns = [
        "pitcher", "game_pk", "game_date", "pitch_type", "pitch_family", "appearance_pitch_number",
        "family_pitch_number", "analysis_bucket", "pitch_stuff_plus", "release_speed", "context_adjusted_stuff",
        "trailing_ma5", "early_pitch_type_baseline", "early_pitch_type_velocity", "observation_weight",
        "balls", "strikes", "p_throws", "stand", "n_thruorder_pitcher", "inning", "home_team",
    ]
    pitch_curves = pitch_curves[pitch_columns].reset_index(drop=True)
    return pitch_curves, appearance_curves.reset_index(drop=True), {
        "status": "ready" if len(pitch_curves) else "insufficient",
        "contract_version": "stamina_v2_slice8_curves_v1",
        "method": "SP pitch-level Stuff+ is adjusted within exact pitch type for count, matchup, TTO, inning, park and calendar context; family MA5 and 20-pitch appearance curves are then built with Slice 2-style direct observation weights.",
        "context_controls": ["exact pitch type", "count", "pitcher/batter handedness", "TTO", "inning", "park", "calendar trend"],
        "context_r_squared": round(float(context_r_squared), 4),
        "pitch_curve_rows": int(len(pitch_curves)),
        "appearance_curve_rows": int(len(appearance_curves)),
        "overall_curve_rows": int(len(overall)),
        "prior_weight_pitchers": int(len(prior_lookup)),
        "early_weight_appearances": int(len(early_lookup)),
        "family_audit": family_audit,
        "league_curves": sorted(league_curves, key=lambda row: (["Overall", "Fastball", "Breaking", "Offspeed"].index(row["family"]), row["order"])),
        "warnings": [
            "Trailing MA5 is a display and feature-extraction smoother; overlapping windows are never counted as independent inference samples.",
            "Overall curves use prior-season repertoire weights when available and first-20-pitch weights otherwise; a missing required family stays unavailable until observed and is never renormalized away.",
            "Curves are retention associations after observed-context adjustment, not causal fatigue estimates or next-start forecasts.",
        ],
    }


def _model_metrics(
    name: str,
    kind: str,
    train: pd.DataFrame,
    test: pd.DataFrame,
    observed: np.ndarray,
    predicted: np.ndarray,
    baseline_rmse: float,
) -> dict[str, Any]:
    weights = test["observation_weight"].to_numpy(dtype="float64")
    weights = weights / weights.sum()
    errors = observed - predicted
    rmse = float(np.sqrt(np.sum(weights * np.square(errors))))
    mae = float(np.sum(weights * np.abs(errors)))
    correlation = float(pd.Series(observed).corr(pd.Series(predicted))) if np.std(predicted) > 0 else float("nan")
    improvement = (baseline_rmse - rmse) / baseline_rmse * 100.0 if baseline_rmse else 0.0
    return {
        "model": name, "kind": kind, "train_pitches": int(len(train)), "test_pitches": int(len(test)),
        "train_appearances": int(train[["pitcher", "game_pk"]].drop_duplicates().shape[0]),
        "test_appearances": int(test[["pitcher", "game_pk"]].drop_duplicates().shape[0]),
        "rmse": round(rmse, 3), "mae": round(mae, 3),
        "correlation": round(correlation, 3) if np.isfinite(correlation) else None,
        "rmse_improvement_pct": round(improvement, 2), "status": "improves" if improvement > 0 else "no_gain",
    }


def _slice9_design(frame: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    workload = ((pd.to_numeric(frame["appearance_pitch_number"], errors="coerce") - 20.0) / 20.0).clip(lower=0)
    early = pd.to_numeric(frame["early_pitch_type_baseline"], errors="coerce")
    family = pd.get_dummies(frame["pitch_family"], prefix="family", dtype="float64")
    columns = [np.ones(len(frame)), early.to_numpy(dtype="float64"), workload.to_numpy(dtype="float64")]
    names = ["intercept", "early_stuff", "workload"]
    for name in ["family_Breaking", "family_Offspeed"]:
        value = family[name].to_numpy(dtype="float64") if name in family else np.zeros(len(frame))
        columns.extend([value, value * workload.to_numpy(dtype="float64")])
        names.extend([name, f"{name}:workload"])
    return np.column_stack(columns), names


def _hierarchical_family_slopes(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    working = frame.copy()
    working["workload_units"] = ((working["appearance_pitch_number"] - 20.0) / 20.0).clip(lower=0)
    working["delta"] = working["context_adjusted_stuff"] - working["early_pitch_type_baseline"]
    candidates = working.groupby(["pitcher", "pitch_family"])
    raw_rows = []
    candidate_counts = working.groupby("pitch_family")["pitcher"].nunique().to_dict()
    for (pitcher, family), group in candidates:
        appearances = int(group["game_pk"].nunique())
        if len(group) < 50 or appearances < 5 or group["workload_units"].nunique() < 2:
            continue
        x = group["workload_units"].to_numpy(dtype="float64")
        y = group["delta"].to_numpy(dtype="float64")
        weights = group["observation_weight"].to_numpy(dtype="float64")
        denominator = float(np.sum(weights * np.square(x)))
        if denominator <= 0:
            continue
        slope = float(np.sum(weights * x * y) / denominator)
        residual = y - slope * x
        cluster_score = pd.Series(weights * x * residual).groupby(group["game_pk"].to_numpy()).sum().to_numpy()
        variance = max(float(np.sum(np.square(cluster_score)) / denominator**2), 1e-6)
        raw_rows.append({
            "pitcher": int(pitcher), "pitch_family": str(family), "raw_slope": slope,
            "variance": variance, "standard_error": float(np.sqrt(variance)),
            "pitches": int(len(group)), "appearances": appearances,
        })
    raw = pd.DataFrame(raw_rows)
    if raw.empty:
        return pd.DataFrame(columns=["pitcher", "pitch_family", "raw_slope", "posterior_slope", "reliability", "standard_error", "pitches", "appearances"]), []
    estimates = []
    priors = []
    for family, group in raw.groupby("pitch_family"):
        league, tau_squared = _random_effects_prior(
            group["raw_slope"].to_numpy(dtype="float64"), group["variance"].to_numpy(dtype="float64")
        )
        for row in group.itertuples(index=False):
            reliability = tau_squared / (tau_squared + float(row.variance)) if tau_squared > 0 else 0.0
            estimates.append({
                "pitcher": int(row.pitcher), "pitch_family": str(family),
                "raw_slope": float(row.raw_slope),
                "posterior_slope": float(league + reliability * (float(row.raw_slope) - league)),
                "reliability": float(reliability), "standard_error": float(row.standard_error),
                "pitches": int(row.pitches), "appearances": int(row.appearances),
            })
        reliability_values = [row["reliability"] for row in estimates if row["pitch_family"] == family]
        priors.append({
            "family": str(family), "candidate_pitchers": int(candidate_counts.get(family, 0)),
            "eligible_pitchers": int(len(group)), "league_slope": round(float(league), 3),
            "between_pitcher_sd": round(float(np.sqrt(tau_squared)), 3),
            "median_reliability": round(float(np.median(reliability_values)), 3),
        })
    return pd.DataFrame(estimates), priors


def _build_slice9(pitch_curves: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.inspection import permutation_importance
    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import SplineTransformer

    model_frame = pitch_curves[
        pd.to_numeric(pitch_curves["appearance_pitch_number"], errors="coerce").gt(20)
        & pitch_curves["early_pitch_type_baseline"].notna()
    ].dropna(subset=["context_adjusted_stuff", "game_date"]).copy()
    hierarchical, family_priors = _hierarchical_family_slopes(model_frame)
    dates = np.sort(pd.to_datetime(model_frame["game_date"]).dt.normalize().unique())
    if len(model_frame) < 500 or len(dates) < 3:
        return hierarchical, {
            "status": "insufficient", "contract_version": "stamina_v2_slice9_challengers_v1",
            "method": "Insufficient late-pitch rows for chronological challenger comparison.",
            "development_split_date": None, "selection_weighting": "Slice 2-style direct observation weights",
            "hierarchical_estimate_rows": int(len(hierarchical)), "comparisons": [],
            "family_priors": family_priors, "challenger_influence": [],
            "warnings": ["Slice 10 holdout scoring remains blocked until complete 2025→2026 validation."],
        }
    split_date = pd.Timestamp(dates[max(1, int(len(dates) * 0.70) - 1)])
    train = model_frame[pd.to_datetime(model_frame["game_date"]).dt.normalize().le(split_date)].copy()
    test = model_frame[pd.to_datetime(model_frame["game_date"]).dt.normalize().gt(split_date)].copy()
    train_y = train["context_adjusted_stuff"].to_numpy(dtype="float64")
    test_y = test["context_adjusted_stuff"].to_numpy(dtype="float64")
    test_weights = test["observation_weight"].to_numpy(dtype="float64")
    test_weights = test_weights / test_weights.sum()
    baseline_prediction = test["early_pitch_type_baseline"].to_numpy(dtype="float64")
    baseline_rmse = float(np.sqrt(np.sum(test_weights * np.square(test_y - baseline_prediction))))
    comparisons = [_model_metrics(
        "Early-quality baseline", "baseline", train, test, test_y, baseline_prediction, baseline_rmse
    )]

    train_x, feature_names = _slice9_design(train)
    test_x, _ = _slice9_design(test)
    train_weights = train["observation_weight"].to_numpy(dtype="float64")
    root_weight = np.sqrt(train_weights)
    ancova_beta = np.linalg.lstsq(train_x * root_weight[:, None], train_y * root_weight, rcond=None)[0]
    ancova_prediction = test_x @ ancova_beta
    comparisons.append(_model_metrics(
        "Linear ANCOVA", "primary", train, test, test_y, ancova_prediction, baseline_rmse
    ))

    train_workload = ((train["appearance_pitch_number"] - 20.0) / 20.0).clip(lower=0).to_numpy().reshape(-1, 1)
    test_workload = ((test["appearance_pitch_number"] - 20.0) / 20.0).clip(lower=0).to_numpy().reshape(-1, 1)
    spline = SplineTransformer(n_knots=5, degree=3, include_bias=False)
    train_spline = spline.fit_transform(train_workload)
    test_spline = spline.transform(test_workload)
    train_family = pd.get_dummies(train["pitch_family"], dtype="float64").reindex(columns=list(PITCH_FAMILY_TYPES), fill_value=0)
    test_family = pd.get_dummies(test["pitch_family"], dtype="float64").reindex(columns=list(PITCH_FAMILY_TYPES), fill_value=0)
    gamm_train_x = np.column_stack([train["early_pitch_type_baseline"], train_spline, train_family])
    gamm_test_x = np.column_stack([test["early_pitch_type_baseline"], test_spline, test_family])
    gamm = Ridge(alpha=10.0)
    gamm.fit(gamm_train_x, train_y, sample_weight=train_weights)
    train_gamm = gamm.predict(gamm_train_x)
    pitcher_offset = pd.DataFrame({
        "pitcher": train["pitcher"].to_numpy(), "residual": train_y - train_gamm,
    }).groupby("pitcher")["residual"].agg(["mean", "size"])
    pitcher_offset["offset"] = pitcher_offset["mean"] * pitcher_offset["size"] / (pitcher_offset["size"] + 50.0)
    gamm_prediction = gamm.predict(gamm_test_x) + test["pitcher"].map(pitcher_offset["offset"]).fillna(0.0).to_numpy()
    comparisons.append(_model_metrics(
        "Spline mixed-effects approximation", "gamm", train, test, test_y, gamm_prediction, baseline_rmse
    ))

    ml_columns = [name for name in feature_names if name != "intercept"]
    ml_train_x = pd.DataFrame(train_x[:, 1:], columns=ml_columns, index=train.index)
    ml_test_x = pd.DataFrame(test_x[:, 1:], columns=ml_columns, index=test.index)
    pitch_dummies = pd.get_dummies(model_frame["pitch_type"], prefix="pitch", dtype="float64")
    ml_train_x = ml_train_x.join(pitch_dummies.loc[train.index])
    ml_test_x = ml_test_x.join(pitch_dummies.loc[test.index]).reindex(columns=ml_train_x.columns, fill_value=0)
    challenger = HistGradientBoostingRegressor(
        max_iter=100, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=50,
        l2_regularization=5.0, random_state=42,
    )
    challenger.fit(ml_train_x, train_y, sample_weight=train_weights)
    challenger_prediction = challenger.predict(ml_test_x)
    comparisons.append(_model_metrics(
        "Explainable boosted tree", "ml_challenger", train, test, test_y, challenger_prediction, baseline_rmse
    ))
    importance_sample = ml_test_x.sample(min(20_000, len(ml_test_x)), random_state=42)
    importance_y = test.loc[importance_sample.index, "context_adjusted_stuff"]
    importance = permutation_importance(
        challenger, importance_sample, importance_y, n_repeats=3, random_state=42,
        scoring="neg_root_mean_squared_error",
    )
    influence = sorted(
        [
            {"feature": str(feature), "importance": max(float(value), 0.0)}
            for feature, value in zip(importance_sample.columns, importance.importances_mean)
        ],
        key=lambda row: row["importance"], reverse=True,
    )[:8]
    maximum = max((row["importance"] for row in influence), default=0.0)
    for row in influence:
        row["importance"] = round(row["importance"], 4)
        row["relative_strength_pct"] = round(row["importance"] / maximum * 100.0, 1) if maximum else 0.0
    return hierarchical, {
        "status": "ready", "contract_version": "stamina_v2_slice9_challengers_v1",
        "method": "Chronological 70/30 development comparison of weighted raw-pitch ANCOVA, a spline model with empirical-Bayes pitcher intercepts, hierarchical pitcher-family slopes and a shallow boosted-tree challenger.",
        "development_split_date": split_date.date().isoformat(),
        "selection_weighting": "Cross-fitted direct appearance-bucket observation weights inherited from the Slice 2 design",
        "hierarchical_estimate_rows": int(len(hierarchical)), "comparisons": comparisons,
        "family_priors": family_priors, "challenger_influence": influence,
        "warnings": [
            "This is a same-season development split, not the Slice 10 2025→2026 publication holdout.",
            "Formal inference uses raw pitch rows and appearance-level selection weights; overlapping MA5 values are excluded from every model fit.",
            "The boosted tree is a challenger only. Feature influence is predictive permutation importance, not a causal fatigue contribution.",
            "No family or Overall v2 score is published in Slice 9.",
        ],
    }


def _rank_correlation(left: pd.Series, right: pd.Series) -> float | None:
    valid = pd.concat([left, right], axis=1).dropna()
    if len(valid) < 3 or valid.iloc[:, 0].nunique() < 2 or valid.iloc[:, 1].nunique() < 2:
        return None
    value = float(valid.iloc[:, 0].rank().corr(valid.iloc[:, 1].rank()))
    return value if np.isfinite(value) else None


def _slice10_model_metrics(
    name: str,
    kind: str,
    train_rows: int,
    observed: np.ndarray,
    predicted: np.ndarray,
    baseline_rmse: float,
    early_stuff: pd.Series,
    early_velocity: pd.Series,
) -> dict[str, Any]:
    residual = pd.Series(observed - predicted)
    rmse = float(np.sqrt(np.mean(np.square(residual))))
    correlation = float(pd.Series(observed).corr(pd.Series(predicted))) if np.std(predicted) > 0 else float("nan")
    if np.std(predicted) > 0:
        calibration_slope, calibration_intercept = np.polyfit(predicted, observed, 1)
    else:
        calibration_slope, calibration_intercept = float("nan"), float("nan")
    early_stuff_corr = _rank_correlation(residual, early_stuff.reset_index(drop=True))
    early_velocity_corr = _rank_correlation(residual, early_velocity.reset_index(drop=True))
    improvement = (baseline_rmse - rmse) / baseline_rmse * 100.0 if baseline_rmse else 0.0
    gates = {
        "rmse": improvement > 0,
        "calibration": np.isfinite(calibration_slope) and 0.80 <= float(calibration_slope) <= 1.20,
        "early_stuff_neutral": early_stuff_corr is not None and abs(early_stuff_corr) <= 0.10,
        "early_velocity_neutral": early_velocity_corr is not None and abs(early_velocity_corr) <= 0.10,
    }
    return {
        "model": name, "kind": kind, "train_pitches": int(train_rows), "test_pitches": int(len(observed)),
        "rmse": round(rmse, 3), "baseline_rmse": round(baseline_rmse, 3),
        "rmse_improvement_pct": round(improvement, 2),
        "correlation": round(correlation, 3) if np.isfinite(correlation) else None,
        "calibration_slope": round(float(calibration_slope), 3) if np.isfinite(calibration_slope) else None,
        "calibration_intercept": round(float(calibration_intercept), 3) if np.isfinite(calibration_intercept) else None,
        "residual_early_stuff_spearman": round(float(early_stuff_corr), 3) if early_stuff_corr is not None else None,
        "residual_early_velocity_spearman": round(float(early_velocity_corr), 3) if early_velocity_corr is not None else None,
        "gates": gates, "status": "validated" if all(gates.values()) else "research_only",
    }


def _slice10_context_design(
    frame: pd.DataFrame,
    columns: list[str] | None = None,
    calendar_origin: pd.Timestamp | None = None,
    calendar_scale: float | None = None,
) -> tuple[pd.DataFrame, pd.Timestamp, float]:
    categories = pd.DataFrame(index=frame.index)
    categories["count"] = frame["balls"].fillna(-1).astype(str) + "-" + frame["strikes"].fillna(-1).astype(str)
    categories["matchup"] = frame["p_throws"].fillna("U").astype(str) + "-" + frame["stand"].fillna("U").astype(str)
    categories["tto"] = pd.to_numeric(frame["n_thruorder_pitcher"], errors="coerce").fillna(0).clip(0, 4).astype(int).astype(str)
    categories["inning"] = pd.cut(
        pd.to_numeric(frame["inning"], errors="coerce"),
        bins=[0, 3, 6, 9, np.inf], labels=["1-3", "4-6", "7-9", "10+"],
    ).astype("object").fillna("unknown")
    categories["park"] = frame["home_team"].fillna("unknown").astype(str)
    design = pd.get_dummies(categories, drop_first=True, dtype="float64")
    dates = pd.to_datetime(frame["game_date"], errors="coerce")
    origin = calendar_origin if calendar_origin is not None else dates.min()
    day = (dates - origin).dt.days.astype(float)
    scale = float(calendar_scale) if calendar_scale is not None else max(float(day.max()), 1.0)
    design["calendar"] = day.div(scale).fillna(0.0)
    if columns is not None:
        design = design.reindex(columns=columns, fill_value=0.0)
    return design, pd.Timestamp(origin), scale


def _cross_season_context_adjust(
    train: pd.DataFrame,
    test: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    train = train.copy().reset_index(drop=True)
    test = test.copy().reset_index(drop=True)
    train["pitch_type"] = train["pitch_type"].astype(str).str.upper()
    test["pitch_type"] = test["pitch_type"].astype(str).str.upper()
    supported_types = set(train["pitch_type"].dropna().unique())
    test = test[test["pitch_type"].isin(supported_types)].reset_index(drop=True)
    train_design, origin, scale = _slice10_context_design(train)
    train_columns = train_design.columns.tolist()
    test_design, _, _ = _slice10_context_design(test, train_columns, origin, scale)
    design_means = train_design.groupby(train["pitch_type"]).mean()
    train_centered_design = train_design - design_means.reindex(train["pitch_type"]).set_axis(train.index)
    test_centered_design = test_design - design_means.reindex(test["pitch_type"]).set_axis(test.index)
    train_centered_design = train_centered_design.fillna(0.0)
    test_centered_design = test_centered_design.fillna(0.0)
    pitch_means = train.groupby("pitch_type")["pitch_stuff_plus"].mean()
    train_y = train["pitch_stuff_plus"].to_numpy(dtype="float64")
    train_centered_y = train_y - train["pitch_type"].map(pitch_means).to_numpy(dtype="float64")
    x_train = train_centered_design.to_numpy(dtype="float64")
    beta = np.linalg.lstsq(x_train, train_centered_y, rcond=None)[0] if x_train.shape[1] else np.array([])
    train["context_adjusted_stuff"] = train_y - (x_train @ beta if len(beta) else 0.0)
    x_test = test_centered_design.to_numpy(dtype="float64")
    test["context_adjusted_stuff"] = test["pitch_stuff_plus"].to_numpy(dtype="float64") - (
        x_test @ beta if len(beta) else 0.0
    )
    for result in [train, test]:
        early = result[pd.to_numeric(result["appearance_pitch_number"], errors="coerce").le(20)]
        stuff_baseline = early.groupby(["pitcher", "game_pk", "pitch_type"])["context_adjusted_stuff"].mean()
        velocity_baseline = early.groupby(["pitcher", "game_pk", "pitch_type"])["release_speed"].mean()
        keys = pd.MultiIndex.from_frame(result[["pitcher", "game_pk", "pitch_type"]])
        result["early_pitch_type_baseline"] = stuff_baseline.reindex(keys).to_numpy(dtype="float64")
        result["early_pitch_type_velocity"] = velocity_baseline.reindex(keys).to_numpy(dtype="float64")
    return train, test


def _slice10_model_holdout(train: pd.DataFrame, test: pd.DataFrame) -> tuple[list[dict[str, Any]], str | None]:
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import SplineTransformer

    train = train[
        pd.to_numeric(train["appearance_pitch_number"], errors="coerce").gt(20)
        & train["early_pitch_type_baseline"].notna()
    ].dropna(subset=["context_adjusted_stuff"]).copy()
    test = test[
        pd.to_numeric(test["appearance_pitch_number"], errors="coerce").gt(20)
        & test["early_pitch_type_baseline"].notna()
    ].dropna(subset=["context_adjusted_stuff"]).copy()
    train_y = train["context_adjusted_stuff"].to_numpy(dtype="float64")
    test_y = test["context_adjusted_stuff"].to_numpy(dtype="float64")
    baseline_prediction = test["early_pitch_type_baseline"].to_numpy(dtype="float64")
    baseline_rmse = float(np.sqrt(np.mean(np.square(test_y - baseline_prediction))))
    early_stuff = test["early_pitch_type_baseline"]
    early_velocity = test["early_pitch_type_velocity"]
    validations = []

    train_x, feature_names = _slice9_design(train)
    test_x, _ = _slice9_design(test)
    train_weights = train["observation_weight"].to_numpy(dtype="float64")
    root_weight = np.sqrt(train_weights)
    beta = np.linalg.lstsq(train_x * root_weight[:, None], train_y * root_weight, rcond=None)[0]
    validations.append(_slice10_model_metrics(
        "Linear ANCOVA", "primary", len(train), test_y, test_x @ beta, baseline_rmse, early_stuff, early_velocity
    ))

    train_workload = ((train["appearance_pitch_number"] - 20.0) / 20.0).clip(lower=0).to_numpy().reshape(-1, 1)
    test_workload = ((test["appearance_pitch_number"] - 20.0) / 20.0).clip(lower=0).to_numpy().reshape(-1, 1)
    spline = SplineTransformer(n_knots=5, degree=3, include_bias=False)
    train_spline = spline.fit_transform(train_workload)
    test_spline = spline.transform(test_workload)
    train_family = pd.get_dummies(train["pitch_family"], dtype="float64").reindex(columns=list(PITCH_FAMILY_TYPES), fill_value=0)
    test_family = pd.get_dummies(test["pitch_family"], dtype="float64").reindex(columns=list(PITCH_FAMILY_TYPES), fill_value=0)
    spline_train_x = np.column_stack([train["early_pitch_type_baseline"], train_spline, train_family])
    spline_test_x = np.column_stack([test["early_pitch_type_baseline"], test_spline, test_family])
    spline_model = Ridge(alpha=10.0)
    spline_model.fit(spline_train_x, train_y, sample_weight=train_weights)
    train_prediction = spline_model.predict(spline_train_x)
    pitcher_offset = pd.DataFrame({
        "pitcher": train["pitcher"].to_numpy(), "residual": train_y - train_prediction,
    }).groupby("pitcher")["residual"].agg(["mean", "size"])
    pitcher_offset["offset"] = pitcher_offset["mean"] * pitcher_offset["size"] / (pitcher_offset["size"] + 50.0)
    spline_prediction = spline_model.predict(spline_test_x) + test["pitcher"].map(pitcher_offset["offset"]).fillna(0.0).to_numpy()
    validations.append(_slice10_model_metrics(
        "Spline mixed-effects approximation", "gamm", len(train), test_y, spline_prediction,
        baseline_rmse, early_stuff, early_velocity,
    ))

    ml_columns = [name for name in feature_names if name != "intercept"]
    ml_train_x = pd.DataFrame(train_x[:, 1:], columns=ml_columns, index=train.index)
    ml_test_x = pd.DataFrame(test_x[:, 1:], columns=ml_columns, index=test.index)
    train_pitch = pd.get_dummies(train["pitch_type"], prefix="pitch", dtype="float64")
    test_pitch = pd.get_dummies(test["pitch_type"], prefix="pitch", dtype="float64")
    pitch_columns = sorted(set(train_pitch.columns) | set(test_pitch.columns))
    ml_train_x = ml_train_x.join(train_pitch.reindex(columns=pitch_columns, fill_value=0))
    ml_test_x = ml_test_x.join(test_pitch.reindex(columns=pitch_columns, fill_value=0)).reindex(columns=ml_train_x.columns, fill_value=0)
    challenger = HistGradientBoostingRegressor(
        max_iter=100, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=50,
        l2_regularization=5.0, random_state=42,
    )
    challenger.fit(ml_train_x, train_y, sample_weight=train_weights)
    validations.append(_slice10_model_metrics(
        "Explainable boosted tree", "ml_challenger", len(train), test_y,
        challenger.predict(ml_test_x), baseline_rmse, early_stuff, early_velocity,
    ))

    passing = [row for row in validations if all(row["gates"].values())]
    selected = None
    if passing:
        best = max(row["rmse_improvement_pct"] for row in passing)
        for kind in ["primary", "gamm", "ml_challenger"]:
            candidate = next((row for row in passing if row["kind"] == kind), None)
            if candidate and candidate["rmse_improvement_pct"] >= best - 0.25:
                selected = candidate["model"]
                break
    return validations, selected


def _early_pitcher_metrics(pitch_curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    early = pitch_curves[pd.to_numeric(pitch_curves["appearance_pitch_number"], errors="coerce").le(20)]
    family = early.groupby(["pitcher", "pitch_family"], as_index=False).agg(
        early_stuff=("context_adjusted_stuff", "mean"), early_velocity=("release_speed", "mean")
    )
    overall = early.groupby("pitcher", as_index=False).agg(
        early_stuff=("context_adjusted_stuff", "mean"), early_velocity=("release_speed", "mean")
    )
    return family, overall


def _overall_slope_pairs(
    train_curves: pd.DataFrame,
    train_hierarchical: pd.DataFrame,
    test_hierarchical: pd.DataFrame,
) -> pd.DataFrame:
    counts = train_curves.groupby(["pitcher", "pitch_family"], as_index=False).size()
    counts["fixed_weight"] = counts["size"] / counts.groupby("pitcher")["size"].transform("sum")
    train_lookup = train_hierarchical.set_index(["pitcher", "pitch_family"])["posterior_slope"]
    test_lookup = test_hierarchical.set_index(["pitcher", "pitch_family"])["posterior_slope"]
    rows = []
    for pitcher, group in counts.groupby("pitcher"):
        keys = [(int(pitcher), str(family)) for family in group["pitch_family"]]
        if not all(key in train_lookup.index and key in test_lookup.index for key in keys):
            continue
        weights = group["fixed_weight"].to_numpy(dtype="float64")
        rows.append({
            "pitcher": int(pitcher),
            "train_slope": float(sum(weight * train_lookup.loc[key] for weight, key in zip(weights, keys))),
            "test_slope": float(sum(weight * test_lookup.loc[key] for weight, key in zip(weights, keys))),
        })
    return pd.DataFrame(rows, columns=["pitcher", "train_slope", "test_slope"])


def _validate_slice10_scope(
    scope: str,
    pairs: pd.DataFrame,
    early_metrics: pd.DataFrame,
    source_coverage_pct: float,
) -> dict[str, Any]:
    merged = pairs.merge(early_metrics, on="pitcher", how="left", validate="one_to_one").dropna(
        subset=["train_slope", "test_slope", "early_stuff", "early_velocity"]
    )
    common = int(len(merged))
    if common < 3:
        return {
            "scope": scope, "status": "insufficient", "common_pitchers": common,
            "source_coverage_pct": round(source_coverage_pct, 1), "gates": {},
        }
    predicted = merged["train_slope"]
    observed = merged["test_slope"]
    residual = observed - predicted
    spearman = _rank_correlation(predicted, observed)
    rmse = float(np.sqrt(np.mean(np.square(residual))))
    baseline_prediction = np.repeat(float(predicted.mean()), common)
    baseline_rmse = float(np.sqrt(np.mean(np.square(observed.to_numpy() - baseline_prediction))))
    improvement = (baseline_rmse - rmse) / baseline_rmse * 100.0 if baseline_rmse else 0.0
    calibration_slope, calibration_intercept = np.polyfit(predicted, observed, 1) if predicted.nunique() > 1 else (np.nan, np.nan)
    early_stuff_corr = _rank_correlation(residual.reset_index(drop=True), merged["early_stuff"].reset_index(drop=True))
    early_velocity_corr = _rank_correlation(residual.reset_index(drop=True), merged["early_velocity"].reset_index(drop=True))
    family_scope = scope != "Overall"
    gates = {
        "coverage": source_coverage_pct >= (90.0 if family_scope else 95.0),
        "sample": common >= (40 if family_scope else 50),
        "rank": spearman is not None and spearman >= (0.30 if family_scope else 0.40),
        "rmse": improvement > 0,
        "calibration": np.isfinite(calibration_slope) and 0.80 <= float(calibration_slope) <= 1.20,
        "early_stuff_neutral": early_stuff_corr is not None and abs(early_stuff_corr) <= 0.10,
        "early_velocity_neutral": early_velocity_corr is not None and abs(early_velocity_corr) <= 0.10,
    }
    return {
        "scope": scope, "status": "validated" if all(gates.values()) else "research_only",
        "common_pitchers": common, "source_coverage_pct": round(source_coverage_pct, 1),
        "spearman_correlation": round(float(spearman), 3) if spearman is not None else None,
        "rmse": round(rmse, 3), "baseline_rmse": round(baseline_rmse, 3),
        "rmse_improvement_pct": round(improvement, 2),
        "calibration_slope": round(float(calibration_slope), 3) if np.isfinite(calibration_slope) else None,
        "calibration_intercept": round(float(calibration_intercept), 3) if np.isfinite(calibration_intercept) else None,
        "residual_early_stuff_spearman": round(float(early_stuff_corr), 3) if early_stuff_corr is not None else None,
        "residual_early_velocity_spearman": round(float(early_velocity_corr), 3) if early_velocity_corr is not None else None,
        "gates": gates,
    }


def _candidate_rows(scope: str, pairs: pd.DataFrame) -> list[dict[str, Any]]:
    if pairs.empty:
        return []
    combined = (pairs["train_slope"] + pairs["test_slope"]) / 2.0
    center = float(combined.mean())
    scale = float(combined.std(ddof=1))
    scores = 100.0 + 10.0 * (combined - center) / scale if scale > 0 else pd.Series(100.0, index=pairs.index)
    return [
        {
            "pitcher": int(pitcher), "scope": scope, "combined_slope": float(slope),
            "stamina_plus_v2_candidate": round(float(score), 1), "seasons": 2,
            "publication_status": "candidate_not_activated",
        }
        for pitcher, slope, score in zip(pairs["pitcher"], combined, scores)
    ]


def _build_slice10(
    test_curves: pd.DataFrame,
    slice7: dict[str, Any],
    year: int,
    data_dir: Path,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    candidate_columns = [
        "pitcher", "scope", "combined_slope", "stamina_plus_v2_candidate", "seasons", "publication_status"
    ]
    train_curve_path = stamina_v2_pitch_curve_path(year - 1, data_dir)
    if not train_curve_path.exists():
        return pd.DataFrame(columns=candidate_columns), {
            "status": "unavailable", "publication_status": "research_only",
            "contract_version": "stamina_v2_slice10_holdout_v1",
            "method": "A 2025 pitch-curve artifact is required before the strict 2025→2026 holdout.",
            "train_year": int(year - 1), "test_year": int(year), "selected_model": None,
            "model_validations": [], "scope_validations": [], "validated_scopes": [], "candidate_rows": 0,
            "warnings": ["Build the prior-season Slice 8–9 artifacts; do not substitute a same-season split."],
        }
    with duckdb.connect() as connection:
        train_curves = connection.execute("SELECT * FROM read_parquet(?)", [str(train_curve_path)]).fetchdf()
    required = {
        "release_speed", "balls", "strikes", "p_throws", "stand",
        "n_thruorder_pitcher", "inning", "home_team",
    }
    if not required.issubset(train_curves.columns) or not required.issubset(test_curves.columns):
        return pd.DataFrame(columns=candidate_columns), {
            "status": "unavailable", "publication_status": "research_only",
            "contract_version": "stamina_v2_slice10_holdout_v1",
            "method": "Both seasons require Slice 10-ready pitch curves with early velocity baselines.",
            "train_year": int(year - 1), "test_year": int(year), "selected_model": None,
            "model_validations": [], "scope_validations": [], "validated_scopes": [], "candidate_rows": 0,
            "warnings": ["Rebuild both seasonal curve artifacts with the current contract."],
        }
    train_curves, test_curves = _cross_season_context_adjust(train_curves, test_curves)
    train_late = train_curves[
        pd.to_numeric(train_curves["appearance_pitch_number"], errors="coerce").gt(20)
        & train_curves["early_pitch_type_baseline"].notna()
    ].copy()
    test_late = test_curves[
        pd.to_numeric(test_curves["appearance_pitch_number"], errors="coerce").gt(20)
        & test_curves["early_pitch_type_baseline"].notna()
    ].copy()
    train_hierarchical, _ = _hierarchical_family_slopes(train_late)
    test_hierarchical, _ = _hierarchical_family_slopes(test_late)
    model_validations, selected_model = _slice10_model_holdout(train_curves, test_curves)
    _, test_overall_early = _early_pitcher_metrics(test_curves)
    test_family_early, _ = _early_pitcher_metrics(test_curves)
    coverage_by_family = {
        str(row["family"]): float(row["stuff_coverage_pct"])
        for row in slice7.get("family_coverage", [])
    }
    pairs_by_scope: dict[str, pd.DataFrame] = {}
    scope_validations = []
    for family in PITCH_FAMILY_TYPES:
        train_rows = train_hierarchical[train_hierarchical["pitch_family"].eq(family)][["pitcher", "posterior_slope"]].rename(columns={"posterior_slope": "train_slope"})
        test_rows = test_hierarchical[test_hierarchical["pitch_family"].eq(family)][["pitcher", "posterior_slope"]].rename(columns={"posterior_slope": "test_slope"})
        pairs = train_rows.merge(test_rows, on="pitcher", how="inner", validate="one_to_one")
        pairs_by_scope[family] = pairs
        early = test_family_early[test_family_early["pitch_family"].eq(family)].drop(columns="pitch_family")
        scope_validations.append(_validate_slice10_scope(
            family, pairs, early, coverage_by_family.get(family, 0.0)
        ))
    overall_pairs = _overall_slope_pairs(train_curves, train_hierarchical, test_hierarchical)
    pairs_by_scope["Overall"] = overall_pairs
    scope_validations.insert(0, _validate_slice10_scope(
        "Overall", overall_pairs, test_overall_early, float(slice7.get("classified_stuff_coverage_pct") or 0.0)
    ))
    validated_scopes = [row["scope"] for row in scope_validations if row["status"] == "validated"]
    candidate_data = []
    if selected_model:
        for scope in validated_scopes:
            candidate_data.extend(_candidate_rows(scope, pairs_by_scope[scope]))
    candidates = pd.DataFrame(candidate_data, columns=candidate_columns)
    publication_status = "candidate_ready" if validated_scopes and selected_model else "research_only"
    return candidates, {
        "status": "ready", "publication_status": publication_status,
        "contract_version": "stamina_v2_slice10_holdout_v1",
        "method": "Strict 2025 training and 2026 untouched holdout for raw-pitch models and pitcher-family retention ranks; scope gates are evaluated independently and failed scopes emit no candidate score.",
        "train_year": int(year - 1), "test_year": int(year), "selected_model": selected_model,
        "model_validations": model_validations, "scope_validations": scope_validations,
        "validated_scopes": validated_scopes, "candidate_rows": int(len(candidates)),
        "warnings": [
            "Candidate scores are research artifacts only and are not connected to Pitcher Personal or next-start surfaces.",
            "Passing retention gates supports a repeatable association, not causal fatigue, injury risk or next-appearance readiness.",
            "A scope that fails any preregistered gate remains research-only with no score, even if another scope passes.",
        ],
    }


def _weighted_optional_mean(frame: pd.DataFrame, column: str, weight_column: str = "curve_weight") -> float | None:
    values = pd.to_numeric(frame[column], errors="coerce")
    weights = pd.to_numeric(frame[weight_column], errors="coerce")
    valid = values.notna() & weights.notna() & weights.gt(0)
    return float(np.average(values[valid], weights=weights[valid])) if valid.any() else None


def _build_slice11(frame: pd.DataFrame, pitch_curves: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Build research-only, within-appearance multi-signal family curves."""
    artifact_columns = [
        "pitcher", "pitcher_name", "team", "game_pk", "game_date", "appearance_total_pitches",
        "pitch_family", "analysis_bucket", "order", "pitches", "reference_pitches", "observation_weight",
        "stuff_delta", "velocity_delta", "spin_delta", "movement_drift_inches",
        "release_point_drift_inches", "extension_delta", "location_delta", "usage_pct", "usage_delta_pp",
    ]
    if frame.empty or pitch_curves.empty:
        return pd.DataFrame(columns=artifact_columns), {
            "status": "insufficient", "publication_status": "research_only",
            "contract_version": "stamina_v2_slice11_multisignal_v1",
            "method": "No eligible SP pitch curves were available.", "artifact_rows": 0,
            "pitchers": 0, "appearances": 0, "minimum_early_pitches": 3,
            "players": [], "signal_coverage": [], "league_curves": [], "transitions": [],
            "warnings": ["Slice 11 requires the cleaned pitch artifact and immutable Slice 8 pitch curves."],
        }
    merge_keys = ["pitcher", "game_pk", "appearance_pitch_number", "pitch_type"]
    physical_columns = [
        *merge_keys, "player_name", "pitcher_team", "pitch_family", "release_speed", "pfx_x", "pfx_z",
        "release_spin_rate", "release_extension", "release_pos_x", "release_pos_z", "location_plus_pitch",
    ]
    source = frame[physical_columns].drop_duplicates(merge_keys, keep="last")
    working = pitch_curves.merge(
        source, on=merge_keys, how="left", suffixes=("", "_source"), validate="one_to_one"
    )
    if "pitch_family_source" in working:
        working["pitch_family"] = working["pitch_family"].fillna(working["pitch_family_source"])
    baseline_metrics = {
        "context_adjusted_stuff": "early_stuff", "release_speed": "early_velocity",
        "release_spin_rate": "early_spin", "pfx_x": "early_pfx_x", "pfx_z": "early_pfx_z",
        "release_extension": "early_extension", "release_pos_x": "early_release_x",
        "release_pos_z": "early_release_z", "location_plus_pitch": "early_location",
    }
    early = working[pd.to_numeric(working["appearance_pitch_number"], errors="coerce").le(20)]
    baseline = early.groupby(["pitcher", "game_pk", "pitch_type"], as_index=False).agg(
        reference_pitches=("pitch_type", "size"),
        **{target: (source_column, "mean") for source_column, target in baseline_metrics.items()},
    )
    working = working.merge(baseline, on=["pitcher", "game_pk", "pitch_type"], how="left", validate="many_to_one")
    supported = pd.to_numeric(working["reference_pitches"], errors="coerce").ge(3)
    delta_sources = {
        "stuff_delta_pitch": ("context_adjusted_stuff", "early_stuff"),
        "velocity_delta_pitch": ("release_speed", "early_velocity"),
        "spin_delta_pitch": ("release_spin_rate", "early_spin"),
        "pfx_x_delta": ("pfx_x", "early_pfx_x"), "pfx_z_delta": ("pfx_z", "early_pfx_z"),
        "extension_delta_pitch": ("release_extension", "early_extension"),
        "release_x_delta": ("release_pos_x", "early_release_x"),
        "release_z_delta": ("release_pos_z", "early_release_z"),
        "location_delta_pitch": ("location_plus_pitch", "early_location"),
    }
    for target, (value, reference) in delta_sources.items():
        working[target] = (pd.to_numeric(working[value], errors="coerce") - pd.to_numeric(working[reference], errors="coerce")).where(supported)

    grouped = working.groupby(
        ["pitcher", "game_pk", "game_date", "pitch_family", "analysis_bucket"], as_index=False
    ).agg(
        pitcher_name=("player_name", "first"), team=("pitcher_team", "first"), pitches=("pitcher", "size"),
        reference_pitches=("reference_pitches", "max"), observation_weight=("observation_weight", "first"),
        stuff_delta=("stuff_delta_pitch", "mean"), velocity_delta=("velocity_delta_pitch", "mean"),
        spin_delta=("spin_delta_pitch", "mean"), pfx_x_delta=("pfx_x_delta", "mean"),
        pfx_z_delta=("pfx_z_delta", "mean"), extension_delta=("extension_delta_pitch", "mean"),
        release_x_delta=("release_x_delta", "mean"), release_z_delta=("release_z_delta", "mean"),
        location_delta=("location_delta_pitch", "mean"), mean_velocity=("release_speed", "mean"),
    )
    grouped["movement_drift_inches"] = np.hypot(grouped["pfx_x_delta"], grouped["pfx_z_delta"]) * 12.0
    grouped["release_point_drift_inches"] = np.hypot(grouped["release_x_delta"], grouped["release_z_delta"]) * 12.0
    bucket_order = {bucket: order for order, (_, _, bucket) in enumerate(SP_BUCKETS)}
    reach = working.groupby(["pitcher", "game_pk", "game_date", "analysis_bucket"], as_index=False).agg(
        pitcher_name=("player_name", "first"), team=("pitcher_team", "first"),
        bucket_pitches=("pitcher", "size"), observation_weight=("observation_weight", "first"),
        appearance_total_pitches=("appearance_pitch_number", "max"),
    )
    total_pitches = working.groupby(["pitcher", "game_pk"])["appearance_pitch_number"].max()
    reach_keys = pd.MultiIndex.from_frame(reach[["pitcher", "game_pk"]])
    reach["appearance_total_pitches"] = total_pitches.reindex(reach_keys).to_numpy(dtype="int64")
    families = pd.DataFrame({"pitch_family": list(PITCH_FAMILY_TYPES)})
    reach["_join"] = 1
    families["_join"] = 1
    grid = reach.merge(families, on="_join", how="inner").drop(columns="_join")
    multisignal = grid.merge(
        grouped,
        on=["pitcher", "game_pk", "game_date", "pitch_family", "analysis_bucket"],
        how="left", suffixes=("", "_group"), validate="one_to_one",
    )
    for column in ["pitcher_name", "team", "observation_weight"]:
        group_column = f"{column}_group"
        if group_column in multisignal:
            multisignal[column] = multisignal[group_column].combine_first(multisignal[column])
    multisignal["pitches"] = multisignal["pitches"].fillna(0).astype(int)
    multisignal["reference_pitches"] = multisignal["reference_pitches"].fillna(0).astype(int)
    multisignal["order"] = multisignal["analysis_bucket"].map(bucket_order).astype(int)
    multisignal["usage_pct"] = multisignal["pitches"] / multisignal["bucket_pitches"].clip(lower=1) * 100.0
    early_usage = multisignal[multisignal["order"].eq(0)].set_index(["pitcher", "game_pk", "pitch_family"])["usage_pct"]
    usage_keys = pd.MultiIndex.from_frame(multisignal[["pitcher", "game_pk", "pitch_family"]])
    multisignal["usage_delta_pp"] = multisignal["usage_pct"] - early_usage.reindex(usage_keys).to_numpy(dtype="float64")
    multisignal["curve_weight"] = multisignal["observation_weight"].clip(lower=0.1) * multisignal["pitches"].clip(lower=1)

    signal_columns = [
        "stuff_delta", "velocity_delta", "spin_delta", "movement_drift_inches",
        "release_point_drift_inches", "extension_delta", "location_delta",
    ]
    signal_coverage = []
    observed = multisignal[multisignal["pitches"].gt(0)]
    for family in PITCH_FAMILY_TYPES:
        family_rows = observed[observed["pitch_family"].eq(family)]
        for signal in signal_columns:
            available = int(family_rows[signal].notna().sum())
            signal_coverage.append({
                "family": family, "signal": signal, "available_rows": available,
                "total_rows": int(len(family_rows)), "coverage_pct": round(_pct(available, len(family_rows)), 1),
            })
    league_curves = []
    for (family, bucket), group in multisignal.groupby(["pitch_family", "analysis_bucket"], sort=False):
        point = {
            "family": str(family), "bucket": str(bucket), "order": int(bucket_order[str(bucket)]),
            "pitches": int(group["pitches"].sum()),
            "appearances": int(group[["pitcher", "game_pk"]].drop_duplicates().shape[0]),
            "pitchers": int(group["pitcher"].nunique()),
        }
        for signal in [*signal_columns, "usage_pct", "usage_delta_pp"]:
            weight_column = "observation_weight" if signal in {"usage_pct", "usage_delta_pp"} else "curve_weight"
            value = _weighted_optional_mean(group, signal, weight_column)
            point[signal] = round(value, 3) if value is not None else None
        league_curves.append(point)

    velocity = grouped.pivot_table(
        index=["pitcher", "game_pk", "analysis_bucket"], columns="pitch_family", values="mean_velocity"
    ).reset_index()
    transitions = []
    if {"Fastball", "Offspeed"}.issubset(velocity.columns):
        velocity["speed_gap_mph"] = velocity["Fastball"] - velocity["Offspeed"]
        early_gap = velocity[velocity["analysis_bucket"].eq("1–20")][["pitcher", "game_pk", "speed_gap_mph"]].rename(
            columns={"speed_gap_mph": "early_speed_gap_mph"}
        )
        velocity = velocity.merge(early_gap, on=["pitcher", "game_pk"], how="left")
        velocity["speed_gap_delta_mph"] = velocity["speed_gap_mph"] - velocity["early_speed_gap_mph"]
        for bucket, group in velocity.groupby("analysis_bucket", sort=False):
            valid = group.dropna(subset=["speed_gap_mph", "speed_gap_delta_mph"])
            transitions.append({
                "bucket": str(bucket), "order": int(bucket_order[str(bucket)]),
                "appearances": int(len(valid)),
                "speed_gap_mph": round(float(valid["speed_gap_mph"].mean()), 3) if len(valid) else None,
                "speed_gap_delta_mph": round(float(valid["speed_gap_delta_mph"].mean()), 3) if len(valid) else None,
            })

    players = (
        multisignal.groupby("pitcher", as_index=False).agg(
            name=("pitcher_name", "first"), team=("team", "last"), appearances=("game_pk", "nunique")
        ).sort_values("name", kind="stable")
    )
    keep = multisignal[artifact_columns].copy()
    for column in [*signal_columns, "usage_pct", "usage_delta_pp"]:
        keep[column] = pd.to_numeric(keep[column], errors="coerce").round(4)
    return keep.reset_index(drop=True), {
        "status": "ready", "publication_status": "research_only",
        "contract_version": "stamina_v2_slice11_multisignal_v1",
        "method": "Within each SP appearance and exact pitch type, later pitches are compared with at least three first-20 reference pitches; family curves retain Stuff+, velocity, spin, movement, release-point, extension, Location+ and usage signals separately.",
        "artifact_rows": int(len(keep)), "pitchers": int(keep["pitcher"].nunique()),
        "appearances": int(keep[["pitcher", "game_pk"]].drop_duplicates().shape[0]), "minimum_early_pitches": 3,
        "players": [
            {"pitcher_id": int(row.pitcher), "name": str(row.name), "team": str(row.team), "appearances": int(row.appearances)}
            for row in players.itertuples(index=False)
        ],
        "signal_coverage": signal_coverage,
        "league_curves": sorted(league_curves, key=lambda row: (list(PITCH_FAMILY_TYPES).index(row["family"]), row["order"])),
        "transitions": sorted(transitions, key=lambda row: row["order"]),
        "warnings": [
            "Slice 11 is diagnostic only: no family leaderboard, Stamina+ v2 score or downstream activation is emitted.",
            "Physical deltas are within-appearance exact-pitch-type comparisons; missing early support remains null rather than zero.",
            "Movement and release-point drift are distances from the early centroid, so larger values mean more shape or delivery displacement, not automatically worse performance.",
            "Fastball–Offspeed speed-gap rows require both families in the early and target windows and therefore remain selection-sensitive.",
        ],
    }


def _build_stamina_archetypes(
    frame: pd.DataFrame,
    multisignal: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    assignment_columns = [
        "pitcher", "game_pk", "early_stuff", "early_location", "stuff_pitches", "location_pitches",
        "stuff_band", "location_band", "archetype_key", "archetype_label",
    ]
    contract = {
        "status": "insufficient", "publication_status": "research_only",
        "contract_version": "stamina_v2_slice11_archetypes_v1",
        "method": "Each SP start is classified from pitches 1–20 into fixed Stuff+ and Location+ bands: Low <95, Average 95–105 and High >105.",
        "minimum_early_pitches": 10, "minimum_curve_appearances": 50, "minimum_curve_pitchers": 20,
        "eligible_appearances": 0, "excluded_appearances": 0, "cells": [], "curves": [],
        "warnings": ["No eligible early-window starts were available."],
    }
    if frame.empty or multisignal.empty:
        return pd.DataFrame(columns=assignment_columns), contract
    early = frame[
        frame["appearance_role"].eq("SP")
        & pd.to_numeric(frame["appearance_pitch_number"], errors="coerce").le(20)
    ].copy()
    assignments = early.groupby(["pitcher", "game_pk"], as_index=False).agg(
        early_stuff=("pitch_stuff_plus", "mean"), early_location=("location_plus_pitch", "mean"),
        stuff_pitches=("pitch_stuff_plus", "count"), location_pitches=("location_plus_pitch", "count"),
    )
    total_appearances = int(assignments.shape[0])
    assignments = assignments[
        assignments["stuff_pitches"].ge(10)
        & assignments["location_pitches"].ge(10)
        & assignments["early_stuff"].notna()
        & assignments["early_location"].notna()
    ].copy()

    def band(values: pd.Series) -> pd.Series:
        return pd.Series(
            np.select([values.lt(95.0), values.le(105.0)], ["Low", "Average"], default="High"),
            index=values.index,
        )

    assignments["stuff_band"] = band(assignments["early_stuff"])
    assignments["location_band"] = band(assignments["early_location"])
    assignments["archetype_key"] = (
        "stuff_" + assignments["stuff_band"].str.lower()
        + "__location_" + assignments["location_band"].str.lower()
    )
    assignments["archetype_label"] = assignments["stuff_band"] + " Stuff / " + assignments["location_band"] + " Location"
    band_order = ["High", "Average", "Low"]
    reached = (
        multisignal[multisignal["analysis_bucket"].eq("61–80")][["pitcher", "game_pk"]]
        .drop_duplicates().assign(reached_61_80=True)
    )
    support = assignments.merge(reached, on=["pitcher", "game_pk"], how="left")
    support["reached_61_80"] = support["reached_61_80"].fillna(False)
    cells = []
    for stuff_band in band_order:
        for location_band in band_order:
            group = support[
                support["stuff_band"].eq(stuff_band) & support["location_band"].eq(location_band)
            ]
            starts = int(len(group))
            pitchers = int(group["pitcher"].nunique())
            reached_count = int(group["reached_61_80"].sum())
            key = f"stuff_{stuff_band.lower()}__location_{location_band.lower()}"
            cells.append({
                "key": key, "label": f"{stuff_band} Stuff / {location_band} Location",
                "stuff_band": stuff_band, "location_band": location_band,
                "appearances": starts, "pitchers": pitchers, "reached_61_80": reached_count,
                "early_stuff": round(float(group["early_stuff"].mean()), 2) if starts else None,
                "early_location": round(float(group["early_location"].mean()), 2) if starts else None,
                "support_status": "supported" if starts >= 100 and pitchers >= 30 and reached_count >= 50 else "limited",
            })

    joined = multisignal.merge(
        assignments[["pitcher", "game_pk", "archetype_key"]],
        on=["pitcher", "game_pk"], how="inner", validate="many_to_one",
    )
    joined["curve_weight"] = joined["observation_weight"].clip(lower=0.1) * joined["pitches"].clip(lower=1)
    signal_columns = [
        "stuff_delta", "velocity_delta", "spin_delta", "movement_drift_inches",
        "release_point_drift_inches", "extension_delta", "location_delta", "usage_pct", "usage_delta_pp",
    ]
    bucket_order = {bucket: order for order, (_, _, bucket) in enumerate(SP_BUCKETS)}
    curves = []
    for (key, family, bucket), group in joined.groupby(
        ["archetype_key", "pitch_family", "analysis_bucket"], sort=False
    ):
        appearances = int(group[["pitcher", "game_pk"]].drop_duplicates().shape[0])
        pitchers = int(group["pitcher"].nunique())
        supported = appearances >= 50 and pitchers >= 20
        row: dict[str, Any] = {
            "archetype_key": str(key), "family": str(family), "bucket": str(bucket),
            "order": int(bucket_order[str(bucket)]), "pitches": int(group["pitches"].sum()),
            "appearances": appearances, "pitchers": pitchers, "supported": supported,
        }
        for signal in signal_columns:
            weight_column = "observation_weight" if signal in {"usage_pct", "usage_delta_pp"} else "curve_weight"
            value = _weighted_optional_mean(group, signal, weight_column) if supported else None
            row[signal] = round(value, 3) if value is not None else None
        curves.append(row)
    assignments = assignments[assignment_columns].reset_index(drop=True)
    return assignments, {
        **contract,
        "status": "ready", "eligible_appearances": int(len(assignments)),
        "excluded_appearances": int(total_appearances - len(assignments)),
        "cells": cells,
        "curves": sorted(curves, key=lambda row: (row["archetype_key"], list(PITCH_FAMILY_TYPES).index(row["family"]), row["order"])),
        "warnings": [
            "The 3×3 grid is a descriptive early-state stratification, not data-driven clustering or a permanent pitcher type.",
            "Only pitches 1–20 define the cell; later signals never feed back into classification.",
            "A family-window curve is suppressed below 50 appearances or 20 pitchers; unavailable values remain null.",
            "Hard bands simplify display and do not replace continuous Stuff+, Location+ or their interaction in later validation.",
        ],
    }


def _game_state_early_summary(source: pd.DataFrame) -> pd.DataFrame:
    starters = source[source["appearance_role"].eq("SP")].copy()
    starters["game_date"] = pd.to_datetime(starters["game_date"], errors="coerce")
    early = starters[pd.to_numeric(starters["appearance_pitch_number"], errors="coerce").le(20)]
    summary = early.groupby(["pitcher", "game_pk"], as_index=False).agg(
        game_date=("game_date", "first"), pitcher_name=("player_name", "first"), team=("pitcher_team", "first"),
        early_location=("location_plus_pitch", "mean"), early_velocity=("release_speed", "mean"),
    )
    totals = starters.groupby(["pitcher", "game_pk"], as_index=False).agg(
        total_pitches=("appearance_pitch_number", "max")
    )
    result = summary.merge(totals, on=["pitcher", "game_pk"], how="left", validate="one_to_one")
    result = result.sort_values(["pitcher", "game_date", "game_pk"], kind="stable")
    result["season_start_number"] = result.groupby("pitcher").cumcount() + 1
    return result


def _game_state_baseline_parameters(curves: pd.DataFrame) -> pd.DataFrame:
    early = curves[
        pd.to_numeric(curves["appearance_pitch_number"], errors="coerce").le(20)
    ].dropna(subset=["pitch_type", "context_adjusted_stuff"]).copy()
    appearance = early.groupby(["pitcher", "game_pk", "pitch_type"], as_index=False).agg(
        baseline=("context_adjusted_stuff", "mean"), pitches=("context_adjusted_stuff", "size"),
        within_variance=("context_adjusted_stuff", "var"),
    )
    rows = []
    for pitch_type, group in appearance.groupby("pitch_type"):
        pitch_rows = early[early["pitch_type"].eq(pitch_type)]
        league_mean = float(pitch_rows["context_adjusted_stuff"].mean())
        sigma2 = max(float(group["within_variance"].dropna().mean()), 1.0)
        between = float(group["baseline"].var(ddof=1)) if len(group) > 1 else 1.0
        tau2 = max(between - sigma2 * float((1.0 / group["pitches"].clip(lower=1)).mean()), 0.25)
        rows.append({"pitch_type": str(pitch_type), "league_baseline": league_mean, "sigma2": sigma2, "tau2": tau2})
    return pd.DataFrame(rows)


def _apply_game_state_baseline(curves: pd.DataFrame, parameters: pd.DataFrame) -> pd.DataFrame:
    early_counts = (
        curves[pd.to_numeric(curves["appearance_pitch_number"], errors="coerce").le(20)]
        .groupby(["pitcher", "game_pk", "pitch_type"], as_index=False).size()
        .rename(columns={"size": "early_exact_pitches"})
    )
    result = curves.merge(early_counts, on=["pitcher", "game_pk", "pitch_type"], how="left", validate="many_to_one")
    result = result.merge(parameters, on="pitch_type", how="left", validate="many_to_one")
    count = result["early_exact_pitches"].fillna(0).clip(lower=1)
    result["early_baseline_reliability"] = result["tau2"] / (result["tau2"] + result["sigma2"] / count)
    result["early_pitch_type_baseline_raw"] = result["early_pitch_type_baseline"]
    result["early_pitch_type_baseline"] = (
        result["early_baseline_reliability"] * result["early_pitch_type_baseline_raw"]
        + (1.0 - result["early_baseline_reliability"]) * result["league_baseline"]
    )
    return result


def _game_state_design(
    frame: pd.DataFrame,
    spline: Any,
    pitch_types: list[str],
) -> np.ndarray:
    early_stuff = pd.to_numeric(frame["early_pitch_type_baseline"], errors="coerce").to_numpy(dtype="float64")
    early_location = pd.to_numeric(frame["early_location"], errors="coerce").to_numpy(dtype="float64")
    early_velocity = pd.to_numeric(frame["early_pitch_type_velocity"], errors="coerce").to_numpy(dtype="float64") - 90.0
    workload = ((pd.to_numeric(frame["appearance_pitch_number"], errors="coerce") - 20.0) / 20.0).clip(lower=0).to_numpy(dtype="float64").reshape(-1, 1)
    workload_spline = spline.transform(workload)
    pitch = pd.get_dummies(frame["pitch_type"], dtype="float64").reindex(columns=pitch_types, fill_value=0).to_numpy(dtype="float64")
    interactions = np.concatenate([workload_spline * pitch[:, [index]] for index in range(len(pitch_types))], axis=1)
    centered_stuff = early_stuff - 100.0
    centered_location = early_location - 100.0
    return np.column_stack([
        early_stuff, centered_location, centered_stuff * centered_location, early_velocity,
        workload_spline, workload_spline * early_velocity[:, None], pitch,
        pitch * early_velocity[:, None], interactions,
    ])


def _build_game_states(
    reference_curves: pd.DataFrame,
    current_curves: pd.DataFrame,
    reference_source: pd.DataFrame,
    current_source: pd.DataFrame,
    reference_year: int,
    current_year: int,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import SplineTransformer

    reference_curves, current_curves = _cross_season_context_adjust(reference_curves, current_curves)
    baseline_parameters = _game_state_baseline_parameters(reference_curves)
    reference_curves = _apply_game_state_baseline(reference_curves, baseline_parameters)
    current_curves = _apply_game_state_baseline(current_curves, baseline_parameters)
    reference_early = _game_state_early_summary(reference_source)
    current_early = _game_state_early_summary(current_source)
    reference_model = reference_curves.merge(
        reference_early[["pitcher", "game_pk", "early_location"]],
        on=["pitcher", "game_pk"], how="left", validate="many_to_one",
    )
    reference_model = reference_model[
        pd.to_numeric(reference_model["appearance_pitch_number"], errors="coerce").between(21, 100)
        & reference_model["early_pitch_type_baseline"].notna()
        & reference_model["early_pitch_type_velocity"].notna()
        & reference_model["early_location"].notna()
        & reference_model["context_adjusted_stuff"].notna()
    ].copy()
    spline = SplineTransformer(n_knots=5, degree=3, include_bias=False)
    reference_workload = ((reference_model["appearance_pitch_number"] - 20.0) / 20.0).clip(lower=0).to_numpy().reshape(-1, 1)
    spline.fit(reference_workload)
    pitch_types = sorted(str(value) for value in reference_model["pitch_type"].dropna().unique())
    design = _game_state_design(reference_model, spline, pitch_types)
    outcome = reference_model["context_adjusted_stuff"].to_numpy(dtype="float64")
    reference_weights = reference_model["observation_weight"].fillna(1.0).clip(lower=0.1).to_numpy(dtype="float64")
    expected_model = Ridge(alpha=10.0)
    expected_model.fit(design, outcome, sample_weight=reference_weights)

    working = current_curves.merge(
        current_early.drop(columns="game_date"), on=["pitcher", "game_pk"], how="left", validate="many_to_one"
    )
    valid = (
        pd.to_numeric(working["appearance_pitch_number"], errors="coerce").between(21, 100)
        & working["early_pitch_type_baseline"].notna()
        & working["early_pitch_type_velocity"].notna()
        & working["early_location"].notna()
        & working["context_adjusted_stuff"].notna()
        & working["early_exact_pitches"].fillna(0).ge(1)
    )
    working = working.loc[valid].copy()
    working["expected_stuff"] = expected_model.predict(_game_state_design(working, spline, pitch_types))
    working["retention"] = working["context_adjusted_stuff"] - working["expected_stuff"]
    working["velocity_delta"] = working["release_speed"] - working["early_pitch_type_velocity"]
    working["weight"] = working["observation_weight"].fillna(1.0).clip(lower=0.1)

    use_cluster_bootstrap = True

    def weighted_summary(group: pd.DataFrame) -> pd.Series:
        weights = group["weight"].to_numpy(dtype="float64")
        values = group["retention"].to_numpy(dtype="float64")
        weight_sum = float(weights.sum())
        mean = float(np.average(values, weights=weights))
        effective_n = float(weight_sum**2 / np.square(weights).sum()) if np.square(weights).sum() else 0.0
        variance = float(np.average(np.square(values - mean), weights=weights)) if len(group) > 1 else 0.0
        cluster = group.groupby("inning", sort=False).apply(
            lambda rows: pd.Series({
                "weight": float(rows["weight"].sum()),
                "mean": float(np.average(rows["retention"], weights=rows["weight"])),
            }), include_groups=False,
        )
        sampling_variance = variance / max(effective_n, 1.0)
        if use_cluster_bootstrap and len(cluster) >= 2:
            rng = np.random.default_rng(42)
            cluster_weights = cluster["weight"].to_numpy(dtype="float64")
            cluster_means = cluster["mean"].to_numpy(dtype="float64")
            bootstrap_means = []
            for _ in range(100):
                indexes = rng.integers(0, len(cluster), len(cluster))
                bootstrap_means.append(float(np.average(cluster_means[indexes], weights=cluster_weights[indexes])))
            sampling_variance = max(float(np.var(bootstrap_means, ddof=1)), sampling_variance)
        velocity = group["velocity_delta"].dropna()
        return pd.Series({
            "pitches": int(len(group)), "effective_pitches": effective_n, "raw_retention": mean,
            "sampling_variance": max(sampling_variance, 0.01), "clusters": int(len(cluster)),
            "velocity_delta": float(velocity.mean()) if len(velocity) else np.nan,
            "early_stuff": float(group["early_pitch_type_baseline"].mean()),
            "early_velocity": float(group["early_pitch_type_velocity"].mean()),
            "early_baseline_reliability": float(group["early_baseline_reliability"].mean()),
        })

    family_states = working.groupby(
        ["pitcher", "game_pk", "game_date", "pitcher_name", "team", "season_start_number", "total_pitches", "pitch_family"],
        as_index=False, sort=False,
    ).apply(weighted_summary, include_groups=False).rename(columns={"pitch_family": "scope"})
    overall_states = working.groupby(
        ["pitcher", "game_pk", "game_date", "pitcher_name", "team", "season_start_number", "total_pitches"],
        as_index=False, sort=False,
    ).apply(weighted_summary, include_groups=False)
    overall_states["scope"] = "Overall"
    overall_states["observed_mix_retention"] = overall_states["raw_retention"]
    early_mix = (
        current_curves[pd.to_numeric(current_curves["appearance_pitch_number"], errors="coerce").le(20)]
        .groupby(["pitcher", "game_pk", "pitch_family"], as_index=False).size()
        .rename(columns={"size": "early_family_pitches"})
    )
    early_mix["early_family_weight"] = early_mix["early_family_pitches"] / early_mix.groupby(
        ["pitcher", "game_pk"]
    )["early_family_pitches"].transform("sum")
    family_lookup = family_states.set_index(["pitcher", "game_pk", "scope"])
    family_eligible = family_states[family_states["pitches"].ge(5)]
    family_prior = family_eligible.groupby("scope").apply(
        lambda group: pd.Series({
            "mean": float(np.average(group["raw_retention"], weights=group["effective_pitches"])),
            "variance": max(float(group["raw_retention"].var(ddof=1)), 0.25),
        }), include_groups=False,
    ).to_dict(orient="index")
    for index, row in overall_states.iterrows():
        mix = early_mix[
            early_mix["pitcher"].eq(row["pitcher"]) & early_mix["game_pk"].eq(row["game_pk"])
        ]
        fixed_retention = 0.0
        fixed_variance = 0.0
        covered_weight = 0.0
        for mix_row in mix.itertuples(index=False):
            family = str(mix_row.pitch_family)
            family_weight = float(mix_row.early_family_weight)
            prior = family_prior.get(family, {"mean": 0.0, "variance": 4.0})
            key = (row["pitcher"], row["game_pk"], family)
            if key in family_lookup.index and int(family_lookup.at[key, "pitches"]) >= 5:
                value = float(family_lookup.at[key, "raw_retention"])
                variance_value = float(family_lookup.at[key, "sampling_variance"])
                covered_weight += family_weight
            else:
                value = float(prior["mean"])
                variance_value = float(prior["variance"])
            fixed_retention += family_weight * value
            fixed_variance += family_weight**2 * variance_value
        overall_states.at[index, "raw_retention"] = fixed_retention
        overall_states.at[index, "sampling_variance"] = max(fixed_variance, 0.01)
        overall_states.at[index, "fixed_mix_coverage"] = covered_weight
    states = pd.concat([overall_states, family_states], ignore_index=True, sort=False)
    states["minimum_pitches"] = np.where(states["scope"].eq("Overall"), 15, 5)
    states["eligible"] = states["pitches"].ge(states["minimum_pitches"])
    states.loc[states["scope"].eq("Overall"), "eligible"] &= states.loc[
        states["scope"].eq("Overall"), "fixed_mix_coverage"
    ].fillna(0).ge(0.80)

    scope_parameters: list[dict[str, Any]] = []
    for scope, indexes in states.groupby("scope").groups.items():
        eligible_indexes = [index for index in indexes if bool(states.at[index, "eligible"])]
        sample = states.loc[eligible_indexes]
        if sample.empty:
            continue
        league_mean = float(np.average(sample["raw_retention"], weights=sample["effective_pitches"]))
        observed_variance = float(np.var(sample["raw_retention"], ddof=1)) if len(sample) > 1 else 0.01
        tau2 = max(observed_variance - float(sample["sampling_variance"].mean()), 0.01)
        scale = float(np.sqrt(tau2))
        for index in eligible_indexes:
            sampling_variance = float(states.at[index, "sampling_variance"])
            reliability = float(tau2 / (tau2 + sampling_variance))
            posterior = league_mean + reliability * (float(states.at[index, "raw_retention"]) - league_mean)
            posterior_variance = float(1.0 / (1.0 / tau2 + 1.0 / sampling_variance))
            posterior_se = float(np.sqrt(posterior_variance))
            states.at[index, "posterior_retention"] = posterior
            states.at[index, "reliability"] = reliability
            states.at[index, "stamina_plus"] = 100.0 + 10.0 * (posterior - league_mean) / scale
            states.at[index, "ci_low"] = 100.0 + 10.0 * (posterior - 1.281552 * posterior_se - league_mean) / scale
            states.at[index, "ci_high"] = 100.0 + 10.0 * (posterior + 1.281552 * posterior_se - league_mean) / scale
        scope_parameters.append({
            "scope": str(scope), "eligible_games": int(len(sample)), "league_retention": round(league_mean, 3),
            "state_sd": round(scale, 3), "median_reliability": round(float(states.loc[eligible_indexes, "reliability"].median()), 3),
        })
    states["confidence"] = np.select(
        [states["reliability"].ge(0.67), states["reliability"].ge(0.40)], ["high", "medium"], default="low"
    )
    for (_, scope), group in states.groupby(["pitcher", "scope"], sort=False):
        ordered = group.sort_values(["game_date", "game_pk"], kind="stable")
        score = ordered["stamina_plus"]
        states.loc[ordered.index, "rolling_3"] = score.rolling(3, min_periods=1).mean().to_numpy()
        states.loc[ordered.index, "rolling_5"] = score.rolling(5, min_periods=1).mean().to_numpy()

    use_cluster_bootstrap = False
    family_windows = working.groupby(
        ["pitcher", "game_pk", "game_date", "pitcher_name", "team", "pitch_family", "analysis_bucket"],
        as_index=False, sort=False,
    ).apply(weighted_summary, include_groups=False).rename(columns={"pitch_family": "scope", "raw_retention": "retention"})
    overall_windows = working.groupby(
        ["pitcher", "game_pk", "game_date", "pitcher_name", "team", "analysis_bucket"],
        as_index=False, sort=False,
    ).apply(weighted_summary, include_groups=False).rename(columns={"raw_retention": "retention"})
    overall_windows["scope"] = "Overall"
    windows = pd.concat([overall_windows, family_windows], ignore_index=True, sort=False)
    bucket_order = {label: index for index, (_, _, label) in enumerate(SP_BUCKETS)}
    windows["order"] = windows["analysis_bucket"].map(bucket_order).astype(int)

    current_prediction = working["expected_stuff"].to_numpy(dtype="float64")
    current_observed = working["context_adjusted_stuff"].to_numpy(dtype="float64")
    baseline_prediction = working["early_pitch_type_baseline"].to_numpy(dtype="float64")
    model_rmse = float(np.sqrt(np.mean(np.square(current_observed - current_prediction))))
    baseline_rmse = float(np.sqrt(np.mean(np.square(current_observed - baseline_prediction))))
    model_improvement = (baseline_rmse - model_rmse) / baseline_rmse * 100.0 if baseline_rmse else 0.0
    overall = states[states["scope"].eq("Overall") & states["eligible"]].copy()
    early_stuff_corr = _rank_correlation(overall["raw_retention"], overall["early_stuff"])
    early_velocity_corr = _rank_correlation(overall["raw_retention"], overall["early_velocity"])
    overall_window_pivot = windows[windows["scope"].eq("Overall")].pivot_table(
        index=["pitcher", "game_pk"], columns="analysis_bucket", values="retention", aggfunc="first"
    )
    split_consistency = None
    if {"21–40", "61–80"}.issubset(overall_window_pivot.columns):
        split_consistency = _rank_correlation(overall_window_pivot["21–40"], overall_window_pivot["61–80"])
    states = states.sort_values(["pitcher", "game_date", "game_pk", "scope"], kind="stable").reset_index(drop=True)
    windows = windows.sort_values(["pitcher", "game_date", "game_pk", "scope", "order"], kind="stable").reset_index(drop=True)
    result = {
        "status": "ready", "publication_status": "observed_state",
        "contract_version": "stamina_observed_game_state_v1_1",
        "method": "Prior-season empirical-Bayes exact-type opening baselines feed exact-pitch-type workload splines; observed pitch 21–100 residuals use inning-clustered uncertainty, and Overall Game Stamina+ fixes each start's first-20-pitch family mix.",
        "reference_year": int(reference_year), "season": int(current_year), "minimum_early_exact_pitches": 1,
        "minimum_overall_late_pitches": 15, "minimum_family_late_pitches": 5,
        "minimum_fixed_mix_coverage_pct": 80.0, "interval_method": "100-replicate inning-cluster bootstrap with analytic floor",
        "state_rows": int(len(states)), "window_rows": int(len(windows)),
        "eligible_overall_games": int(len(overall)), "pitchers": int(overall["pitcher"].nunique()),
        "overall_start_coverage_pct": round(float(len(overall) / max(len(current_early), 1) * 100.0), 1),
        "median_interval_width": round(float((overall["ci_high"] - overall["ci_low"]).median()), 1),
        "pitch_model_rmse": round(model_rmse, 3), "pitch_baseline_rmse": round(baseline_rmse, 3),
        "pitch_rmse_improvement_pct": round(model_improvement, 2),
        "early_stuff_spearman": round(float(early_stuff_corr), 3) if early_stuff_corr is not None else None,
        "early_velocity_spearman": round(float(early_velocity_corr), 3) if early_velocity_corr is not None else None,
        "within_game_split_spearman": round(float(split_consistency), 3) if split_consistency is not None else None,
        "scope_parameters": sorted(scope_parameters, key=lambda row: ["Overall", "Fastball", "Breaking", "Offspeed"].index(row["scope"])),
        "warnings": [
            "Game Stamina+ describes only the pitches observed in that game; it is not a next-start forecast or a permanent pitcher trait.",
            "Overall requires at least 15 supported pitches after pitch 20 and 80% fixed early-family-mix coverage; family scores require 5 pitches.",
            "Unobserved fixed-mix family weight receives the league family retention prior and added uncertainty; it is never silently renormalized away.",
            "Opening exact-type means shrink toward prior-season pitch-type baselines according to their observed pitch count.",
            "A score measures performance retention after observed-context adjustment, not direct physiological fatigue.",
        ],
    }
    return states, windows, result


def _build_season_summaries(
    states: pd.DataFrame,
    year: int,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Pool observed game states into a season estimate without creating a future-facing trait."""
    required = {
        "pitcher", "game_pk", "game_date", "pitcher_name", "team", "season_start_number",
        "total_pitches", "scope", "pitches", "eligible", "stamina_plus", "ci_low", "ci_high", "reliability",
    }
    missing = sorted(required.difference(states.columns))
    if missing:
        raise ValueError(f"Game-state artifact is missing season-summary columns: {', '.join(missing)}")

    source = states.copy()
    source["game_date"] = pd.to_datetime(source["game_date"], errors="coerce")
    overall_source = source[source["scope"].eq("Overall")].sort_values(
        ["pitcher", "game_date", "game_pk"], kind="stable"
    )
    pitcher_meta = overall_source.groupby("pitcher", as_index=True).agg(
        total_starts=("season_start_number", "max"),
        average_pitches=("total_pitches", "mean"),
    )
    latest_meta = overall_source.groupby("pitcher", as_index=True).tail(1).set_index("pitcher")
    pitcher_meta["pitcher_name"] = latest_meta["pitcher_name"]
    pitcher_meta["team"] = latest_meta["team"]

    working = source[
        source["eligible"].fillna(False)
        & source["stamina_plus"].notna()
        & source["reliability"].notna()
    ].copy()
    if working.empty:
        raise ValueError("No eligible observed game states are available for season aggregation.")

    scope_rules = {
        "Overall": {"minimum_games": 10, "minimum_pitches": 150},
        "Fastball": {"minimum_games": 8, "minimum_pitches": 50},
        "Breaking": {"minimum_games": 8, "minimum_pitches": 50},
        "Offspeed": {"minimum_games": 8, "minimum_pitches": 50},
    }
    minimum_season_reliability = 0.70
    z80 = 1.281552
    records: list[dict[str, Any]] = []

    for (pitcher, scope), group in working.groupby(["pitcher", "scope"], sort=False):
        group = group.sort_values(["game_date", "game_pk"], kind="stable")
        scores = group["stamina_plus"].to_numpy(dtype="float64")
        game_reliability = group["reliability"].clip(lower=0.05, upper=0.95).to_numpy(dtype="float64")
        weight_sum = float(game_reliability.sum())
        raw_score = float(np.average(scores, weights=game_reliability))
        unweighted_score = float(np.mean(scores))
        effective_games = float(weight_sum**2 / np.square(game_reliability).sum())
        weighted_variance = float(np.average(np.square(scores - raw_score), weights=game_reliability))
        between_game_se2 = weighted_variance / max(effective_games, 1.0)
        game_se = (
            pd.to_numeric(group["ci_high"], errors="coerce")
            - pd.to_numeric(group["ci_low"], errors="coerce")
        ).to_numpy(dtype="float64") / (2.0 * z80)
        valid_game_se = np.isfinite(game_se) & (game_se > 0)
        measurement_se2 = 0.0
        if valid_game_se.any():
            valid_weights = game_reliability[valid_game_se]
            measurement_se2 = float(
                np.sum(np.square(valid_weights) * np.square(game_se[valid_game_se]))
                / np.square(valid_weights.sum())
            )
        season_variance = max(between_game_se2, measurement_se2, 0.25)
        rules = scope_rules.get(str(scope), {"minimum_games": 8, "minimum_pitches": 50})
        eligible_games = int(group["game_pk"].nunique())
        supported_pitches = int(group["pitches"].sum())
        mean_reliability = float(group["reliability"].mean())
        qualified = bool(
            eligible_games >= int(rules["minimum_games"])
            and supported_pitches >= int(rules["minimum_pitches"])
        )
        meta = pitcher_meta.loc[pitcher]
        records.append({
            "pitcher": int(pitcher),
            "pitcher_name": str(meta["pitcher_name"]),
            "team": str(meta["team"]),
            "scope": str(scope),
            "total_starts": int(meta["total_starts"]),
            "eligible_games": eligible_games,
            "supported_pitches": supported_pitches,
            "effective_games": effective_games,
            "average_pitches": float(meta["average_pitches"]),
            "mean_game_reliability": mean_reliability,
            "raw_stamina_plus": raw_score,
            "unweighted_stamina_plus": unweighted_score,
            "season_sampling_variance": season_variance,
            "qualified": qualified,
            "minimum_games": int(rules["minimum_games"]),
            "minimum_pitches": int(rules["minimum_pitches"]),
        })

    summaries = pd.DataFrame(records)
    scope_audits: list[dict[str, Any]] = []
    for scope, indexes in summaries.groupby("scope").groups.items():
        scope_frame = summaries.loc[indexes]
        prior_frame = scope_frame[scope_frame["eligible_games"].ge(3)]
        observed_variance = float(prior_frame["raw_stamina_plus"].var(ddof=1)) if len(prior_frame) > 1 else 1.0
        typical_sampling_variance = float(prior_frame["season_sampling_variance"].median()) if len(prior_frame) else 1.0
        tau2 = max(observed_variance - typical_sampling_variance, 1.0)
        for index in indexes:
            sampling_variance = float(summaries.at[index, "season_sampling_variance"])
            reliability = float(tau2 / (tau2 + sampling_variance))
            posterior = 100.0 + reliability * (float(summaries.at[index, "raw_stamina_plus"]) - 100.0)
            posterior_variance = float(1.0 / (1.0 / tau2 + 1.0 / sampling_variance))
            posterior_se = float(np.sqrt(posterior_variance))
            summaries.at[index, "stamina_plus"] = posterior
            summaries.at[index, "ci_low"] = posterior - z80 * posterior_se
            summaries.at[index, "ci_high"] = posterior + z80 * posterior_se
            summaries.at[index, "reliability"] = reliability
            summaries.at[index, "qualified"] = bool(
                summaries.at[index, "qualified"]
                and reliability >= minimum_season_reliability
            )
        qualified = summaries.loc[indexes][summaries.loc[indexes, "qualified"]].copy()
        rank_correlation = _rank_correlation(
            qualified["raw_stamina_plus"], qualified["unweighted_stamina_plus"]
        ) if len(qualified) >= 3 else None
        interval_width = qualified["ci_high"] - qualified["ci_low"]
        scope_audits.append({
            "scope": str(scope),
            "pitchers": int(len(scope_frame)),
            "qualified_pitchers": int(len(qualified)),
            "minimum_games": int(scope_rules[str(scope)]["minimum_games"]),
            "minimum_pitches": int(scope_rules[str(scope)]["minimum_pitches"]),
            "median_reliability": round(float(qualified["reliability"].median()), 3) if len(qualified) else 0.0,
            "median_interval_width": round(float(interval_width.median()), 1) if len(qualified) else 0.0,
            "weighted_vs_unweighted_spearman": round(float(rank_correlation), 3) if rank_correlation is not None else None,
        })

    summaries["confidence"] = np.select(
        [summaries["reliability"].ge(0.80), summaries["reliability"].ge(0.60)],
        ["high", "medium"],
        default="low",
    )
    summaries["rank"] = np.nan
    for scope, indexes in summaries.groupby("scope").groups.items():
        qualified_indexes = [index for index in indexes if bool(summaries.at[index, "qualified"])]
        if qualified_indexes:
            summaries.loc[qualified_indexes, "rank"] = summaries.loc[qualified_indexes, "stamina_plus"].rank(
                method="min", ascending=False
            )
    summaries = summaries.sort_values(
        ["scope", "qualified", "stamina_plus", "pitcher_name"],
        ascending=[True, False, False, True],
        kind="stable",
    ).reset_index(drop=True)
    numeric_columns = [
        "effective_games", "average_pitches", "mean_game_reliability", "raw_stamina_plus",
        "unweighted_stamina_plus", "season_sampling_variance", "stamina_plus", "ci_low", "ci_high", "reliability",
    ]
    summaries[numeric_columns] = summaries[numeric_columns].round(3)
    result = {
        "status": "ready",
        "publication_status": "research_only",
        "contract_version": "stamina_observed_season_state_v1_1",
        "season": int(year),
        "method": "Reliability-weighted game-state means with between-game and measurement uncertainty, followed by scope-level empirical-Bayes partial pooling.",
        "minimum_season_reliability": minimum_season_reliability,
        "rows": int(len(summaries)),
        "scope_audits": sorted(
            scope_audits,
            key=lambda row: ["Overall", "Fastball", "Breaking", "Offspeed"].index(row["scope"]),
        ),
        "warnings": [
            "Season Stamina+ ranks observed in-season state only; it is not a permanent trait or next-start prediction.",
            "Overall qualification requires 10 eligible starts, 150 supported late pitches and season reliability of 0.70.",
            "Family qualification requires 8 eligible starts, 50 supported late pitches and season reliability of 0.70.",
            "Leaderboard publication remains blocked until the same contract is checked on an independent season.",
        ],
    }
    return summaries, result


def _build_external_validation(
    metas: dict[int, dict[str, Any]],
    states: dict[int, pd.DataFrame],
    summaries: dict[int, pd.DataFrame],
    validation_year: int,
    test_year: int,
) -> dict[str, Any]:
    years = [int(validation_year), int(test_year)]
    season_audits: list[dict[str, Any]] = []
    game_results: dict[int, dict[str, Any]] = {}
    summary_results: dict[int, dict[str, Any]] = {}
    for year in years:
        game_result = dict(metas[year].get("slice11_game_state") or {})
        summary_result = dict(metas[year].get("slice12") or {})
        if not game_result or not summary_result:
            raise ValueError(f"{year} is missing the frozen game-state or season-summary result.")
        game_results[year] = game_result
        summary_results[year] = summary_result
        overall_states = states[year][
            states[year]["scope"].eq("Overall")
            & states[year]["eligible"].fillna(False)
            & states[year]["stamina_plus"].notna()
        ].copy()
        overall_summaries = summaries[year][
            summaries[year]["scope"].eq("Overall")
            & summaries[year]["qualified"].fillna(False)
        ].copy()
        early = overall_states.groupby("pitcher", as_index=False).agg(
            early_stuff=("early_stuff", "mean"),
            early_velocity=("early_velocity", "mean"),
        )
        audit = overall_summaries.merge(early, on="pitcher", how="left", validate="one_to_one")
        season_audits.append({
            "year": year,
            "qualified_pitchers": int(len(audit)),
            "stamina_vs_early_stuff_spearman": _rounded_correlation(
                _rank_correlation(audit["stamina_plus"], audit["early_stuff"])
            ),
            "stamina_vs_early_velocity_spearman": _rounded_correlation(
                _rank_correlation(audit["stamina_plus"], audit["early_velocity"])
            ),
            "stamina_vs_eligible_games_spearman": _rounded_correlation(
                _rank_correlation(audit["stamina_plus"], audit["eligible_games"])
            ),
            "stamina_vs_average_pitches_spearman": _rounded_correlation(
                _rank_correlation(audit["stamina_plus"], audit["average_pitches"])
            ),
        })

    common = summaries[validation_year][
        summaries[validation_year]["scope"].eq("Overall")
        & summaries[validation_year]["qualified"].fillna(False)
    ][["pitcher", "stamina_plus"]].merge(
        summaries[test_year][
            summaries[test_year]["scope"].eq("Overall")
            & summaries[test_year]["qualified"].fillna(False)
        ][["pitcher", "stamina_plus"]],
        on="pitcher", suffixes=(f"_{validation_year}", f"_{test_year}"), validate="one_to_one",
    )
    cross_season_rank = _rank_correlation(
        common[f"stamina_plus_{validation_year}"], common[f"stamina_plus_{test_year}"]
    ) if len(common) >= 3 else None

    game_contracts = [game_results[year].get("contract_version") for year in years]
    season_contracts = [summary_results[year].get("contract_version") for year in years]
    game_correlations = [
        abs(float(game_results[year][key]))
        for year in years
        for key in ["early_stuff_spearman", "early_velocity_spearman"]
        if game_results[year].get(key) is not None
    ]
    season_correlations = [
        abs(float(row[key]))
        for row in season_audits
        for key in ["stamina_vs_early_stuff_spearman", "stamina_vs_early_velocity_spearman"]
        if row.get(key) is not None
    ]
    scope_audits = [
        audit
        for year in years
        for audit in summary_results[year].get("scope_audits", [])
    ]

    gates = [
        {
            "key": "frozen_contracts",
            "label": "Frozen contracts match",
            "threshold": "both seasons use game v1.1 and season v1.1",
            "value": f"game={game_contracts}; season={season_contracts}",
            "passed": all(value == "stamina_observed_game_state_v1_1" for value in game_contracts)
            and all(value == "stamina_observed_season_state_v1_1" for value in season_contracts),
        },
        {
            "key": "overall_coverage",
            "label": "Overall start coverage",
            "threshold": ">= 80% in both seasons",
            "value": round(min(float(game_results[year]["overall_start_coverage_pct"]) for year in years), 3),
            "passed": min(float(game_results[year]["overall_start_coverage_pct"]) for year in years) >= 80.0,
        },
        {
            "key": "pitch_rmse_gain",
            "label": "Pitch-model gain over strong baseline",
            "threshold": ">= 1% in both seasons",
            "value": round(min(float(game_results[year]["pitch_rmse_improvement_pct"]) for year in years), 3),
            "passed": min(float(game_results[year]["pitch_rmse_improvement_pct"]) for year in years) >= 1.0,
        },
        {
            "key": "game_ceiling_neutrality",
            "label": "Game-state ceiling neutrality",
            "threshold": "max |rho| <= 0.10 for early Stuff+ and velocity",
            "value": round(max(game_correlations), 3),
            "passed": bool(game_correlations) and max(game_correlations) <= 0.10,
        },
        {
            "key": "within_game_consistency",
            "label": "Within-game split consistency",
            "threshold": "rho >= 0.30 in both seasons",
            "value": round(min(float(game_results[year]["within_game_split_spearman"]) for year in years), 3),
            "passed": min(float(game_results[year]["within_game_split_spearman"]) for year in years) >= 0.30,
        },
        {
            "key": "season_support",
            "label": "Qualified Overall pitcher support",
            "threshold": ">= 100 pitchers in both seasons",
            "value": min(row["qualified_pitchers"] for row in season_audits),
            "passed": min(row["qualified_pitchers"] for row in season_audits) >= 100,
        },
        {
            "key": "season_precision",
            "label": "Season estimate precision",
            "threshold": "median reliability >= 0.70 and 80% interval width <= 15 in every scope",
            "value": {
                "minimum_reliability": round(min(float(row["median_reliability"]) for row in scope_audits), 3),
                "maximum_interval_width": round(max(float(row["median_interval_width"]) for row in scope_audits), 3),
            },
            "passed": min(float(row["median_reliability"]) for row in scope_audits) >= 0.70
            and max(float(row["median_interval_width"]) for row in scope_audits) <= 15.0,
        },
        {
            "key": "weighting_sensitivity",
            "label": "Season ranking weighting sensitivity",
            "threshold": "weighted-vs-unweighted rho >= 0.90 in every scope",
            "value": round(min(float(row["weighted_vs_unweighted_spearman"]) for row in scope_audits), 3),
            "passed": min(float(row["weighted_vs_unweighted_spearman"]) for row in scope_audits) >= 0.90,
        },
        {
            "key": "season_ceiling_neutrality",
            "label": "Season leaderboard ceiling neutrality",
            "threshold": "max |rho| <= 0.20 for early Stuff+ and velocity",
            "value": round(max(season_correlations), 3),
            "passed": bool(season_correlations) and max(season_correlations) <= 0.20,
        },
    ]
    release_eligible = all(bool(gate["passed"]) for gate in gates)
    return {
        "status": "passed" if release_eligible else "failed",
        "publication_status": "validated_observed_state" if release_eligible else "research_only",
        "contract_version": "stamina_observed_external_validation_v1_1",
        "validation_year": int(validation_year),
        "test_year": int(test_year),
        "leaderboard_release_eligible": release_eligible,
        "gates": gates,
        "season_audits": season_audits,
        "common_qualified_pitchers": int(len(common)),
        "cross_season_stamina_spearman": _rounded_correlation(cross_season_rank),
        "cross_season_note": "Cross-season rank is descriptive only because this score measures season state, not a permanent trait.",
        "warnings": [
            "Passing validates a descriptive observed-season leaderboard, not physiological stamina or future-start prediction.",
            "Average pitch depth remains separate from Stamina+ because managerial removal and performance selection are not causal fatigue measures.",
        ],
    }


def _build_season_bias_repair(
    states: dict[int, pd.DataFrame],
    summaries: dict[int, pd.DataFrame],
    external_validation: dict[str, Any],
    development_year: int,
    test_year: int,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import SplineTransformer, StandardScaler

    years = [int(development_year), int(test_year)]
    prepared: dict[int, pd.DataFrame] = {}
    for year in years:
        eligible_states = states[year][
            states[year]["eligible"].fillna(False)
            & states[year]["stamina_plus"].notna()
        ]
        early = eligible_states.groupby(["pitcher", "scope"], as_index=False).agg(
            season_early_stuff=("early_stuff", "mean"),
            season_early_velocity=("early_velocity", "mean"),
        )
        frame = summaries[year].merge(early, on=["pitcher", "scope"], how="left", validate="one_to_one")
        frame["season"] = year
        prepared[year] = frame

    scopes = ["Overall", "Fastball", "Breaking", "Offspeed"]
    adjusted_frames: list[pd.DataFrame] = []
    model_audits: list[dict[str, Any]] = []
    rng = np.random.default_rng(1301)
    for scope in scopes:
        train = prepared[development_year][
            prepared[development_year]["scope"].eq(scope)
            & prepared[development_year]["qualified"].fillna(False)
            & prepared[development_year][["season_early_stuff", "season_early_velocity", "stamina_plus"]].notna().all(axis=1)
        ].copy()
        if len(train) < 50:
            raise ValueError(f"Insufficient {development_year} qualified rows to fit {scope} season correction.")
        feature_columns = ["season_early_stuff", "season_early_velocity"]
        spline = SplineTransformer(n_knots=3, degree=2, include_bias=False, extrapolation="constant")
        scaler = StandardScaler()
        train_basis = scaler.fit_transform(spline.fit_transform(train[feature_columns].to_numpy(dtype="float64")))
        train_target = train["stamina_plus"].to_numpy(dtype="float64")
        train_weights = train["reliability"].clip(lower=0.10, upper=0.95).to_numpy(dtype="float64")
        model = Ridge(alpha=10.0)
        model.fit(train_basis, train_target, sample_weight=train_weights)
        train_prediction = model.predict(train_basis)
        prediction_center = float(np.average(train_prediction, weights=train_weights))

        scope_frames: list[pd.DataFrame] = []
        for year in years:
            frame = prepared[year][prepared[year]["scope"].eq(scope)].copy()
            valid = frame[feature_columns].notna().all(axis=1)
            frame["predicted_ceiling_component"] = np.nan
            frame["ceiling_correction"] = np.nan
            frame["correction_variance"] = np.nan
            basis = scaler.transform(spline.transform(frame.loc[valid, feature_columns].to_numpy(dtype="float64")))
            predictions = model.predict(basis)
            corrections = predictions - prediction_center
            bootstrap_corrections = np.zeros((100, len(basis)), dtype="float64")
            for replicate in range(100):
                sample_indexes = rng.integers(0, len(train), len(train))
                bootstrap_model = Ridge(alpha=10.0)
                bootstrap_model.fit(
                    train_basis[sample_indexes], train_target[sample_indexes],
                    sample_weight=train_weights[sample_indexes],
                )
                bootstrap_center = float(np.average(
                    bootstrap_model.predict(train_basis), weights=train_weights
                ))
                bootstrap_corrections[replicate] = bootstrap_model.predict(basis) - bootstrap_center
            correction_variance = np.var(bootstrap_corrections, axis=0, ddof=1)
            frame.loc[valid, "predicted_ceiling_component"] = predictions
            frame.loc[valid, "ceiling_correction"] = corrections
            frame.loc[valid, "correction_variance"] = correction_variance
            frame["adjusted_raw_stamina_plus"] = frame["stamina_plus"] - frame["ceiling_correction"]
            frame["adjusted_unweighted_stamina_plus"] = frame["unweighted_stamina_plus"] - frame["ceiling_correction"]
            original_se = (frame["ci_high"] - frame["ci_low"]) / (2.0 * 1.281552)
            adjusted_se2 = np.square(original_se) + frame["correction_variance"]
            frame["adjusted_stamina_plus"] = frame["adjusted_raw_stamina_plus"]
            frame["adjusted_ci_low"] = frame["adjusted_stamina_plus"] - 1.281552 * np.sqrt(adjusted_se2)
            frame["adjusted_ci_high"] = frame["adjusted_stamina_plus"] + 1.281552 * np.sqrt(adjusted_se2)
            frame["adjusted_reliability"] = (
                frame["reliability"] * np.square(original_se) / adjusted_se2
            ).clip(lower=0.0, upper=1.0)
            frame["adjusted_confidence"] = np.select(
                [frame["adjusted_reliability"].ge(0.80), frame["adjusted_reliability"].ge(0.60)],
                ["high", "medium"], default="low",
            )
            frame["adjusted_qualified"] = frame["qualified"] & frame["adjusted_reliability"].ge(0.70)
            frame["adjusted_rank"] = np.nan
            qualified_indexes = frame.index[
                frame["adjusted_qualified"] & frame["adjusted_stamina_plus"].notna()
            ]
            frame.loc[qualified_indexes, "adjusted_rank"] = frame.loc[
                qualified_indexes, "adjusted_stamina_plus"
            ].rank(method="min", ascending=False)
            scope_frames.append(frame)
        adjusted_frames.extend(scope_frames)
        model_audits.append({
            "scope": scope,
            "development_pitchers": int(len(train)),
            "ridge_alpha": 10.0,
            "spline_knots": 3,
            "spline_degree": 2,
            "prediction_center": round(prediction_center, 3),
        })

    adjusted = pd.concat(adjusted_frames, ignore_index=True, sort=False)
    audit_rows: list[dict[str, Any]] = []
    for (year, scope), frame in adjusted.groupby(["season", "scope"], sort=True):
        qualified = frame[
            frame["adjusted_qualified"] & frame["adjusted_stamina_plus"].notna()
        ].copy()
        before_sd = float(qualified["stamina_plus"].std(ddof=1))
        after_sd = float(qualified["adjusted_stamina_plus"].std(ddof=1))
        audit_rows.append({
            "year": int(year),
            "scope": str(scope),
            "qualified_pitchers": int(len(qualified)),
            "before_early_stuff_spearman": _rounded_correlation(
                _rank_correlation(qualified["stamina_plus"], qualified["season_early_stuff"])
            ),
            "after_early_stuff_spearman": _rounded_correlation(
                _rank_correlation(qualified["adjusted_stamina_plus"], qualified["season_early_stuff"])
            ),
            "before_early_velocity_spearman": _rounded_correlation(
                _rank_correlation(qualified["stamina_plus"], qualified["season_early_velocity"])
            ),
            "after_early_velocity_spearman": _rounded_correlation(
                _rank_correlation(qualified["adjusted_stamina_plus"], qualified["season_early_velocity"])
            ),
            "median_reliability": round(float(qualified["adjusted_reliability"].median()), 3),
            "median_interval_width": round(float(
                (qualified["adjusted_ci_high"] - qualified["adjusted_ci_low"]).median()
            ), 3),
            "weighted_vs_unweighted_spearman": _rounded_correlation(
                _rank_correlation(
                    qualified["adjusted_stamina_plus"], qualified["adjusted_unweighted_stamina_plus"]
                )
            ),
            "spread_retained_ratio": round(after_sd / before_sd, 3) if before_sd > 0 else None,
        })

    test_audits = [row for row in audit_rows if row["year"] == test_year]
    test_correlations = [
        abs(float(row[key]))
        for row in test_audits
        for key in ["after_early_stuff_spearman", "after_early_velocity_spearman"]
        if row.get(key) is not None
    ]
    preserved_slice13_gates = [
        gate for gate in external_validation.get("gates", []) if gate.get("key") != "season_ceiling_neutrality"
    ]
    gates = [
        {
            "key": "development_isolation",
            "label": "Development/test isolation",
            "threshold": "fit on 2025 only; evaluate once on 2026",
            "value": {"development_year": development_year, "test_year": test_year},
            "passed": development_year == test_year - 1,
        },
        {
            "key": "preserve_slice13_gates",
            "label": "Preserve prior passing gates",
            "threshold": "all eight non-season-ceiling Slice 13 gates remain passed",
            "value": sum(bool(gate.get("passed")) for gate in preserved_slice13_gates),
            "passed": len(preserved_slice13_gates) == 8 and all(bool(gate.get("passed")) for gate in preserved_slice13_gates),
        },
        {
            "key": "adjusted_season_ceiling_neutrality",
            "label": "Adjusted season ceiling neutrality",
            "threshold": "2026 max |rho| <= 0.20 across every scope and both early-quality features",
            "value": round(max(test_correlations), 3),
            "passed": bool(test_correlations) and max(test_correlations) <= 0.20,
        },
        {
            "key": "adjusted_precision",
            "label": "Adjusted season precision",
            "threshold": "2026 median reliability >= 0.70 and interval width <= 15 in every scope",
            "value": {
                "minimum_reliability": round(min(row["median_reliability"] for row in test_audits), 3),
                "maximum_interval_width": round(max(row["median_interval_width"] for row in test_audits), 3),
            },
            "passed": min(row["median_reliability"] for row in test_audits) >= 0.70
            and max(row["median_interval_width"] for row in test_audits) <= 15.0,
        },
        {
            "key": "adjusted_support",
            "label": "Adjusted qualified support",
            "threshold": "2026 has at least 100 reliability-qualified pitchers in every scope",
            "value": min(row["qualified_pitchers"] for row in test_audits),
            "passed": min(row["qualified_pitchers"] for row in test_audits) >= 100,
        },
        {
            "key": "adjusted_weighting_sensitivity",
            "label": "Adjusted weighting sensitivity",
            "threshold": "2026 weighted-vs-unweighted rho >= 0.90 in every scope",
            "value": round(min(row["weighted_vs_unweighted_spearman"] for row in test_audits), 3),
            "passed": min(row["weighted_vs_unweighted_spearman"] for row in test_audits) >= 0.90,
        },
        {
            "key": "signal_retention",
            "label": "Adjusted score spread retention",
            "threshold": "2026 retains at least 50% of original score spread in every scope",
            "value": round(min(row["spread_retained_ratio"] for row in test_audits), 3),
            "passed": min(row["spread_retained_ratio"] for row in test_audits) >= 0.50,
        },
    ]
    release_eligible = all(bool(gate["passed"]) for gate in gates)
    numeric_columns = [
        "season_early_stuff", "season_early_velocity", "predicted_ceiling_component", "ceiling_correction",
        "correction_variance", "adjusted_raw_stamina_plus", "adjusted_unweighted_stamina_plus",
        "adjusted_stamina_plus", "adjusted_ci_low", "adjusted_ci_high", "adjusted_reliability", "adjusted_rank",
    ]
    adjusted[numeric_columns] = adjusted[numeric_columns].round(3)
    result = {
        "status": "passed" if release_eligible else "failed",
        "publication_status": "validated_observed_state" if release_eligible else "research_only",
        "contract_version": "stamina_observed_season_bias_repair_v1_1",
        "development_year": int(development_year),
        "test_year": int(test_year),
        "leaderboard_release_eligible": release_eligible,
        "method": "Scope-specific low-degree splines of season early Stuff+ and velocity with Ridge alpha 10, trained only on 2025; 100 bootstrap refits add correction uncertainty.",
        "model_audits": model_audits,
        "season_audits": sorted(audit_rows, key=lambda row: (row["year"], scopes.index(row["scope"]))),
        "gates": gates,
        "warnings": [
            "The correction targets quality-neutral descriptive season state; it does not estimate physiology or predict a future start.",
            "Only 2026 is an untouched external season for this correction version.",
        ],
    }
    return adjusted, result


def _rounded_correlation(value: float | None) -> float | None:
    return round(float(value), 3) if value is not None and np.isfinite(value) else None


def _cold_start_early_summary(source: pd.DataFrame) -> pd.DataFrame:
    starters = source[source["appearance_role"].eq("SP")].copy()
    starters["game_date"] = pd.to_datetime(starters["game_date"], errors="coerce")
    early = starters[pd.to_numeric(starters["appearance_pitch_number"], errors="coerce").le(20)]
    summary = early.groupby(["pitcher", "game_pk"], as_index=False).agg(
        game_date=("game_date", "first"), pitcher_name=("player_name", "first"), team=("pitcher_team", "first"),
        early_stuff=("pitch_stuff_plus", "mean"), early_location=("location_plus_pitch", "mean"),
        early_velocity=("release_speed", "mean"), early_stuff_pitches=("pitch_stuff_plus", "count"),
        early_location_pitches=("location_plus_pitch", "count"), early_velocity_pitches=("release_speed", "count"),
    )
    totals = starters.groupby(["pitcher", "game_pk"], as_index=False).agg(
        total_pitches=("appearance_pitch_number", "max")
    )
    return summary.merge(totals, on=["pitcher", "game_pk"], how="left", validate="one_to_one")


def _cold_start_design(frame: pd.DataFrame) -> np.ndarray:
    early_stuff = pd.to_numeric(frame["early_pitch_type_baseline"], errors="coerce").to_numpy(dtype="float64")
    early_location = pd.to_numeric(frame["early_location"], errors="coerce").to_numpy(dtype="float64")
    workload = ((pd.to_numeric(frame["appearance_pitch_number"], errors="coerce") - 20.0) / 20.0).clip(lower=0).to_numpy(dtype="float64")
    family = pd.get_dummies(frame["pitch_family"], dtype="float64").reindex(columns=list(PITCH_FAMILY_TYPES), fill_value=0)
    centered_stuff = early_stuff - 100.0
    centered_location = early_location - 100.0
    return np.column_stack([
        np.ones(len(frame)), early_stuff, centered_location, centered_stuff * centered_location,
        workload, np.square(workload), family.to_numpy(dtype="float64"),
    ])


def _cold_start_appearance_table(
    curves: pd.DataFrame,
    source: pd.DataFrame,
    beta: np.ndarray,
) -> pd.DataFrame:
    early = _cold_start_early_summary(source)
    working = curves.merge(
        early[["pitcher", "game_pk", "early_location"]],
        on=["pitcher", "game_pk"], how="left", validate="many_to_one",
    )
    valid_model = (
        pd.to_numeric(working["appearance_pitch_number"], errors="coerce").gt(20)
        & working["early_pitch_type_baseline"].notna()
        & working["early_location"].notna()
        & working["context_adjusted_stuff"].notna()
    )
    working["predicted_late_stuff"] = np.nan
    working.loc[valid_model, "predicted_late_stuff"] = _cold_start_design(working.loc[valid_model]) @ beta
    working["retention_residual"] = working["context_adjusted_stuff"] - working["predicted_late_stuff"]
    working["raw_retention_delta"] = working["context_adjusted_stuff"] - working["early_pitch_type_baseline"]
    working["velocity_delta_pitch"] = working["release_speed"] - working["early_pitch_type_velocity"]
    target = working[
        pd.to_numeric(working["appearance_pitch_number"], errors="coerce").between(61, 80)
    ].copy()
    target_summary = target.groupby(["pitcher", "game_pk"], as_index=False).agg(
        game_retention=("retention_residual", "mean"), raw_retention_delta=("raw_retention_delta", "mean"),
        observed_late_stuff=("context_adjusted_stuff", "mean"), expected_late_stuff=("predicted_late_stuff", "mean"),
        velocity_delta=("velocity_delta_pitch", "mean"), late_pitches=("retention_residual", "count"),
        observation_weight=("observation_weight", "first"),
    )
    source_target = source[
        source["appearance_role"].eq("SP")
        & pd.to_numeric(source["appearance_pitch_number"], errors="coerce").between(61, 80)
    ].groupby(["pitcher", "game_pk"], as_index=False).agg(late_location=("location_plus_pitch", "mean"))
    result = early.merge(target_summary, on=["pitcher", "game_pk"], how="left", validate="one_to_one")
    result = result.merge(source_target, on=["pitcher", "game_pk"], how="left", validate="one_to_one")
    result["location_delta"] = result["late_location"] - result["early_location"]
    result["reached_61_80"] = result["total_pitches"].ge(61)
    result["retention_eligible"] = result["game_retention"].notna() & result["late_pitches"].ge(5)
    result = result.sort_values(["pitcher", "game_date", "game_pk"], kind="stable")
    result["season_start_number"] = result.groupby("pitcher").cumcount() + 1
    result["retention_start_number"] = result["retention_eligible"].astype(int).groupby(result["pitcher"]).cumsum()
    return result.reset_index(drop=True)


def _cold_start_prior_model(train_appearances: pd.DataFrame) -> tuple[Any, dict[str, float]]:
    from sklearn.linear_model import Ridge

    eligible = train_appearances[train_appearances["retention_eligible"]].dropna(
        subset=["game_retention", "early_stuff", "early_location", "early_velocity"]
    )
    pitchers = eligible.groupby("pitcher", as_index=False).agg(
        retention=("game_retention", "mean"), appearances=("game_pk", "size"),
        early_stuff=("early_stuff", "mean"), early_location=("early_location", "mean"),
        early_velocity=("early_velocity", "mean"),
    )
    feature_means = pitchers[["early_stuff", "early_location", "early_velocity"]].mean()
    feature_scales = pitchers[["early_stuff", "early_location", "early_velocity"]].std(ddof=1).replace(0, 1.0)
    x = (pitchers[["early_stuff", "early_location", "early_velocity"]] - feature_means) / feature_scales
    model = Ridge(alpha=10.0)
    model.fit(x, pitchers["retention"], sample_weight=pitchers["appearances"])
    pitchers["prior"] = model.predict(x)
    pitcher_mean = eligible.groupby("pitcher")["game_retention"].transform("mean")
    sigma2 = max(float(np.mean(np.square(eligible["game_retention"] - pitcher_mean))), 0.01)
    mean_inverse_n = float(np.mean(1.0 / pitchers["appearances"].clip(lower=1)))
    tau2 = max(float(np.var(pitchers["retention"] - pitchers["prior"], ddof=1)) - sigma2 * mean_inverse_n, 0.01)
    return model, {
        "stuff_mean": float(feature_means["early_stuff"]), "location_mean": float(feature_means["early_location"]),
        "velocity_mean": float(feature_means["early_velocity"]), "stuff_scale": float(feature_scales["early_stuff"]),
        "location_scale": float(feature_scales["early_location"]), "velocity_scale": float(feature_scales["early_velocity"]),
        "sigma2": sigma2, "tau2": tau2, "pitchers": int(len(pitchers)), "appearances": int(len(eligible)),
    }


def _cold_start_prior_prediction(model: Any, parameters: dict[str, float], frame: pd.DataFrame) -> np.ndarray:
    features = pd.DataFrame({
        "early_stuff": (frame["early_stuff"] - parameters["stuff_mean"]) / parameters["stuff_scale"],
        "early_location": (frame["early_location"] - parameters["location_mean"]) / parameters["location_scale"],
        "early_velocity": (frame["early_velocity"] - parameters["velocity_mean"]) / parameters["velocity_scale"],
    })
    return model.predict(features)


def _cold_start_checkpoint_metrics(backtest: pd.DataFrame, checkpoint: int) -> dict[str, Any]:
    sample = backtest[backtest["checkpoint"].eq(checkpoint)].dropna(subset=["future_retention", "posterior", "prior"])
    if sample.empty:
        return {
            "checkpoint": checkpoint, "pitchers": 0, "future_appearances": 0, "rmse": None,
            "baseline_rmse": None, "rmse_improvement_pct": None, "spearman_correlation": None,
            "calibration_slope": None, "interval_80_coverage_pct": None,
            "residual_early_stuff_spearman": None, "residual_early_velocity_spearman": None,
            "median_reliability": None, "gates": {}, "status": "insufficient",
        }
    observed = sample["future_retention"].to_numpy(dtype="float64")
    predicted = sample["posterior"].to_numpy(dtype="float64")
    baseline = sample["prior"].to_numpy(dtype="float64")
    rmse = float(np.sqrt(np.mean(np.square(observed - predicted))))
    baseline_rmse = float(np.sqrt(np.mean(np.square(observed - baseline))))
    improvement = (baseline_rmse - rmse) / baseline_rmse * 100.0 if baseline_rmse else 0.0
    def safe_spearman(left: Any, right: Any) -> float:
        left_series = pd.Series(left).reset_index(drop=True)
        right_series = pd.Series(right).reset_index(drop=True)
        if left_series.nunique(dropna=True) < 2 or right_series.nunique(dropna=True) < 2:
            return float("nan")
        return float(left_series.corr(right_series, method="spearman"))

    spearman = safe_spearman(observed, predicted)
    calibration = np.linalg.lstsq(np.column_stack([np.ones(len(predicted)), predicted]), observed, rcond=None)[0] if np.std(predicted) > 0 else [np.nan, np.nan]
    residual = observed - predicted
    early_stuff_corr = safe_spearman(residual, sample["early_stuff"])
    early_velocity_corr = safe_spearman(residual, sample["early_velocity"])
    coverage = float(sample["interval_contains"].mean() * 100.0)
    gates = {
        "common_pitchers": len(sample) >= 50,
        "future_skill": improvement > 0 and pd.notna(spearman) and float(spearman) >= 0.30,
        "calibration": np.isfinite(calibration[1]) and 0.80 <= float(calibration[1]) <= 1.20,
        "interval_coverage": 72.0 <= coverage <= 88.0,
        "early_stuff_neutral": pd.notna(early_stuff_corr) and abs(float(early_stuff_corr)) <= 0.10,
        "early_velocity_neutral": pd.notna(early_velocity_corr) and abs(float(early_velocity_corr)) <= 0.10,
    }
    return {
        "checkpoint": checkpoint, "pitchers": int(len(sample)),
        "future_appearances": int(sample["future_appearances"].sum()), "rmse": round(rmse, 3),
        "baseline_rmse": round(baseline_rmse, 3), "rmse_improvement_pct": round(improvement, 2),
        "spearman_correlation": round(float(spearman), 3) if pd.notna(spearman) else None,
        "calibration_slope": round(float(calibration[1]), 3) if np.isfinite(calibration[1]) else None,
        "interval_80_coverage_pct": round(coverage, 1),
        "residual_early_stuff_spearman": round(float(early_stuff_corr), 3) if pd.notna(early_stuff_corr) else None,
        "residual_early_velocity_spearman": round(float(early_velocity_corr), 3) if pd.notna(early_velocity_corr) else None,
        "median_reliability": round(float(sample["reliability"].median()), 3),
        "gates": gates, "status": "validated" if all(gates.values()) else "research_only",
    }


def _cold_start_checkpoint_rows(
    appearances: pd.DataFrame,
    prior_model: Any,
    prior_parameters: dict[str, float],
    checkpoints: list[int],
    fold: int | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    eligible = appearances[appearances["retention_eligible"]].dropna(
        subset=["game_retention", "early_stuff", "early_location", "early_velocity"]
    )
    for pitcher, pitcher_rows in eligible.groupby("pitcher", sort=False):
        pitcher_rows = pitcher_rows.sort_values(["game_date", "game_pk"], kind="stable").reset_index(drop=True)
        for checkpoint in checkpoints:
            if len(pitcher_rows) < checkpoint + 3:
                continue
            observed = pitcher_rows.iloc[:checkpoint]
            future = pitcher_rows.iloc[checkpoint:]
            profile = pd.DataFrame([{
                "early_stuff": float(observed["early_stuff"].mean()),
                "early_location": float(observed["early_location"].mean()),
                "early_velocity": float(observed["early_velocity"].mean()),
            }])
            prior = float(_cold_start_prior_prediction(prior_model, prior_parameters, profile)[0])
            row = {
                "pitcher": int(pitcher), "checkpoint": int(checkpoint),
                "observed_appearances": int(checkpoint), "future_appearances": int(len(future)),
                "prior": prior, "observed_retention": float(observed["game_retention"].mean()),
                "future_retention": float(future["game_retention"].mean()),
                "early_stuff": float(profile["early_stuff"].iloc[0]),
                "early_location": float(profile["early_location"].iloc[0]),
                "early_velocity": float(profile["early_velocity"].iloc[0]),
            }
            if fold is not None:
                row["fold"] = int(fold)
            rows.append(row)
    return rows


def _build_cold_start_v2(
    development_curves: pd.DataFrame,
    audit_curves: pd.DataFrame,
    development_source: pd.DataFrame,
    audit_source: pd.DataFrame,
    development_year: int,
    audit_year: int,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Learn shrinkage/interval calibration on cross-fitted development pitchers, then freeze it for audit."""
    checkpoints = [1, 3, 5, 8]
    development_curves, audit_curves = _cross_season_context_adjust(development_curves, audit_curves)
    development_early = _cold_start_early_summary(development_source)
    development_model = development_curves.merge(
        development_early[["pitcher", "game_pk", "early_location"]],
        on=["pitcher", "game_pk"], how="left", validate="many_to_one",
    )
    development_model = development_model[
        pd.to_numeric(development_model["appearance_pitch_number"], errors="coerce").between(21, 100)
        & development_model["early_pitch_type_baseline"].notna()
        & development_model["early_location"].notna()
        & development_model["context_adjusted_stuff"].notna()
    ].copy()
    x = _cold_start_design(development_model)
    y = development_model["context_adjusted_stuff"].to_numpy(dtype="float64")
    root_weight = np.sqrt(development_model["observation_weight"].fillna(1.0).to_numpy(dtype="float64"))
    beta = np.linalg.lstsq(x * root_weight[:, None], y * root_weight, rcond=None)[0]
    development_appearances = _cold_start_appearance_table(development_curves, development_source, beta)
    audit_appearances = _cold_start_appearance_table(audit_curves, audit_source, beta)

    eligible_development = development_appearances[development_appearances["retention_eligible"]].copy()
    pitchers = sorted(int(value) for value in eligible_development["pitcher"].dropna().unique())
    fold_count = min(5, len(pitchers))
    fold_by_pitcher = {pitcher: index % fold_count for index, pitcher in enumerate(pitchers)} if fold_count else {}
    development_rows: list[dict[str, Any]] = []
    for fold in range(fold_count):
        held_pitchers = {pitcher for pitcher, assigned in fold_by_pitcher.items() if assigned == fold}
        train = development_appearances[~development_appearances["pitcher"].isin(held_pitchers)]
        held = development_appearances[development_appearances["pitcher"].isin(held_pitchers)]
        prior_model, prior_parameters = _cold_start_prior_model(train)
        development_rows.extend(
            _cold_start_checkpoint_rows(held, prior_model, prior_parameters, checkpoints, fold=fold)
        )
    development = pd.DataFrame(development_rows)

    calibrations: list[dict[str, Any]] = []
    for checkpoint in checkpoints:
        mask = development["checkpoint"].eq(checkpoint) if not development.empty else pd.Series(dtype=bool)
        sample = development.loc[mask].copy() if not development.empty else pd.DataFrame()
        if sample.empty:
            personal_weight = 0.0
            interval_halfwidth = float("nan")
        else:
            personal_delta = sample["observed_retention"] - sample["prior"]
            future_delta = sample["future_retention"] - sample["prior"]
            denominator = float(np.dot(personal_delta, personal_delta))
            personal_weight = float(np.clip(np.dot(personal_delta, future_delta) / denominator, 0.0, 1.0)) if denominator else 0.0
            sample["posterior"] = sample["prior"] + personal_weight * personal_delta
            interval_halfwidth = float(np.quantile(np.abs(sample["future_retention"] - sample["posterior"]), 0.80))
            development.loc[mask, "posterior"] = sample["posterior"]
            development.loc[mask, "reliability"] = personal_weight
            development.loc[mask, "interval_80_low"] = sample["posterior"] - interval_halfwidth
            development.loc[mask, "interval_80_high"] = sample["posterior"] + interval_halfwidth
            development.loc[mask, "interval_contains"] = (
                (sample["future_retention"] >= sample["posterior"] - interval_halfwidth)
                & (sample["future_retention"] <= sample["posterior"] + interval_halfwidth)
            )
        calibrations.append({
            "checkpoint": checkpoint, "personal_weight": round(personal_weight, 4),
            "interval_80_halfwidth": round(interval_halfwidth, 4) if np.isfinite(interval_halfwidth) else None,
            "development_pitchers": int(len(sample)),
        })

    development_metrics = [_cold_start_checkpoint_metrics(development, checkpoint) for checkpoint in checkpoints]
    full_prior_model, full_prior_parameters = _cold_start_prior_model(development_appearances)
    audit = pd.DataFrame(_cold_start_checkpoint_rows(
        audit_appearances, full_prior_model, full_prior_parameters, checkpoints
    ))
    calibration_by_checkpoint = {row["checkpoint"]: row for row in calibrations}
    for checkpoint in checkpoints:
        mask = audit["checkpoint"].eq(checkpoint) if not audit.empty else pd.Series(dtype=bool)
        if audit.empty or not mask.any():
            continue
        calibration = calibration_by_checkpoint[checkpoint]
        personal_weight = float(calibration["personal_weight"])
        halfwidth = calibration["interval_80_halfwidth"]
        audit.loc[mask, "posterior"] = audit.loc[mask, "prior"] + personal_weight * (
            audit.loc[mask, "observed_retention"] - audit.loc[mask, "prior"]
        )
        audit.loc[mask, "reliability"] = personal_weight
        if halfwidth is not None:
            audit.loc[mask, "interval_80_low"] = audit.loc[mask, "posterior"] - float(halfwidth)
            audit.loc[mask, "interval_80_high"] = audit.loc[mask, "posterior"] + float(halfwidth)
            audit.loc[mask, "interval_contains"] = (
                (audit.loc[mask, "future_retention"] >= audit.loc[mask, "interval_80_low"])
                & (audit.loc[mask, "future_retention"] <= audit.loc[mask, "interval_80_high"])
            )
    audit_metrics = [_cold_start_checkpoint_metrics(audit, checkpoint) for checkpoint in checkpoints]
    audit_passed = [row["checkpoint"] for row in audit_metrics if row["status"] == "validated"]
    result = {
        "status": "ready", "publication_status": "research_only",
        "contract_version": "stamina_v2_slice11_cold_start_v2",
        "method": "Checkpoint-specific personal-data weights and 80% intervals are learned from five-fold pitcher-held-out 2025 pseudo-rookies, then frozen and applied to the 2026 external audit.",
        "development_year": int(development_year), "audit_year": int(audit_year), "target_window": "61–80",
        "development_rows": int(len(development)), "audit_rows": int(len(audit)),
        "development_pitchers": int(development["pitcher"].nunique()) if not development.empty else 0,
        "audit_pitchers": int(audit["pitcher"].nunique()) if not audit.empty else 0,
        "prior_pitchers": int(full_prior_parameters["pitchers"]),
        "prior_appearances": int(full_prior_parameters["appearances"]),
        "calibrations": calibrations, "development_checkpoints": development_metrics,
        "audit_checkpoints": audit_metrics, "audit_passed_checkpoints": audit_passed,
        "formal_release_eligible": False, "candidate_rows": 0,
        "release_gates": [
            "at least 50 pitchers with 3 or more future eligible starts",
            "RMSE improvement >0 and Spearman >=0.30 versus the peer prior",
            "calibration slope 0.80–1.20 and frozen 80% interval coverage 72–88%",
            "absolute residual correlation <=0.10 versus early Stuff+ and velocity",
        ],
        "warnings": [
            "The 2025 development rows use pitcher-held-out peer priors, so each pseudo-rookie's prior excludes that pitcher.",
            "The 2026 audit is external to calibration, but it is not a pristine blind release set because earlier v1 results were already inspected.",
            "Even a fully passing checkpoint remains research-only here; formal release requires a future untouched season under the frozen contract.",
            "Retention remains conditional on reaching pitches 61–80; reach/depth is not converted into physiological stamina.",
        ],
    }
    return development, audit, result


def _build_cold_start_research(
    train_curves: pd.DataFrame,
    test_curves: pd.DataFrame,
    train_source: pd.DataFrame,
    test_source: pd.DataFrame,
    train_year: int,
    test_year: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    train_curves, test_curves = _cross_season_context_adjust(train_curves, test_curves)
    train_early = _cold_start_early_summary(train_source)
    test_early = _cold_start_early_summary(test_source)
    train_model = train_curves.merge(
        train_early[["pitcher", "game_pk", "early_location"]], on=["pitcher", "game_pk"], how="left"
    )
    train_model = train_model[
        pd.to_numeric(train_model["appearance_pitch_number"], errors="coerce").between(21, 100)
        & train_model["early_pitch_type_baseline"].notna()
        & train_model["early_location"].notna()
        & train_model["context_adjusted_stuff"].notna()
    ].copy()
    x = _cold_start_design(train_model)
    y = train_model["context_adjusted_stuff"].to_numpy(dtype="float64")
    weights = train_model["observation_weight"].fillna(1.0).to_numpy(dtype="float64")
    root_weight = np.sqrt(weights)
    beta = np.linalg.lstsq(x * root_weight[:, None], y * root_weight, rcond=None)[0]
    train_appearances = _cold_start_appearance_table(train_curves, train_source, beta)
    test_appearances = _cold_start_appearance_table(test_curves, test_source, beta)
    prior_model, prior_parameters = _cold_start_prior_model(train_appearances)
    sigma2 = prior_parameters["sigma2"]
    tau2 = prior_parameters["tau2"]
    backtest_rows = []
    checkpoints = [1, 3, 5, 8]
    eligible_test = test_appearances[test_appearances["retention_eligible"]].copy()
    for pitcher, pitcher_rows in eligible_test.groupby("pitcher", sort=False):
        pitcher_rows = pitcher_rows.sort_values(["game_date", "game_pk"], kind="stable").reset_index(drop=True)
        for checkpoint in checkpoints:
            if len(pitcher_rows) < checkpoint + 3:
                continue
            observed = pitcher_rows.iloc[:checkpoint]
            future = pitcher_rows.iloc[checkpoint:]
            profile = pd.DataFrame([{
                "early_stuff": float(observed["early_stuff"].mean()),
                "early_location": float(observed["early_location"].mean()),
                "early_velocity": float(observed["early_velocity"].mean()),
            }])
            prior = float(_cold_start_prior_prediction(prior_model, prior_parameters, profile)[0])
            reliability = float(tau2 / (tau2 + sigma2 / checkpoint))
            posterior = reliability * float(observed["game_retention"].mean()) + (1.0 - reliability) * prior
            posterior_variance = 1.0 / (1.0 / tau2 + checkpoint / sigma2)
            future_mean = float(future["game_retention"].mean())
            prediction_se = float(np.sqrt(posterior_variance + sigma2 / len(future)))
            interval_low = posterior - 1.281552 * prediction_se
            interval_high = posterior + 1.281552 * prediction_se
            backtest_rows.append({
                "pitcher": int(pitcher), "checkpoint": checkpoint, "observed_appearances": checkpoint,
                "future_appearances": int(len(future)), "prior": prior, "posterior": posterior,
                "future_retention": future_mean, "reliability": reliability,
                "interval_80_low": interval_low, "interval_80_high": interval_high,
                "interval_contains": bool(interval_low <= future_mean <= interval_high),
                "early_stuff": float(profile["early_stuff"].iloc[0]),
                "early_location": float(profile["early_location"].iloc[0]),
                "early_velocity": float(profile["early_velocity"].iloc[0]),
            })
    backtest = pd.DataFrame(backtest_rows)
    checkpoint_metrics = [_cold_start_checkpoint_metrics(backtest, checkpoint) for checkpoint in checkpoints]
    validated = [row["checkpoint"] for row in checkpoint_metrics if row["status"] == "validated"]
    validated_checkpoint = min(validated) if validated else None
    candidate_columns = [
        "pitcher", "pitcher_name", "team", "season", "stamina_plus", "posterior_retention",
        "ci_low", "ci_high", "reliability", "retention_appearances", "total_starts", "late_pitches",
        "prior_source", "status", "publication_status",
    ]
    candidate_rows = []
    if validated_checkpoint is not None:
        for pitcher, rows in eligible_test.groupby("pitcher", sort=False):
            if len(rows) < validated_checkpoint:
                continue
            profile = pd.DataFrame([{
                "early_stuff": float(rows["early_stuff"].mean()), "early_location": float(rows["early_location"].mean()),
                "early_velocity": float(rows["early_velocity"].mean()),
            }])
            prior = float(_cold_start_prior_prediction(prior_model, prior_parameters, profile)[0])
            reliability = float(tau2 / (tau2 + sigma2 / len(rows)))
            posterior = reliability * float(rows["game_retention"].mean()) + (1.0 - reliability) * prior
            posterior_se = float(np.sqrt(1.0 / (1.0 / tau2 + len(rows) / sigma2)))
            scale = float(np.sqrt(tau2))
            all_pitcher = test_appearances[test_appearances["pitcher"].eq(pitcher)]
            candidate_rows.append({
                "pitcher": int(pitcher), "pitcher_name": str(rows["pitcher_name"].iloc[-1]),
                "team": str(rows["team"].iloc[-1]), "season": int(test_year),
                "stamina_plus": round(100.0 + 10.0 * posterior / scale, 1),
                "posterior_retention": round(posterior, 4),
                "ci_low": round(100.0 + 10.0 * (posterior - 1.96 * posterior_se) / scale, 1),
                "ci_high": round(100.0 + 10.0 * (posterior + 1.96 * posterior_se) / scale, 1),
                "reliability": round(reliability, 4), "retention_appearances": int(len(rows)),
                "total_starts": int(len(all_pitcher)), "late_pitches": int(rows["late_pitches"].sum()),
                "prior_source": "2025 peer-profile hierarchical prior", "status": "provisional",
                "publication_status": "lab_candidate_not_downstream",
            })
    candidates = pd.DataFrame(candidate_rows, columns=candidate_columns)
    appearance_columns = [
        "pitcher", "pitcher_name", "team", "game_pk", "game_date", "season_start_number",
        "retention_start_number", "total_pitches", "reached_61_80", "retention_eligible",
        "early_stuff", "early_location", "early_velocity", "game_retention", "raw_retention_delta",
        "observed_late_stuff", "expected_late_stuff", "velocity_delta", "location_delta", "late_pitches",
        "observation_weight",
    ]
    appearances = test_appearances[appearance_columns].copy()
    pitch_test = test_curves.merge(
        test_early[["pitcher", "game_pk", "early_location"]], on=["pitcher", "game_pk"], how="left"
    )
    pitch_test = pitch_test[
        pd.to_numeric(pitch_test["appearance_pitch_number"], errors="coerce").between(21, 100)
        & pitch_test["early_pitch_type_baseline"].notna() & pitch_test["early_location"].notna()
    ].dropna(subset=["context_adjusted_stuff"])
    prediction = _cold_start_design(pitch_test) @ beta
    observed = pitch_test["context_adjusted_stuff"].to_numpy(dtype="float64")
    baseline_prediction = pitch_test["early_pitch_type_baseline"].to_numpy(dtype="float64")
    pitch_rmse = float(np.sqrt(np.mean(np.square(observed - prediction))))
    pitch_baseline_rmse = float(np.sqrt(np.mean(np.square(observed - baseline_prediction))))
    pitch_improvement = (pitch_baseline_rmse - pitch_rmse) / pitch_baseline_rmse * 100.0
    result = {
        "status": "ready", "publication_status": "provisional_candidate" if len(candidates) else "research_only",
        "contract_version": "stamina_v2_slice11_cold_start_v1",
        "method": "2025-only conditional late-pitch model plus a peer-profile empirical-Bayes prior; 2026 pitchers are replayed as pseudo-rookies after 1, 3, 5 and 8 eligible 61–80-pitch starts.",
        "train_year": int(train_year), "test_year": int(test_year), "target_window": "61–80",
        "appearance_rows": int(len(appearances)), "eligible_retention_appearances": int(appearances["retention_eligible"].sum()),
        "reached_61_80_appearances": int(appearances["reached_61_80"].sum()),
        "prior_pitchers": int(prior_parameters["pitchers"]), "prior_appearances": int(prior_parameters["appearances"]),
        "between_pitcher_sd": round(float(np.sqrt(tau2)), 4), "within_pitcher_sd": round(float(np.sqrt(sigma2)), 4),
        "pitch_model_rmse": round(pitch_rmse, 3), "pitch_baseline_rmse": round(pitch_baseline_rmse, 3),
        "pitch_rmse_improvement_pct": round(pitch_improvement, 2),
        "checkpoints": checkpoint_metrics, "validated_checkpoint": validated_checkpoint,
        "candidate_rows": int(len(candidates)),
        "release_gates": [
            "at least 50 pitchers with 3 or more future eligible starts",
            "RMSE improvement >0 and Spearman >=0.30 versus the peer prior",
            "calibration slope 0.80–1.20 and 80% interval coverage 72–88%",
            "absolute residual correlation <=0.10 versus early Stuff+ and velocity",
        ],
        "warnings": [
            "One start can produce Game Retention, but a single-season Stamina+ candidate is emitted only if a pseudo-rookie checkpoint passes every release gate.",
            "Retention is conditional on reaching pitches 61–80; reach/depth remains a separate observed field and is not scored as physiological stamina.",
            "The peer prior uses only 2025 pitcher profiles; no 2026 future start or prior personal season is required for a rookie estimate.",
            "Location+, velocity and raw late-minus-early values remain diagnostics and are not manually weighted into the primary score.",
        ],
    }
    return appearances, backtest, candidates, result


def _build_slice4(frame: pd.DataFrame, year: int, data_dir: Path) -> dict[str, Any]:
    readiness = _appearance_quality_table(frame)
    retention = _appearance_retention_table(frame)
    readiness_effects: list[dict[str, Any]] = []
    retention_effects: list[dict[str, Any]] = []
    season_effects: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    validations: list[dict[str, Any]] = []
    for role in ["SP", "RP"]:
        for outcome, label in [("pitch_stuff_plus", "Stuff+"), ("location_plus_pitch", "Location+")]:
            readiness_metric = f"readiness_{outcome}"
            ready_sample = readiness[readiness["appearance_role"].eq(role)].dropna(subset=[readiness_metric]).copy()
            ready_fit = _fit_workload_effects(ready_sample, readiness_metric, role, outcome, label, "readiness")
            readiness_effects.extend(ready_fit["effects"])
            diagnostics.append(ready_fit["diagnostic"])
            season_effects.extend([
                {**row, "analysis": "season_load"}
                for row in ready_fit["effects"] if row["feature"] in {"season_pitches_500", "calendar_month", "calendar_month_sq"}
            ])
            retention_metric = f"retention_{outcome}"
            retention_sample = retention[retention["appearance_role"].eq(role)].dropna(subset=[retention_metric]).copy()
            retention_fit = _fit_workload_effects(retention_sample, retention_metric, role, outcome, label, "retention")
            retention_effects.extend(retention_fit["effects"])
            diagnostics.append(retention_fit["diagnostic"])
            season_effects.extend([
                {**row, "analysis": "season_load"}
                for row in retention_fit["effects"] if row["feature"] in {"season_pitches_500", "calendar_month", "calendar_month_sq"}
            ])
            validations.append(_time_validation(ready_sample, readiness_metric, role, outcome, label, "readiness", int(year)))
            validations.append(_time_validation(retention_sample, retention_metric, role, outcome, label, "retention", int(year)))
    cross_season = _cross_season_validation(readiness, int(year), data_dir)
    audit_features = [
        ("Previous appearance pitches", "previous_appearance_pitches"),
        ("Prior 3-day pitches", "workload_pitches_3d"),
        ("Prior 7-day pitches", "workload_pitches_7d"),
        ("Prior 14-day pitches", "workload_pitches_14d"),
        ("Prior 28-day pitches", "workload_pitches_28d"),
        ("All-role season pitches", "all_role_season_pitches_before"),
        ("Role transition", "role_changed"),
    ]
    workload_audit = [{
        "feature": label,
        "field": field,
        "coverage_pct": _pct(frame[field].notna().sum(), len(frame)),
        "lagged_only": True,
    } for label, field in audit_features]
    return {
        "status": "ready" if readiness_effects and retention_effects else "insufficient",
        "method": "Pitcher fixed-effects workload models using only pre-appearance workload; readiness is pitch-type-normalized early-window quality and retention is the Slice 2 weighted within-appearance slope.",
        "workload_audit": workload_audit,
        "readiness_effects": readiness_effects,
        "retention_effects": retention_effects,
        "season_effects": season_effects,
        "diagnostics": diagnostics,
        "time_validation": validations,
        "cross_season_validation": cross_season,
        "warnings": [
            "All workload features stop before the current appearance; current-game final pitch count is never used as a predictor.",
            "Role-specific models use all-role physiological workload, so an SP-to-RP or RP-to-SP transition does not reset cumulative load.",
            "Location+ remains a secondary endpoint because Slice 3 individual repeatability was weak.",
            "Warm-up pitches, private health, soreness, sleep and manager intent remain unobserved.",
        ],
    }


def _appearance_quality_table(frame: pd.DataFrame) -> pd.DataFrame:
    working = frame[
        frame["pitch_type"].notna()
        & frame["pitch_stuff_plus"].notna()
        & frame["location_plus_pitch"].notna()
    ].copy()
    early_limit = np.where(working["appearance_role"].eq("SP"), 20, 5)
    working = working[working["appearance_pitch_number"].le(early_limit)].copy()
    keys = ["pitcher", "appearance_role", "pitch_type", "game_pk", "game_date"]
    for outcome in ["pitch_stuff_plus", "location_plus_pitch"]:
        history = working.groupby(keys, as_index=False).agg(outcome_sum=(outcome, "sum"), outcome_count=(outcome, "count"))
        history = history.sort_values(["pitcher", "appearance_role", "pitch_type", "game_date", "game_pk"], kind="stable")
        groups = history.groupby(["pitcher", "appearance_role", "pitch_type"], sort=False)
        history["prior_sum"] = groups["outcome_sum"].cumsum() - history["outcome_sum"]
        history["prior_count"] = groups["outcome_count"].cumsum() - history["outcome_count"]
        history[f"baseline_{outcome}"] = np.where(history["prior_count"].ge(20), history["prior_sum"] / history["prior_count"], np.nan)
        working = working.merge(history[[*keys, f"baseline_{outcome}"]], on=keys, how="left")
        working[f"readiness_{outcome}"] = working[outcome] - working[f"baseline_{outcome}"]
    workload_columns = _workload_columns()
    aggregation: dict[str, tuple[str, str]] = {
        "readiness_pitch_stuff_plus": ("readiness_pitch_stuff_plus", "mean"),
        "readiness_location_plus_pitch": ("readiness_location_plus_pitch", "mean"),
        "game_date": ("game_date", "first"),
        "appearance_role": ("appearance_role", "first"),
    }
    aggregation.update({column: (column, "first") for column in workload_columns})
    return working.groupby(["pitcher", "game_pk"], as_index=False).agg(**aggregation)


def _appearance_retention_table(frame: pd.DataFrame) -> pd.DataFrame:
    workload_columns = _workload_columns()
    appearance_context = frame.groupby(["pitcher", "game_pk"], as_index=False).agg(
        game_date=("game_date", "first"), appearance_role=("appearance_role", "first"),
        **{column: (column, "first") for column in workload_columns},
    )
    rows: list[dict[str, Any]] = []
    for role in ["SP", "RP"]:
        role_frame = frame[
            frame["appearance_role"].eq(role)
            & frame["pitch_stuff_plus"].notna()
            & frame["location_plus_pitch"].notna()
            & frame["pitch_type"].notna()
        ].copy()
        buckets = SP_BUCKETS if role == "SP" else RP_BUCKETS
        unit = 20.0 if role == "SP" else 5.0
        observations = _pitcher_retention_observations(role_frame, buckets, unit)
        for (pitcher, game_pk, outcome), group in observations.groupby(["pitcher", "game_pk", "outcome"], sort=False):
            if group["target_bucket"].nunique() < 2:
                continue
            slope, _ = _weighted_slope_with_clustered_se(group)
            rows.append({"pitcher": int(pitcher), "game_pk": int(game_pk), "outcome": outcome, "slope": slope})
    if not rows:
        empty = appearance_context.iloc[0:0].copy()
        empty["retention_pitch_stuff_plus"] = pd.Series(dtype="float64")
        empty["retention_location_plus_pitch"] = pd.Series(dtype="float64")
        return empty
    slopes = pd.DataFrame(rows).pivot(index=["pitcher", "game_pk"], columns="outcome", values="slope").reset_index()
    slopes = slopes.rename(columns={
        "pitch_stuff_plus": "retention_pitch_stuff_plus",
        "location_plus_pitch": "retention_location_plus_pitch",
    })
    return appearance_context.merge(slopes, on=["pitcher", "game_pk"], how="inner")


def _workload_columns() -> list[str]:
    return [
        "days_rest", "appearance_number", "season_pitches_before", "all_role_appearance_number",
        "all_role_season_pitches_before", "previous_appearance_pitches", "workload_pitches_3d",
        "workload_pitches_7d", "workload_pitches_14d", "workload_pitches_28d",
        "workload_appearances_3d", "workload_appearances_7d", "workload_appearances_14d",
        "workload_appearances_28d", "back_to_back", "long_gap", "role_changed",
    ]


def _workload_design(sample: pd.DataFrame, role: str) -> tuple[pd.DataFrame, dict[str, tuple[str, str]]]:
    unit = 20.0 if role == "SP" else 5.0
    design = pd.DataFrame(index=sample.index)
    design["previous_load_unit"] = pd.to_numeric(sample["previous_appearance_pitches"], errors="coerce").fillna(0) / unit
    design["acute_3d_unit"] = pd.to_numeric(sample["workload_pitches_3d"], errors="coerce").fillna(0) / unit
    design["medium_4_14d_unit"] = (
        pd.to_numeric(sample["workload_pitches_14d"], errors="coerce").fillna(0)
        - pd.to_numeric(sample["workload_pitches_3d"], errors="coerce").fillna(0)
    ) / unit
    design["chronic_15_28d_unit"] = (
        pd.to_numeric(sample["workload_pitches_28d"], errors="coerce").fillna(0)
        - pd.to_numeric(sample["workload_pitches_14d"], errors="coerce").fillna(0)
    ) / unit
    design["season_pitches_500"] = pd.to_numeric(sample["all_role_season_pitches_before"], errors="coerce").fillna(0) / 500.0
    design["role_changed"] = pd.to_numeric(sample["role_changed"], errors="coerce").fillna(0)
    start = pd.to_datetime(sample["game_date"], errors="coerce").min()
    calendar = (pd.to_datetime(sample["game_date"], errors="coerce") - start).dt.days.fillna(0) / 30.0
    design["calendar_month"] = calendar
    design["calendar_month_sq"] = calendar**2
    rest = pd.to_numeric(sample["days_rest"], errors="coerce")
    if role == "SP":
        rest_group = pd.cut(rest, [-1, 2, 3, 4, 5, 6, 13, np.inf], labels=["0–2", "3", "4", "5", "6", "7–13", "14+"])
        reference = "4"
    else:
        rest_group = pd.cut(rest, [-1, 0, 1, 2, 6, 13, np.inf], labels=["0", "1", "2", "3–6", "7–13", "14+"])
        reference = "1"
    for label in rest_group.cat.categories:
        if str(label) != reference:
            design[f"rest_{label}"] = rest_group.astype("object").eq(label).astype(float)
    metadata = {
        "previous_load_unit": ("Previous appearance workload", f"per {int(unit)} pitches"),
        "acute_3d_unit": ("Prior 3-day workload", f"per {int(unit)} pitches"),
        "medium_4_14d_unit": ("Prior 4–14 day workload", f"per {int(unit)} pitches"),
        "chronic_15_28d_unit": ("Prior 15–28 day workload", f"per {int(unit)} pitches"),
        "season_pitches_500": ("All-role season workload", "per 500 pitches"),
        "role_changed": ("Role changed since prior appearance", "yes vs no"),
        "calendar_month": ("Season calendar", "per month"),
        "calendar_month_sq": ("Season calendar curvature", "month²"),
    }
    metadata.update({column: (f"Rest {column.removeprefix('rest_')} days", f"vs {reference} days") for column in design if column.startswith("rest_")})
    return design, metadata


def _fit_workload_effects(
    sample: pd.DataFrame,
    metric: str,
    role: str,
    outcome: str,
    outcome_label: str,
    endpoint: str,
) -> dict[str, Any]:
    working = sample[pd.to_numeric(sample["all_role_appearance_number"], errors="coerce").gt(1)].copy()
    design, metadata = _workload_design(working, role)
    y = pd.to_numeric(working[metric], errors="coerce")
    valid = y.notna() & design.notna().all(axis=1)
    working, design, y = working.loc[valid], design.loc[valid], y.loc[valid]
    pitcher_means = design.groupby(working["pitcher"]).transform("mean")
    transformed_x = design - pitcher_means
    transformed_y = y - y.groupby(working["pitcher"]).transform("mean")
    varying = transformed_x.abs().sum(axis=0).gt(1e-9)
    transformed_x = transformed_x.loc[:, varying]
    clusters = pd.factorize(working["pitcher"], sort=True)[0]
    if len(working) <= len(transformed_x.columns) or transformed_x.empty:
        return {"effects": [], "diagnostic": {"endpoint": endpoint, "role": role, "outcome": outcome, "status": "insufficient", "appearances": int(len(working)), "pitchers": int(working["pitcher"].nunique()), "within_r_squared": 0.0}}
    beta, standard_errors, r_squared = _cluster_ols(
        transformed_x.to_numpy(dtype="float64"), transformed_y.to_numpy(dtype="float64"), clusters
    )
    effects = []
    for index, feature in enumerate(transformed_x.columns):
        estimate, standard_error = float(beta[index]), float(standard_errors[index])
        within_sd = float(transformed_x[feature].std(ddof=0))
        standardized_effect = estimate * within_sd
        label, unit = metadata[feature]
        effects.append({
            "analysis": endpoint, "endpoint": endpoint, "role": role, "outcome": outcome,
            "outcome_label": outcome_label, "feature": feature, "feature_label": label, "unit": unit,
            "estimate": round(estimate, 3), "ci_low": round(estimate - 1.96 * standard_error, 3),
            "ci_high": round(estimate + 1.96 * standard_error, 3),
            "within_pitcher_sd": round(within_sd, 3),
            "standardized_effect": round(standardized_effect, 3),
            "significant": bool(estimate - 1.96 * standard_error > 0 or estimate + 1.96 * standard_error < 0),
            "appearances": int(len(working)), "pitchers": int(working["pitcher"].nunique()),
        })
    maximum_effect = max((abs(row["standardized_effect"]) for row in effects), default=0.0)
    for row in effects:
        row["relative_strength_pct"] = round(abs(row["standardized_effect"]) / maximum_effect * 100, 1) if maximum_effect > 0 else 0.0
    return {
        "effects": effects,
        "diagnostic": {"endpoint": endpoint, "role": role, "outcome": outcome, "status": "ready", "appearances": int(len(working)), "pitchers": int(working["pitcher"].nunique()), "within_r_squared": round(r_squared, 3)},
    }


def _time_validation(
    sample: pd.DataFrame,
    metric: str,
    role: str,
    outcome: str,
    outcome_label: str,
    endpoint: str,
    year: int,
) -> dict[str, Any]:
    working = sample.dropna(subset=[metric, "game_date"]).sort_values("game_date").copy()
    if len(working) < 100:
        return {"validation": "time_split", "year": year, "role": role, "outcome": outcome, "outcome_label": outcome_label, "endpoint": endpoint, "status": "insufficient", "train_appearances": 0, "test_appearances": 0}
    cutoff = pd.to_datetime(working["game_date"]).quantile(0.70)
    train = working[pd.to_datetime(working["game_date"]).le(cutoff)]
    test = working[pd.to_datetime(working["game_date"]).gt(cutoff)]
    return _predictive_validation(train, test, metric, role, outcome, outcome_label, endpoint, "time_split", year, year)


def _cross_season_validation(current_readiness: pd.DataFrame, year: int, data_dir: Path) -> list[dict[str, Any]]:
    prior_year = year - 1
    prior_path = stamina_dataset_path(prior_year, data_dir)
    if not prior_path.exists():
        return [{"validation": "cross_season", "train_year": prior_year, "test_year": year, "status": "unavailable", "reason": f"Missing {prior_path.name}"}]
    with duckdb.connect() as connection:
        prior = connection.execute("SELECT * FROM read_parquet(?)", [str(prior_path)]).fetchdf()
    required = set(_workload_columns()) | {"pitch_stuff_plus", "location_plus_pitch", "pitch_type", "appearance_role"}
    if not required.issubset(prior.columns):
        return [{"validation": "cross_season", "train_year": prior_year, "test_year": year, "status": "unavailable", "reason": "Prior Stamina dataset predates Slice 4 workload fields."}]
    source_coverage_pct = _pct(
        (prior["pitch_stuff_plus"].notna() & prior["location_plus_pitch"].notna()).sum(),
        len(prior),
    )
    prior_readiness = _appearance_quality_table(prior)
    results = []
    for role in ["SP", "RP"]:
        for outcome, label in [("pitch_stuff_plus", "Stuff+"), ("location_plus_pitch", "Location+")]:
            metric = f"readiness_{outcome}"
            train = prior_readiness[prior_readiness["appearance_role"].eq(role)].dropna(subset=[metric])
            test = current_readiness[current_readiness["appearance_role"].eq(role)].dropna(subset=[metric])
            result = _predictive_validation(train, test, metric, role, outcome, label, "readiness", "cross_season", prior_year, year)
            result["source_coverage_pct"] = source_coverage_pct
            if source_coverage_pct < 95.0 and result["status"] not in {"insufficient", "unavailable"}:
                result["status"] = f"provisional_{result['status']}"
                result["reason"] = "Historical Stuff+ coverage is incomplete; use this cross-season result only as a pipeline smoke test."
            results.append(result)
    return results


def _predictive_validation(
    train: pd.DataFrame,
    test: pd.DataFrame,
    metric: str,
    role: str,
    outcome: str,
    outcome_label: str,
    endpoint: str,
    validation: str,
    train_year: int,
    test_year: int,
) -> dict[str, Any]:
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    train_x, _ = _workload_design(train, role)
    test_x, _ = _workload_design(test, role)
    train_x, test_x = train_x.align(test_x, join="left", axis=1, fill_value=0)
    train_y = pd.to_numeric(train[metric], errors="coerce").to_numpy(dtype="float64")
    test_y = pd.to_numeric(test[metric], errors="coerce").to_numpy(dtype="float64")
    if len(train) < 100 or len(test) < 50:
        return {"validation": validation, "train_year": train_year, "test_year": test_year, "role": role, "outcome": outcome, "outcome_label": outcome_label, "endpoint": endpoint, "status": "insufficient", "train_appearances": int(len(train)), "test_appearances": int(len(test))}
    model = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), Ridge(alpha=10.0))
    model.fit(train_x, train_y)
    predicted = model.predict(test_x)
    baseline = np.repeat(float(np.mean(train_y)), len(test_y))
    rmse = float(np.sqrt(np.mean((test_y - predicted) ** 2)))
    baseline_rmse = float(np.sqrt(np.mean((test_y - baseline) ** 2)))
    mae = float(np.mean(np.abs(test_y - predicted)))
    correlation = float(pd.Series(predicted).corr(pd.Series(test_y))) if np.std(predicted) > 0 and np.std(test_y) > 0 else 0.0
    return {
        "validation": validation, "train_year": train_year, "test_year": test_year, "role": role,
        "outcome": outcome, "outcome_label": outcome_label, "endpoint": endpoint,
        "status": "improves" if rmse < baseline_rmse else "no_gain",
        "train_appearances": int(len(train)), "test_appearances": int(len(test)),
        "correlation": round(correlation, 3), "rmse": round(rmse, 3),
        "baseline_rmse": round(baseline_rmse, 3), "mae": round(mae, 3),
        "rmse_improvement_pct": round((baseline_rmse - rmse) / baseline_rmse * 100.0, 2) if baseline_rmse else 0.0,
    }


def _cross_fitted_reach_probability(frame: pd.DataFrame) -> tuple[np.ndarray, dict[str, Any]]:
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import GroupKFold
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    features = ["pitch_stuff_plus", "location_plus_pitch", "release_speed", "days_rest", "season_pitches_before", "appearance_number", "prior_avg_pitches"]
    x = frame[features]
    y = frame["reached"].to_numpy(dtype="int64")
    groups = frame["pitcher"].to_numpy()
    predictions = np.full(len(frame), float(y.mean()), dtype="float64")
    folds = min(5, max(2, int(frame["pitcher"].nunique())))
    splitter = GroupKFold(n_splits=folds)
    for train, test in splitter.split(x, y, groups):
        if np.unique(y[train]).size < 2:
            continue
        model = make_pipeline(
            ColumnTransformer([("numeric", make_pipeline(SimpleImputer(strategy="median"), StandardScaler()), features)]),
            LogisticRegression(max_iter=1000, class_weight=None),
        )
        model.fit(x.iloc[train], y[train])
        predictions[test] = model.predict_proba(x.iloc[test])[:, 1]
    predictions = np.clip(predictions, 0.03, 0.97)
    auc = float(roc_auc_score(y, predictions)) if np.unique(y).size == 2 else 0.5
    return predictions, {"auc": round(auc, 3), "features": features, "cross_fit": "GroupKFold by pitcher"}


def _clustered_weighted_mean(values: np.ndarray, weights: np.ndarray, clusters: np.ndarray) -> tuple[float, float]:
    valid = np.isfinite(values) & np.isfinite(weights) & (weights > 0)
    values = values[valid]
    weights = weights[valid]
    clusters = clusters[valid]
    total_weight = float(weights.sum())
    mean = float(np.sum(weights * values) / total_weight)
    codes = pd.factorize(clusters, sort=True)[0]
    influence = weights * (values - mean) / total_weight
    cluster_scores = np.zeros(int(codes.max()) + 1, dtype="float64")
    np.add.at(cluster_scores, codes, influence)
    variance = float(np.sum(cluster_scores**2))
    if len(cluster_scores) > 1:
        variance *= len(cluster_scores) / (len(cluster_scores) - 1)
    return mean, float(np.sqrt(max(variance, 0.0)))


def _effective_sample_size(weights: np.ndarray) -> float:
    return float(weights.sum() ** 2 / np.sum(weights**2)) if len(weights) and np.sum(weights**2) else 0.0


def _season_fixed_cohort(frame: pd.DataFrame, role: str) -> list[dict[str, Any]]:
    buckets = SP_SEASON_BUCKETS if role == "SP" else RP_SEASON_BUCKETS
    working = frame.copy()
    working["season_bucket"] = _assign_bucket(working["season_pitches_before"], buckets)
    pitcher_bucket = working.dropna(subset=["season_bucket"]).groupby(["pitcher", "season_bucket"], as_index=False).agg(
        pitch_stuff_plus=("pitch_stuff_plus", "mean"), location_plus_pitch=("location_plus_pitch", "mean"), pitches=("pitcher", "size")
    )
    baseline_label = buckets[0][2]
    baseline = pitcher_bucket[pitcher_bucket["season_bucket"].eq(baseline_label)]
    results = []
    for order, (_, _, bucket) in enumerate(buckets[1:], start=1):
        target = pitcher_bucket[pitcher_bucket["season_bucket"].eq(bucket)]
        paired = baseline.merge(target, on="pitcher", suffixes=("_base", "_target"))
        for outcome, label in [("pitch_stuff_plus", "Stuff+"), ("location_plus_pitch", "Location+")]:
            differences = paired[f"{outcome}_target"].to_numpy() - paired[f"{outcome}_base"].to_numpy()
            mean = float(np.mean(differences)) if len(differences) else 0.0
            se = float(np.std(differences, ddof=1) / np.sqrt(len(differences))) if len(differences) > 1 else 0.0
            results.append({
                "role": role, "outcome": outcome, "outcome_label": label, "reference_bucket": baseline_label,
                "target_bucket": bucket, "order": order, "pitchers": int(len(paired)),
                "paired_delta": round(mean, 3), "ci_low": round(mean - 1.96 * se, 3), "ci_high": round(mean + 1.96 * se, 3),
            })
    return results


def _hypotheses() -> list[dict[str, Any]]:
    controls = ["pitcher × pitch type", "batter quality", "count", "handedness", "times through order", "game state"]
    return [
        {"key": "H1", "title": "Within-game decline", "status": "scoped", "question": "Does adjusted pitch quality decline as appearance pitch count rises?", "primary_outcomes": ["Stuff+", "Location+"], "required_controls": controls},
        {"key": "H2", "title": "Short-term recovery", "status": "scoped", "question": "Do rest days and rolling workload predict the next appearance's quality retention?", "primary_outcomes": ["Stuff+", "Location+", "release stability"], "required_controls": ["role", "recent workload", "days rest", "opponent", "game state"]},
        {"key": "H3", "title": "Season accumulation", "status": "scoped", "question": "Does quality decline with cumulative workload after separating calendar progression from workload?", "primary_outcomes": ["Stuff+", "Location+"], "required_controls": ["calendar spline", "cumulative pitches", "recent workload", "park", "weather"]},
        {"key": "H4", "title": "Repeatable pitcher differences", "status": "scoped", "question": "Are pitcher-specific retention slopes stable across periods and seasons?", "primary_outcomes": ["random retention slopes", "out-of-sample quality"], "required_controls": ["partial pooling", "minimum sample", "uncertainty", "season holdout"]},
    ]
