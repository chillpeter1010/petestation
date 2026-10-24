from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import duckdb
import numpy as np
import pandas as pd

from app.core.config import settings
from app.repositories.pitch_repository import get_season_duckdb_path, resolve_pitch_table
from app.services.catcher_descriptive_ledger_service import slice1_root


CONTRACT_VERSION = "catcher_descriptive_slice5_xera_v1"
MODEL_VERSION = "petehub_xera_v1_statcast_xwoba_additive"
DEFAULT_YEARS = tuple(range(2021, 2027))
TRAIN_YEARS = (2021, 2022, 2023)
SELECTION_YEAR = 2024
FINAL_TEST_YEAR = 2025
EXTERNAL_DIAGNOSTIC_YEAR = 2026
MIN_BENCHMARK_OUTS = 60
MIN_SOURCE_COVERAGE = 0.95
RATE_MULTIPLIER = 27.0
BOOTSTRAP_SAMPLES = 1_000
BOOTSTRAP_SEED = 20261020

NON_BIP_EVENTS = {
    "strikeout",
    "strikeout_double_play",
    "walk",
    "intent_walk",
    "hit_by_pitch",
}


def slice5_root(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "research" / "catcher_descriptive" / "slice5_xera"


def summary_json_path(data_dir: Path | None = None) -> Path:
    return slice5_root(data_dir) / "catcher_descriptive_slice5_summary.json"


def model_json_path(data_dir: Path | None = None) -> Path:
    return slice5_root(data_dir) / "catcher_descriptive_slice5_model.json"


def pa_parquet_path(data_dir: Path | None = None) -> Path:
    return slice5_root(data_dir) / "pa_expected_runs_2021_2026.parquet"


def pitcher_parquet_path(data_dir: Path | None = None) -> Path:
    return slice5_root(data_dir) / "pitcher_xera_2021_2026.parquet"


def pair_parquet_path(data_dir: Path | None = None) -> Path:
    return slice5_root(data_dir) / "pitcher_catcher_xera_2021_2026.parquet"


def catcher_parquet_path(data_dir: Path | None = None) -> Path:
    return slice5_root(data_dir) / "catcher_xera_2021_2026.parquet"


def team_parquet_path(data_dir: Path | None = None) -> Path:
    return slice5_root(data_dir) / "team_xera_2021_2026.parquet"


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _atomic_write_parquet(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    frame.to_parquet(temporary, index=False)
    temporary.replace(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _round(value: float | int | None, digits: int = 6) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def baseball_ip_to_outs(value: object) -> int:
    text = str(value).strip()
    if not text or text.lower() == "nan":
        raise ValueError("Baseball innings are unavailable")
    whole, dot, remainder = text.partition(".")
    fractional_outs = int((remainder or "0")[0]) if dot else 0
    if fractional_outs not in (0, 1, 2):
        raise ValueError(f"Invalid baseball innings value: {text}")
    return int(whole) * 3 + fractional_outs


def _display_ip(outs: int) -> str:
    return f"{int(outs) // 3}.{int(outs) % 3}"


def _load_target_snapshot(root: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    path = root / "pitcher_2021_2026_xStats.csv"
    if not path.exists():
        raise FileNotFoundError(f"Slice 5 xERA benchmark is unavailable: {path}")
    frame = pd.read_csv(path, low_memory=False)
    required = {"Season", "Name", "Team", "IP", "xERA", "MLBAMID"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"xERA benchmark is missing required columns: {missing}")
    frame = frame.rename(
        columns={"Season": "season", "Name": "pitcher_name", "Team": "benchmark_team", "MLBAMID": "pitcher_id", "xERA": "official_xera"}
    )
    frame["season"] = pd.to_numeric(frame["season"], errors="raise").astype(int)
    frame["pitcher_id"] = pd.to_numeric(frame["pitcher_id"], errors="raise").astype(int)
    frame["official_xera"] = pd.to_numeric(frame["official_xera"], errors="coerce")
    frame["target_outs"] = frame["IP"].map(baseball_ip_to_outs)
    duplicate_keys = int(frame.duplicated(["season", "pitcher_id"]).sum())
    if duplicate_keys:
        raise ValueError(f"xERA benchmark contains {duplicate_keys} duplicate season-pitcher keys")
    selected = frame.loc[frame["season"].isin(DEFAULT_YEARS)].copy()
    coverage = []
    for year, group in selected.groupby("season", sort=True):
        coverage.append(
            {
                "season": int(year),
                "rows": int(len(group)),
                "xera_present": int(group["official_xera"].notna().sum()),
                "xera_missing": int(group["official_xera"].isna().sum()),
            }
        )
    metadata = {
        "path": str(path),
        "sha256": _sha256(path),
        "bytes": int(path.stat().st_size),
        "last_modified_utc": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
        "source_name": "User-provided FanGraphs-style pitcher export carrying Statcast xERA",
        "provenance_status": "file_fingerprinted_source_url_not_embedded",
        "source_url": None,
        "grain": "season-pitcher",
        "unique_key": ["season", "pitcher_id"],
        "rows": int(len(selected)),
        "duplicate_keys": duplicate_keys,
        "coverage": coverage,
        "warnings": [
            "The file structure is consistent with a FanGraphs export, but the download URL is not embedded in the CSV.",
            "Team='- - -' is a multi-team aggregate marker and is not used as a join key.",
            "IP is parsed as baseball notation and converted to outs before every calculation.",
        ],
    }
    return selected, metadata


def _load_canonical_pa(year: int, root: Path) -> pd.DataFrame:
    path = slice1_root(root) / "yearly" / f"pa_accounting_{int(year)}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Canonical PA accounting is unavailable: {path}")
    columns = [
        "season",
        "game_pk",
        "game_date",
        "at_bat_number",
        "pitching_team_id",
        "pitching_team_abbr",
        "pitcher_id",
        "pitcher_name",
        "current_catcher_id",
        "current_catcher_name",
        "event_type",
        "outs",
        "bf",
    ]
    frame = pd.read_parquet(path, columns=columns)
    if frame.duplicated(["game_pk", "at_bat_number"]).any():
        raise ValueError(f"Canonical PA keys are not unique for {year}")
    return frame


def _load_terminal_statcast(year: int, root: Path) -> pd.DataFrame:
    path = get_season_duckdb_path(year, root)
    if not path.exists():
        raise FileNotFoundError(f"Statcast DuckDB is unavailable: {path}")
    with duckdb.connect(str(path), read_only=True) as connection:
        tables = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
        table = resolve_pitch_table(tables)
        if not table:
            raise FileNotFoundError(f"No pitch table is available in {path}")
        frame = connection.execute(
            f"""
            WITH terminal AS (
                SELECT
                    game_pk,
                    at_bat_number,
                    pitcher AS statcast_pitcher_id,
                    fielder_2 AS statcast_catcher_id,
                    events AS statcast_event,
                    try_cast(woba_value AS DOUBLE) AS woba_value,
                    try_cast(woba_denom AS DOUBLE) AS woba_denom,
                    try_cast(estimated_woba_using_speedangle AS DOUBLE) AS estimated_woba,
                    try_cast(launch_speed AS DOUBLE) AS launch_speed,
                    try_cast(launch_angle AS DOUBLE) AS launch_angle,
                    row_number() OVER (
                        PARTITION BY game_pk, at_bat_number
                        ORDER BY pitch_number DESC NULLS LAST
                    ) AS terminal_rank
                FROM {table}
                WHERE game_type = 'R'
                  AND events IS NOT NULL
            )
            SELECT * EXCLUDE (terminal_rank)
            FROM terminal
            WHERE terminal_rank = 1
            """
        ).fetchdf()
    if frame.duplicated(["game_pk", "at_bat_number"]).any():
        raise ValueError(f"Statcast terminal PA keys are not unique for {year}")
    return frame


def _load_pa_sources(years: Iterable[int], root: Path) -> pd.DataFrame:
    frames = []
    for year in years:
        canonical = _load_canonical_pa(year, root)
        statcast = _load_terminal_statcast(year, root)
        merged = canonical.merge(statcast, on=["game_pk", "at_bat_number"], how="left", validate="one_to_one")
        merged["statcast_joined_for_xera"] = merged["statcast_event"].notna()
        frames.append(merged)
    return pd.concat(frames, ignore_index=True)


def _prepare_expected_woba(pa: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    frame = pa.copy()
    training = frame.loc[frame["season"].isin(TRAIN_YEARS) & frame["statcast_event"].notna()].copy()
    training["woba_denom"] = pd.to_numeric(training["woba_denom"], errors="coerce")
    training["estimated_woba"] = pd.to_numeric(training["estimated_woba"], errors="coerce")
    training["woba_value"] = pd.to_numeric(training["woba_value"], errors="coerce")

    denom_by_event = (
        training.dropna(subset=["statcast_event", "woba_denom"])
        .groupby("statcast_event")["woba_denom"]
        .agg(lambda values: float(values.mode().iloc[0]))
        .to_dict()
    )
    deterministic_value = (
        training.loc[training["statcast_event"].isin(NON_BIP_EVENTS)]
        .dropna(subset=["statcast_event", "woba_value"])
        .groupby("statcast_event")["woba_value"]
        .mean()
        .to_dict()
    )
    bip_training = training.loc[
        (~training["statcast_event"].isin(NON_BIP_EVENTS))
        & training["estimated_woba"].notna()
        & training["woba_denom"].gt(0)
    ]
    if bip_training.empty:
        raise ValueError("No training-period BIP expected-wOBA rows are available")
    bip_fallback = float(bip_training["estimated_woba"].mean())

    frame["woba_denom"] = pd.to_numeric(frame["woba_denom"], errors="coerce")
    mapped_denom = frame["event_type"].map(denom_by_event)
    frame["effective_woba_denom"] = frame["woba_denom"].fillna(mapped_denom).fillna(1.0)
    frame["estimated_woba"] = pd.to_numeric(frame["estimated_woba"], errors="coerce")
    frame["woba_value"] = pd.to_numeric(frame["woba_value"], errors="coerce")
    direct = frame["effective_woba_denom"].gt(0) & frame["estimated_woba"].notna()
    excluded = frame["effective_woba_denom"].le(0)
    event_name = frame["statcast_event"].fillna(frame["event_type"])
    deterministic = (
        frame["effective_woba_denom"].gt(0)
        & ~direct
        & event_name.isin(NON_BIP_EVENTS)
    )
    deterministic_fallback = event_name.map(deterministic_value)
    deterministic_fallback = deterministic_fallback.fillna(frame["woba_value"])
    other_fallback = frame["effective_woba_denom"].gt(0) & ~direct & ~deterministic

    frame["expected_woba_value"] = 0.0
    frame.loc[direct, "expected_woba_value"] = frame.loc[direct, "estimated_woba"]
    frame.loc[deterministic, "expected_woba_value"] = deterministic_fallback.loc[deterministic].fillna(0.0)
    frame.loc[other_fallback, "expected_woba_value"] = bip_fallback
    frame["expected_woba_source"] = "woba_denominator_excluded"
    frame.loc[direct, "expected_woba_source"] = "statcast_expected_woba"
    frame.loc[deterministic, "expected_woba_source"] = "deterministic_event_fallback"
    frame.loc[other_fallback, "expected_woba_source"] = "training_bip_mean_fallback"
    frame["source_supported"] = direct | deterministic | excluded
    frame["fallback_bf"] = (~frame["source_supported"]).astype(int) * pd.to_numeric(frame["bf"], errors="coerce").fillna(0).astype(int)

    summary = {
        "training_bip_expected_woba_mean": _round(bip_fallback, 9),
        "rows": int(len(frame)),
        "statcast_joined_rows": int(frame["statcast_joined_for_xera"].sum()),
        "direct_expected_woba_rows": int(direct.sum()),
        "deterministic_fallback_rows": int(deterministic.sum()),
        "training_bip_mean_fallback_rows": int(other_fallback.sum()),
        "woba_denominator_excluded_rows": int(excluded.sum()),
        "fallback_bf": int(frame["fallback_bf"].sum()),
        "source_supported_bf_pct": _round(100.0 * (1.0 - frame["fallback_bf"].sum() / frame["bf"].sum()), 6),
        "fallback_policy": "Missing tracked BIP uses the frozen 2021-2023 mean expected-wOBA; deterministic K/BB/HBP outcomes use their training-period event value.",
    }
    return frame, summary


def _aggregate_pitchers(pa: pd.DataFrame, ledger: pd.DataFrame) -> pd.DataFrame:
    pa_totals = (
        pa.groupby(["season", "pitcher_id"], as_index=False)
        .agg(
            pitcher_name=("pitcher_name", "first"),
            pa_outs=("outs", "sum"),
            pa_bf=("bf", "sum"),
            woba_denom=("effective_woba_denom", "sum"),
            expected_woba_sum=("expected_woba_value", "sum"),
            fallback_bf=("fallback_bf", "sum"),
        )
    )
    ledger_totals = ledger.groupby(["season", "pitcher_id"], as_index=False).agg(
        outs=("outs", "sum"),
        bf=("bf", "sum"),
    )
    frame = ledger_totals.merge(pa_totals, on=["season", "pitcher_id"], how="outer", validate="one_to_one")
    frame[["outs", "bf", "pa_outs", "pa_bf", "woba_denom", "expected_woba_sum", "fallback_bf"]] = frame[
        ["outs", "bf", "pa_outs", "pa_bf", "woba_denom", "expected_woba_sum", "fallback_bf"]
    ].fillna(0)
    if int((frame["bf"] - frame["pa_bf"]).abs().sum()):
        raise ValueError("Canonical ledger BF do not reconcile to PA accounting")
    return frame


def _fit_additive_calibration(
    frame: pd.DataFrame,
    feature_names: list[str],
    train_years: Iterable[int] = TRAIN_YEARS,
) -> dict[str, float]:
    training = frame.loc[frame["season"].isin(tuple(train_years))].copy()
    if training.empty:
        raise ValueError("No chronological training rows are available for xERA calibration")
    x = training[feature_names].to_numpy(dtype=float)
    y = (training["official_xera"] * training["outs"] / RATE_MULTIPLIER).to_numpy(dtype=float)
    weights = np.sqrt(training["outs"].to_numpy(dtype=float))[:, None]
    coefficients = np.linalg.lstsq(x * weights, y * weights[:, 0], rcond=None)[0]
    return {name: float(value) for name, value in zip(feature_names, coefficients)}


def _apply_additive_calibration(frame: pd.DataFrame, coefficients: dict[str, float]) -> pd.Series:
    expected_runs = sum(pd.to_numeric(frame[name], errors="coerce") * value for name, value in coefficients.items())
    outs = pd.to_numeric(frame["outs"], errors="coerce")
    return RATE_MULTIPLIER * expected_runs / outs.where(outs.gt(0))


def _bootstrap_mae_interval(actual: np.ndarray, predicted: np.ndarray) -> dict[str, Any] | None:
    if len(actual) < 2:
        return None
    generator = np.random.default_rng(BOOTSTRAP_SEED)
    indices = generator.integers(0, len(actual), size=(BOOTSTRAP_SAMPLES, len(actual)))
    errors = np.abs(predicted - actual)
    samples = errors[indices].mean(axis=1)
    return {
        "samples": BOOTSTRAP_SAMPLES,
        "seed": BOOTSTRAP_SEED,
        "ci_level": 0.95,
        "low": _round(np.quantile(samples, 0.025), 6),
        "high": _round(np.quantile(samples, 0.975), 6),
    }


def _evaluation_metrics(frame: pd.DataFrame, prediction_column: str) -> dict[str, Any]:
    valid = frame.dropna(subset=["official_xera", prediction_column]).copy()
    if valid.empty:
        return {"rows": 0, "mae": None, "rmse": None, "bias": None, "pearson": None, "spearman": None, "mae_bootstrap_95_ci": None}
    actual = valid["official_xera"].to_numpy(dtype=float)
    predicted = valid[prediction_column].to_numpy(dtype=float)
    return {
        "rows": int(len(valid)),
        "mae": _round(np.mean(np.abs(predicted - actual)), 6),
        "rmse": _round(np.sqrt(np.mean((predicted - actual) ** 2)), 6),
        "bias": _round(np.mean(predicted - actual), 6),
        "pearson": _round(pd.Series(actual).corr(pd.Series(predicted), method="pearson"), 6),
        "spearman": _round(pd.Series(actual).corr(pd.Series(predicted), method="spearman"), 6),
        "mae_bootstrap_95_ci": _bootstrap_mae_interval(actual, predicted),
    }


def _period_metrics(frame: pd.DataFrame, prediction_column: str) -> dict[str, Any]:
    periods = {
        "training_2021_2023": frame["season"].isin(TRAIN_YEARS),
        "selection_2024": frame["season"].eq(SELECTION_YEAR),
        "final_test_2025": frame["season"].eq(FINAL_TEST_YEAR),
        "external_diagnostic_2026": frame["season"].eq(EXTERNAL_DIAGNOSTIC_YEAR),
    }
    return {name: _evaluation_metrics(frame.loc[mask], prediction_column) for name, mask in periods.items()}


def _load_legacy_ols_predictions(root: Path, target: pd.DataFrame, model_path: Path) -> pd.DataFrame:
    if not model_path.exists():
        return pd.DataFrame(columns=["season", "pitcher_id", "legacy_ols_xera"])
    model = json.loads(model_path.read_text(encoding="utf-8"))
    features = list(model["features"])
    frames = []
    for year in DEFAULT_YEARS:
        path = root / f"{year}_pitcher_comparison.csv"
        if not path.exists():
            continue
        frame = pd.read_csv(path, low_memory=False)
        if not set(features).issubset(frame.columns):
            continue
        frame[features] = frame[features].apply(pd.to_numeric, errors="coerce")
        complete = frame[features].notna().all(axis=1)
        scored = frame.loc[complete, ["player_id"]].copy()
        x = frame.loc[complete, features].to_numpy(dtype=float)
        beta = np.array([model["coefficients"][feature] for feature in features], dtype=float)
        scored["legacy_ols_xera"] = np.clip(float(model["intercept"]) + x @ beta, 1.5, 8.5)
        scored["season"] = int(year)
        scored = scored.rename(columns={"player_id": "pitcher_id"})
        scored["pitcher_id"] = pd.to_numeric(scored["pitcher_id"], errors="coerce").astype("Int64")
        frames.append(scored.dropna(subset=["pitcher_id"]))
    if not frames:
        return pd.DataFrame(columns=["season", "pitcher_id", "legacy_ols_xera"])
    predictions = pd.concat(frames, ignore_index=True)
    predictions["pitcher_id"] = predictions["pitcher_id"].astype(int)
    return predictions.merge(target[["season", "pitcher_id"]], on=["season", "pitcher_id"], how="inner")


def _source_status(outs: pd.Series, coverage: pd.Series) -> pd.Series:
    return pd.Series(
        np.select(
            [outs.le(0), coverage.lt(MIN_SOURCE_COVERAGE), outs.lt(MIN_BENCHMARK_OUTS)],
            ["unavailable", "limited", "limited"],
            default="available",
        ),
        index=outs.index,
        dtype="object",
    )


def _aggregate_outputs(
    pa: pd.DataFrame,
    pitchers: pd.DataFrame,
    ledger: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    pa_pair = (
        pa.dropna(subset=["current_catcher_id"])
        .groupby(["season", "pitcher_id", "current_catcher_id"], as_index=False)
        .agg(
            pitcher_name=("pitcher_name", "first"),
            catcher_name=("current_catcher_name", "first"),
            teams=("pitching_team_abbr", lambda values: ", ".join(sorted(set(values.dropna().astype(str))))),
            games=("game_pk", "nunique"),
            pa_outs=("outs", "sum"),
            pa_bf=("bf", "sum"),
            expected_woba_sum=("expected_woba_value", "sum"),
            xera_expected_runs=("xera_expected_runs", "sum"),
            fallback_bf=("fallback_bf", "sum"),
        )
        .rename(columns={"current_catcher_id": "catcher_id"})
    )
    pa_pair["catcher_id"] = pa_pair["catcher_id"].astype(int)
    ledger_pair = (
        ledger.dropna(subset=["catcher_id"])
        .groupby(["season", "pitcher_id", "catcher_id"], as_index=False)
        .agg(
            ledger_pitcher_name=("pitcher_name", "first"),
            ledger_catcher_name=("catcher_name", "first"),
            ledger_teams=("pitching_team_abbr", lambda values: ", ".join(sorted(set(values.dropna().astype(str))))),
            ledger_games=("games", "sum"),
            outs=("outs", "sum"),
            bf=("bf", "sum"),
        )
    )
    ledger_pair["catcher_id"] = ledger_pair["catcher_id"].astype(int)
    pair = ledger_pair.merge(pa_pair, on=["season", "pitcher_id", "catcher_id"], how="left", validate="one_to_one")
    if pair[["xera_expected_runs", "expected_woba_sum"]].isna().any().any():
        raise ValueError("At least one canonical pitcher-catcher pair has no PA expected-run rows")
    pair["pitcher_name"] = pair["pitcher_name"].fillna(pair["ledger_pitcher_name"])
    pair["catcher_name"] = pair["catcher_name"].fillna(pair["ledger_catcher_name"])
    pair["teams"] = pair["teams"].fillna(pair["ledger_teams"])
    pair["games"] = pair["games"].fillna(pair["ledger_games"])
    if int((pair["bf"] - pair["pa_bf"]).abs().sum()):
        raise ValueError("Canonical pair BF do not reconcile to PA accounting")
    pair["source_coverage_pct"] = 100.0 * (1.0 - pair["fallback_bf"] / pair["bf"].where(pair["bf"].gt(0)))
    pair["pair_xera"] = RATE_MULTIPLIER * pair["xera_expected_runs"] / pair["outs"].where(pair["outs"].gt(0))
    pair = pair.merge(
        pitchers[["season", "pitcher_id", "xera"]].rename(columns={"xera": "pitcher_xera"}),
        on=["season", "pitcher_id"],
        how="left",
        validate="many_to_one",
    )
    pair["pitcher_mix_expected_runs"] = pair["pitcher_xera"] * pair["outs"] / RATE_MULTIPLIER
    pair["x_runs_vs_pitcher_mix"] = pair["pitcher_mix_expected_runs"] - pair["xera_expected_runs"]
    pair["x_runs_vs_pitcher_mix_per_ip"] = pair["x_runs_vs_pitcher_mix"] / (pair["outs"] / 3.0).where(pair["outs"].gt(0))
    pair["xera_status"] = _source_status(pair["outs"], pair["source_coverage_pct"] / 100.0)
    pair["display_ip"] = pair["outs"].astype(int).map(_display_ip)
    pair["contract_version"] = CONTRACT_VERSION

    catcher = (
        pair.groupby(["season", "catcher_id"], as_index=False)
        .agg(
            catcher_name=("catcher_name", "first"),
            teams=("teams", lambda values: ", ".join(sorted({code for value in values for code in str(value).split(", ") if code}))),
            pitchers=("pitcher_id", "nunique"),
            outs=("outs", "sum"),
            bf=("bf", "sum"),
            expected_woba_sum=("expected_woba_sum", "sum"),
            xera_expected_runs=("xera_expected_runs", "sum"),
            pitcher_mix_expected_runs=("pitcher_mix_expected_runs", "sum"),
            fallback_bf=("fallback_bf", "sum"),
        )
    )
    catcher["source_coverage_pct"] = 100.0 * (1.0 - catcher["fallback_bf"] / catcher["bf"].where(catcher["bf"].gt(0)))
    catcher["cxera"] = RATE_MULTIPLIER * catcher["xera_expected_runs"] / catcher["outs"].where(catcher["outs"].gt(0))
    catcher["txera"] = RATE_MULTIPLIER * catcher["pitcher_mix_expected_runs"] / catcher["outs"].where(catcher["outs"].gt(0))
    catcher["x_runs_vs_mix"] = catcher["pitcher_mix_expected_runs"] - catcher["xera_expected_runs"]
    catcher["x_runs_vs_mix_per_ip"] = catcher["x_runs_vs_mix"] / (catcher["outs"] / 3.0).where(catcher["outs"].gt(0))
    catcher["xera_status"] = _source_status(catcher["outs"], catcher["source_coverage_pct"] / 100.0)
    catcher["display_ip"] = catcher["outs"].astype(int).map(_display_ip)
    catcher["contract_version"] = CONTRACT_VERSION

    pa_team = (
        pa.groupby(["season", "pitching_team_id", "pitching_team_abbr"], as_index=False)
        .agg(
            pa_outs=("outs", "sum"),
            pa_bf=("bf", "sum"),
            expected_woba_sum=("expected_woba_value", "sum"),
            xera_expected_runs=("xera_expected_runs", "sum"),
            fallback_bf=("fallback_bf", "sum"),
        )
    )
    ledger_team = ledger.groupby(["season", "pitching_team_id", "pitching_team_abbr"], as_index=False).agg(
        outs=("outs", "sum"),
        bf=("bf", "sum"),
    )
    team = ledger_team.merge(
        pa_team,
        on=["season", "pitching_team_id", "pitching_team_abbr"],
        how="left",
        validate="one_to_one",
    )
    if int((team["bf"] - team["pa_bf"]).abs().sum()):
        raise ValueError("Canonical team BF do not reconcile to PA accounting")
    team["source_coverage_pct"] = 100.0 * (1.0 - team["fallback_bf"] / team["bf"].where(team["bf"].gt(0)))
    team["xera"] = RATE_MULTIPLIER * team["xera_expected_runs"] / team["outs"].where(team["outs"].gt(0))
    team["xera_status"] = _source_status(team["outs"], team["source_coverage_pct"] / 100.0)
    team["display_ip"] = team["outs"].astype(int).map(_display_ip)
    team["contract_version"] = CONTRACT_VERSION
    return pair, catcher, team


def _reconciliation(
    root: Path,
    pa: pd.DataFrame,
    pitchers: pd.DataFrame,
    pairs: pd.DataFrame,
    catchers: pd.DataFrame,
    teams: pd.DataFrame,
) -> dict[str, Any]:
    ledger = pd.read_parquet(slice1_root(root) / "pitcher_catcher_ledger_2021_2026.parquet")
    ledger_pair = (
        ledger.dropna(subset=["catcher_id"])
        .groupby(["season", "pitcher_id", "catcher_id"], as_index=False)
        .agg(ledger_outs=("outs", "sum"), ledger_bf=("bf", "sum"))
    )
    ledger_pair["catcher_id"] = ledger_pair["catcher_id"].astype(int)
    pair_check = ledger_pair.merge(
        pairs[["season", "pitcher_id", "catcher_id", "outs", "bf"]],
        on=["season", "pitcher_id", "catcher_id"],
        how="outer",
        validate="one_to_one",
    ).fillna(0)
    pair_outs_difference = int((pair_check["ledger_outs"] - pair_check["outs"]).abs().sum())
    pair_bf_difference = int((pair_check["ledger_bf"] - pair_check["bf"]).abs().sum())

    totals = {
        "pa": {"outs": int(pa["outs"].sum()), "bf": int(pa["bf"].sum()), "xera_expected_runs": float(pa["xera_expected_runs"].sum())},
        "pitcher": {"outs": int(pitchers["outs"].sum()), "bf": int(pitchers["bf"].sum()), "xera_expected_runs": float(pitchers["xera_expected_runs"].sum())},
        "pair": {"outs": int(pairs["outs"].sum()), "bf": int(pairs["bf"].sum()), "xera_expected_runs": float(pairs["xera_expected_runs"].sum())},
        "catcher": {"outs": int(catchers["outs"].sum()), "bf": int(catchers["bf"].sum()), "xera_expected_runs": float(catchers["xera_expected_runs"].sum())},
        "team": {"outs": int(teams["outs"].sum()), "bf": int(teams["bf"].sum()), "xera_expected_runs": float(teams["xera_expected_runs"].sum())},
    }
    base = totals["pa"]
    differences = {
        level: {
            "outs": int(values["outs"] - base["outs"]),
            "bf": int(values["bf"] - base["bf"]),
            "xera_expected_runs": _round(values["xera_expected_runs"] - base["xera_expected_runs"], 12),
        }
        for level, values in totals.items()
    }
    passed = bool(
        pair_outs_difference == 0
        and pair_bf_difference == 0
        and all(values["outs"] == 0 and values["bf"] == 0 and abs(values["xera_expected_runs"] or 0) <= 1e-8 for values in differences.values())
    )
    return {
        "passed": passed,
        "pair_key_rows": int(len(pair_check)),
        "ledger_pair_absolute_outs_difference": pair_outs_difference,
        "ledger_pair_absolute_bf_difference": pair_bf_difference,
        "totals": totals,
        "differences_from_pa": differences,
    }


def build_catcher_descriptive_slice5_xera(
    years: Iterable[int] = DEFAULT_YEARS,
    data_dir: Path | None = None,
) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    selected_years = tuple(sorted(set(int(year) for year in years)))
    if selected_years != DEFAULT_YEARS:
        raise ValueError(f"Slice 5 requires the frozen 2021-2026 contract; received {selected_years}")
    target, target_metadata = _load_target_snapshot(root)
    pa = _load_pa_sources(selected_years, root)
    pa, source_coverage = _prepare_expected_woba(pa)
    ledger = pd.read_parquet(slice1_root(root) / "pitcher_catcher_ledger_2021_2026.parquet")
    pitcher_base = _aggregate_pitchers(pa, ledger)
    benchmark = pitcher_base.merge(
        target[["season", "pitcher_id", "official_xera", "target_outs"]],
        on=["season", "pitcher_id"],
        how="left",
        validate="one_to_one",
    )
    benchmark["outs_difference"] = benchmark["outs"] - benchmark["target_outs"]
    target_outs_mismatches = int(benchmark.loc[benchmark["target_outs"].notna(), "outs_difference"].abs().sum())
    if target_outs_mismatches:
        raise ValueError(f"xERA benchmark outs do not reconcile to the canonical ledger: {target_outs_mismatches}")
    benchmark = benchmark.loc[
        benchmark["official_xera"].notna() & benchmark["outs"].ge(MIN_BENCHMARK_OUTS)
    ].copy()

    candidates = {
        "additive_expected_woba_bf": ["expected_woba_sum", "bf"],
        "additive_expected_woba_bf_outs": ["expected_woba_sum", "bf", "outs"],
    }
    candidate_payload: dict[str, Any] = {}
    for name, features in candidates.items():
        coefficients = _fit_additive_calibration(benchmark, features)
        benchmark[name] = _apply_additive_calibration(benchmark, coefficients)
        candidate_payload[name] = {
            "features": features,
            "coefficients": coefficients,
            "pa_additive_eligible": "outs" not in features,
            "eligibility_note": (
                "Eligible: every feature has an unambiguous terminal-PA contribution."
                if "outs" not in features
                else "Diagnostic only: canonical pitcher outs differ from PA-current-pitcher outs on a mid-PA/pickoff edge case, so the outs term cannot be assigned to a terminal PA without fabrication."
            ),
            "period_metrics": _period_metrics(benchmark, name),
        }
    selected_model = min(
        (name for name in candidates if candidate_payload[name]["pa_additive_eligible"]),
        key=lambda name: (
            candidate_payload[name]["period_metrics"]["selection_2024"]["mae"],
            candidate_payload[name]["period_metrics"]["selection_2024"]["rmse"],
            len(candidates[name]),
        ),
    )
    selected_coefficients = candidate_payload[selected_model]["coefficients"]

    pitcher_base["xera_expected_runs"] = sum(
        pitcher_base[feature] * coefficient for feature, coefficient in selected_coefficients.items()
    )
    pitcher_base["xera"] = RATE_MULTIPLIER * pitcher_base["xera_expected_runs"] / pitcher_base["outs"].where(pitcher_base["outs"].gt(0))
    pitcher_base["source_coverage_pct"] = 100.0 * (1.0 - pitcher_base["fallback_bf"] / pitcher_base["bf"].where(pitcher_base["bf"].gt(0)))
    pitcher_base["xera_status"] = _source_status(pitcher_base["outs"], pitcher_base["source_coverage_pct"] / 100.0)
    pitcher_base["display_ip"] = pitcher_base["outs"].astype(int).map(_display_ip)
    pitcher_base["contract_version"] = CONTRACT_VERSION
    pitcher_base = pitcher_base.merge(
        target[["season", "pitcher_id", "official_xera"]],
        on=["season", "pitcher_id"],
        how="left",
        validate="one_to_one",
    )

    pa["xera_expected_runs"] = 0.0
    for feature, coefficient in selected_coefficients.items():
        if feature == "expected_woba_sum":
            values = pa["expected_woba_value"]
        elif feature == "bf":
            values = pa["bf"]
        elif feature == "outs":
            values = pa["outs"]
        else:
            raise ValueError(f"Unsupported PA-level additive feature: {feature}")
        pa["xera_expected_runs"] += pd.to_numeric(values, errors="coerce").fillna(0) * coefficient
    pair, catcher, team = _aggregate_outputs(pa, pitcher_base, ledger)
    reconciliation = _reconciliation(root, pa, pitcher_base, pair, catcher, team)

    benchmark["legacy_cubic_xera"] = (
        -1.78
        + 22.7 * (benchmark["expected_woba_sum"] / benchmark["woba_denom"])
        - 62.3 * (benchmark["expected_woba_sum"] / benchmark["woba_denom"]) ** 2
        + 135.0 * (benchmark["expected_woba_sum"] / benchmark["woba_denom"]) ** 3
    ).clip(1.5, 8.5)
    legacy_ols = _load_legacy_ols_predictions(root, target, root / "estimated_xera_model_2025.json")
    benchmark = benchmark.merge(legacy_ols, on=["season", "pitcher_id"], how="left", validate="one_to_one")
    baseline_metrics = {
        "legacy_xwoba_cubic": _period_metrics(benchmark, "legacy_cubic_xera"),
        "legacy_expanded_ols": _period_metrics(benchmark, "legacy_ols_xera"),
    }

    selected_test = candidate_payload[selected_model]["period_metrics"]["final_test_2025"]
    release_gates = {
        "target_outs_reconcile": target_outs_mismatches == 0,
        "pa_pair_catcher_team_reconcile": reconciliation["passed"],
        "source_supported_bf_pct_at_least_99": float(source_coverage["source_supported_bf_pct"] or 0) >= 99.0,
        "selection_2024_mae_at_most_0_20": candidate_payload[selected_model]["period_metrics"]["selection_2024"]["mae"] <= 0.20,
        "final_test_2025_mae_at_most_0_20": selected_test["mae"] <= 0.20,
        "final_test_2025_rmse_at_most_0_25": selected_test["rmse"] <= 0.25,
        "final_test_2025_abs_bias_at_most_0_15": abs(selected_test["bias"]) <= 0.15,
        "final_test_2025_pearson_at_least_0_95": selected_test["pearson"] >= 0.95,
    }
    release_gate_passed = all(release_gates.values())

    model_payload = {
        "contract_version": CONTRACT_VERSION,
        "model_version": MODEL_VERSION,
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "chronological_contract": {
            "training_years": list(TRAIN_YEARS),
            "selection_year": SELECTION_YEAR,
            "final_test_year": FINAL_TEST_YEAR,
            "external_diagnostic_year": EXTERNAL_DIAGNOSTIC_YEAR,
            "minimum_benchmark_outs": MIN_BENCHMARK_OUTS,
            "selection_rule": "Lowest 2024 MAE, then RMSE, then fewer additive features; 2025 and 2026 cannot change the selected model.",
        },
        "target_snapshot": target_metadata,
        "upstream_expected_value": {
            "field": "estimated_woba_using_speedangle",
            "provider": "Statcast",
            "role": "Per-PA expected-wOBA input; Petehub learns the additive ERA-scale translation.",
            "source_coverage": source_coverage,
        },
        "selected_model": selected_model,
        "selected_coefficients": selected_coefficients,
        "selection_result": {
            "selected_for_release": selected_model,
            "reason": "The selected model is the lowest-error candidate whose numerator can be assigned to terminal PAs without fabricating pitcher-out ownership.",
            "diagnostic_only_candidate": "additive_expected_woba_bf_outs",
            "diagnostic_only_reason": candidate_payload["additive_expected_woba_bf_outs"]["eligibility_note"],
        },
        "candidates": candidate_payload,
        "baselines": baseline_metrics,
        "baseline_notes": {
            "legacy_xwoba_cubic": "Frozen historical formula. Its ranking correlation remains high, but its absolute ERA scale is systematically low.",
            "legacy_expanded_ols": "Diagnostic only. The coefficients were trained on 2025 target data, so 2021-2024 are backward-looking applications and 2025 is in-sample; none is a valid chronological release comparison.",
        },
        "leakage_audit": {
            "actual_runs_feature": False,
            "actual_earned_runs_feature": False,
            "actual_era_feature": False,
            "catcher_id_feature": False,
            "pitcher_id_feature": False,
            "target_year_feature": False,
            "features": list(selected_coefficients),
            "note": "BF and outs are additive exposure/denominator terms. Catcher and pitcher IDs are aggregation keys only.",
        },
        "release_gates": release_gates,
        "release_gate_passed": release_gate_passed,
    }
    summary = {
        "contract_version": CONTRACT_VERSION,
        "model_version": MODEL_VERSION,
        "built_at_utc": model_payload["built_at_utc"],
        "status": "passed" if release_gate_passed else "failed_release_gate",
        "release_gate_passed": release_gate_passed,
        "years": list(selected_years),
        "selected_model": selected_model,
        "selected_coefficients": selected_coefficients,
        "target_snapshot": target_metadata,
        "source_coverage": source_coverage,
        "evaluation": candidate_payload[selected_model]["period_metrics"],
        "baseline_metrics": baseline_metrics,
        "baseline_notes": model_payload["baseline_notes"],
        "release_gates": release_gates,
        "reconciliation": reconciliation,
        "row_counts": {
            "pa": int(len(pa)),
            "pitcher_seasons": int(len(pitcher_base)),
            "pitcher_catcher_pairs": int(len(pair)),
            "catcher_seasons": int(len(catcher)),
            "team_seasons": int(len(team)),
            "benchmark_qualified_pitcher_seasons": int(len(benchmark)),
        },
        "definitions": {
            "xera": "27 × the sum of Petehub PA-level expected-run components ÷ outs.",
            "cxera": "The same expected-run numerator aggregated over every PA caught by the catcher, divided by catcher outs.",
            "txera": "Each handled pitcher's Petehub season xERA weighted by the catcher's actual outs with that pitcher.",
            "x_runs_vs_mix": "Pitcher-mix expected runs minus catcher-PA expected runs; an observed expected-results association, not causal catcher value.",
        },
        "warnings": [
            "Petehub xERA v1 is calibrated to a fingerprinted FanGraphs-style Statcast xERA snapshot but is not MLB's published formula.",
            "The upstream expected contact value is Statcast estimated_woba_using_speedangle; Petehub owns the chronological additive ERA-scale calibration and aggregation.",
            "cxERA, txERA and their difference are descriptive expected-results associations, not causal catcher value.",
            "Park and non-catcher defense adjustments remain outside Slice 5.",
            "Small samples are labeled limited and are not annualized.",
        ],
    }

    output_columns = [
        "season", "game_pk", "game_date", "at_bat_number", "pitching_team_id", "pitching_team_abbr",
        "pitcher_id", "pitcher_name", "current_catcher_id", "current_catcher_name", "event_type", "outs", "bf",
        "effective_woba_denom", "expected_woba_value", "expected_woba_source", "source_supported", "fallback_bf",
        "xera_expected_runs",
    ]
    _atomic_write_parquet(pa_parquet_path(root), pa[output_columns])
    _atomic_write_parquet(pitcher_parquet_path(root), pitcher_base)
    _atomic_write_parquet(pair_parquet_path(root), pair)
    _atomic_write_parquet(catcher_parquet_path(root), catcher)
    _atomic_write_parquet(team_parquet_path(root), team)
    _atomic_write_json(model_json_path(root), model_payload)
    _atomic_write_json(summary_json_path(root), summary)
    if not release_gate_passed:
        raise RuntimeError(f"Slice 5 xERA release gate failed; inspect {summary_json_path(root)}")
    return summary


def get_catcher_xera_rows(
    year: int,
    data_dir: Path | None = None,
) -> tuple[dict[int, dict[str, Any]], dict[str, Any] | None]:
    path = catcher_parquet_path(data_dir)
    summary_path = summary_json_path(data_dir)
    if not path.exists() or not summary_path.exists():
        return {}, None
    frame = pd.read_parquet(path, filters=[("season", "==", int(year))])
    rows = {int(row["catcher_id"]): row for row in frame.to_dict(orient="records")}
    return rows, json.loads(summary_path.read_text(encoding="utf-8"))


def get_pair_xera_rows(
    year: int,
    data_dir: Path | None = None,
) -> dict[tuple[int, int], dict[str, Any]]:
    path = pair_parquet_path(data_dir)
    if not path.exists():
        return {}
    frame = pd.read_parquet(path, filters=[("season", "==", int(year))])
    return {
        (int(row["pitcher_id"]), int(row["catcher_id"])): row
        for row in frame.to_dict(orient="records")
    }
