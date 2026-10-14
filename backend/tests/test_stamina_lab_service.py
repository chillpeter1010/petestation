from __future__ import annotations

import json

import duckdb
import pandas as pd

from app.api.schemas.stamina import (
    StaminaSlice7Result,
    StaminaSlice8Result,
    StaminaSlice9Result,
    StaminaSlice10Result,
    StaminaSlice11Result,
    StaminaGameStateResult,
    StaminaGameStatesResponse,
    StaminaResearchCurvesResponse,
    StaminaSeasonSummariesResponse,
    StaminaSlice12Result,
    StaminaSlice13Result,
    StaminaSlice13AResult,
    StaminaLeaderboardResponse,
    StaminaPhysicalStabilityResponse,
    StaminaCommandRetentionResponse,
    StaminaSlice19Result,
)
from app.services import stamina_lab_service as service
from app.services import physical_stability_service as physical_service
from app.services import command_retention_service as command_service


def test_refresh_stamina_dataset_cleans_and_splits_roles(tmp_path, monkeypatch):
    mlb_dir = tmp_path / "MLB2026"
    mlb_dir.mkdir()
    rows = pd.DataFrame([
        _pitch(1, "2026-04-01", 1, 1, 1, "AZ"),
        _pitch(1, "2026-04-01", 1, 1, 1, "AZ"),
        _pitch(1, "2026-04-01", 2, 1, 2, "AZ"),
        _pitch(3, "2026-04-01", 1, 2, 3, "AZ"),
        _pitch(2, "2026-04-05", 1, 1, 4, "AZ", game_pk=2),
        _pitch(1, "2026-04-05", 1, 2, 5, "AZ", game_pk=2),
        {**_pitch(9, "2026-04-06", 1, 1, 6, "AZ", game_pk=3), "pitcher": None},
    ])
    with duckdb.connect(str(mlb_dir / "mlb_2026.duckdb")) as connection:
        connection.register("source", rows)
        connection.execute("CREATE TABLE pitches AS SELECT * FROM source")
    monkeypatch.setattr(service.settings, "data_dir", tmp_path)
    monkeypatch.setattr(service, "load_pitch_stuff_scores", lambda frame, root: pd.Series(101.0, index=frame.index))
    monkeypatch.setattr(service, "load_pitch_location_scores", lambda frame, root: pd.Series(99.0, index=frame.index))

    result = service.refresh_stamina_dataset(2026, tmp_path)

    assert result["dataset_rows"] == 5
    assert result["appearances"] == 4
    assert result["dual_role_pitchers"] == 1
    assert {row["role"]: row["appearances"] for row in result["roles"]} == {"SP": 2, "RP": 2}
    assert result["coverage"][0]["both_coverage_pct"] == 100.0
    assert service.stamina_dataset_path(2026, tmp_path).exists()
    assert service.get_stamina_overview(2026, tmp_path)["dataset_status"] == "current"


def test_slice1_builds_adjusted_role_curves() -> None:
    rows = []
    for role in ["SP", "RP"]:
        for index in range(600):
            appearance_pitch = index % (110 if role == "SP" else 35) + 1
            season_before = (index * (5 if role == "SP" else 2)) % (2400 if role == "SP" else 1000)
            rows.append({
                "appearance_role": role,
                "pitch_stuff_plus": 102.0 - appearance_pitch * 0.01 + (index % 7) * 0.1,
                "location_plus_pitch": 100.0 - appearance_pitch * 0.005 + (index % 5) * 0.1,
                "pitch_type": "FF" if index % 2 else "SL",
                "batter": 1000 + index % 30,
                "pitcher": 10 + index % 12,
                "game_pk": 5000 + index // 30,
                "appearance_pitch_number": appearance_pitch,
                "season_pitches_before": season_before,
                "balls": index % 4,
                "strikes": index % 3,
                "p_throws": "R" if index % 3 else "L",
                "stand": "R" if index % 2 else "L",
                "n_thruorder_pitcher": index % 4 + 1,
                "inning": index % 9 + 1,
                "home_team": "AZ" if index % 2 else "LAD",
                "game_date": pd.Timestamp("2026-03-25") + pd.Timedelta(days=index % 180),
            })

    result = service._build_slice1(pd.DataFrame(rows))

    assert result["status"] == "ready"
    assert {row["role"] for row in result["diagnostics"]} == {"SP", "RP"}
    assert {row["dimension"] for row in result["points"]} == {"appearance_pitch_count", "season_workload"}
    assert {row["outcome"] for row in result["points"]} == {"pitch_stuff_plus", "location_plus_pitch"}
    assert all(row["ci_low"] <= row["adjusted_delta"] <= row["ci_high"] for row in result["points"])


def test_slice2_pairs_windows_and_builds_observation_weights() -> None:
    rows = []
    game_pk = 10_000
    for role in ["SP", "RP"]:
        for pitcher_offset in range(10):
            pitcher = 100 + pitcher_offset + (1000 if role == "RP" else 0)
            for appearance in range(18):
                game_pk += 1
                if role == "SP":
                    total = [55, 75, 95, 105][appearance % 4]
                else:
                    total = [12, 20, 30][appearance % 3]
                for pitch_number in range(1, total + 1):
                    rows.append({
                        "appearance_role": role,
                        "pitch_stuff_plus": 104.0 - pitch_number * 0.025 + pitcher_offset * 0.04,
                        "location_plus_pitch": 100.0 - pitch_number * 0.01 + appearance * 0.01,
                        "pitch_type": "FF" if pitch_number % 3 else "SL",
                        "release_speed": 95.0 - pitch_number * 0.003,
                        "n_thruorder_pitcher": min(4, (pitch_number - 1) // 25 + 1),
                        "pitcher": pitcher,
                        "game_pk": game_pk,
                        "appearance_pitch_number": pitch_number,
                        "days_rest": 4 if role == "SP" else 1,
                        "season_pitches_before": appearance * (85 if role == "SP" else 20),
                        "appearance_number": appearance + 1,
                        "game_date": pd.Timestamp("2026-04-01") + pd.Timedelta(days=appearance * 5 + pitcher_offset),
                        "player_name": f"Pitcher, Test {pitcher}",
                        "pitcher_team": "AZ" if pitcher_offset % 2 else "LAD",
                    })
    slice1 = {"summaries": [
        {"role": role, "dimension": "appearance_pitch_count", "outcome": outcome, "adjusted_delta": 0.2}
        for role in ["SP", "RP"] for outcome in ["pitch_stuff_plus", "location_plus_pitch"]
    ]}

    result = service._build_slice2(pd.DataFrame(rows), slice1)

    assert result["status"] == "ready"
    assert {row["role"] for row in result["appearance_results"]} == {"SP", "RP"}
    assert {row["outcome"] for row in result["appearance_results"]} == {"pitch_stuff_plus", "location_plus_pitch"}
    assert all(row["effective_sample_size"] <= row["reached_appearances"] for row in result["selection_models"])
    assert all(row["unweighted_ci_low"] <= row["unweighted_delta"] <= row["unweighted_ci_high"] for row in result["appearance_results"])

    slice3 = service._build_slice3(pd.DataFrame(rows))
    assert slice3["status"] == "ready"
    assert {row["role"] for row in slice3["leaderboard"]} == {"SP", "RP"}
    assert {row["outcome"] for row in slice3["leaderboard"]} == {"pitch_stuff_plus", "location_plus_pitch"}
    assert all(0 <= row["reliability"] <= 1 for row in slice3["leaderboard"])
    assert all(row["ci_low"] <= row["posterior_slope"] <= row["ci_high"] for row in slice3["leaderboard"])


def test_workload_history_is_all_role_and_strictly_lagged() -> None:
    appearances = pd.DataFrame([
        {"pitcher": 7, "game_pk": 1, "game_date": pd.Timestamp("2026-04-01"), "pitches": 80, "appearance_role": "SP", "days_rest": None},
        {"pitcher": 7, "game_pk": 2, "game_date": pd.Timestamp("2026-04-05"), "pitches": 15, "appearance_role": "RP", "days_rest": 3},
        {"pitcher": 7, "game_pk": 3, "game_date": pd.Timestamp("2026-04-07"), "pitches": 90, "appearance_role": "SP", "days_rest": 1},
    ])

    result = service._add_workload_history(appearances).sort_values("game_pk")
    third = result.iloc[2]

    assert third["all_role_season_pitches_before"] == 95
    assert third["previous_appearance_pitches"] == 15
    assert third["workload_pitches_3d"] == 15
    assert third["workload_pitches_7d"] == 95
    assert third["role_changed"] == 1
    assert third["all_role_season_pitches_before"] != 185


def test_slice5_builds_role_specific_two_season_stamina_plus(tmp_path) -> None:
    def slice3(year_shift: float) -> dict[str, object]:
        rows = []
        priors = []
        for role in ["SP", "RP"]:
            priors.append({
                "role": role, "outcome": "pitch_stuff_plus", "outcome_label": "Stuff+",
                "unit_pitches": 20 if role == "SP" else 5, "candidate_pitchers": 60,
                "eligible_pitchers": 60, "minimum_appearances": 8, "league_slope": year_shift,
                "between_pitcher_sd": 1.0,
            })
            for index in range(60):
                centered = (index - 29.5) / 12
                rows.append({
                    "rank": index + 1, "pitcher_id": index + (1000 if role == "RP" else 0),
                    "pitcher_name": f"Test {role} {index}", "team": "AZ", "role": role,
                    "outcome": "pitch_stuff_plus", "outcome_label": "Stuff+",
                    "unit_pitches": 20 if role == "SP" else 5,
                    "raw_slope": centered + year_shift + (0.03 if index % 2 else -0.03),
                    "standard_error": 0.2, "posterior_slope": centered * 0.95 + year_shift,
                    "ci_low": centered * 0.95 + year_shift - 0.3,
                    "ci_high": centered * 0.95 + year_shift + 0.3,
                    "reliability": 0.7, "reliability_label": "strong",
                    "retention_band": "indistinguishable", "appearances": 20,
                    "observations": 50, "matched_pitches": 300, "target_windows": 4,
                })
        return {"status": "ready", "leaderboard": rows, "priors": priors, "split_half_validation": [], "warnings": []}

    derived = tmp_path / "derived"
    derived.mkdir()
    prior_payload = {
        "coverage": [
            {"role": "SP", "stuff_coverage_pct": 99.5},
            {"role": "RP", "stuff_coverage_pct": 99.2},
        ],
        "slice3": slice3(-0.2),
    }
    (derived / "stamina_lab_2025.json").write_text(json.dumps(prior_payload), encoding="utf-8")
    current = slice3(0.1)
    frame = pd.DataFrame([
        {
            "pitcher": index + offset, "appearance_role": role, "player_name": f"Current {role} {index}",
            "pitcher_team": "AZ", "game_date": pd.Timestamp("2026-09-01"), "game_pk": index + 1,
            "pitch_stuff_plus": 100.0,
        }
        for role, offset in [("SP", 0), ("RP", 1000)] for index in range(60)
    ])

    result = service._build_slice5(frame, 2026, tmp_path, current)

    assert result["status"] == "ready"
    assert result["publication_status"] == "validated"
    assert {row["role"] for row in result["leaderboard"]} == {"SP", "RP"}
    assert all(row["seasons"] == 2 for row in result["leaderboard"])
    assert all(row["sample_label"] == "qualified" for row in result["leaderboard"])
    assert all(row["ci_low"] <= row["stamina_plus"] <= row["ci_high"] for row in result["leaderboard"])
    assert all(validation["gates"]["rank"] for validation in result["validations"])
    assert {row["season"] for row in result["season_leaderboard"]} == {2025, 2026}
    assert {row["role"] for row in result["season_priors"]} == {"SP", "RP"}


def test_workload_effects_expose_standardized_relative_strength() -> None:
    rows = []
    for pitcher in range(10):
        for appearance in range(1, 21):
            previous = appearance * 3 + pitcher
            rows.append({
                "pitcher": pitcher,
                "game_date": pd.Timestamp("2026-04-01") + pd.Timedelta(days=appearance * 3),
                "all_role_appearance_number": appearance,
                "previous_appearance_pitches": previous,
                "workload_pitches_3d": previous,
                "workload_pitches_14d": previous + appearance * 2,
                "workload_pitches_28d": previous + appearance * 4,
                "all_role_season_pitches_before": appearance * 50,
                "role_changed": appearance % 3 == 0,
                "days_rest": 4,
                "metric": previous * -0.02 + appearance * 0.01,
            })

    result = service._fit_workload_effects(
        pd.DataFrame(rows), "metric", "SP", "pitch_stuff_plus", "Stuff+", "readiness"
    )

    assert result["effects"]
    assert max(row["relative_strength_pct"] for row in result["effects"]) == 100.0
    assert all(row["within_pitcher_sd"] >= 0 for row in result["effects"])
    assert all("standardized_effect" in row for row in result["effects"])


def test_slice6_caches_trait_and_expected_pitch_state(tmp_path) -> None:
    frame = pd.DataFrame([
        {
            "game_pk": 1, "at_bat_number": 1, "pitch_number": pitch_number, "pitcher": 7,
            "appearance_role": "SP", "appearance_pitch_number": appearance_pitch_number,
            "pitch_type": "FF", "pitch_stuff_plus": stuff_plus, "location_plus_pitch": 101.0,
        }
        for pitch_number, appearance_pitch_number, stuff_plus in [(1, 1, 102.0), (2, 10, 100.0), (3, 21, 97.0)]
    ])
    slice5 = {
        "status": "ready",
        "leaderboard": [{
            "pitcher_id": 7, "role": "SP", "stamina_plus": 110.0,
            "retention_advantage": 0.2, "reliability": 0.7, "sample_label": "qualified",
        }],
    }
    slice3 = {
        "priors": [{"role": "SP", "outcome": "pitch_stuff_plus", "league_slope": -0.4}],
    }

    cached, audit = service._attach_stamina_state(frame, slice5, slice3)

    assert audit["status"] == "current"
    assert cached["stamina_plus_trait"].tolist() == [110.0, 110.0, 110.0]
    assert cached.loc[0, "stamina_expected_retention_delta"] == 0
    assert round(cached.loc[2, "stamina_expected_retention_delta"], 6) == -0.01
    assert cached.loc[2, "stamina_early_stuff_baseline"] == 101.0
    assert round(cached.loc[2, "stamina_expected_stuff_plus"], 6) == 100.99

    output = service.stamina_dataset_path(2026, tmp_path)
    output.parent.mkdir()
    cached.to_parquet(output, index=False)
    loaded = service.load_pitch_stamina_state(frame.iloc[[2]][list(service.PITCH_KEY)], 2026, tmp_path)
    assert loaded.iloc[0]["stamina_plus_trait"] == 110.0
    assert loaded.iloc[0]["stamina_sample_label"] == "qualified"


def test_slice7_locks_family_taxonomy_and_bias_audit() -> None:
    rows = []
    pitch_types = ["FF", "SL", "FO", "XX"]
    for pitcher in range(1, 9):
        for pitch_number in range(1, 41):
            pitch_type = pitch_types[(pitch_number + pitcher) % len(pitch_types)]
            rows.append({
                "pitcher": pitcher,
                "game_pk": pitcher * 100,
                "appearance_role": "SP",
                "appearance_pitch_number": pitch_number,
                "pitch_type": pitch_type,
                "pitch_stuff_plus": 92.0 + pitcher * 2.0 - max(0, pitch_number - 20) * 0.05,
                "release_speed": 90.0 + pitcher * 0.5,
            })
    slice5 = {
        "leaderboard": [
            {"pitcher_id": pitcher, "role": "SP", "stamina_plus": 112.0 - pitcher * 2.0}
            for pitcher in range(1, 9)
        ]
    }

    result = service._build_slice7(pd.DataFrame(rows), slice5)
    StaminaSlice7Result(**result)

    assert result["status"] == "ready"
    assert result["contract_version"] == "stamina_v2_slice7_preregistered_v1"
    families = {row["family"]: row for row in result["family_coverage"]}
    assert families["Offspeed"]["pitch_types"] == ["CH", "FS", "FO"]
    assert families["Offspeed"]["pitches"] > 0
    assert result["unclassified_pitch_types"] == [{"pitch_type": "XX", "pitches": 80}]
    assert {row["key"] for row in result["bias_correlations"]} >= {
        "early_stuff_vs_v1", "early_stuff_vs_naive_delta"
    }
    assert len(result["ceiling_bands"]) == 4
    assert {gate["key"] for gate in result["release_gates"]} >= {
        "ceiling_neutrality", "family_support"
    }


def test_slice8_and_slice9_build_family_curves_and_challengers(tmp_path) -> None:
    rows = []
    game_pk = 20_000
    for pitcher in range(1, 7):
        for appearance in range(6):
            game_pk += 1
            game_date = pd.Timestamp("2026-04-01") + pd.Timedelta(days=appearance * 7 + pitcher)
            for pitch_number in range(1, 81):
                pitch_type, family, velocity = [
                    ("FF", "Fastball", 95.0), ("SL", "Breaking", 85.0), ("FO", "Offspeed", 87.0),
                ][(pitch_number - 1) % 3]
                rows.append({
                    "pitcher": pitcher, "game_pk": game_pk, "game_date": game_date,
                    "appearance_role": "SP", "appearance_pitch_number": pitch_number,
                    "appearance_number": appearance + 1, "pitch_type": pitch_type,
                    "pitch_family": family, "pitch_stuff_plus": 105.0 + pitcher * 0.2 - pitch_number * 0.04,
                    "location_plus_pitch": 100.0, "release_speed": velocity - pitch_number * 0.002,
                    "days_rest": 5, "season_pitches_before": appearance * 60,
                    "balls": pitch_number % 4, "strikes": pitch_number % 3,
                    "p_throws": "R", "stand": "L" if pitch_number % 2 else "R",
                    "n_thruorder_pitcher": min(3, (pitch_number - 1) // 20 + 1),
                    "inning": min(9, (pitch_number - 1) // 10 + 1), "home_team": "AZ",
                })
    frame = pd.DataFrame(rows)

    pitch_curves, appearance_curves, slice8 = service._build_slice8(frame, 2026, tmp_path)
    hierarchical, slice9 = service._build_slice9(pitch_curves)
    StaminaSlice8Result(**slice8)
    StaminaSlice9Result(**slice9)

    assert slice8["status"] == "ready"
    assert slice8["pitch_curve_rows"] == len(frame)
    assert pitch_curves.groupby(["pitcher", "game_pk", "pitch_family"])["trailing_ma5"].apply(
        lambda values: values.iloc[:4].isna().all() and values.iloc[4:].notna().all()
    ).all()
    assert set(appearance_curves["pitch_family"]) == {"Fastball", "Breaking", "Offspeed", "Overall"}
    overall = appearance_curves[appearance_curves["pitch_family"].eq("Overall")]
    assert overall["weight_source"].eq("appearance_first_20").all()
    assert overall["order"].max() == 3
    assert len(overall) == frame[["pitcher", "game_pk"]].drop_duplicates().shape[0] * 4
    assert slice9["status"] == "ready"
    assert {row["kind"] for row in slice9["comparisons"]} == {"baseline", "primary", "gamm", "ml_challenger"}
    assert {row["family"] for row in slice9["family_priors"]} == {"Fastball", "Breaking", "Offspeed"}
    assert len(hierarchical) > 0
    assert "trailing_ma5" not in slice9["method"]

    prior_frame = frame.copy()
    prior_frame["game_date"] = prior_frame["game_date"] - pd.DateOffset(years=1)
    prior_frame["pitch_stuff_plus"] = prior_frame["pitch_stuff_plus"] - 0.15
    prior_curves, _, _ = service._build_slice8(prior_frame, 2025, tmp_path)
    service._write_parquet_atomic(
        prior_curves, service.stamina_v2_pitch_curve_path(2025, tmp_path), "test_prior_curves"
    )
    candidates, slice10 = service._build_slice10(
        pitch_curves,
        {
            "classified_stuff_coverage_pct": 100.0,
            "family_coverage": [
                {"family": family, "stuff_coverage_pct": 100.0}
                for family in ["Fastball", "Breaking", "Offspeed"]
            ],
        },
        2026,
        tmp_path,
    )
    StaminaSlice10Result(**slice10)
    assert slice10["status"] == "ready"
    assert slice10["train_year"] == 2025 and slice10["test_year"] == 2026
    assert {row["kind"] for row in slice10["model_validations"]} == {"primary", "gamm", "ml_challenger"}
    assert {row["scope"] for row in slice10["scope_validations"]} == {"Overall", "Fastball", "Breaking", "Offspeed"}
    assert set(candidates.columns) == {
        "pitcher", "scope", "combined_slope", "stamina_plus_v2_candidate", "seasons", "publication_status"
    }

    signal_frame = frame.copy()
    signal_frame["player_name"] = signal_frame["pitcher"].map(lambda value: f"Pitcher {value}")
    signal_frame["pitcher_team"] = "AZ"
    signal_frame["pfx_x"] = -0.4
    signal_frame["pfx_z"] = 1.2
    signal_frame["release_spin_rate"] = 2400.0
    signal_frame["release_extension"] = 6.2
    signal_frame["release_pos_x"] = -2.0
    signal_frame["release_pos_z"] = 6.0
    multisignal, slice11 = service._build_slice11(signal_frame, pitch_curves)
    StaminaSlice11Result(**slice11)
    assert slice11["publication_status"] == "research_only"
    assert set(multisignal["pitch_family"]) == {"Fastball", "Breaking", "Offspeed"}
    assert multisignal["usage_pct"].between(0, 100).all()
    assert multisignal[multisignal["pitches"].eq(0)]["stuff_delta"].isna().all()
    service._write_parquet_atomic(
        multisignal, service.stamina_v2_multisignal_path(2026, tmp_path), "test_multisignal"
    )
    detail = service.get_stamina_research_curves(2026, 1, tmp_path)
    StaminaResearchCurvesResponse(**detail)
    assert detail["publication_status"] == "research_only"

    prior_signal_frame = signal_frame.copy()
    prior_signal_frame["game_date"] = prior_signal_frame["game_date"] - pd.DateOffset(years=1)
    prior_signal_frame["pitch_stuff_plus"] = prior_signal_frame["pitch_stuff_plus"] - 0.15
    states, windows, game_state = service._build_game_states(
        prior_curves, pitch_curves, prior_signal_frame, signal_frame, 2025, 2026
    )
    StaminaGameStateResult(**game_state)
    assert game_state["publication_status"] == "observed_state"
    assert set(states["scope"]).issubset({"Overall", "Fastball", "Breaking", "Offspeed"})
    assert set(windows["analysis_bucket"]).issubset({"21–40", "41–60", "61–80", "81–100"})
    service._write_parquet_atomic(
        states, service.stamina_game_state_path(2026, tmp_path), "test_game_states"
    )
    service._write_parquet_atomic(
        windows, service.stamina_game_state_window_path(2026, tmp_path), "test_game_state_windows"
    )
    game_detail = service.get_stamina_game_states(2026, 1, tmp_path)
    StaminaGameStatesResponse(**game_detail)
    assert game_detail["pitcher_id"] == 1


def test_slice12_builds_qualified_observed_season_summaries(tmp_path) -> None:
    rows = []
    for pitcher, offset, game_reliability in [(1, 4.0, 0.82), (2, -3.0, 0.82), (3, 0.0, 0.60)]:
        for start in range(1, 13):
            for scope, pitches in [("Overall", 45), ("Fastball", 24), ("Breaking", 12), ("Offspeed", 9)]:
                score = 100.0 + offset + (start % 3 - 1)
                rows.append({
                    "pitcher": pitcher,
                    "game_pk": pitcher * 1000 + start,
                    "game_date": pd.Timestamp("2026-04-01") + pd.Timedelta(days=start * 6),
                    "pitcher_name": f"Pitcher {pitcher}",
                    "team": "AZ",
                    "season_start_number": start,
                    "total_pitches": 82,
                    "scope": scope,
                    "pitches": pitches,
                    "eligible": True,
                    "stamina_plus": score,
                    "ci_low": score - 5.0,
                    "ci_high": score + 5.0,
                    "reliability": game_reliability,
                })
    summaries, result = service._build_season_summaries(pd.DataFrame(rows), 2026)

    StaminaSlice12Result(**result)
    assert result["publication_status"] == "research_only"
    assert {row["scope"] for row in result["scope_audits"]} == {
        "Overall", "Fastball", "Breaking", "Offspeed"
    }
    assert summaries["qualified"].all()
    assert summaries.groupby("scope")["rank"].apply(lambda values: sorted(values.tolist()) == [1.0, 2.0, 3.0]).all()
    assert summaries[summaries["pitcher"].eq(1)]["stamina_plus"].gt(100).all()
    low_game_precision = summaries[summaries["pitcher"].eq(3)]
    assert low_game_precision["mean_game_reliability"].lt(0.70).all()
    assert low_game_precision["reliability"].ge(0.70).all()
    assert low_game_precision["qualified"].all()

    service._write_parquet_atomic(
        summaries, service.stamina_season_summary_path(2026, tmp_path), "test_season_summaries"
    )
    response = service.get_stamina_season_summaries(2026, tmp_path)
    StaminaSeasonSummariesResponse(**response)
    assert len(response["rows"]) == 12


def test_slice13_external_validation_keeps_failed_gate_visible() -> None:
    years = [2025, 2026]
    metas = {}
    states = {}
    summaries = {}
    scope_audits = [
        {
            "scope": scope, "pitchers": 3, "qualified_pitchers": 3,
            "minimum_games": 10 if scope == "Overall" else 8,
            "minimum_pitches": 150 if scope == "Overall" else 50,
            "median_reliability": 0.9, "median_interval_width": 4.0,
            "weighted_vs_unweighted_spearman": 0.99,
        }
        for scope in ["Overall", "Fastball", "Breaking", "Offspeed"]
    ]
    for year in years:
        metas[year] = {
            "slice11_game_state": {
                "contract_version": "stamina_observed_game_state_v1_1",
                "overall_start_coverage_pct": 95.0,
                "pitch_rmse_improvement_pct": 2.0,
                "early_stuff_spearman": 0.05,
                "early_velocity_spearman": 0.05,
                "within_game_split_spearman": 0.4,
            },
            "slice12": {
                "contract_version": "stamina_observed_season_state_v1_1",
                "scope_audits": scope_audits,
            },
        }
        states[year] = pd.DataFrame([
            {
                "pitcher": pitcher, "scope": "Overall", "eligible": True,
                "stamina_plus": 95.0 + pitcher * 5.0, "early_stuff": 90.0 + pitcher * 10.0,
                "early_velocity": 90.0 + pitcher,
            }
            for pitcher in range(1, 4)
        ])
        summaries[year] = pd.DataFrame([
            {
                "pitcher": pitcher, "scope": "Overall", "qualified": True,
                "stamina_plus": 95.0 + pitcher * 5.0, "eligible_games": 12,
                "average_pitches": 80.0,
            }
            for pitcher in range(1, 4)
        ])

    result = service._build_external_validation(metas, states, summaries, 2025, 2026)

    StaminaSlice13Result(**result)
    assert result["leaderboard_release_eligible"] is False
    failed = [gate["key"] for gate in result["gates"] if not gate["passed"]]
    assert "season_support" in failed
    assert "season_ceiling_neutrality" in failed


def test_slice13a_fits_only_development_year_and_emits_adjusted_scores() -> None:
    scopes = ["Overall", "Fastball", "Breaking", "Offspeed"]
    states = {}
    summaries = {}
    for year in [2025, 2026]:
        state_rows = []
        summary_rows = []
        for scope_index, scope in enumerate(scopes):
            for pitcher in range(1, 121):
                early_stuff = 86.0 + pitcher * 0.35 + scope_index
                early_velocity = 86.0 + (pitcher % 12) * 0.45 + scope_index * 0.2
                score = 100.0 + 0.28 * (early_stuff - 96.0) + 0.18 * (early_velocity - 89.0)
                score += ((pitcher * 7) % 11 - 5) * 0.35
                state_rows.append({
                    "pitcher": pitcher, "scope": scope, "eligible": True,
                    "stamina_plus": score, "early_stuff": early_stuff,
                    "early_velocity": early_velocity,
                })
                summary_rows.append({
                    "pitcher": pitcher, "scope": scope, "qualified": True,
                    "stamina_plus": score, "unweighted_stamina_plus": score + 0.05,
                    "ci_low": score - 4.0, "ci_high": score + 4.0,
                    "reliability": 0.9,
                })
        states[year] = pd.DataFrame(state_rows)
        summaries[year] = pd.DataFrame(summary_rows)
    external_validation = {
        "gates": [
            {"key": key, "passed": True}
            for key in [
                "frozen_contracts", "overall_coverage", "pitch_rmse_gain", "game_ceiling_neutrality",
                "within_game_consistency", "season_support", "season_precision", "weighting_sensitivity",
            ]
        ] + [{"key": "season_ceiling_neutrality", "passed": False}]
    }

    adjusted, result = service._build_season_bias_repair(
        states, summaries, external_validation, 2025, 2026
    )

    StaminaSlice13AResult(**result)
    assert result["development_year"] == 2025 and result["test_year"] == 2026
    assert len(result["model_audits"]) == 4
    assert set(adjusted["season"]) == {2025, 2026}
    assert adjusted["adjusted_stamina_plus"].notna().all()
    gates = {gate["key"]: gate for gate in result["gates"]}
    assert gates["development_isolation"]["passed"] is True
    assert gates["preserve_slice13_gates"]["passed"] is True
    assert gates["adjusted_support"]["passed"] is True


def test_stamina_leaderboard_releases_only_qualified_adjusted_rows(tmp_path) -> None:
    derived = tmp_path / "derived"
    derived.mkdir()
    rows = pd.DataFrame([
        {
            "pitcher": 1, "pitcher_name": "Qualified Pitcher", "team": "AZ",
            "scope": "Overall", "total_starts": 20, "eligible_games": 18,
            "average_pitches": 88.4, "adjusted_stamina_plus": 106.25,
            "adjusted_ci_low": 103.1, "adjusted_ci_high": 109.4,
            "adjusted_reliability": 0.91, "adjusted_qualified": True, "adjusted_rank": 1.0,
        },
        {
            "pitcher": 1, "pitcher_name": "Qualified Pitcher", "team": "AZ",
            "scope": "Fastball", "total_starts": 20, "eligible_games": 17,
            "average_pitches": 88.4, "adjusted_stamina_plus": 104.75,
            "adjusted_ci_low": 101.0, "adjusted_ci_high": 108.5,
            "adjusted_reliability": 0.88, "adjusted_qualified": True, "adjusted_rank": 1.0,
        },
        {
            "pitcher": 1, "pitcher_name": "Qualified Pitcher", "team": "AZ",
            "scope": "Breaking", "total_starts": 20, "eligible_games": 6,
            "average_pitches": 88.4, "adjusted_stamina_plus": 108.0,
            "adjusted_ci_low": 95.0, "adjusted_ci_high": 121.0,
            "adjusted_reliability": 0.50, "adjusted_qualified": False, "adjusted_rank": None,
        },
        {
            "pitcher": 2, "pitcher_name": "Unqualified Pitcher", "team": "LAD",
            "scope": "Overall", "total_starts": 8, "eligible_games": 5,
            "average_pitches": 70.0, "adjusted_stamina_plus": 110.0,
            "adjusted_ci_low": 90.0, "adjusted_ci_high": 130.0,
            "adjusted_reliability": 0.40, "adjusted_qualified": False, "adjusted_rank": None,
        },
    ])
    service._write_parquet_atomic(
        rows, service.stamina_adjusted_season_summary_path(2026, tmp_path), "test_adjusted_summaries"
    )
    service.stamina_season_bias_repair_path(2026, tmp_path).write_text(json.dumps({
        "leaderboard_release_eligible": True,
        "contract_version": "stamina_season_bias_repair_v1",
        "development_year": 2025,
        "test_year": 2026,
    }), encoding="utf-8")
    service.stamina_meta_path(2026, tmp_path).write_text(
        json.dumps({"data_as_of": "2026-09-28"}), encoding="utf-8"
    )
    game_rows = [{
        "pitcher": 1, "game_pk": game, "scope": "Overall", "eligible": True,
        "stamina_plus": 101.0 + game / 10.0,
    } for game in range(1, 11)]
    physical_rows = [{
        "pitcher": 1, "game_pk": game, "eligible": True,
        "physical_stability_plus": 98.0 + game / 10.0,
    } for game in range(1, 11)]
    command_rows = [{
        "pitcher": 1, "game_pk": game, "scope": "Overall", "eligible": True,
        "command_retention_plus": 99.0 + game / 10.0,
    } for game in range(1, 11)]
    service._write_parquet_atomic(pd.DataFrame(game_rows), service.stamina_game_state_path(2026, tmp_path), "leaderboard_games")
    physical_service._write_parquet_atomic(pd.DataFrame(physical_rows), physical_service.physical_game_path(2026, tmp_path), "leaderboard_physical")
    command_service._write_parquet_atomic(pd.DataFrame(command_rows), command_service.command_game_path(2026, tmp_path), "leaderboard_command")

    result = service.get_stamina_leaderboard(2026, tmp_path)

    StaminaLeaderboardResponse(**result)
    assert len(result["rows"]) == 1
    assert result["rows"][0]["rank"] == 1
    assert result["rows"][0]["fastball_stamina_plus"] == 104.8
    assert result["rows"][0]["breaking_stamina_plus"] is None
    assert result["rows"][0]["offspeed_stamina_plus"] is None
    assert result["rows"][0]["quality_game_stamina_plus"] == 101.5
    assert result["rows"][0]["physical_stability_plus"] == 98.5
    assert result["rows"][0]["command_retention_plus"] == 99.5


def test_physical_stability_scores_exact_type_windows_without_stuff_target(tmp_path) -> None:
    rows = []
    for game_pk in range(1, 6):
        for pitch_number in range(1, 61):
            late = max(pitch_number - 20, 0) / 40.0
            drift = game_pk * late
            rows.append({
                "pitcher": 1, "player_name": "Doe, John", "pitcher_team": "AZ", "game_pk": game_pk,
                "game_date": f"2023-04-{game_pk:02d}", "appearance_role": "SP",
                "appearance_pitch_number": pitch_number, "pitch_type": "FF", "pitch_family": "Fastball",
                "release_speed": 95.0 - 0.20 * drift, "pfx_x": -0.4 + 0.01 * drift,
                "pfx_z": 1.2 - 0.01 * drift, "release_spin_rate": 2400.0 - 8.0 * drift,
                "spin_axis": 210.0 + 0.3 * drift, "release_extension": 6.2 - 0.01 * drift,
                "release_pos_x": -2.0 + 0.005 * drift, "release_pos_z": 6.0 - 0.005 * drift,
                "arm_angle": 45.0 - 0.15 * drift,
            })
    raw, audit = physical_service._build_raw_windows(pd.DataFrame(rows), 2023)
    reference = physical_service._fit_reference(raw)
    windows, games = physical_service._score_year(raw, reference)

    assert audit["supported_late_pct"] == 100.0
    assert set(windows["analysis_bucket"]) == {"21–40", "41–60"}
    assert games["eligible"].all()
    assert games.iloc[0]["physical_stability_plus"] > games.iloc[-1]["physical_stability_plus"]
    assert games.iloc[0]["pitcher_name"] == "John Doe"

    physical_service._write_parquet_atomic(
        windows, physical_service.physical_window_path(2023, tmp_path), "physical_windows"
    )
    physical_service._write_parquet_atomic(
        games, physical_service.physical_game_path(2023, tmp_path), "physical_games"
    )
    detail = physical_service.get_physical_stability(2023, 1, tmp_path)
    StaminaPhysicalStabilityResponse(**detail)
    assert len(detail["games"]) == 5
    assert len(detail["windows"]) == 10


def test_command_retention_learns_early_location_ceiling_and_serves_detail(tmp_path) -> None:
    rows = []
    for game_pk in range(1, 13):
        early_level = 72.0 + game_pk * 3.0
        for pitch_number in range(1, 81):
            if pitch_number <= 20:
                location = early_level + (pitch_number % 3 - 1)
            else:
                location = 92.0 + 0.35 * (early_level - 92.0) - 0.025 * pitch_number + (pitch_number % 4 - 1.5)
            rows.append({
                "pitcher": 1, "player_name": "Doe, John", "pitcher_team": "AZ", "game_pk": game_pk,
                "game_date": f"2023-04-{game_pk:02d}", "appearance_pitch_number": pitch_number,
                "pitch_type": "FF", "pitch_family": "Fastball", "location_plus_pitch": location,
            })
    prepared, _ = command_service._prepare_pitch_rows(pd.DataFrame(rows))
    model = command_service._fit_expected_model(prepared)
    scored = command_service._attach_early_family_weights(prepared, command_service._score_pitches(prepared, model))
    baseline_rmse = ((scored["location_plus_pitch"] - scored["early_location"]) ** 2).mean() ** 0.5
    model_rmse = ((scored["location_plus_pitch"] - scored["expected_location"]) ** 2).mean() ** 0.5
    assert model_rmse < baseline_rmse
    assert abs(scored["command_residual"].corr(scored["early_location"], method="spearman")) < 0.25

    raw = command_service._build_raw_windows(scored, 2023)
    reference = command_service._fit_scoring_reference(raw, float(scored["command_residual"].var(ddof=1)))
    windows, games = command_service._score_windows_and_games(raw, reference)
    command_service._write_parquet_atomic(windows, command_service.command_window_path(2023, tmp_path), "command_windows")
    command_service._write_parquet_atomic(games, command_service.command_game_path(2023, tmp_path), "command_games")
    command_service.command_contract_path(2023, tmp_path).write_text(json.dumps({
        "publication_status": "research_only", "warnings": []
    }), encoding="utf-8")
    detail = command_service.get_command_retention(2023, 1, tmp_path)
    StaminaCommandRetentionResponse(**detail)
    assert detail["pitcher_name"] == "John Doe"
    assert len([row for row in detail["games"] if row["scope"] == "Overall"]) == 12


def test_product_integration_keeps_three_signals_separate(tmp_path) -> None:
    quality_rows, physical_rows, command_rows = [], [], []
    profiles = {
        1: (108.0, 91.0, 99.0), 2: (102.0, 105.0, 101.0),
        3: (89.0, 107.0, 98.0), 4: (104.0, 103.0, 104.0),
    }
    for pitcher, (quality, physical, command) in profiles.items():
        for game in range(1, 13):
            common = {"pitcher": pitcher, "game_pk": pitcher * 100 + game, "game_date": f"2026-04-{game:02d}"}
            quality_rows.append({**common, "pitcher_name": f"Pitcher, {pitcher}", "team": "AZ", "scope": "Overall", "eligible": True, "stamina_plus": quality, "reliability": .8})
            physical_rows.append({**common, "eligible": True, "physical_stability_plus": physical, "reliability": .85})
            command_rows.append({**common, "scope": "Overall", "eligible": True, "command_retention_plus": command, "reliability": .5})
    command_service._write_parquet_atomic(pd.DataFrame(quality_rows), tmp_path / "derived" / "stamina_game_states_2026.parquet", "quality")
    command_service._write_parquet_atomic(pd.DataFrame(physical_rows), command_service._physical_window_path(2026, tmp_path).with_name("stamina_physical_games_2026.parquet"), "physical")
    command_service._write_parquet_atomic(pd.DataFrame(command_rows), command_service.command_game_path(2026, tmp_path), "command")
    command_service.incremental_validation_path(2026, tmp_path).write_text(json.dumps({"composite_release_eligible": False}), encoding="utf-8")

    result = command_service.refresh_product_integration(2026, tmp_path)

    StaminaSlice19Result(**result)
    assert result["decision"] == "keep_separate"
    assert result["composite_release_eligible"] is False
    assert result["qualified_three_signal_pitchers"] == 4
    assert {row["case"] for row in result["representative_pitchers"]} >= {"quality_over_physical", "physical_over_quality"}


def _pitch(pitcher: int, date: str, pitch_number: int, at_bat: int, uid: int, team: str, game_pk: int = 1) -> dict[str, object]:
    return {
        "pitch_type": "FF", "game_date": date, "release_speed": 95.0, "release_pos_x": -2.0,
        "release_pos_z": 6.0, "pitcher": pitcher, "game_type": "R", "stand": "R", "p_throws": "R",
        "home_team": team, "away_team": "LAD", "balls": 0, "strikes": 0, "pfx_x": -0.4, "pfx_z": 1.2,
        "plate_x": 0.1, "plate_z": 2.6, "sz_top": 3.5, "sz_bot": 1.5, "inning": 1,
        "inning_topbot": "Top", "release_spin_rate": 2400, "release_extension": 6.2, "game_pk": game_pk,
        "at_bat_number": at_bat, "pitch_number": pitch_number, "pitch_name": "4-Seam Fastball",
        "spin_axis": 210, "arm_angle": 45.0, "n_thruorder_pitcher": 1, "pitcher_team": team,
        "pitch_uid": f"{game_pk}_{at_bat}_{pitch_number}_{uid}",
    }
