from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, SplineTransformer, StandardScaler

from app.core.config import settings


CONTRACT_VERSION = "stamina_command_retention_contract_v1"
MODEL_VERSION = "command_retention_challenger_v1"
VALIDATION_VERSION = "stamina_incremental_validation_v1"
PRODUCT_INTEGRATION_VERSION = "stamina_product_integration_v1"
DEVELOPMENT_YEAR = 2023
VALIDATION_TRAIN_YEAR = 2025
VALIDATION_TEST_YEAR = 2026
WINDOWS = [(21, 40, "21–40"), (41, 60, "41–60"), (61, 80, "61–80"), (81, 100, "81–100")]
FAMILIES = ("Fastball", "Breaking", "Offspeed")
MINIMUM_EARLY_EXACT_PITCHES = 3
MINIMUM_WINDOW_PITCHES = 5
MINIMUM_GAME_PITCHES = 15
MINIMUM_FIXED_MIX_COVERAGE = 0.80
EARLY_PRIOR_PITCHES = 5.0


def command_contract_path(year: int, data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / f"stamina_command_contract_{int(year)}.json"


def command_window_path(year: int, data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / f"stamina_command_windows_{int(year)}.parquet"


def command_game_path(year: int, data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / f"stamina_command_games_{int(year)}.parquet"


def incremental_validation_path(year: int, data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / f"stamina_incremental_validation_{int(year)}.json"


def product_integration_path(year: int, data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / f"stamina_product_integration_{int(year)}.json"


def _dataset_path(year: int, root: Path) -> Path:
    return root / "derived" / f"stamina_lab_{int(year)}.parquet"


def _quality_window_path(year: int, root: Path) -> Path:
    return root / "derived" / f"stamina_game_state_windows_{int(year)}.parquet"


def _physical_window_path(year: int, root: Path) -> Path:
    return root / "derived" / f"stamina_physical_windows_{int(year)}.parquet"


def _write_parquet_atomic(frame: pd.DataFrame, path: Path, relation_name: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp.parquet")
    with duckdb.connect() as connection:
        connection.register(relation_name, frame)
        target = str(temporary).replace("'", "''")
        connection.execute(f"COPY {relation_name} TO '{target}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        connection.unregister(relation_name)
    temporary.replace(path)


def _write_json_atomic(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp.json")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _display_name(value: object) -> str:
    text = str(value or "").strip()
    if "," not in text:
        return text
    last, first = [part.strip() for part in text.split(",", 1)]
    return f"{first} {last}".strip()


def _spearman(left: pd.Series, right: pd.Series) -> float | None:
    sample = pd.concat([left, right], axis=1).dropna()
    if len(sample) < 3 or sample.iloc[:, 0].nunique() < 2 or sample.iloc[:, 1].nunique() < 2:
        return None
    return float(sample.iloc[:, 0].corr(sample.iloc[:, 1], method="spearman"))


def _load_source(year: int, root: Path) -> pd.DataFrame:
    path = _dataset_path(year, root)
    if not path.exists():
        raise FileNotFoundError(f"Required Stamina dataset not found: {path}")
    columns = [
        "pitcher", "player_name", "pitcher_team", "game_pk", "game_date", "appearance_pitch_number",
        "pitch_type", "pitch_family", "location_plus_pitch",
    ]
    with duckdb.connect() as connection:
        return connection.execute(
            f"SELECT {', '.join(columns)} FROM read_parquet(?) "
            "WHERE appearance_role = 'SP' AND appearance_pitch_number BETWEEN 1 AND 100 "
            "AND pitch_type IS NOT NULL AND pitch_family IS NOT NULL AND location_plus_pitch IS NOT NULL",
            [str(path)],
        ).fetchdf()


def _prepare_pitch_rows(frame: pd.DataFrame, priors: dict[str, float] | None = None) -> tuple[pd.DataFrame, dict[str, float]]:
    working = frame.copy()
    working["player_name"] = working["player_name"].map(_display_name)
    for column in ["appearance_pitch_number", "location_plus_pitch"]:
        working[column] = pd.to_numeric(working[column], errors="coerce")
    early = working[working["appearance_pitch_number"].le(20)]
    if priors is None:
        pitch_priors = early.groupby("pitch_type")["location_plus_pitch"].mean().to_dict()
        pitch_priors["__league__"] = float(early["location_plus_pitch"].mean())
    else:
        pitch_priors = priors
    baseline = early.groupby(["pitcher", "game_pk", "pitch_type"], as_index=False).agg(
        early_exact_pitches=("location_plus_pitch", "count"),
        early_location_raw=("location_plus_pitch", "mean"),
    )
    working = working.merge(baseline, on=["pitcher", "game_pk", "pitch_type"], how="left", validate="many_to_one")
    working["location_prior"] = working["pitch_type"].map(pitch_priors).fillna(pitch_priors["__league__"])
    n = working["early_exact_pitches"].fillna(0.0)
    weight = n / (n + EARLY_PRIOR_PITCHES)
    working["early_baseline_reliability"] = weight
    working["early_location"] = (
        weight * working["early_location_raw"].fillna(working["location_prior"])
        + (1.0 - weight) * working["location_prior"]
    )
    working["exact_type_supported"] = n.ge(MINIMUM_EARLY_EXACT_PITCHES)
    working["order"] = pd.cut(
        working["appearance_pitch_number"], bins=[20, 40, 60, 80, 100], labels=[1, 2, 3, 4]
    ).astype("float64")
    labels = {index: label for index, (_, _, label) in enumerate(WINDOWS, start=1)}
    working["analysis_bucket"] = working["order"].map(labels)
    return working, pitch_priors


def _fit_expected_model(development: pd.DataFrame) -> Pipeline:
    later = development[
        development["order"].notna() & development["exact_type_supported"] & development["early_location"].notna()
    ].copy()
    transformer = ColumnTransformer(
        [
            ("early_location", StandardScaler(), ["early_location"]),
            ("workload", SplineTransformer(n_knots=5, degree=3, include_bias=False), ["appearance_pitch_number"]),
            ("pitch_type", OneHotEncoder(handle_unknown="ignore", sparse_output=False), ["pitch_type"]),
        ],
        remainder="drop",
    )
    model = Pipeline([("features", transformer), ("ridge", Ridge(alpha=10.0))])
    model.fit(later[["early_location", "appearance_pitch_number", "pitch_type"]], later["location_plus_pitch"])
    return model


def _score_pitches(prepared: pd.DataFrame, model: Pipeline) -> pd.DataFrame:
    later = prepared[
        prepared["order"].notna() & prepared["exact_type_supported"] & prepared["early_location"].notna()
    ].copy()
    later["expected_location"] = model.predict(later[["early_location", "appearance_pitch_number", "pitch_type"]])
    later["expected_location_change"] = later["expected_location"] - later["early_location"]
    later["raw_location_change"] = later["location_plus_pitch"] - later["early_location"]
    later["command_residual"] = later["location_plus_pitch"] - later["expected_location"]
    return later


def _build_raw_windows(scored: pd.DataFrame, year: int) -> pd.DataFrame:
    keys = ["pitcher", "game_pk", "game_date", "order", "analysis_bucket"]
    family = scored.groupby(keys + ["pitch_family"], as_index=False).agg(
        pitcher_name=("player_name", "first"), team=("pitcher_team", "first"),
        pitches=("command_residual", "count"), retention=("command_residual", "mean"),
        observed_location_change=("raw_location_change", "mean"),
        early_location=("early_location", "mean"),
        early_baseline_reliability=("early_baseline_reliability", "mean"),
        pitch_variance=("command_residual", "var"),
    ).rename(columns={"pitch_family": "scope"})
    # Exact first-20 family weights are attached by the caller; absent weights are handled conservatively below.
    if "early_family_weight" not in scored.columns:
        scored["early_family_weight"] = np.nan
    weight_table = scored[["pitcher", "game_pk", "pitch_family", "early_family_weight"]].dropna().drop_duplicates(
        ["pitcher", "game_pk", "pitch_family"]
    )
    weight_lookup = {
        (int(pitcher), int(game_pk)): dict(zip(group["pitch_family"], group["early_family_weight"]))
        for (pitcher, game_pk), group in weight_table.groupby(["pitcher", "game_pk"], sort=False)
    }
    overall_rows: list[dict[str, Any]] = []
    for key, group in family.groupby(keys, sort=False):
        pitcher, game_pk, game_date, order, bucket = key
        weight_map = weight_lookup.get((int(pitcher), int(game_pk)), {})
        if not weight_map:
            counts = group.set_index("scope")["pitches"]
            weight_map = (counts / counts.sum()).to_dict()
        retention = 0.0
        coverage = 0.0
        for scope, weight in weight_map.items():
            match = group[group["scope"].eq(scope)]
            if len(match):
                retention += float(weight) * float(match["retention"].iloc[0])
                coverage += float(weight)
        total_pitches = int(group["pitches"].sum())
        observed = float(np.average(group["retention"], weights=group["pitches"]))
        overall_rows.append({
            "pitcher": int(pitcher), "game_pk": int(game_pk), "game_date": game_date,
            "order": int(order), "analysis_bucket": bucket,
            "pitcher_name": str(group["pitcher_name"].iloc[0]), "team": str(group["team"].iloc[0]),
            "scope": "Overall", "pitches": total_pitches, "retention": retention,
            "observed_mix_retention": observed, "fixed_mix_coverage": coverage,
            "observed_location_change": float(np.average(group["observed_location_change"], weights=group["pitches"])),
            "early_location": float(np.average(group["early_location"], weights=group["pitches"])),
            "early_baseline_reliability": float(np.average(group["early_baseline_reliability"], weights=group["pitches"])),
            "pitch_variance": float(np.nanmean(group["pitch_variance"])) if group["pitch_variance"].notna().any() else np.nan,
        })
    family["observed_mix_retention"] = np.nan
    family["fixed_mix_coverage"] = np.nan
    windows = pd.concat([pd.DataFrame(overall_rows), family], ignore_index=True, sort=False)
    windows["year"] = int(year)
    return windows


def _attach_early_family_weights(prepared: pd.DataFrame, scored: pd.DataFrame) -> pd.DataFrame:
    early = prepared[prepared["appearance_pitch_number"].le(20)].copy()
    counts = early.groupby(["pitcher", "game_pk", "pitch_family"], as_index=False).size().rename(columns={"size": "family_n"})
    totals = counts.groupby(["pitcher", "game_pk"])["family_n"].transform("sum")
    counts["early_family_weight"] = counts["family_n"] / totals.clip(lower=1)
    return scored.merge(
        counts[["pitcher", "game_pk", "pitch_family", "early_family_weight"]],
        on=["pitcher", "game_pk", "pitch_family"], how="left", validate="many_to_one",
    )


def _fit_scoring_reference(windows: pd.DataFrame, residual_variance: float) -> dict[str, Any]:
    parameters: dict[str, Any] = {}
    for scope in ("Overall", *FAMILIES):
        subset = windows[windows["scope"].eq(scope)]
        games = subset.groupby(["pitcher", "game_pk"], as_index=False).agg(
            raw_retention=("retention", "mean"), pitches=("pitches", "sum")
        )
        center = float(games["raw_retention"].median()) if len(games) else 0.0
        scale = float((games["raw_retention"] - center).abs().median() * 1.4826) if len(games) else 1.0
        scale = max(scale, 1.0)
        median_sampling = residual_variance / max(float(games["pitches"].median()) if len(games) else 15.0, 1.0)
        between_variance = max(float(games["raw_retention"].var(ddof=1)) - median_sampling, 1.0) if len(games) > 1 else 1.0
        parameters[scope] = {"center": center, "scale": scale, "between_variance": between_variance}
    return {"residual_variance": max(float(residual_variance), 1.0), "scopes": parameters}


def _score_windows_and_games(raw: pd.DataFrame, reference: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    windows = raw.copy()
    residual_variance = float(reference["residual_variance"])
    window_scores: list[pd.DataFrame] = []
    game_scores: list[pd.DataFrame] = []
    for scope, parameters in reference["scopes"].items():
        part = windows[windows["scope"].eq(scope)].copy()
        if part.empty:
            continue
        part["sampling_variance"] = residual_variance / part["pitches"].clip(lower=1)
        part["raw_command_retention_plus"] = 100.0 + 10.0 * (part["retention"] - parameters["center"]) / parameters["scale"]
        part["reliability"] = parameters["between_variance"] / (parameters["between_variance"] + part["sampling_variance"])
        part["command_retention_plus"] = 100.0 + part["reliability"] * (part["raw_command_retention_plus"] - 100.0)
        posterior_var = parameters["between_variance"] * part["sampling_variance"] / (
            parameters["between_variance"] + part["sampling_variance"]
        )
        half = 1.281552 * np.sqrt(posterior_var) * 10.0 / parameters["scale"]
        part["ci_low"] = part["command_retention_plus"] - half
        part["ci_high"] = part["command_retention_plus"] + half
        minimum = MINIMUM_GAME_PITCHES if scope == "Overall" else MINIMUM_WINDOW_PITCHES
        part["eligible"] = part["pitches"].ge(MINIMUM_WINDOW_PITCHES)
        if scope == "Overall":
            part["eligible"] &= part["fixed_mix_coverage"].ge(MINIMUM_FIXED_MIX_COVERAGE)
        window_scores.append(part)

        rows: list[dict[str, Any]] = []
        for (pitcher, game_pk), group in part.groupby(["pitcher", "game_pk"], sort=False):
            weights = group["pitches"].to_numpy(dtype="float64")
            raw_retention = float(np.average(group["retention"], weights=weights))
            pitches = int(group["pitches"].sum())
            sampling = residual_variance / max(pitches, 1)
            reliability = parameters["between_variance"] / (parameters["between_variance"] + sampling)
            raw_plus = 100.0 + 10.0 * (raw_retention - parameters["center"]) / parameters["scale"]
            score = 100.0 + reliability * (raw_plus - 100.0)
            posterior = parameters["between_variance"] * sampling / (parameters["between_variance"] + sampling)
            halfwidth = 1.281552 * np.sqrt(posterior) * 10.0 / parameters["scale"]
            mix_coverage = float(np.average(group["fixed_mix_coverage"].fillna(1.0), weights=weights))
            rows.append({
                "pitcher": int(pitcher), "game_pk": int(game_pk), "game_date": group["game_date"].iloc[0],
                "pitcher_name": str(group["pitcher_name"].iloc[0]), "team": str(group["team"].iloc[0]),
                "year": int(group["year"].iloc[0]), "scope": scope, "windows": int(len(group)),
                "late_pitches": pitches, "raw_retention": raw_retention,
                "raw_command_retention_plus": raw_plus, "command_retention_plus": score,
                "ci_low": score - halfwidth, "ci_high": score + halfwidth,
                "reliability": reliability, "fixed_mix_coverage": mix_coverage,
                "early_location": float(np.average(group["early_location"], weights=weights)),
                "early_baseline_reliability": float(np.average(group["early_baseline_reliability"], weights=weights)),
                "eligible": pitches >= minimum and (scope != "Overall" or mix_coverage >= MINIMUM_FIXED_MIX_COVERAGE),
            })
        game_scores.append(pd.DataFrame(rows))
    scored_windows = pd.concat(window_scores, ignore_index=True)
    games = pd.concat(game_scores, ignore_index=True)
    games["confidence"] = np.select(
        [games["reliability"].ge(0.75), games["reliability"].ge(0.50)], ["high", "medium"], default="low"
    )
    games = games.sort_values(["pitcher", "game_date", "game_pk", "scope"], kind="stable")
    starts = games[["pitcher", "game_pk", "game_date"]].drop_duplicates().sort_values(["pitcher", "game_date", "game_pk"])
    starts["season_start_number"] = starts.groupby("pitcher").cumcount() + 1
    games = games.merge(starts[["pitcher", "game_pk", "season_start_number"]], on=["pitcher", "game_pk"], how="left")
    for frame in (scored_windows, games):
        for column in ["raw_command_retention_plus", "command_retention_plus", "ci_low", "ci_high", "reliability"]:
            frame[column] = pd.to_numeric(frame[column], errors="coerce").round(4)
    return scored_windows, games


def _command_audit(
    year: int, scored_pitches: pd.DataFrame, windows: pd.DataFrame, games: pd.DataFrame
) -> dict[str, Any]:
    baseline_rmse = float(np.sqrt(mean_squared_error(scored_pitches["location_plus_pitch"], scored_pitches["early_location"])))
    model_rmse = float(np.sqrt(mean_squared_error(scored_pitches["location_plus_pitch"], scored_pitches["expected_location"])))
    overall = games[(games["scope"].eq("Overall")) & games["eligible"]]
    early_relation = _spearman(overall["command_retention_plus"], overall["early_location"])
    overall_windows = windows[windows["scope"].eq("Overall")]
    fixed_relation = _spearman(overall_windows["retention"], overall_windows["observed_mix_retention"])
    pivot = overall_windows[overall_windows["eligible"]].pivot_table(
        index=["pitcher", "game_pk"], columns="order", values="command_retention_plus", aggfunc="first"
    )
    split = _spearman(pivot.get(1, pd.Series(dtype="float64")), pivot.get(3, pd.Series(dtype="float64")))
    return {
        "year": int(year), "pitch_rows": int(len(scored_pitches)), "window_rows": int(len(windows)),
        "game_rows": int(len(games)), "eligible_overall_games": int(len(overall)),
        "pitchers": int(overall["pitcher"].nunique()),
        "pitch_model_rmse": round(model_rmse, 3), "pitch_baseline_rmse": round(baseline_rmse, 3),
        "pitch_rmse_improvement_pct": round((baseline_rmse - model_rmse) / baseline_rmse * 100.0, 2),
        "early_location_spearman": round(early_relation, 3) if early_relation is not None else None,
        "fixed_vs_observed_mix_spearman": round(fixed_relation, 3) if fixed_relation is not None else None,
        "split_window_spearman": round(split, 3) if split is not None else None,
        "median_reliability": round(float(overall["reliability"].median()), 3) if len(overall) else 0.0,
        "median_interval_width": round(float((overall["ci_high"] - overall["ci_low"]).median()), 3) if len(overall) else 0.0,
        "score_p05": round(float(overall["command_retention_plus"].quantile(.05)), 1) if len(overall) else None,
        "score_p50": round(float(overall["command_retention_plus"].median()), 1) if len(overall) else None,
        "score_p95": round(float(overall["command_retention_plus"].quantile(.95)), 1) if len(overall) else None,
    }


def _load_validation_frame(year: int, root: Path) -> tuple[pd.DataFrame, int]:
    quality_path = _quality_window_path(year, root)
    physical_path = _physical_window_path(year, root)
    command_path = command_window_path(year, root)
    for path in [quality_path, physical_path, command_path]:
        if not path.exists():
            raise FileNotFoundError(f"Slice 18 requires artifact: {path}")
    quality = pd.read_parquet(quality_path)
    quality = quality[quality["scope"].eq("Overall")]
    early_quality = quality[quality["order"].eq(1)][["pitcher", "game_pk", "retention"]].rename(
        columns={"retention": "early_quality"}
    )
    late_quality = quality[quality["order"].eq(3)][["pitcher", "game_pk", "retention"]].rename(
        columns={"retention": "late_quality"}
    )
    eligible_pairs = early_quality.merge(late_quality, on=["pitcher", "game_pk"], how="inner")
    physical = pd.read_parquet(physical_path)
    physical = physical[(physical["order"].eq(1)) & physical["eligible"]][
        ["pitcher", "game_pk", "physical_stability_plus", "velocity_plus"]
    ]
    command = pd.read_parquet(command_path)
    command = command[(command["scope"].eq("Overall")) & (command["order"].eq(1)) & command["eligible"]][
        ["pitcher", "game_pk", "command_retention_plus"]
    ]
    matched = eligible_pairs.merge(physical, on=["pitcher", "game_pk"], how="inner").merge(
        command, on=["pitcher", "game_pk"], how="inner"
    ).dropna()
    return matched, len(eligible_pairs)


def _fit_ridge(train: pd.DataFrame, features: list[str]) -> Pipeline:
    model = Pipeline([("scale", StandardScaler()), ("ridge", Ridge(alpha=10.0))])
    model.fit(train[features], train["late_quality"])
    return model


def _prediction_audit(model: Pipeline, test: pd.DataFrame, features: list[str]) -> dict[str, float | None]:
    prediction = pd.Series(model.predict(test[features]), index=test.index)
    rmse = float(np.sqrt(mean_squared_error(test["late_quality"], prediction)))
    correlation = _spearman(prediction, test["late_quality"])
    slope = None
    if prediction.nunique() > 1:
        slope = float(np.polyfit(prediction, test["late_quality"], 1)[0])
    return {
        "rmse": round(rmse, 4), "spearman": round(correlation, 4) if correlation is not None else None,
        "calibration_slope": round(slope, 4) if slope is not None and np.isfinite(slope) else None,
    }


def refresh_incremental_validation(year: int = 2026, data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    train, train_pairs = _load_validation_frame(VALIDATION_TRAIN_YEAR, root)
    test, test_pairs = _load_validation_frame(VALIDATION_TEST_YEAR, root)
    baseline_features = ["early_quality"]
    velocity_features = ["early_quality", "velocity_plus"]
    challenger_features = ["early_quality", "physical_stability_plus", "command_retention_plus"]
    baseline = _prediction_audit(_fit_ridge(train, baseline_features), test, baseline_features)
    velocity = _prediction_audit(_fit_ridge(train, velocity_features), test, velocity_features)
    challenger_model = _fit_ridge(train, challenger_features)
    challenger = _prediction_audit(challenger_model, test, challenger_features)
    baseline_rmse = float(baseline["rmse"] or np.nan)
    challenger_rmse = float(challenger["rmse"] or np.nan)
    improvement = (baseline_rmse - challenger_rmse) / baseline_rmse * 100.0
    velocity_improvement = (float(velocity["rmse"] or np.nan) - challenger_rmse) / float(velocity["rmse"] or np.nan) * 100.0
    pairwise = {
        "quality_vs_physical": _spearman(test["early_quality"], test["physical_stability_plus"]),
        "quality_vs_command": _spearman(test["early_quality"], test["command_retention_plus"]),
        "physical_vs_command": _spearman(test["physical_stability_plus"], test["command_retention_plus"]),
    }
    maximum_overlap = max(abs(value) for value in pairwise.values() if value is not None)
    coverage_pct = len(test) / max(test_pairs, 1) * 100.0
    gates = [
        {"key": "test_sample", "label": "Matched 2026 starts", "threshold": ">= 500", "value": len(test), "passed": len(test) >= 500},
        {"key": "matched_coverage", "label": "Matched-pair coverage", "threshold": ">= 70%", "value": round(coverage_pct, 2), "passed": coverage_pct >= 70.0},
        {"key": "rmse_gain", "label": "RMSE gain over early Quality", "threshold": ">= 1%", "value": round(improvement, 3), "passed": improvement >= 1.0},
        {"key": "velocity_gain", "label": "RMSE gain over velocity comparator", "threshold": "> 0%", "value": round(velocity_improvement, 3), "passed": velocity_improvement > 0.0},
        {"key": "calibration", "label": "2026 calibration slope", "threshold": "0.80–1.20", "value": challenger["calibration_slope"], "passed": challenger["calibration_slope"] is not None and 0.80 <= float(challenger["calibration_slope"]) <= 1.20},
        {"key": "distinctness", "label": "Maximum pairwise Spearman", "threshold": "<= 0.80", "value": round(maximum_overlap, 3), "passed": maximum_overlap <= 0.80},
    ]
    release_eligible = all(gate["passed"] for gate in gates)
    ridge = challenger_model.named_steps["ridge"]
    payload = {
        "status": "completed", "publication_status": "research_only", "validation_version": VALIDATION_VERSION,
        "train_year": VALIDATION_TRAIN_YEAR, "test_year": VALIDATION_TEST_YEAR,
        "predictor_window": "21–40", "target_window": "61–80",
        "method": "Frozen 2025-to-2026 Ridge audit: early Quality baseline versus adding independent Physical Stability+ and Command Retention+.",
        "train_rows": int(len(train)), "test_rows": int(len(test)),
        "train_pair_coverage_pct": round(len(train) / max(train_pairs, 1) * 100.0, 2),
        "test_pair_coverage_pct": round(coverage_pct, 2),
        "models": {"baseline": baseline, "velocity_comparator": velocity, "challenger": challenger},
        "rmse_improvement_pct": round(improvement, 3), "rmse_improvement_over_velocity_pct": round(velocity_improvement, 3),
        "pairwise_spearman": {key: round(value, 4) if value is not None else None for key, value in pairwise.items()},
        "challenger_standardized_coefficients": {
            name: round(float(value), 5) for name, value in zip(challenger_features, ridge.coef_)
        },
        "gates": gates, "composite_release_eligible": release_eligible,
        "decision": "Eligible for Slice 19 composite review." if release_eligible else "Keep Quality, Physical, and Command separate; no composite score is released.",
        "warnings": [
            "This tests within-game incremental information, not injury risk or medical status.",
            "2026 is chronologically held out for this frozen formula, but it is not globally untouched by earlier exploratory work.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_json_atomic(payload, incremental_validation_path(year, root))
    return payload


def refresh_command_retention(year: int = 2026, data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    years = [candidate for candidate in range(DEVELOPMENT_YEAR, int(year) + 1) if _dataset_path(candidate, root).exists()]
    if DEVELOPMENT_YEAR not in years:
        raise FileNotFoundError(f"Command Retention+ requires the {DEVELOPMENT_YEAR} Stamina dataset.")
    prepared: dict[int, pd.DataFrame] = {}
    development, priors = _prepare_pitch_rows(_load_source(DEVELOPMENT_YEAR, root))
    prepared[DEVELOPMENT_YEAR] = development
    for candidate in years:
        if candidate != DEVELOPMENT_YEAR:
            prepared[candidate], _ = _prepare_pitch_rows(_load_source(candidate, root), priors)
    model = _fit_expected_model(development)
    development_scored = _attach_early_family_weights(development, _score_pitches(development, model))
    development_raw = _build_raw_windows(development_scored, DEVELOPMENT_YEAR)
    reference = _fit_scoring_reference(development_raw, float(development_scored["command_residual"].var(ddof=1)))
    year_audits: list[dict[str, Any]] = []
    target_games = pd.DataFrame()
    for candidate in years:
        scored = development_scored if candidate == DEVELOPMENT_YEAR else _attach_early_family_weights(
            prepared[candidate], _score_pitches(prepared[candidate], model)
        )
        raw = development_raw if candidate == DEVELOPMENT_YEAR else _build_raw_windows(scored, candidate)
        windows, games = _score_windows_and_games(raw, reference)
        _write_parquet_atomic(windows, command_window_path(candidate, root), "command_windows")
        _write_parquet_atomic(games, command_game_path(candidate, root), "command_games")
        year_audits.append(_command_audit(candidate, scored, windows, games))
        if candidate == int(year):
            target_games = games
    players = []
    if len(target_games):
        source = target_games[(target_games["scope"].eq("Overall")) & target_games["eligible"]]
        for pitcher, group in source.groupby("pitcher", sort=False):
            players.append({
                "pitcher_id": int(pitcher), "name": str(group["pitcher_name"].iloc[-1]),
                "team": str(group["team"].iloc[-1]), "appearances": int(len(group)),
            })
        players.sort(key=lambda row: row["name"])
    payload = {
        "status": "completed", "publication_status": "research_only", "contract_version": CONTRACT_VERSION,
        "model_version": MODEL_VERSION, "development_year": DEVELOPMENT_YEAR, "scoring_year": int(year),
        "covered_years": years, "minimum_early_exact_pitches": MINIMUM_EARLY_EXACT_PITCHES,
        "minimum_window_pitches": MINIMUM_WINDOW_PITCHES, "minimum_game_pitches": MINIMUM_GAME_PITCHES,
        "minimum_fixed_mix_coverage_pct": MINIMUM_FIXED_MIX_COVERAGE * 100.0,
        "method": "Location+ change is residualized against a frozen 2023 pitch-count spline and exact pitch type, then summarized with the first-20 family mix.",
        "players": players, "year_audits": year_audits,
        "warnings": [
            "Command Retention+ is independent of Stuff+ and is not merged into the published Stamina+.",
            "A missing early pitch family is not reweighted away; its missing weight lowers fixed-mix coverage.",
            "Higher means Location+ held up better than the 2023 pitch-count and pitch-type expectation.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_json_atomic(payload, command_contract_path(year, root))
    return payload


def refresh_slices_17_18(year: int = 2026, data_dir: Path | None = None) -> dict[str, Any]:
    command = refresh_command_retention(year, data_dir)
    validation = refresh_incremental_validation(year, data_dir)
    return {"slice17": command, "slice18": validation}


def refresh_product_integration(year: int = 2026, data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    paths = {
        "quality": root / "derived" / f"stamina_game_states_{int(year)}.parquet",
        "physical": root / "derived" / f"stamina_physical_games_{int(year)}.parquet",
        "command": command_game_path(year, root),
        "validation": incremental_validation_path(year, root),
    }
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Slice 19 requires existing artifacts: {', '.join(missing)}")

    quality = pd.read_parquet(paths["quality"])
    quality = quality[(quality["scope"].eq("Overall")) & quality["eligible"]]
    quality = quality.groupby("pitcher", as_index=False).agg(
        pitcher_name=("pitcher_name", "last"), team=("team", "last"),
        quality_games=("game_pk", "nunique"), quality_stamina_plus=("stamina_plus", "mean"),
        quality_reliability=("reliability", "median"),
    )
    quality["pitcher_name"] = quality["pitcher_name"].map(_display_name)

    physical = pd.read_parquet(paths["physical"])
    physical = physical[physical["eligible"]].groupby("pitcher", as_index=False).agg(
        physical_games=("game_pk", "nunique"), physical_stability_plus=("physical_stability_plus", "mean"),
        physical_reliability=("reliability", "median"),
    )
    command = pd.read_parquet(paths["command"])
    command = command[(command["scope"].eq("Overall")) & command["eligible"]].groupby("pitcher", as_index=False).agg(
        command_games=("game_pk", "nunique"), command_retention_plus=("command_retention_plus", "mean"),
        command_reliability=("reliability", "median"),
    )
    joined = quality.merge(physical, on="pitcher", how="inner").merge(command, on="pitcher", how="inner")
    qualified = joined[
        joined[["quality_games", "physical_games", "command_games"]].min(axis=1).ge(10)
    ].copy()
    for metric in ["quality_stamina_plus", "physical_stability_plus", "command_retention_plus"]:
        scale = max(float(qualified[metric].std(ddof=1)), 0.1)
        qualified[f"{metric}_z"] = (qualified[metric] - qualified[metric].mean()) / scale

    cases: list[tuple[str, pd.Series]] = []
    named = qualified[qualified["pitcher_name"].isin(["Dylan Cease", "Shane Baz", "Kyle Leahy"])]
    for _, row in named.iterrows():
        cases.append(("named_review", row))
    archetypes = {
        "quality_over_physical": qualified["quality_stamina_plus_z"] - qualified["physical_stability_plus_z"],
        "quality_over_command": qualified["quality_stamina_plus_z"] - qualified["command_retention_plus_z"],
        "physical_over_quality": qualified["physical_stability_plus_z"] - qualified["quality_stamina_plus_z"],
        "balanced_high": qualified[[
            "quality_stamina_plus_z", "physical_stability_plus_z", "command_retention_plus_z"
        ]].min(axis=1),
    }
    used = {int(row["pitcher"]) for _, row in cases}
    for label, values in archetypes.items():
        for index in values.sort_values(ascending=False).index:
            row = qualified.loc[index]
            if int(row["pitcher"]) not in used:
                cases.append((label, row))
                used.add(int(row["pitcher"]))
                break

    representative_pitchers = []
    for case, row in cases:
        representative_pitchers.append({
            "case": case, "pitcher_id": int(row["pitcher"]), "name": str(row["pitcher_name"]),
            "team": str(row["team"]), "quality_games": int(row["quality_games"]),
            "physical_games": int(row["physical_games"]), "command_games": int(row["command_games"]),
            "quality_stamina_plus": round(float(row["quality_stamina_plus"]), 1),
            "physical_stability_plus": round(float(row["physical_stability_plus"]), 1),
            "command_retention_plus": round(float(row["command_retention_plus"]), 1),
            "quality_reliability": round(float(row["quality_reliability"]), 3),
            "physical_reliability": round(float(row["physical_reliability"]), 3),
            "command_reliability": round(float(row["command_reliability"]), 3),
        })

    validation = json.loads(paths["validation"].read_text(encoding="utf-8"))
    payload = {
        "status": "completed", "publication_status": "research_only",
        "contract_version": PRODUCT_INTEGRATION_VERSION, "year": int(year),
        "decision": "keep_separate", "composite_release_eligible": bool(validation["composite_release_eligible"]),
        "method": "Align Quality Stamina+, Physical Stability+, and Command Retention+ by game while preserving separate scales, reliability, and intervals.",
        "qualified_three_signal_pitchers": int(len(qualified)),
        "representative_pitchers": representative_pitchers,
        "product_rules": [
            "Use synchronized small multiples with one shared game axis and one shared 70–130 Plus scale.",
            "Never average the three scores or label their disagreement as injury risk.",
            "Show each score's own reliability and 80% interval; missing values stay unavailable.",
            "Reconsider a composite only after a future frozen validation passes the incremental RMSE gates.",
        ],
        "warnings": [
            "The three signals describe observed performance and tracking states, not physiology or medical status.",
            "A large difference between panels is an interpretation prompt, not an automatic alert.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_json_atomic(payload, product_integration_path(year, root))
    return payload


def get_command_retention(year: int, pitcher_id: int, data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    contract = command_contract_path(year, root)
    windows_path = command_window_path(year, root)
    games_path = command_game_path(year, root)
    if not contract.exists() or not windows_path.exists() or not games_path.exists():
        raise FileNotFoundError(f"Command Retention+ artifacts for {year} are not built.")
    metadata = json.loads(contract.read_text(encoding="utf-8"))
    games = pd.read_parquet(games_path)
    games = games[games["pitcher"].eq(int(pitcher_id))].copy()
    if games.empty:
        raise ValueError(f"Pitcher {pitcher_id} has no Command Retention+ data for {year}.")
    windows = pd.read_parquet(windows_path)
    windows = windows[windows["pitcher"].eq(int(pitcher_id))].copy()
    for frame in (games, windows):
        frame["game_date"] = pd.to_datetime(frame["game_date"]).dt.strftime("%Y-%m-%d")
        frame.replace({np.nan: None}, inplace=True)
    return {
        "year": int(year), "publication_status": metadata["publication_status"], "pitcher_id": int(pitcher_id),
        "pitcher_name": str(games["pitcher_name"].iloc[-1]), "team": str(games["team"].iloc[-1]),
        "games": games.to_dict("records"), "windows": windows.to_dict("records"), "warnings": metadata["warnings"],
    }


def get_incremental_validation(year: int = 2026, data_dir: Path | None = None) -> dict[str, Any]:
    path = incremental_validation_path(year, Path(data_dir or settings.data_dir))
    if not path.exists():
        raise FileNotFoundError(f"Slice 18 artifact for {year} is not built.")
    return json.loads(path.read_text(encoding="utf-8"))
