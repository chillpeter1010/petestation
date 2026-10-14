from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd
from arch.univariate import StudentsT
from hmmlearn.hmm import GaussianHMM
from scipy.linalg import fractional_matrix_power
from scipy.optimize import linear_sum_assignment, minimize
from scipy.special import logsumexp
from scipy.stats import chi2, genpareto, kstest
from scipy.stats import t as student_t
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import average_precision_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.core.config import settings
from app.services.performance_state_service import (
    DEVELOPMENT_YEAR,
    ROLES,
    STATE_MODEL_VERSION,
    TEST_YEAR,
    filtered_state_path,
)


ADVANCED_MODEL_VERSION = "performance_state_regime_volatility_v1"
REGIME_MODEL_VERSION = "role_gaussian_hmm_calendar_transition_v1"
GAS_MODEL_VERSION = "student_t_gas_har_panel_v1"
GJR_MODEL_VERSION = "student_t_gjr_garch_panel_v1"
TAIL_MODEL_VERSION = "pot_evt_caviar_panel_v1"
REGIME_FEATURES = (
    "stuff_state_filtered",
    "stuff_state_change",
    "stuff_innovation_volatility5",
)
VOLATILITY_SIGNAL = "stuff_state_standardized_innovation"
LONG_GAP_RESET_DAYS = 60.0


def advanced_audit_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "performance_state_slice4_6.json"


def advanced_state_path(year: int, data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / f"performance_state_advanced_{int(year)}.parquet"


def tail_audit_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "performance_state_slice7.json"


def tail_state_path(year: int, data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / f"performance_state_tail_{int(year)}.parquet"


def _number(value: Any, digits: int = 4) -> float | None:
    numeric = pd.to_numeric(value, errors="coerce")
    return round(float(numeric), digits) if pd.notna(numeric) and np.isfinite(float(numeric)) else None


def _write_json_atomic(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def _write_parquet_atomic(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp.parquet")
    with duckdb.connect() as connection:
        connection.register("advanced_states", frame)
        target = str(temporary).replace("'", "''")
        connection.execute(f"COPY advanced_states TO '{target}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    temporary.replace(path)


def _load_filtered_panel(root: Path, years: tuple[int, int]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for year in years:
        path = filtered_state_path(year, root)
        if not path.exists():
            raise FileNotFoundError(f"Performance State filtered artifact not found: {path}")
        with duckdb.connect() as connection:
            frame = connection.execute("SELECT * FROM read_parquet(?)", [str(path)]).fetchdf()
        frame["year"] = int(year)
        frames.append(frame)
    panel = pd.concat(frames, ignore_index=True)
    panel["game_date"] = pd.to_datetime(panel["game_date"], errors="coerce")
    panel = panel.sort_values(["pitcher_id", "role", "game_date", "game_pk"], kind="stable").reset_index(drop=True)
    groups = panel.groupby(["pitcher_id", "role"], sort=False)
    panel["stuff_state_change"] = groups["stuff_state_filtered"].diff()
    panel["stuff_innovation_volatility5"] = groups[VOLATILITY_SIGNAL].transform(
        lambda values: values.rolling(5, min_periods=3).std()
    )
    squared = pd.to_numeric(panel[VOLATILITY_SIGNAL], errors="coerce").pow(2)
    panel["lag_innovation_squared"] = groups[VOLATILITY_SIGNAL].shift(1).pow(2)
    panel["innovation_variance5"] = squared.groupby([panel["pitcher_id"], panel["role"]]).transform(
        lambda values: values.shift(1).rolling(5, min_periods=2).mean()
    )
    panel["innovation_variance15"] = squared.groupby([panel["pitcher_id"], panel["role"]]).transform(
        lambda values: values.shift(1).rolling(15, min_periods=3).mean()
    )
    return panel


def _role_feature_matrix(
    panel: pd.DataFrame,
    role: str,
    development_year: int,
) -> tuple[np.ndarray, dict[str, list[float]]]:
    role_rows = panel[panel["role"].eq(role)]
    development = role_rows[role_rows["year"].eq(development_year)]
    means = development[list(REGIME_FEATURES)].mean(skipna=True).fillna(0.0)
    scales = development[list(REGIME_FEATURES)].std(ddof=1, skipna=True).replace(0, np.nan).fillna(1.0)
    matrix = ((role_rows[list(REGIME_FEATURES)] - means) / scales).fillna(0.0).to_numpy(dtype=float)
    return matrix, {
        "means": [float(means[column]) for column in REGIME_FEATURES],
        "scales": [float(scales[column]) for column in REGIME_FEATURES],
    }


def _sequence_lengths(rows: pd.DataFrame) -> list[int]:
    return rows.groupby(["pitcher_id", "role"], sort=False).size().astype(int).tolist()


def _fit_hmm_candidate(
    matrix: np.ndarray,
    lengths: list[int],
    states: int,
    seeds: tuple[int, ...] = (17, 41),
) -> GaussianHMM:
    best: GaussianHMM | None = None
    best_score = -float("inf")
    for seed in seeds:
        model = GaussianHMM(
            n_components=states,
            covariance_type="diag",
            n_iter=75,
            tol=1e-4,
            min_covar=1e-3,
            random_state=seed,
            implementation="log",
        )
        model.fit(matrix, lengths)
        score = float(model.score(matrix, lengths))
        if np.isfinite(score) and score > best_score:
            best, best_score = model, score
    if best is None:
        raise RuntimeError(f"No converged HMM candidate for {states} states.")
    return best


def _model_parameter_count(states: int, dimensions: int) -> int:
    return (states - 1) + states * (states - 1) + 2 * states * dimensions


def _safe_hmm_score(model: GaussianHMM, matrix: np.ndarray, lengths: list[int]) -> float:
    return float(model.score(matrix, lengths)) if len(matrix) else float("nan")


def _regime_labels(means: np.ndarray) -> dict[int, str]:
    states = len(means)
    label_sets = {
        2: ("stable", "collapse"),
        3: ("stable", "collapse", "high_volatility"),
        4: ("stable", "declining", "collapse", "recovering"),
        5: ("stable", "declining", "collapse", "recovering", "high_volatility"),
    }
    prototypes = {
        "stable": np.array([0.0, 0.0, -0.6]),
        "declining": np.array([-0.4, -1.0, 0.0]),
        "collapse": np.array([-1.5, -1.0, 0.7]),
        "recovering": np.array([0.5, 1.0, 0.0]),
        "high_volatility": np.array([0.0, 0.0, 1.5]),
    }
    labels = label_sets[states]
    cost = np.vstack([np.square(means - prototypes[label]).sum(axis=1) for label in labels])
    label_indices, state_indices = linear_sum_assignment(cost)
    return {int(state): labels[int(label_index)] for label_index, state in zip(label_indices, state_indices)}


def _stationary_distribution(transition: np.ndarray) -> np.ndarray:
    values, vectors = np.linalg.eig(transition.T)
    vector = np.real(vectors[:, np.argmin(np.abs(values - 1.0))])
    vector = np.maximum(vector, 0.0)
    if vector.sum() <= 0:
        return np.full(len(transition), 1.0 / len(transition))
    return vector / vector.sum()


def _gap_transition(transition: np.ndarray, gap_days: float, median_gap_days: float) -> np.ndarray:
    if np.isfinite(gap_days) and gap_days >= LONG_GAP_RESET_DAYS:
        stationary = _stationary_distribution(transition)
        return np.tile(stationary, (len(transition), 1))
    units = max(float(gap_days) / max(median_gap_days, 1.0), 0.25) if np.isfinite(gap_days) else 1.0
    powered = np.real_if_close(fractional_matrix_power(transition, units)).real
    powered = np.clip(powered, 1e-12, None)
    return powered / powered.sum(axis=1, keepdims=True)


def _filtered_regime_probabilities(
    model: GaussianHMM,
    matrix: np.ndarray,
    rows: pd.DataFrame,
    median_gap_days: float,
) -> tuple[np.ndarray, np.ndarray, float]:
    emissions = model._compute_log_likelihood(matrix)
    prior_output = np.zeros_like(emissions)
    posterior_output = np.zeros_like(emissions)
    log_likelihood = 0.0
    start = 0
    for _, group in rows.groupby(["pitcher_id", "role"], sort=False):
        probability = np.asarray(model.startprob_, dtype=float)
        group_length = len(group)
        for local_index in range(group_length):
            index = start + local_index
            gap = pd.to_numeric(group.iloc[local_index]["calendar_days_since_prior"], errors="coerce")
            if local_index == 0 or (pd.notna(gap) and float(gap) >= LONG_GAP_RESET_DAYS):
                prior = np.asarray(model.startprob_, dtype=float)
            else:
                prior = probability @ _gap_transition(model.transmat_, float(gap), median_gap_days)
            prior = np.clip(prior, 1e-12, None)
            prior /= prior.sum()
            prior_output[index] = prior
            log_joint = np.log(prior) + emissions[index]
            normalizer = float(logsumexp(log_joint))
            probability = np.exp(log_joint - normalizer)
            posterior_output[index] = probability
            log_likelihood += normalizer
        start += group_length
    return prior_output, posterior_output, log_likelihood


def _bootstrap_emission_stability(
    rows: pd.DataFrame,
    matrix: np.ndarray,
    selected: GaussianHMM,
    states: int,
    samples: int = 3,
) -> dict[str, Any]:
    rng = np.random.default_rng(20261005)
    keys = rows[["pitcher_id", "role"]].drop_duplicates().reset_index(drop=True)
    reference_order = np.argsort(selected.means_[:, 0])
    reference = selected.means_[reference_order, 0]
    reference_transition = selected.transmat_[np.ix_(reference_order, reference_order)]
    emission_similarities: list[float] = []
    transition_similarities: list[float] = []
    for sample in range(samples):
        selected_keys = keys.iloc[rng.integers(0, len(keys), len(keys))]
        blocks: list[np.ndarray] = []
        lengths: list[int] = []
        for pitcher_id, role in selected_keys.itertuples(index=False, name=None):
            mask = rows["pitcher_id"].eq(pitcher_id) & rows["role"].eq(role)
            block = matrix[mask.to_numpy()]
            if len(block):
                blocks.append(block)
                lengths.append(len(block))
        try:
            fitted = _fit_hmm_candidate(np.vstack(blocks), lengths, states, seeds=(sample + 101,))
            fitted_order = np.argsort(fitted.means_[:, 0])
            ordered = fitted.means_[fitted_order, 0]
            fitted_transition = fitted.transmat_[np.ix_(fitted_order, fitted_order)]
            scale = max(float(np.std(reference)), 0.25)
            emission_similarities.append(float(np.exp(-np.mean(np.abs(ordered - reference)) / scale)))
            transition_similarities.append(
                float(np.exp(-np.mean(np.abs(fitted_transition - reference_transition)) / 0.25))
            )
        except Exception:
            emission_similarities.append(0.0)
            transition_similarities.append(0.0)
    return {
        "samples": samples,
        "median_emission_similarity": _number(np.median(emission_similarities)),
        "minimum_emission_similarity": _number(np.min(emission_similarities)),
        "median_transition_similarity": _number(np.median(transition_similarities)),
        "minimum_transition_similarity": _number(np.min(transition_similarities)),
    }


def _fit_regime_models(
    panel: pd.DataFrame,
    development_year: int,
    test_year: int,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    output = panel[["year", "pitcher_id", "role", "game_pk", "game_date"]].copy()
    for label in ("stable", "declining", "collapse", "recovering", "high_volatility"):
        output[f"regime_prior_{label}"] = np.nan
        output[f"regime_filtered_{label}"] = np.nan
    output["regime_filtered_label"] = None
    audit: dict[str, Any] = {
        "version": REGIME_MODEL_VERSION,
        "development_year": development_year,
        "external_diagnostic_year": test_year,
        "evaluation_status": "test_with_documented_slice3a_amendment",
        "roles": {},
    }
    for role in ROLES:
        role_mask = panel["role"].eq(role)
        rows = panel.loc[role_mask].copy().reset_index()
        matrix, scaling = _role_feature_matrix(panel, role, development_year)
        development_mask = rows["year"].eq(development_year).to_numpy()
        development_rows = rows.loc[development_mask]
        development_matrix = matrix[development_mask]
        cutoff = development_rows["game_date"].quantile(0.80)
        fit_mask = development_rows["game_date"].le(cutoff).to_numpy()
        validation_mask = ~fit_mask
        fit_rows = development_rows.loc[fit_mask]
        validation_rows = development_rows.loc[validation_mask]
        fit_matrix = development_matrix[fit_mask]
        validation_matrix = development_matrix[validation_mask]
        candidates: list[dict[str, Any]] = []
        fitted_models: dict[int, GaussianHMM] = {}
        for states in range(2, 6):
            model = _fit_hmm_candidate(fit_matrix, _sequence_lengths(fit_rows), states)
            fitted_models[states] = model
            train_ll = _safe_hmm_score(model, fit_matrix, _sequence_lengths(fit_rows))
            validation_ll = _safe_hmm_score(model, validation_matrix, _sequence_lengths(validation_rows))
            posterior = model.predict_proba(fit_matrix, _sequence_lengths(fit_rows))
            occupancy = posterior.mean(axis=0)
            parameters = _model_parameter_count(states, fit_matrix.shape[1])
            bic = -2.0 * train_ll + parameters * math.log(len(fit_matrix))
            penalized_validation = validation_ll / len(validation_matrix) - 0.5 * parameters * math.log(
                len(fit_matrix)
            ) / len(fit_matrix)
            candidates.append({
                "states": states,
                "train_rows": int(len(fit_matrix)),
                "validation_rows": int(len(validation_matrix)),
                "train_log_likelihood": _number(train_ll),
                "validation_log_likelihood_per_row": _number(validation_ll / len(validation_matrix), 6),
                "bic": _number(bic),
                "minimum_occupancy": _number(occupancy.min()),
                "eligible": bool(occupancy.min() >= 0.02),
                "selection_score": _number(penalized_validation, 6),
            })
        eligible = [row for row in candidates if row["eligible"]]
        selected_row = max(eligible or candidates, key=lambda row: float(row["selection_score"] or -1e9))
        states = int(selected_row["states"])
        final_model = _fit_hmm_candidate(development_matrix, _sequence_lengths(development_rows), states)
        labels = _regime_labels(final_model.means_)
        positive_gaps = pd.to_numeric(
            development_rows["calendar_days_since_prior"], errors="coerce"
        ).dropna()
        median_gap_days = max(float(positive_gaps[positive_gaps.gt(0)].median()), 1.0)
        prior, filtered, full_ll = _filtered_regime_probabilities(
            final_model, matrix, rows, median_gap_days
        )
        for state, label in labels.items():
            output.loc[rows["index"], f"regime_prior_{label}"] = prior[:, state]
            output.loc[rows["index"], f"regime_filtered_{label}"] = filtered[:, state]
        assigned = np.argmax(filtered, axis=1)
        output.loc[rows["index"], "regime_filtered_label"] = [labels[int(state)] for state in assigned]
        test_rows = rows[rows["year"].eq(test_year)]
        test_indices = test_rows.index.to_numpy()
        collapse_state = next(state for state, label in labels.items() if label == "collapse")
        collapse_probability = prior[test_indices, collapse_state]
        collapse_truth = panel.loc[rows.loc[test_indices, "index"], "process_collapse"].astype(int).to_numpy()
        collapse_ap = average_precision_score(collapse_truth, collapse_probability) if len(np.unique(collapse_truth)) > 1 else None
        transition = {
            labels[row]: {labels[column]: _number(final_model.transmat_[row, column]) for column in range(states)}
            for row in range(states)
        }
        audit["roles"][role] = {
            "features": list(REGIME_FEATURES),
            "feature_scaling": scaling,
            "candidate_models": candidates,
            "selected_states": states,
            "labels": {str(state): label for state, label in labels.items()},
            "emission_means_standardized": {
                labels[state]: [_number(value) for value in final_model.means_[state]] for state in range(states)
            },
            "transition_matrix_per_role_appearance": transition,
            "median_gap_days": _number(median_gap_days),
            "long_gap_rule": "Gaps of at least 60 days reset prior probabilities to the 2025 stationary distribution.",
            "filtered_log_likelihood_per_row": _number(full_ll / len(rows), 6),
            "bootstrap_stability": _bootstrap_emission_stability(
                development_rows, development_matrix, final_model, states
            ),
            "test_process_collapse_average_precision": _number(collapse_ap),
            "test_process_collapse_prevalence": _number(collapse_truth.mean()),
        }
    return output, audit


def _student_t_log_likelihood(errors: np.ndarray, variances: np.ndarray, nu: float) -> np.ndarray:
    distribution = StudentsT()
    return np.asarray(
        distribution.loglikelihood(
            np.asarray([nu], dtype=float),
            np.asarray(errors, dtype=float),
            np.maximum(np.asarray(variances, dtype=float), 1e-8),
            individual=True,
        ),
        dtype=float,
    )


def _panel_arrays(rows: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    errors = pd.to_numeric(rows[VOLATILITY_SIGNAL], errors="coerce").to_numpy(dtype=float)
    gaps = pd.to_numeric(rows["calendar_days_since_prior"], errors="coerce").to_numpy(dtype=float)
    pitcher_ids = rows["pitcher_id"].to_numpy()
    roles = rows["role"].astype(str).to_numpy()
    starts = np.zeros(len(rows), dtype=bool)
    if len(rows):
        starts[0] = True
        starts[1:] = (pitcher_ids[1:] != pitcher_ids[:-1]) | (roles[1:] != roles[:-1])
        starts |= np.isfinite(gaps) & (gaps >= LONG_GAP_RESET_DAYS)
    return errors, gaps, starts


def _gas_forecasts(rows: pd.DataFrame, parameters: np.ndarray) -> np.ndarray:
    long_run_log_variance, alpha, beta, nu = map(float, parameters)
    forecasts = np.full(len(rows), np.nan)
    errors, gaps, starts = _panel_arrays(rows)
    previous_log_variance = long_run_log_variance
    previous_score = 0.0
    for index in range(len(rows)):
        if starts[index]:
            log_variance = long_run_log_variance
        else:
            gap_units = max(gaps[index] / 5.0, 0.25) if np.isfinite(gaps[index]) else 1.0
            log_variance = (
                long_run_log_variance
                + beta ** gap_units * (previous_log_variance - long_run_log_variance)
                + alpha * previous_score
            )
        log_variance = float(np.clip(log_variance, -6.0, 4.0))
        variance = math.exp(log_variance)
        forecasts[index] = variance
        if np.isfinite(errors[index]):
            scaled_squared = errors[index] ** 2 / variance
            previous_score = 0.5 * (
                (nu + 1.0) * scaled_squared / max(nu - 2.0 + scaled_squared, 1e-9) - 1.0
            )
        else:
            previous_score = 0.0
        previous_log_variance = log_variance
    return forecasts


def _fit_gas(rows: pd.DataFrame) -> dict[str, Any]:
    valid_variance = max(float(pd.to_numeric(rows[VOLATILITY_SIGNAL], errors="coerce").var()), 0.05)

    def objective(parameters: np.ndarray) -> float:
        forecasts = _gas_forecasts(rows, parameters)
        errors = pd.to_numeric(rows[VOLATILITY_SIGNAL], errors="coerce").to_numpy(dtype=float)
        valid = np.isfinite(errors) & np.isfinite(forecasts)
        return -float(_student_t_log_likelihood(errors[valid], forecasts[valid], float(parameters[3])).sum())

    initial = np.array([math.log(valid_variance), 0.10, 0.85, 8.0])
    result = minimize(
        objective,
        initial,
        method="L-BFGS-B",
        bounds=[(-6.0, 3.0), (0.0, 1.0), (0.0, 0.995), (2.10, 30.0)],
        options={"maxiter": 200, "ftol": 1e-8},
    )
    parameters = result.x
    return {
        "parameters": parameters,
        "converged": bool(result.success),
        "optimizer_message": str(result.message),
        "development_negative_log_likelihood": float(result.fun),
    }


def _ewma_forecasts(rows: pd.DataFrame, decay: float, initial_variance: float) -> np.ndarray:
    forecasts = np.full(len(rows), np.nan)
    errors, _, starts = _panel_arrays(rows)
    variance = initial_variance
    previous_error = np.nan
    for index in range(len(rows)):
        if starts[index]:
            variance = initial_variance
        elif np.isfinite(previous_error):
            variance = decay * variance + (1.0 - decay) * previous_error ** 2
        forecasts[index] = variance
        previous_error = errors[index]
    return forecasts


def _fit_ewma(rows: pd.DataFrame) -> dict[str, float]:
    errors = pd.to_numeric(rows[VOLATILITY_SIGNAL], errors="coerce").to_numpy(dtype=float)
    initial_variance = max(float(np.nanvar(errors)), 0.05)
    best: tuple[float, float] | None = None
    for decay in (0.70, 0.80, 0.90, 0.94, 0.97):
        forecasts = _ewma_forecasts(rows, decay, initial_variance)
        valid = np.isfinite(errors) & np.isfinite(forecasts)
        loss = -float(_student_t_log_likelihood(errors[valid], forecasts[valid], 8.0).sum())
        candidate = (loss, decay)
        if best is None or candidate < best:
            best = candidate
    assert best is not None
    return {"development_negative_log_likelihood": best[0], "decay": best[1], "initial_variance": initial_variance}


def _har_features(rows: pd.DataFrame, gas_variance: np.ndarray) -> pd.DataFrame:
    return pd.DataFrame({
        "gas_log_variance": np.log(np.maximum(gas_variance, 1e-8)),
        "lag_log_squared": np.log(pd.to_numeric(rows["lag_innovation_squared"], errors="coerce") + 0.05),
        "ma5_log_variance": np.log(pd.to_numeric(rows["innovation_variance5"], errors="coerce") + 0.05),
        "ma15_log_variance": np.log(pd.to_numeric(rows["innovation_variance15"], errors="coerce") + 0.05),
        "workload_7d": pd.to_numeric(rows["workload_pitches_7d"], errors="coerce"),
        "workload_28d": pd.to_numeric(rows["workload_pitches_28d"], errors="coerce"),
        "log_gap_days": np.log1p(pd.to_numeric(rows["calendar_days_since_prior"], errors="coerce")),
    })


def _fit_har_correction(
    development_rows: pd.DataFrame,
    development_gas_variance: np.ndarray,
) -> tuple[Any, float]:
    features = _har_features(development_rows, development_gas_variance)
    errors = pd.to_numeric(development_rows[VOLATILITY_SIGNAL], errors="coerce")
    target = np.log(errors.pow(2) + 0.05)
    valid = errors.notna() & target.notna()
    model = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), Ridge(alpha=10.0))
    model.fit(features.loc[valid], target.loc[valid])
    residuals = target.loc[valid].to_numpy(dtype=float) - model.predict(features.loc[valid])
    smearing_factor = float(np.mean(np.exp(residuals)))
    return model, smearing_factor


def _volatility_metrics(
    rows: pd.DataFrame,
    variances: np.ndarray,
    nu: float,
) -> dict[str, Any]:
    errors = pd.to_numeric(rows[VOLATILITY_SIGNAL], errors="coerce").to_numpy(dtype=float)
    valid = np.isfinite(errors) & np.isfinite(variances) & (variances > 0)
    errors = errors[valid]
    variance = variances[valid]
    if not len(errors):
        return {"rows": 0}
    standardized = errors / np.sqrt(variance)
    quantile80 = float(student_t.ppf(0.90, nu) * math.sqrt((nu - 2.0) / nu))
    quantile95 = float(student_t.ppf(0.975, nu) * math.sqrt((nu - 2.0) / nu))
    collapse = rows.loc[valid, "process_collapse"].astype(int).to_numpy()
    ap = average_precision_score(collapse, variance) if len(np.unique(collapse)) > 1 else None
    residual_frame = rows.loc[valid, ["pitcher_id", "role"]].copy()
    residual_frame["squared_standardized"] = np.square(standardized)
    residual_frame["lag_squared_standardized"] = residual_frame.groupby(
        ["pitcher_id", "role"], sort=False
    )["squared_standardized"].shift(1)
    residual_autocorrelation = residual_frame[
        ["squared_standardized", "lag_squared_standardized"]
    ].corr().iloc[0, 1]
    return {
        "rows": int(len(errors)),
        "negative_log_likelihood_per_row": _number(-_student_t_log_likelihood(errors, variance, nu).mean(), 6),
        "qlike": _number(np.mean(np.log(variance) + np.square(errors) / variance), 6),
        "interval_80_coverage": _number(np.mean(np.abs(standardized) <= quantile80)),
        "interval_95_coverage": _number(np.mean(np.abs(standardized) <= quantile95)),
        "collapse_average_precision": _number(ap),
        "mean_forecast_variance": _number(np.mean(variance)),
        "squared_standardized_residual_lag1_autocorrelation": _number(residual_autocorrelation),
    }


def _gjr_forecasts(rows: pd.DataFrame, parameters: np.ndarray) -> np.ndarray:
    omega, alpha, gamma, beta, _ = map(float, parameters)
    persistence = min(alpha + 0.5 * gamma + beta, 0.995)
    unconditional = omega / max(1.0 - persistence, 1e-6)
    forecasts = np.full(len(rows), np.nan)
    errors, _, starts = _panel_arrays(rows)
    variance = unconditional
    previous_error = np.nan
    for index in range(len(rows)):
        if starts[index]:
            variance = unconditional
        elif np.isfinite(previous_error):
            shock = alpha * previous_error ** 2
            if previous_error < 0:
                shock += gamma * previous_error ** 2
            variance = omega + shock + beta * variance
        forecasts[index] = max(float(variance), 1e-8)
        previous_error = errors[index]
    return forecasts


def _fit_gjr(rows: pd.DataFrame) -> dict[str, Any]:
    errors = pd.to_numeric(rows[VOLATILITY_SIGNAL], errors="coerce").to_numpy(dtype=float)
    variance = max(float(np.nanvar(errors)), 0.05)

    def objective(parameters: np.ndarray) -> float:
        forecasts = _gjr_forecasts(rows, parameters)
        valid = np.isfinite(errors) & np.isfinite(forecasts)
        return -float(_student_t_log_likelihood(errors[valid], forecasts[valid], float(parameters[4])).sum())

    constraint = {"type": "ineq", "fun": lambda p: 0.995 - p[1] - 0.5 * p[2] - p[3]}
    starts = (
        np.array([variance * 0.05, 0.05, 0.05, 0.85, 8.0]),
        np.array([variance * 0.10, 0.10, 0.10, 0.70, 10.0]),
    )
    results = [
        minimize(
            objective,
            start,
            method="SLSQP",
            bounds=[(1e-5, 5.0), (0.0, 0.60), (0.0, 1.00), (0.0, 0.995), (2.10, 30.0)],
            constraints=[constraint],
            options={"maxiter": 250, "ftol": 1e-8},
        )
        for start in starts
    ]
    result = min(results, key=lambda item: float(item.fun))
    return {
        "parameters": result.x,
        "converged": bool(result.success),
        "optimizer_message": str(result.message),
        "development_negative_log_likelihood": float(result.fun),
    }


def _fit_volatility_models(
    panel: pd.DataFrame,
    development_year: int,
    test_year: int,
) -> tuple[pd.DataFrame, dict[str, Any], dict[str, Any]]:
    output = panel[["year", "pitcher_id", "role", "game_pk", "game_date"]].copy()
    for column in ("ewma_variance_forecast", "gas_variance_forecast", "gas_har_variance_forecast", "gjr_variance_forecast"):
        output[column] = np.nan
    slice5: dict[str, Any] = {
        "version": GAS_MODEL_VERSION,
        "development_year": development_year,
        "external_diagnostic_year": test_year,
        "evaluation_status": "test_with_documented_slice3a_amendment",
        "roles": {},
    }
    slice6: dict[str, Any] = {
        "version": GJR_MODEL_VERSION,
        "engine": "arch.StudentsT likelihood with explicit pitcher-role panel resets; scipy constrained optimizer.",
        "development_year": development_year,
        "external_diagnostic_year": test_year,
        "evaluation_status": "test_with_documented_slice3a_amendment",
        "roles": {},
    }
    for role in ROLES:
        role_mask = panel["role"].eq(role)
        rows = panel.loc[role_mask].copy().reset_index()
        development_rows = rows[rows["year"].eq(development_year)].copy().reset_index(drop=True)
        gas = _fit_gas(development_rows)
        ewma = _fit_ewma(development_rows)
        gjr = _fit_gjr(development_rows)
        gas_variance = _gas_forecasts(rows, gas["parameters"])
        ewma_variance = _ewma_forecasts(rows, ewma["decay"], ewma["initial_variance"])
        gjr_variance = _gjr_forecasts(rows, gjr["parameters"])
        development_positions = rows["year"].eq(development_year).to_numpy()
        har, har_smearing_factor = _fit_har_correction(
            rows.loc[development_positions].reset_index(drop=True), gas_variance[development_positions]
        )
        har_log_variance = har.predict(_har_features(rows, gas_variance))
        gas_har_variance = np.clip(np.exp(har_log_variance) * har_smearing_factor, 0.01, 25.0)
        output.loc[rows["index"], "ewma_variance_forecast"] = ewma_variance
        output.loc[rows["index"], "gas_variance_forecast"] = gas_variance
        output.loc[rows["index"], "gas_har_variance_forecast"] = gas_har_variance
        output.loc[rows["index"], "gjr_variance_forecast"] = gjr_variance
        test_mask = rows["year"].eq(test_year).to_numpy()
        test_rows = rows.loc[test_mask].reset_index(drop=True)
        gas_nu = float(gas["parameters"][3])
        gjr_nu = float(gjr["parameters"][4])
        test_metrics = {
            "ewma": _volatility_metrics(test_rows, ewma_variance[test_mask], 8.0),
            "gas": _volatility_metrics(test_rows, gas_variance[test_mask], gas_nu),
            "gas_har": _volatility_metrics(test_rows, gas_har_variance[test_mask], gas_nu),
            "gjr_garch": _volatility_metrics(test_rows, gjr_variance[test_mask], gjr_nu),
        }
        ridge = har.named_steps["ridge"]
        slice5["roles"][role] = {
            "signal": VOLATILITY_SIGNAL,
            "gas_parameters": {
                "long_run_log_variance": _number(gas["parameters"][0]),
                "score_reaction_alpha": _number(gas["parameters"][1]),
                "persistence_beta": _number(gas["parameters"][2]),
                "student_t_nu": _number(gas_nu),
            },
            "gas_converged": gas["converged"],
            "gas_optimizer_message": gas["optimizer_message"],
            "har_features": list(_har_features(rows.head(1), np.ones(1)).columns),
            "har_log_to_level_smearing_factor": _number(har_smearing_factor),
            "har_standardized_coefficients": {
                feature: _number(coefficient)
                for feature, coefficient in zip(_har_features(rows.head(1), np.ones(1)).columns, ridge.coef_)
            },
            "ewma_decay": _number(ewma["decay"]),
            "test_metrics": {key: value for key, value in test_metrics.items() if key != "gjr_garch"},
        }
        persistence = float(gjr["parameters"][1] + 0.5 * gjr["parameters"][2] + gjr["parameters"][3])
        slice6["roles"][role] = {
            "signal": VOLATILITY_SIGNAL,
            "parameters": {
                "omega": _number(gjr["parameters"][0]),
                "alpha": _number(gjr["parameters"][1]),
                "negative_shock_gamma": _number(gjr["parameters"][2]),
                "beta": _number(gjr["parameters"][3]),
                "student_t_nu": _number(gjr_nu),
                "persistence": _number(persistence),
            },
            "converged": gjr["converged"],
            "optimizer_message": gjr["optimizer_message"],
            "asymmetry_detected": bool(gjr["parameters"][2] > 0.01),
            "per_pitcher_fit_policy": "Rejected: individual appearance histories are too short; parameters are pooled by role with pitcher-role resets.",
            "test_metrics": test_metrics,
        }
    return output, slice5, slice6


def refresh_performance_state_advanced(
    data_dir: Path | None = None,
    development_year: int = DEVELOPMENT_YEAR,
    test_year: int = TEST_YEAR,
) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    panel = _load_filtered_panel(root, (development_year, test_year))
    regime_rows, slice4 = _fit_regime_models(panel, development_year, test_year)
    volatility_rows, slice5, slice6 = _fit_volatility_models(panel, development_year, test_year)
    keys = ["year", "pitcher_id", "role", "game_pk", "game_date"]
    advanced = regime_rows.merge(volatility_rows, on=keys, how="inner", validate="one_to_one")
    for year in (development_year, test_year):
        _write_parquet_atomic(advanced[advanced["year"].eq(year)].copy(), advanced_state_path(year, root))
    source_modified_at = {
        str(year): int(filtered_state_path(year, root).stat().st_mtime_ns)
        for year in (development_year, test_year)
    }
    audit = {
        "model_version": ADVANCED_MODEL_VERSION,
        "status": "research_only",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "development_year": development_year,
        "test_year": test_year,
        "evaluation_status": "test_with_documented_slice3a_amendment",
        "prospective_untouched_year": 2027,
        "source_state_model_version": STATE_MODEL_VERSION,
        "source_modified_at": source_modified_at,
        "data_as_of": {
            str(year): str(panel.loc[panel["year"].eq(year), "game_date"].max())[:10]
            for year in (development_year, test_year)
        },
        "slice4": slice4,
        "slice5": slice5,
        "slice6": slice6,
        "warnings": [
            "All outputs are research-only performance-state estimates, not health, injury or medical predictions.",
            "Regime names are assigned after fitting from standardized emission profiles; absent states are not forced into the model.",
            "2026 is an external diagnostic with a documented Slice 3A amendment, not pristine untouched validation.",
        ],
    }
    _write_json_atomic(audit, advanced_audit_path(root))
    _cached_advanced_audit.cache_clear()
    return audit


@lru_cache(maxsize=2)
def _cached_advanced_audit(path_value: str, modified_at: int) -> dict[str, Any]:
    del modified_at
    return json.loads(Path(path_value).read_text(encoding="utf-8"))


def get_performance_state_advanced_audit(data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    path = advanced_audit_path(root)
    if not path.exists():
        raise FileNotFoundError("Performance State Slices 4-6 have not been built.")
    payload = _cached_advanced_audit(str(path.resolve()), path.stat().st_mtime_ns).copy()
    stale_years = [
        int(year)
        for year, stamp in payload.get("source_modified_at", {}).items()
        if filtered_state_path(int(year), root).exists()
        and filtered_state_path(int(year), root).stat().st_mtime_ns > int(stamp)
    ]
    payload["dataset_status"] = "stale" if stale_years else "current"
    if stale_years:
        payload["warnings"] = list(payload.get("warnings", [])) + [
            f"Source filtered-state artifacts changed after build for: {', '.join(map(str, stale_years))}."
        ]
    return payload


def _load_tail_panel(root: Path, years: tuple[int, int]) -> pd.DataFrame:
    panel = _load_filtered_panel(root, years)
    advanced_frames: list[pd.DataFrame] = []
    for year in years:
        path = advanced_state_path(year, root)
        if not path.exists():
            raise FileNotFoundError(f"Performance State advanced artifact not found: {path}")
        with duckdb.connect() as connection:
            advanced_frames.append(
                connection.execute(
                    "SELECT year, pitcher_id, role, game_pk, gas_har_variance_forecast FROM read_parquet(?)",
                    [str(path)],
                ).fetchdf()
            )
    advanced = pd.concat(advanced_frames, ignore_index=True)
    panel = panel.merge(
        advanced,
        on=["year", "pitcher_id", "role", "game_pk"],
        how="left",
        validate="one_to_one",
    )
    error = pd.to_numeric(panel[VOLATILITY_SIGNAL], errors="coerce")
    variance = pd.to_numeric(panel["gas_har_variance_forecast"], errors="coerce")
    panel["standardized_loss"] = -error / np.sqrt(variance.where(variance.gt(0)))
    panel["sequence_index"] = panel.groupby(["pitcher_id", "role"], sort=False).cumcount()
    return panel


def _decluster_exceedances(rows: pd.DataFrame, threshold: float, run_length: int) -> np.ndarray:
    excesses: list[float] = []
    for _, group in rows.groupby(["pitcher_id", "role"], sort=False):
        values = pd.to_numeric(group["standardized_loss"], errors="coerce").to_numpy(dtype=float)
        positions = pd.to_numeric(group["sequence_index"], errors="coerce").to_numpy(dtype=int)
        selected = np.where(np.isfinite(values) & (values > threshold))[0]
        if not len(selected):
            continue
        cluster_values = [values[selected[0]]]
        previous_position = positions[selected[0]]
        for selected_index in selected[1:]:
            position = positions[selected_index]
            if position - previous_position <= run_length + 1:
                cluster_values.append(values[selected_index])
            else:
                excesses.append(max(cluster_values) - threshold)
                cluster_values = [values[selected_index]]
            previous_position = position
        excesses.append(max(cluster_values) - threshold)
    return np.asarray(excesses, dtype=float)


def _fit_gpd(excesses: np.ndarray) -> tuple[float, float]:
    shape, _, scale = genpareto.fit(excesses, floc=0.0)
    return float(shape), max(float(scale), 1e-6)


def _gpd_candidate_audit(
    fit_rows: pd.DataFrame,
    validation_rows: pd.DataFrame,
    quantile: float,
    run_length: int,
) -> dict[str, Any]:
    fit_values = pd.to_numeric(fit_rows["standardized_loss"], errors="coerce").dropna()
    threshold = float(fit_values.quantile(quantile))
    exceedance_rate = float(fit_values.gt(threshold).mean())
    fit_excess = _decluster_exceedances(fit_rows, threshold, run_length)
    validation_excess = _decluster_exceedances(validation_rows, threshold, run_length)
    eligible = len(fit_excess) >= 100 and len(validation_excess) >= 20
    if not eligible:
        return {
            "threshold_quantile": quantile,
            "decluster_run_length": run_length,
            "threshold": _number(threshold),
            "fit_clusters": int(len(fit_excess)),
            "validation_clusters": int(len(validation_excess)),
            "eligible": False,
            "validation_score": None,
        }
    shape, scale = _fit_gpd(fit_excess)
    validation_values = pd.to_numeric(validation_rows["standardized_loss"], errors="coerce").dropna()
    validation_rate = float(validation_values.gt(threshold).mean())
    exceedance_mask = validation_values.gt(threshold).to_numpy()
    log_likelihood = np.full(len(validation_values), math.log(max(1.0 - exceedance_rate, 1e-12)))
    validation_tail_excess = validation_values.to_numpy(dtype=float)[exceedance_mask] - threshold
    log_likelihood[exceedance_mask] = math.log(max(exceedance_rate, 1e-12)) + genpareto.logpdf(
        validation_tail_excess, c=shape, loc=0.0, scale=scale
    )
    score = -float(np.mean(log_likelihood))
    return {
        "threshold_quantile": quantile,
        "decluster_run_length": run_length,
        "threshold": _number(threshold),
        "fit_clusters": int(len(fit_excess)),
        "validation_clusters": int(len(validation_excess)),
        "fit_exceedance_rate": _number(exceedance_rate),
        "validation_exceedance_rate": _number(validation_rate),
        "shape": _number(shape),
        "scale": _number(scale),
        "eligible": True,
        "score_type": "censored_validation_negative_log_likelihood_per_row",
        "validation_score": _number(score, 6),
    }


def _bootstrap_gpd(excesses: np.ndarray, samples: int = 100) -> dict[str, Any]:
    rng = np.random.default_rng(20261005)
    shapes: list[float] = []
    scales: list[float] = []
    for _ in range(samples):
        sampled = excesses[rng.integers(0, len(excesses), len(excesses))]
        try:
            shape, scale = _fit_gpd(sampled)
            shapes.append(shape)
            scales.append(scale)
        except Exception:
            continue
    return {
        "requested_samples": samples,
        "successful_samples": len(shapes),
        "shape_95_interval": [_number(np.quantile(shapes, 0.025)), _number(np.quantile(shapes, 0.975))],
        "scale_95_interval": [_number(np.quantile(scales, 0.025)), _number(np.quantile(scales, 0.975))],
    }


def _tail_probability_and_severity(
    rows: pd.DataFrame,
    development_losses: np.ndarray,
    raw_extreme_threshold: float,
    threshold: float,
    exceedance_rate: float,
    shape: float,
    scale: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    variance = pd.to_numeric(rows["gas_har_variance_forecast"], errors="coerce").to_numpy(dtype=float)
    standardized_target = raw_extreme_threshold / np.sqrt(variance)
    probabilities = np.full(len(rows), np.nan)
    severities = np.full(len(rows), np.nan)
    supported = np.zeros(len(rows), dtype=bool)
    sorted_losses = np.sort(development_losses[np.isfinite(development_losses)])
    for index, target in enumerate(standardized_target):
        if not np.isfinite(target):
            continue
        if target >= threshold:
            excess = target - threshold
            support = 1.0 + shape * excess / scale
            if support > 0:
                survival = math.exp(-excess / scale) if abs(shape) < 1e-8 else support ** (-1.0 / shape)
                probabilities[index] = float(np.clip(exceedance_rate * survival, 0.0, 1.0))
                supported[index] = True
                if shape < 1.0:
                    expected_excess = (scale + shape * excess) / (1.0 - shape)
                    severities[index] = math.sqrt(variance[index]) * (target + expected_excess)
        else:
            insertion = int(np.searchsorted(sorted_losses, target, side="right"))
            probabilities[index] = 1.0 - insertion / max(len(sorted_losses), 1)
    return probabilities, severities, supported


def _caviar_forecasts(
    rows: pd.DataFrame,
    parameters: np.ndarray,
    model_type: str,
    initial_quantile: float,
) -> np.ndarray:
    loss = -pd.to_numeric(rows[VOLATILITY_SIGNAL], errors="coerce").to_numpy(dtype=float)
    _, _, starts = _panel_arrays(rows)
    forecasts = np.full(len(rows), np.nan)
    previous_quantile = initial_quantile
    previous_loss = np.nan
    for index in range(len(rows)):
        if starts[index]:
            quantile = initial_quantile
        elif not np.isfinite(previous_loss):
            quantile = previous_quantile
        elif model_type == "sav":
            quantile = parameters[0] + parameters[1] * previous_quantile + parameters[2] * abs(previous_loss)
        else:
            quantile = (
                parameters[0]
                + parameters[1] * previous_quantile
                + parameters[2] * max(previous_loss, 0.0)
                + parameters[3] * max(-previous_loss, 0.0)
            )
        quantile = float(np.clip(quantile, 0.01, 10.0))
        forecasts[index] = quantile
        previous_quantile = quantile
        previous_loss = loss[index]
    return forecasts


def _quantile_loss(loss: np.ndarray, forecast: np.ndarray, quantile: float = 0.95) -> float:
    valid = np.isfinite(loss) & np.isfinite(forecast)
    residual = loss[valid] - forecast[valid]
    return float(np.mean(residual * (quantile - (residual < 0).astype(float))))


def _fit_caviar(rows: pd.DataFrame, model_type: str) -> dict[str, Any]:
    loss = -pd.to_numeric(rows[VOLATILITY_SIGNAL], errors="coerce").to_numpy(dtype=float)
    initial_quantile = float(np.nanquantile(loss, 0.95))
    parameter_count = 3 if model_type == "sav" else 4

    def objective(parameters: np.ndarray) -> float:
        return _quantile_loss(loss, _caviar_forecasts(rows, parameters, model_type, initial_quantile))

    initial = np.array([0.10, 0.80, 0.10] + ([0.10] if parameter_count == 4 else []))
    bounds = [(0.0, 3.0), (0.0, 0.995)] + [(0.0, 2.0)] * (parameter_count - 2)
    result = minimize(objective, initial, method="L-BFGS-B", bounds=bounds, options={"maxiter": 300})
    return {
        "parameters": result.x,
        "initial_quantile": initial_quantile,
        "loss": float(result.fun),
        "converged": bool(result.success),
        "optimizer_message": str(result.message),
    }


def _kupiec_test(violations: np.ndarray, expected_rate: float = 0.05) -> dict[str, Any]:
    valid = np.asarray(violations, dtype=bool)
    observations = len(valid)
    events = int(valid.sum())
    observed_rate = events / observations if observations else float("nan")
    if not observations or events in (0, observations):
        return {"observations": observations, "violations": events, "rate": _number(observed_rate), "p_value": None}
    null_ll = (observations - events) * math.log(1.0 - expected_rate) + events * math.log(expected_rate)
    fitted_ll = (observations - events) * math.log(1.0 - observed_rate) + events * math.log(observed_rate)
    statistic = -2.0 * (null_ll - fitted_ll)
    return {
        "observations": observations,
        "violations": events,
        "rate": _number(observed_rate),
        "lr_statistic": _number(statistic),
        "p_value": _number(chi2.sf(statistic, 1), 6),
    }


def _binary_alert_metrics(truth: np.ndarray, score: np.ndarray, alert_threshold: float) -> dict[str, Any]:
    valid = np.isfinite(score)
    truth = np.asarray(truth, dtype=bool)[valid]
    score = np.asarray(score, dtype=float)[valid]
    alerts = score >= alert_threshold
    positives = int(truth.sum())
    negatives = int((~truth).sum())
    return {
        "rows": int(len(truth)),
        "average_precision": _number(average_precision_score(truth.astype(int), score)) if positives else None,
        "alert_rate": _number(alerts.mean()),
        "recall": _number((alerts & truth).sum() / positives) if positives else None,
        "false_alert_rate": _number((alerts & ~truth).sum() / negatives) if negatives else None,
    }


def refresh_performance_state_tail(
    data_dir: Path | None = None,
    development_year: int = DEVELOPMENT_YEAR,
    test_year: int = TEST_YEAR,
) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    panel = _load_tail_panel(root, (development_year, test_year))
    output = panel[["year", "pitcher_id", "role", "game_pk", "game_date"]].copy()
    output["evt_extreme_probability"] = np.nan
    output["evt_expected_loss_severity"] = np.nan
    output["evt_tail_supported"] = False
    output["caviar_var95"] = np.nan
    output["extreme_innovation"] = False
    output["evt_alert"] = False
    output["caviar_alert"] = False
    audit: dict[str, Any] = {
        "version": TAIL_MODEL_VERSION,
        "status": "research_only",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "development_year": development_year,
        "external_diagnostic_year": test_year,
        "evaluation_status": "test_with_documented_slice3a_amendment",
        "prospective_untouched_year": 2027,
        "source_advanced_model_version": ADVANCED_MODEL_VERSION,
        "roles": {},
    }
    for role in ROLES:
        rows = panel[panel["role"].eq(role)].copy().reset_index()
        development = rows[rows["year"].eq(development_year)].copy()
        cutoff = development["game_date"].quantile(0.80)
        fit_rows = development[development["game_date"].le(cutoff)]
        validation_rows = development[development["game_date"].gt(cutoff)]
        candidates = [
            _gpd_candidate_audit(fit_rows, validation_rows, quantile, run_length)
            for quantile in (0.90, 0.925, 0.95)
            for run_length in (0, 1, 2)
        ]
        eligible = [candidate for candidate in candidates if candidate["eligible"]]
        if not eligible:
            raise RuntimeError(f"No eligible POT-EVT candidate for {role}.")
        selected = min(eligible, key=lambda candidate: float(candidate["validation_score"]))
        development_losses = pd.to_numeric(development["standardized_loss"], errors="coerce").dropna().to_numpy()
        threshold = float(np.quantile(development_losses, float(selected["threshold_quantile"])))
        run_length = int(selected["decluster_run_length"])
        excesses = _decluster_exceedances(development, threshold, run_length)
        shape, scale = _fit_gpd(excesses)
        exceedance_rate = float(np.mean(development_losses > threshold))
        raw_errors = pd.to_numeric(development[VOLATILITY_SIGNAL], errors="coerce").dropna().to_numpy()
        raw_extreme_threshold = float(-np.quantile(raw_errors, 0.05))
        probabilities, severities, supported = _tail_probability_and_severity(
            rows,
            development_losses,
            raw_extreme_threshold,
            threshold,
            exceedance_rate,
            shape,
            scale,
        )
        development_mask = rows["year"].eq(development_year).to_numpy()
        evt_alert_threshold = float(np.nanquantile(probabilities[development_mask], 0.90))

        fit_caviar_rows = development[development["game_date"].le(cutoff)].reset_index(drop=True)
        validation_caviar_rows = development[development["game_date"].gt(cutoff)].reset_index(drop=True)
        caviar_candidates: dict[str, dict[str, Any]] = {}
        for model_type in ("sav", "asymmetric_slope"):
            fitted = _fit_caviar(fit_caviar_rows, model_type)
            validation_loss = -pd.to_numeric(
                validation_caviar_rows[VOLATILITY_SIGNAL], errors="coerce"
            ).to_numpy(dtype=float)
            validation_forecast = _caviar_forecasts(
                validation_caviar_rows,
                fitted["parameters"],
                model_type,
                fitted["initial_quantile"],
            )
            fitted["validation_quantile_loss"] = _quantile_loss(validation_loss, validation_forecast)
            caviar_candidates[model_type] = fitted
        selected_type = min(caviar_candidates, key=lambda key: caviar_candidates[key]["validation_quantile_loss"])
        final_caviar = _fit_caviar(development.reset_index(drop=True), selected_type)
        caviar_forecast = _caviar_forecasts(
            rows,
            final_caviar["parameters"],
            selected_type,
            final_caviar["initial_quantile"],
        )
        caviar_alert_threshold = float(np.nanquantile(caviar_forecast[development_mask], 0.90))
        errors = pd.to_numeric(rows[VOLATILITY_SIGNAL], errors="coerce").to_numpy(dtype=float)
        extreme = errors <= -raw_extreme_threshold
        output.loc[rows["index"], "evt_extreme_probability"] = probabilities
        output.loc[rows["index"], "evt_expected_loss_severity"] = severities
        output.loc[rows["index"], "evt_tail_supported"] = supported
        output.loc[rows["index"], "caviar_var95"] = caviar_forecast
        output.loc[rows["index"], "extreme_innovation"] = extreme
        output.loc[rows["index"], "evt_alert"] = probabilities >= evt_alert_threshold
        output.loc[rows["index"], "caviar_alert"] = caviar_forecast >= caviar_alert_threshold
        test_mask = rows["year"].eq(test_year).to_numpy()
        test_loss = -errors[test_mask]
        test_extreme = extreme[test_mask]
        test_standardized_loss = pd.to_numeric(
            rows.loc[test_mask, "standardized_loss"], errors="coerce"
        ).to_numpy(dtype=float)
        test_probabilities = probabilities[test_mask]
        test_caviar = caviar_forecast[test_mask]
        test_supported = supported[test_mask]
        ks = kstest(excesses, lambda value: genpareto.cdf(value, c=shape, loc=0.0, scale=scale))
        audit["roles"][role] = {
            "signal": VOLATILITY_SIGNAL,
            "tail_definition": "Negative Stuff-state standardized innovation divided by pre-appearance GAS+HAR volatility.",
            "raw_extreme_threshold": _number(raw_extreme_threshold),
            "pot_candidates": candidates,
            "selected_threshold_quantile": selected["threshold_quantile"],
            "selected_decluster_run_length": run_length,
            "threshold": _number(threshold),
            "development_exceedance_rate": _number(exceedance_rate),
            "development_clusters": int(len(excesses)),
            "gpd_shape": _number(shape),
            "gpd_scale": _number(scale),
            "gpd_ks_statistic": _number(ks.statistic),
            "gpd_ks_p_value": _number(ks.pvalue),
            "bootstrap": _bootstrap_gpd(excesses),
            "evt_probability_note": "GPD survival is used when the requested raw threshold maps above u; below u the frozen 2025 empirical survival is used and evt_tail_supported is false.",
            "evt_alert_threshold": _number(evt_alert_threshold),
            "test_evt_supported_rate": _number(test_supported.mean()),
            "test_raw_extreme_rate": _number(test_extreme.mean()),
            "test_standardized_threshold_exceedance_rate": _number(
                np.mean(test_standardized_loss[np.isfinite(test_standardized_loss)] > threshold)
            ),
            "test_evt_alert_metrics": _binary_alert_metrics(test_extreme, test_probabilities, evt_alert_threshold),
            "caviar_candidates": {
                model_type: {
                    "parameters": [_number(value) for value in values["parameters"]],
                    "converged": values["converged"],
                    "validation_quantile_loss": _number(values["validation_quantile_loss"], 6),
                }
                for model_type, values in caviar_candidates.items()
            },
            "selected_caviar": selected_type,
            "caviar_parameters": [_number(value) for value in final_caviar["parameters"]],
            "caviar_alert_threshold": _number(caviar_alert_threshold),
            "test_caviar_quantile_loss": _number(_quantile_loss(test_loss, test_caviar), 6),
            "test_caviar_kupiec": _kupiec_test(test_loss > test_caviar),
            "test_caviar_alert_metrics": _binary_alert_metrics(test_extreme, test_caviar, caviar_alert_threshold),
        }
    for year in (development_year, test_year):
        _write_parquet_atomic(output[output["year"].eq(year)].copy(), tail_state_path(year, root))
    audit["source_modified_at"] = {
        str(year): int(advanced_state_path(year, root).stat().st_mtime_ns)
        for year in (development_year, test_year)
    }
    audit["warnings"] = [
        "Tail probabilities estimate extreme performance innovations, not injury, health or medical risk.",
        "2026 is an amended external diagnostic; all thresholds, tail parameters and CAViaR choices use 2025 only.",
        "Expected severity is available only where the raw threshold lies inside the fitted EVT tail.",
    ]
    _write_json_atomic(audit, tail_audit_path(root))
    _cached_tail_audit.cache_clear()
    return audit


@lru_cache(maxsize=2)
def _cached_tail_audit(path_value: str, modified_at: int) -> dict[str, Any]:
    del modified_at
    return json.loads(Path(path_value).read_text(encoding="utf-8"))


def get_performance_state_tail_audit(data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    path = tail_audit_path(root)
    if not path.exists():
        raise FileNotFoundError("Performance State Slice 7 has not been built.")
    payload = _cached_tail_audit(str(path.resolve()), path.stat().st_mtime_ns).copy()
    stale_years = [
        int(year)
        for year, stamp in payload.get("source_modified_at", {}).items()
        if advanced_state_path(int(year), root).exists()
        and advanced_state_path(int(year), root).stat().st_mtime_ns > int(stamp)
    ]
    payload["dataset_status"] = "stale" if stale_years else "current"
    if stale_years:
        payload["warnings"] = list(payload.get("warnings", [])) + [
            f"Source advanced-state artifacts changed after build for: {', '.join(map(str, stale_years))}."
        ]
    return payload
