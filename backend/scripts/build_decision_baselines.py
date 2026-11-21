"""Build Decision Support 12.5–12.7 with frozen predecision features and validation."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import time
import warnings

import duckdb
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.exceptions import ConvergenceWarning
from sklearn.impute import SimpleImputer
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import log_loss
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from scripts.build_decision_preparation import OUT as PREP, SAMPLE, TEMPORAL, FOLDS, OUTCOMES, digest, save_json
from scripts.build_decision_temporal_context import post_state, re_get, we_predict

OUT = ROOT / "data/research/decision_baseline_v1"
YEARS = range(2021, 2027)
SITUATION_NUM = ["inning", "defense_lead", "outs"]
SITUATION_CAT = ["half", "base_state", "extra", "scheduled_innings"]
LOAD_NUM = ["option_game_pitches", "option_current_bf", "pitches_1d_before", "pitches_3d_before", "pitches_7d_before",
            "pitches_14d_before", "rest_hours", "previous_pitches", "consecutive_days"]
LOAD_CAT = ["option_role", "role_known", "is_current", "appeared_earlier_today", "lookback_14d_complete"]
ABILITY_NUM = [f"{actor}_{key}_rate" for actor in ("pitcher", "batter") for key in OUTCOMES]
ABILITY_NUM += ["pitcher_log_n", "batter_log_n"]
ABILITY_CAT = ["pitcher_hand", "expected_stand", "pitcher_ability_status", "batter_ability_status"]
LEVELS = {
    "situation": (SITUATION_NUM, SITUATION_CAT),
    "workload": (SITUATION_NUM + LOAD_NUM, SITUATION_CAT + LOAD_CAT),
    "matchup": (SITUATION_NUM + LOAD_NUM + ABILITY_NUM, SITUATION_CAT + LOAD_CAT + ABILITY_CAT),
}
LEARNER = {"loss": "log_loss", "penalty": "l2", "max_iter": 80, "tol": 0.001,
           "average": True, "random_state": 20261118, "early_stopping": False}


def connection() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(config={"threads": 1, "memory_limit": "2GB", "preserve_insertion_order": False})


def records(conn: duckdb.DuckDBPyConnection, sql: str) -> list[dict]:
    result = conn.execute(sql)
    return [dict(zip([col[0] for col in result.description], row, strict=True)) for row in result.fetchall()]


def publish(conn: duckdb.DuckDBPyConnection, name: str, year: int) -> None:
    target = OUT / f"{name}_{year}.parquet"
    temp = target.with_suffix(".tmp.parquet")
    conn.table(name).write_parquet(str(temp), compression="zstd")
    temp.replace(target)


def lookup_ability(conn: duckdb.DuckDBPyConnection, actor: str, year: int) -> None:
    """Use one option-independent request per batter/decision/hand, and strict ASOF."""
    history_path = str(PREP / "ability_history.parquet").replace("\\", "/")
    end = pd.Timestamp(f"{year+1}-01-01", tz="UTC").timestamp()
    conn.execute(f"""CREATE OR REPLACE TEMP TABLE history AS SELECT * FROM read_parquet('{history_path}')
                     WHERE actor='{actor}' AND available_at<{end}""")
    fields = ",".join(f"coalesce(h.{key}_n/nullif(h.pa_n,0),a.{key}_n/nullif(a.pa_n,0),r.{key}_n/nullif(r.pa_n,0)) AS {key}_rate" for key in OUTCOMES)
    conn.execute(f"""
        CREATE TABLE {actor}_option_ability AS
        SELECT q.request_id,coalesce(h.pa_n,0) AS own_split_n,coalesce(a.pa_n,0) AS own_all_n,
            coalesce(h.available_at,a.available_at,r.latest_label_at) AS history_available_at,
            CASE WHEN h.pa_n>0 THEN 'own_split' WHEN a.pa_n>0 THEN 'own_all'
                WHEN r.pa_n>0 THEN 'frozen_reference' ELSE 'cold_start_unavailable' END AS ability_status,
            CASE WHEN coalesce(h.pa_n,a.pa_n) IS NULL THEN r.train_cutoff END AS fallback_train_cutoff,
            {fields}
        FROM ability_requests q
        ASOF LEFT JOIN history h ON q.player_id=h.player_id AND q.actor_role=h.role
            AND q.requested_split=h.split AND q.decision_at>h.available_at
        ASOF LEFT JOIN (SELECT * FROM history WHERE split='All') a ON q.player_id=a.player_id
            AND q.actor_role=a.role AND q.decision_at>a.available_at
        LEFT JOIN ability_references r ON r.actor='{actor}' AND r.role=q.actor_role
            AND r.split='All' AND r.fold_id=q.fold_id
    """)
    assert conn.execute(f"SELECT count(*) FROM {actor}_option_ability x JOIN ability_requests q USING(request_id) WHERE history_available_at>=decision_at OR fallback_train_cutoff>decision_at").fetchone()[0] == 0


def candidates(year: int) -> None:
    with connection() as conn:
        for directory, names in ((SAMPLE, ("decision_candidates",)),
                                 (PREP, ("prepared_features", "listed_hands", "decision_matchup", "clean_labels"))):
            for name in names:
                conn.read_parquet(str(directory / f"{name}_{year}.parquet")).create_view(name)
        conn.read_parquet(str(PREP / "ability_references.parquet")).create_view("ability_references")
        conn.execute("""
            CREATE TABLE option_core AS
            SELECT f.year,f.game_pk,f.decision_id,f.decision_at,f.outgoing_pitcher_id AS option_pitcher_id,
                true AS is_current,f.role AS option_role,true AS role_known,
                f.current_pitches AS option_game_pitches,f.current_bf AS option_current_bf,
                f.pitches_1d_before,f.pitches_3d_before,f.pitches_7d_before,f.pitches_14d_before,
                f.rest_hours_since_closed_session AS rest_hours,NULL::BIGINT AS previous_pitches,
                f.prior_session_consecutive_days AS consecutive_days,f.appeared_earlier_today,f.lookback_14d_complete,
                f.last_pitch_at AS last_pitch_available_at,f.history_closed_at AS role_history_available_at,
                f.quality_plus AS quality,f.physical_plus AS physical,f.command_plus AS command,
                f.state_observed_at AS state_available_at,f.state_reliability AS state_reliability,
                f.prefix_status AS state_status,f.roster_confidence,'current_pitcher' AS candidate_reason,
                NULL::BOOLEAN AS warmup_available,NULL::BOOLEAN AS body_available,
                'observed_current_prefix' AS state_scope
            FROM prepared_features f
            UNION ALL
            SELECT c.year,c.game_pk,c.decision_id,c.cutoff_epoch,c.pitcher_id,false,
                coalesce(c.previous_role,'RP'),c.previous_role IS NOT NULL,0,0,
                c.pitches_1d_before,c.pitches_3d_before,c.pitches_7d_before,c.pitches_14d_before,
                c.hours_since_last_pitch,c.previous_session_pitches,c.consecutive_days_before,
                c.appeared_earlier_today,c.lookback_14d_complete,c.last_pitch_epoch,c.history_closed_epoch,
                c.prior_quality,c.prior_physical,c.prior_command,c.prior_state_available_at,c.prior_state_reliability,
                c.prior_state_status,c.roster_confidence,c.reason,c.warmup_available,c.body_available,
                'last_closed_appearance_not_readiness'
            FROM decision_candidates c
        """)
        # Current pitcher previous-session pitches are available in the original workload, not final appearance data.
        conn.read_parquet(str(ROOT / f"data/research/decision_support_pipeline_20261114/workload_{year}.parquet")).create_view("workload")
        conn.execute("UPDATE option_core o SET previous_pitches=w.previous_session_pitches FROM workload w WHERE o.is_current AND o.decision_id=w.decision_id")
        conn.execute("""
            CREATE TABLE option_requests AS
            SELECT row_number() OVER(ORDER BY o.decision_id,o.is_current DESC,o.option_pitcher_id) AS request_id,o.*,
                f.batter_id,f.listed_bats,m.ability_fold_id AS fold_id,
                coalesce(CASE WHEN h.listed_throws IN ('L','R') THEN h.listed_throws END,'unknown') AS pitcher_hand,
                CASE WHEN f.listed_bats IN ('L','R') THEN f.listed_bats
                    WHEN f.listed_bats='S' AND h.listed_throws='L' THEN 'R'
                    WHEN f.listed_bats='S' AND h.listed_throws='R' THEN 'L' ELSE 'unknown' END AS expected_stand
            FROM option_core o JOIN prepared_features f USING(decision_id)
            JOIN decision_matchup m USING(decision_id)
            LEFT JOIN listed_hands h ON h.game_pk=o.game_pk AND h.player_id=o.option_pitcher_id
        """)
        print(f"{year}: option roster and workload assembled", flush=True)
        conn.execute("CREATE TABLE ability_requests AS SELECT request_id,option_pitcher_id AS player_id,option_role AS actor_role,expected_stand AS requested_split,decision_at,fold_id FROM option_requests")
        lookup_ability(conn, "pitcher", year)
        conn.execute("DROP TABLE ability_requests")
        # Batter histories repeat across candidates with the same hand. Resolve each hand once per decision.
        conn.execute("""CREATE TABLE batter_requests AS
            SELECT row_number() OVER(ORDER BY decision_id,pitcher_hand) AS request_id,* FROM (
                SELECT DISTINCT decision_id,pitcher_hand,batter_id,decision_at,fold_id FROM option_requests)""")
        conn.execute("CREATE TABLE ability_requests AS SELECT request_id,batter_id AS player_id,'BAT' AS actor_role,pitcher_hand AS requested_split,decision_at,fold_id FROM batter_requests")
        lookup_ability(conn, "batter", year)
        columns = []
        for alias, actor in (("p", "pitcher"), ("b", "batter")):
            columns.extend(f"{alias}.{field} AS {actor}_{field}" for field in
                           ("own_split_n", "own_all_n", "history_available_at", "ability_status", "fallback_train_cutoff", *(f"{key}_rate" for key in OUTCOMES)))
        conn.execute("""CREATE TABLE option_features AS SELECT o.* EXCLUDE(request_id,fold_id),
            """ + ",".join(columns) + """,false AS individual_ranking_allowed
            FROM option_requests o JOIN pitcher_option_ability p USING(request_id)
            JOIN batter_requests r ON r.decision_id=o.decision_id AND r.pitcher_hand=o.pitcher_hand
            JOIN batter_option_ability b ON b.request_id=r.request_id""")
        checks = records(conn, """SELECT
            count(*) FILTER(WHERE last_pitch_available_at>=decision_at OR role_history_available_at>=decision_at
                OR state_available_at>=decision_at OR pitcher_history_available_at>=decision_at
                OR batter_history_available_at>=decision_at OR pitcher_fallback_train_cutoff>decision_at
                OR batter_fallback_train_cutoff>decision_at) AS time_violations,
            count(*)-count(DISTINCT (decision_id,option_pitcher_id)) AS duplicate_keys,
            count(*) FILTER(WHERE warmup_available IS NOT NULL OR body_available IS NOT NULL OR individual_ranking_allowed) AS availability_fabricated
            FROM option_features""")[0]
        assert all(value == 0 for value in checks.values()), checks
        assert conn.execute("SELECT count(*) FROM option_features WHERE is_current").fetchone()[0] == conn.execute("SELECT count(*) FROM prepared_features").fetchone()[0]
        conn.execute("""CREATE TABLE observed_features AS
            SELECT f.year,f.game_pk,f.decision_id,f.decision_at,f.inning,f.half,f.scheduled_innings,f.defense_lead,
                f.outs,f.base_state,(f.inning>f.scheduled_innings)::INTEGER AS extra,
                f.research_home_we,f.research_re,f.role AS outgoing_role,
                o.* EXCLUDE(year,game_pk,decision_id,decision_at),l.observed_action
            FROM prepared_features f JOIN clean_labels l USING(decision_id)
            JOIN option_features o ON o.decision_id=f.decision_id AND o.option_pitcher_id=l.incoming_pitcher_id
        """)
        assert conn.execute("SELECT count(*) FROM observed_features").fetchone()[0] == conn.execute("SELECT count(*) FROM prepared_features").fetchone()[0]
        summary = records(conn, """SELECT year,count(*) AS decisions,
            sum(candidate_n) AS candidate_rows,
            count(*) FILTER(WHERE ability_n>0) AS any_candidate_ability,
            count(*) FILTER(WHERE ability_n=candidate_n) AS all_candidate_ability,
            count(*) FILTER(WHERE state_n>0) AS any_candidate_state,
            count(*) FILTER(WHERE state_n=candidate_n) AS all_candidate_state FROM (
                SELECT year,decision_id,count(*) AS candidate_n,
                    count(*) FILTER(WHERE pitcher_k_rate IS NOT NULL AND batter_k_rate IS NOT NULL) AS ability_n,
                    count(*) FILTER(WHERE quality IS NOT NULL AND physical IS NOT NULL AND command IS NOT NULL) AS state_n
                FROM option_features WHERE NOT is_current GROUP BY ALL) GROUP BY year""")[0]
        coverage = records(conn, """SELECT is_current,option_role,count(*) AS n,count(pitcher_k_rate) AS pitcher_ability,
            count(batter_k_rate) AS batter_ability,count(rest_hours) AS rest_hours,count(previous_pitches) AS previous_pitches,
            count(quality) AS quality,count(physical) AS physical,count(command) AS command,
            count(*) FILTER(WHERE pitcher_hand IN ('L','R')) AS known_hand FROM option_features GROUP BY ALL ORDER BY ALL""")
        names=[row[0] for row in conn.execute('DESCRIBE option_features').fetchall()]
        counts=records(conn,'SELECT is_current,option_role,count(*) AS denominator,'+
                       ','.join(f'count({name}) AS {name}_present' for name in names)+
                       ' FROM option_features GROUP BY ALL ORDER BY ALL')
        for name in ("option_features", "observed_features"):
            publish(conn, name, year)
        save_json(OUT / f"candidates_{year}.json", {**summary, "checks": checks, "coverage": coverage,"field_coverage":counts,
            "candidate_role": "previous observed role; unknown uses RP reference with role_known=false; not readiness",
            "state_scope": "current observed prefix versus candidate last closed appearance; separate scope flags",
            "operational_availability": "warmup, medical and exact intraday availability unknown"})
        print(f"{year}: {summary['candidate_rows']:,} candidate profiles published", flush=True)


def protocol() -> dict:
    inputs = [PREP / "manifest.json", TEMPORAL / "protocol.json", Path(__file__)]
    inputs.extend(OUT/f'observed_features_{year}.parquet' for year in YEARS)
    return {
        "version": "decision_baseline_v1.2", "frozen_before_training": True,
        "implementation_revision": "Nullable boolean categorical conversion repaired before workload/matchup fitting; original protocol and partial situation experiment preserved in attempt1_nullable_category_failure; no split, target or feature changes.",
        "superseded_protocol_sha256": "c4950edb4d6c5fc1c206c6d16366e1b6a93665c1b5fd585a77ea8e9614a5d0d4",
        "terminal_revision": "Before final delivery, enforce walk-off non-HR run cap in both joint scores and value expectations; preserve interrupted v1.1 experiment in attempt2_terminal_constraint_revision. No outcome, split, feature or model-selection rule change.",
        "superseded_v1_1_protocol_sha256": "8d1c3a8ae3487462992c65b8cbb0651eac81beca677161db5e0e2ef85cae7851",
        "input_sha256": {str(path.relative_to(ROOT)): digest(path) for path in inputs},
        "split": {"train": [2021, 2022, 2023], "selection_and_diagnostics": [2024],
                  "locked_test": [2025], "retrospective_score_only": [2026]},
        "target": "organic next completed PA category and joint (runs, final outs, final bases), starting at decision",
        "training_actor": "observed incoming pitcher option; ID is joined, not encoded as a numeric predictor",
        "levels": {name: {"numeric": num, "categorical": cat} for name, (num, cat) in LEVELS.items()},
        "candidate_alphas": [0.0001, 0.001], "pooling_strengths_matchup": [0, 20],
        "learner": LEARNER,
        "preprocessing": "median plus missing indicators and StandardScaler on numeric; explicit unknown category and OneHotEncoder ignore unknown; fit train only",
        "cold_start": "raw features retained; optional empirical pooling uses training outcome frequency and own sample n only",
        "weighting": "train equal total weight per game, rescaled to mean weight 1; evaluation reports PA metrics and game-cluster uncertainty",
        "transition": "training-only legal conditional distributions by outs/base/extra and PA category; 20-count shrinkage toward same outs/base/category reference; game-context walk-off run cap excludes non-HR events exceeding the winning run",
        "selection": "lowest 2024 PA log loss per level; ties within 0.0001 prefer stronger regularization, then simpler pooling; keep simpler level unless log loss and Brier both improve",
        "calibration": "raw probabilities; report 2024 top-label and classwise reliability bins and ECE; no calibration refit on test years",
        "resampling": "100 paired game-cluster bootstrap replicates, fixed random seed",
        "test_policy": "publish 2025/2026 scores without examining their outcome metrics; final test remains Slice 17",
        "boundaries": "organic_pa_eligible plus legal runner conservation; IBB action handled separately; no causal or replacement superiority claims",
        "formal_model_replaced": False, "individual_ranking_allowed": False,
    }


def freeze() -> None:
    path = OUT / "protocol.json"
    value = protocol()
    if path.exists() and json.loads(path.read_text("utf-8")) != value:
        raise ValueError("Frozen baseline protocol differs. Preserve the prior experiment and use an explicit new version.")
    save_json(path, value)
    print("Baseline protocol frozen before reading 2024 outcomes for selection", flush=True)


def read_year(year: int, labels: bool) -> pd.DataFrame:
    with connection() as conn:
        conn.read_parquet(str(OUT / f"observed_features_{year}.parquet")).create_view("f")
        if not labels:
            return conn.execute("SELECT * EXCLUDE(observed_action) FROM f").fetchdf()
        conn.read_parquet(str(PREP / f"clean_labels_{year}.parquet")).create_view("l")
        return conn.execute("""SELECT f.* EXCLUDE(observed_action),l.observed_pa_result,l.runs_to_pa_end,
            l.outs_after,CASE WHEN l.outs_after=3 THEN 0 ELSE l.base_state_after END AS post_base,
            l.pa_end_at,l.research_pa_wpa,l.research_pa_re24,l.context_model_id
            FROM f JOIN l USING(decision_id) WHERE l.organic_pa_eligible""").fetchdf()


def label_code(frame: pd.DataFrame) -> np.ndarray:
    kinds = frame.observed_pa_result
    value = np.full(len(frame), 8, dtype=np.int64)
    for index, events in enumerate((('strikeout','strikeout_double_play'), ('walk',), ('hit_by_pitch',), ('home_run',), ('single',), ('double',), ('triple',))):
        value[kinds.isin(events)] = index
    other = ~kinds.isin([event for events in (("strikeout","strikeout_double_play"),("walk",),("hit_by_pitch",),("home_run",),("single",),("double",),("triple",)) for event in events])
    value[other & frame.outs_after.gt(frame.outs)] = 7
    return value


def legal_transition(outs: int, bases: int, runs: int, final_outs: int, final_bases: int) -> bool:
    if not (0 <= outs <= 2 and 0 <= bases <= 7 and 0 <= runs <= 4 and outs <= final_outs <= 3 and 0 <= final_bases <= 7):
        return False
    if final_outs == 3 and final_bases != 0:
        return False
    accounted = runs + final_outs - outs + int(final_bases).bit_count()
    available = int(bases).bit_count() + 1
    return accounted <= available and (final_outs == 3 or accounted == available)


def clean_model_frame(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    frame = frame.copy()
    frame["target"] = label_code(frame)
    valid = np.array([legal_transition(int(o), int(b), int(r), int(e), int(p)) for o,b,r,e,p in
                      frame[["outs","base_state","runs_to_pa_end","outs_after","post_base"]].itertuples(index=False,name=None)])
    report = {"before": len(frame), "runner_conservation_excluded": int((~valid).sum()), "after": int(valid.sum())}
    return frame.loc[valid].reset_index(drop=True), report


def design(frame: pd.DataFrame, level: str, pooling: int, prior: np.ndarray) -> pd.DataFrame:
    num, cat = LEVELS[level]
    result = frame[[name for name in num + cat if name not in ('pitcher_log_n','batter_log_n')]].copy()
    if level == "matchup" and pooling:
        for actor in ("pitcher", "batter"):
            n = np.where(frame[f"{actor}_ability_status"].eq("own_split"), frame[f"{actor}_own_split_n"], frame[f"{actor}_own_all_n"])
            for index, key in enumerate(OUTCOMES):
                rate = pd.to_numeric(frame[f"{actor}_{key}_rate"], errors="coerce")
                result[f"{actor}_{key}_rate"] = (rate.fillna(prior[index]) * n + pooling * prior[index]) / (n + pooling)
    for actor in ("pitcher", "batter"):
        key = f"{actor}_log_n"
        if key in num:
            result[key] = np.log1p(frame[f"{actor}_own_all_n"])
    for name in cat:
        result[name] = result[name].astype("string").fillna("unknown").astype(str)
    for name in num:
        result[name] = pd.to_numeric(result[name], errors="coerce").replace([np.inf,-np.inf],np.nan)
    return result


def make_model(level: str, alpha: float):
    num, cat = LEVELS[level]
    transform = ColumnTransformer([
        ("numeric", make_pipeline(SimpleImputer(strategy="median",add_indicator=True,keep_empty_features=True),StandardScaler()),num),
        ("categorical", OneHotEncoder(handle_unknown="ignore",sparse_output=False),cat),
    ])
    learner = LEARNER
    learner = {key: value for key,value in learner.items() if key not in ("loss","penalty")}
    return make_pipeline(transform, SGDClassifier(loss="log_loss",penalty="l2",alpha=alpha,**learner))


def probabilities(model, x: pd.DataFrame) -> np.ndarray:
    p = model.predict_proba(x)
    output = np.zeros((len(x),len(OUTCOMES)))
    output[:,model[-1].classes_.astype(int)] = p
    output = np.clip(output,1e-12,1)
    return output / output.sum(axis=1,keepdims=True)


def metrics(y: np.ndarray, p: np.ndarray) -> dict:
    picked = p.argmax(axis=1)
    confidence = p.max(axis=1)
    bins = []
    for low in np.arange(0,1,.1):
        mask = (confidence >= low) & (confidence < low+.1 if low<.9 else confidence<=1)
        if mask.any():
            bins.append({"lower": round(float(low),1), "n": int(mask.sum()), "mean_confidence": float(confidence[mask].mean()),
                         "accuracy": float((picked[mask]==y[mask]).mean())})
    classwise=[]
    for index,name in enumerate(OUTCOMES):
        labels=(y==index)
        reliability=[]
        for lower in np.arange(0,1,.1):
            mask=(p[:,index]>=lower)&(p[:,index]<lower+.1 if lower<.9 else p[:,index]<=1)
            if mask.any():
                reliability.append({'lower':round(float(lower),1),'n':int(mask.sum()),
                    'mean_probability':float(p[mask,index].mean()),'event_rate':float(labels[mask].mean())})
        classwise.append({'outcome':name,'events':int(labels.sum()),'brier':float(np.mean((p[:,index]-labels)**2)),
            'ece':float(sum(r['n']*abs(r['mean_probability']-r['event_rate']) for r in reliability)/len(y)),
            'bins':reliability})
    return {"n": len(y), "log_loss": float(log_loss(y,p,labels=np.arange(len(OUTCOMES)))),
            "brier": float(np.mean(np.sum(p*p,axis=1)-2*p[np.arange(len(y)),y]+1)),
            "accuracy": float((picked==y).mean()),
            "ece": float(sum(row['n']*abs(row['mean_confidence']-row['accuracy']) for row in bins)/len(y)),
            "calibration_bins": bins,"classwise_calibration":classwise}


def fit_transitions(frame: pd.DataFrame) -> dict:
    fine, parent = {}, {}
    for row in frame[["outs","base_state","extra","target","runs_to_pa_end","outs_after","post_base"]].itertuples(index=False,name=None):
        outs,bases,extra,target,runs,end,b = map(int,row)
        event = (target,runs,end,b)
        fine.setdefault((outs,bases,extra),Counter())[event] += 1
        parent.setdefault((outs,bases),Counter())[event] += 1
    tables = {}
    for outs,bases in parent:
        for extra in (0,1):
            detailed = fine.get((outs,bases,extra),Counter())
            full = parent[(outs,bases)]
            events = sorted(full)
            matrix = np.zeros((len(OUTCOMES),len(events)))
            supports = []
            for target in range(len(OUTCOMES)):
                n = sum(v for k,v in detailed.items() if k[0]==target)
                total = sum(v for k,v in full.items() if k[0]==target)
                supports.append(n)
                for j,event in enumerate(events):
                    if event[0]==target and total:
                        matrix[target,j] = (detailed[event]+20*full[event]/total)/(n+20)
            assert all(legal_transition(outs,bases,*event[1:]) for event in events)
            tables[(outs,bases,extra)] = {"events": events,"conditional": matrix,"n_by_target": supports}
    return tables


def transition_groups(frame: pd.DataFrame, tables: dict):
    """Condition legal runner transitions on walk-off rules before normalization."""
    work = frame.copy(deep=False)
    if {'half', 'inning', 'scheduled_innings', 'defense_lead'}.issubset(work.columns):
        walkoff = work.half.eq('bottom') & work.inning.ge(work.scheduled_innings)
        work = work.assign(walkoff_limit=np.where(walkoff, np.maximum(work.defense_lead + 1, 1), 5))
    else:
        work = work.assign(walkoff_limit=5)
    for key, group in work.groupby(['outs', 'base_state', 'extra', 'walkoff_limit']):
        table = tables[tuple(map(int, key[:3]))]
        conditional = table['conditional'].copy()
        events = np.asarray(table['events'])
        forbidden = (events[:, 0] != 3) & (events[:, 1] > key[3])
        conditional[:, forbidden] = 0
        total = conditional.sum(axis=1, keepdims=True)
        conditional = np.divide(conditional, total, out=np.zeros_like(conditional), where=total > 0)
        yield group, {**table, 'conditional': conditional}


def transition_scores(frame: pd.DataFrame, p: np.ndarray, tables: dict, observed: bool) -> dict:
    mean_runs,mean_outs = np.full(len(frame),np.nan),np.full(len(frame),np.nan)
    joint_ll,joint_brier = np.full(len(frame),np.nan),np.full(len(frame),np.nan)
    normalized = p.copy()
    unsupported = np.zeros(len(frame))
    for group,table in transition_groups(frame,tables):
        idx = group.index.to_numpy()
        supported = table["conditional"].sum(axis=1)>0
        unsupported[idx] = normalized[idx][:,~supported].sum(axis=1)
        normalized[np.ix_(idx,np.flatnonzero(~supported))] = 0
        normalized[idx] /= normalized[idx].sum(axis=1,keepdims=True)
        joint = normalized[idx] @ table["conditional"]
        assert np.max(np.abs(joint.sum(axis=1)-1))<1e-8
        event_array = np.array(table["events"])
        mean_runs[idx] = joint @ event_array[:,1]
        mean_outs[idx] = joint @ event_array[:,2]
        if observed:
            actual = frame.loc[idx,["target","runs_to_pa_end","outs_after","post_base"]].to_numpy(dtype=int)
            lookup = {event:j for j,event in enumerate(table['events'])}
            index = np.array([lookup.get(tuple(event),-1) for event in actual])
            target_p = np.zeros(len(idx))
            valid = index>=0
            target_p[valid] = joint[np.flatnonzero(valid),index[valid]]
            joint_ll[idx] = -np.log(np.maximum(target_p,1e-12))
            joint_brier[idx] = np.sum(joint*joint,axis=1)-2*target_p+1
    return {"p":normalized,"runs":mean_runs,"outs":mean_outs,"unsupported_mass":unsupported,"joint_ll":joint_ll,"joint_brier":joint_brier}


def expected_values(frame: pd.DataFrame, p: np.ndarray, tables: dict) -> tuple[np.ndarray,np.ndarray]:
    """Compute unique state value vectors once, then combine them with PA probabilities."""
    wpa,re24 = np.full(len(frame),np.nan),np.full(len(frame),np.nan)
    for model_id,indices in frame.groupby("context_model_id").groups.items():
        bundle = joblib.load(TEMPORAL / "models" / model_id.rsplit(":",1)[1] / "context.joblib")
        subset = frame.loc[indices]
        for group,table in transition_groups(subset,tables):
            events = np.asarray(table["events"])
            context = ['inning','half','scheduled_innings','defense_lead','outs','base_state','extra']
            unique = group[context+['research_home_we','research_re']].drop_duplicates(context).reset_index(drop=True)
            state = unique.loc[unique.index.repeat(len(events))].reset_index(drop=True)
            state['bottom'] = state.half.eq('bottom').astype(int)
            state['score_diff'] = np.where(state.bottom.eq(0),state.defense_lead,-state.defense_lead)
            state['balls'] = state['strikes'] = 0
            expanded = np.tile(events,(len(unique),1))
            post,terminal = post_state(state,expanded[:,1],expanded[:,2],expanded[:,3])
            future = we_predict(bundle,post)
            known = np.isfinite(terminal);future[known] = terminal[known]
            after_re = re_get(pd.DataFrame({'outs':expanded[:,2],'base_state':expanded[:,3],'extra':state.extra}),bundle['re'])
            re_end = np.array([row['mean'] if row else np.nan for row in after_re]);re_end[known] = 0
            idx = group.index.to_numpy()
            delta = np.where(state.bottom.eq(0),1,-1)*(future-state.research_home_we.to_numpy())
            re_delta = state.research_re.to_numpy()-expanded[:,1]-re_end
            positions = pd.MultiIndex.from_frame(unique[context]).get_indexer(pd.MultiIndex.from_frame(group[context]))
            wpa_vectors = delta.reshape(len(unique),len(events)) @ table['conditional'].T
            re_vectors = re_delta.reshape(len(unique),len(events)) @ table['conditional'].T
            wpa[idx] = np.sum(p[idx]*wpa_vectors[positions],axis=1)
            re24[idx] = np.sum(p[idx]*re_vectors[positions],axis=1)
    return wpa,re24


def cluster_difference(frame: pd.DataFrame, baseline: np.ndarray, challenger: np.ndarray) -> dict:
    delta = pd.DataFrame({"game_pk":frame.game_pk,"delta":challenger-baseline}).groupby("game_pk").delta.agg(['sum','count'])
    rng = np.random.default_rng(20261118)
    boot=[]
    for _ in range(100):
        take = rng.integers(0,len(delta),len(delta))
        boot.append(float(delta['sum'].to_numpy()[take].sum()/delta['count'].to_numpy()[take].sum()))
    return {"games":len(delta),"mean_challenger_minus_baseline":float((challenger-baseline).mean()),
            "game_cluster_95pct":np.quantile(boot,[.025,.975]).tolist(),"replicates":100}


def train() -> None:
    frozen = json.loads((OUT / "protocol.json").read_text("utf-8"))
    assert frozen == protocol(), "Frozen inputs changed"
    frames=[];flow=[]
    for year in (2021,2022,2023,2024):
        raw=read_year(year,True)
        frame,report = clean_model_frame(raw);flow.append({"year":year,**report});frames.append(frame)
        cohort=raw[['decision_id','game_pk','year']].copy()
        cohort['runner_conservation_eligible']=cohort.decision_id.isin(frame.decision_id)
        cohort.to_parquet(OUT/f'model_cohort_{year}.parquet',index=False,compression='zstd')
    development = pd.concat(frames[:3],ignore_index=True)
    validation = frames[3]
    assert development.pa_end_at.max()<pd.Timestamp('2024-01-01',tz='UTC').timestamp()
    prior = np.bincount(development.target,minlength=len(OUTCOMES))/len(development)
    weights = 1/development.groupby('game_pk').decision_id.transform('count').to_numpy()
    weights /= weights.mean()
    transitions = fit_transitions(development)
    joblib.dump(transitions,OUT/'transitions.joblib')
    candidates_meta=[];selected={};validation_predictions={}
    with threadpool_limits(limits=2):
        for level in LEVELS:
            best=None
            for pooling in ([0,20] if level=='matchup' else [0]):
                x = design(development,level,pooling,prior)
                v = design(validation,level,pooling,prior)
                for alpha in frozen['candidate_alphas']:
                    started=time.monotonic();print(f"fit {level}: alpha={alpha}, pooling={pooling}, n={len(x):,}",flush=True)
                    model = make_model(level,alpha)
                    with warnings.catch_warnings(record=True) as caught:
                        warnings.simplefilter('always',ConvergenceWarning)
                        model.fit(x,development.target,sgdclassifier__sample_weight=weights)
                    p = probabilities(model,v)
                    report = {"level":level,"alpha":alpha,"pooling":pooling,"iterations":int(model[-1].n_iter_),
                        "convergence_warning":any(isinstance(w.message,ConvergenceWarning) for w in caught),
                        "seconds":round(time.monotonic()-started,3),"validation":metrics(validation.target.to_numpy(),p)}
                    candidates_meta.append(report)
                    print(f"validation {level}: log_loss={report['validation']['log_loss']:.6f}, Brier={report['validation']['brier']:.6f}",flush=True)
                    better=best is None or report['validation']['log_loss']<best['validation']['log_loss']-.0001
                    tied=best is not None and abs(report['validation']['log_loss']-best['validation']['log_loss'])<=.0001
                    simpler=tied and (alpha,-pooling)>(best['alpha'],-best['pooling'])
                    if better or simpler:
                        best=report
                        joblib.dump({"model":model,"level":level,"pooling":pooling,"prior":prior},OUT/f'{level}.joblib')
                        validation_predictions[level]=p
            selected[level]=best
    report={"version":"decision_baseline_v1.2","flow":flow,"candidates":candidates_meta,"selected":selected,
            "promotion":"research_only","test_outcome_metrics_examined":False,"frozen_protocol_sha256":digest(OUT/'protocol.json')}
    baseline_p=validation_predictions['situation'];y=validation.target.to_numpy()
    best_level='situation'
    for level,p in validation_predictions.items():
        stats=transition_scores(validation,p,transitions,True)
        print(f"value reference {level}: computing unique state expectations",flush=True)
        wpa,re24=expected_values(validation,stats['p'],transitions)
        finite_wpa=np.isfinite(wpa)&np.isfinite(validation.research_pa_wpa)
        finite_re=np.isfinite(re24)&np.isfinite(validation.research_pa_re24)
        selected[level]['transitions']={"joint_log_loss":float(np.mean(stats['joint_ll'])),"joint_brier":float(np.mean(stats['joint_brier'])),
            "runs_rmse":float(np.sqrt(np.mean((stats['runs']-validation.runs_to_pa_end)**2))),
            "unsupported_category_mass_mean":float(stats['unsupported_mass'].mean()),
            "wpa_n":int(finite_wpa.sum()),"wpa_rmse":float(np.sqrt(np.mean((wpa[finite_wpa]-validation.research_pa_wpa[finite_wpa])**2))),
            "re24_n":int(finite_re.sum()),"re24_rmse":float(np.sqrt(np.mean((re24[finite_re]-validation.research_pa_re24[finite_re])**2)))}
        selected[level]['cluster_log_loss_delta']=cluster_difference(validation,-np.log(baseline_p[np.arange(len(y)),y]),-np.log(p[np.arange(len(y)),y]))
        if selected[level]['validation']['log_loss']<selected[best_level]['validation']['log_loss'] and selected[level]['validation']['brier']<selected[best_level]['validation']['brier']:
            best_level=level
        out=validation[['decision_id','game_pk','year']].copy()
        for i,key in enumerate(OUTCOMES):out[f'p_{key}']=p[:,i]
        out['expected_runs']=stats['runs'];out['expected_wpa']=wpa;out['expected_re24']=re24
        out['unsupported_category_mass']=stats['unsupported_mass']
        out.to_parquet(OUT/f'validation_2024_{level}.parquet',index=False,compression='zstd')
    report['retained_baseline']=best_level
    save_json(OUT/'validation.json',report)
    print(f"Frozen retained baseline: {best_level}",flush=True)


def score(year: int) -> None:
    frame=read_year(year,False)
    # Only predecision features are loaded for 2025 and 2026; outcome metrics stay closed.
    frame['context_model_id'] = None
    for fold in FOLDS:
        start=pd.Timestamp(fold['score_start'],tz='UTC').timestamp()
        end=pd.Timestamp(fold['score_end'],tz='UTC').timestamp()
        mask=frame.decision_at.between(start,end,inclusive='left') & frame.research_home_we.notna()
        frame.loc[mask,'context_model_id']='decision_temporal_research_v1:context:'+fold['id']
    tables=joblib.load(OUT/'transitions.joblib')
    for level in LEVELS:
        bundle=joblib.load(OUT/f'{level}.joblib')
        p=probabilities(bundle['model'],design(frame,level,bundle['pooling'],bundle['prior']))
        out=frame[['decision_id','game_pk','year']].copy()
        for i,key in enumerate(OUTCOMES):out[f'p_{key}']=p[:,i]
        joint=transition_scores(frame,p,tables,False)
        wpa,re24=expected_values(frame,joint['p'],tables)
        out['expected_runs']=joint['runs'];out['expected_wpa']=wpa;out['expected_re24']=re24
        out['unsupported_category_mass']=joint['unsupported_mass']
        print(f'{year}: {level} outcome and legal transition scores ready',flush=True)
        assert np.max(np.abs(p.sum(axis=1)-1))<1e-9
        out.to_parquet(OUT/f'predictions_{year}_{level}.parquet',index=False,compression='zstd')
    save_json(OUT/f'score_{year}.json',{"year":year,"rows":len(frame),"levels":list(LEVELS),"outcome_metrics_examined":False})
    print(f"{year}: three frozen baseline predictions saved, {len(frame):,} rows",flush=True)


def finalize() -> None:
    validation=json.loads((OUT/'validation.json').read_text('utf-8'))
    years=[]
    for year in YEARS:
        report=json.loads((OUT/f'candidates_{year}.json').read_text('utf-8'))
        if 'field_coverage' not in report:
            with connection() as conn:
                conn.read_parquet(str(OUT/f'option_features_{year}.parquet')).create_view('o')
                names=[row[0] for row in conn.execute('DESCRIBE o').fetchall()]
                report['field_coverage']=records(conn,'SELECT is_current,option_role,count(*) AS denominator,'+
                    ','.join(f'count({name}) AS {name}_present' for name in names)+' FROM o GROUP BY ALL ORDER BY ALL')
            save_json(OUT/f'candidates_{year}.json',report)
        years.append(report)
    source={"version":"decision_baseline_v1.2","years":years}
    save_json(ROOT/'data/sample/petehub_pitcher_decision_slice12_5_v1.json',source)
    save_json(ROOT/'data/sample/petehub_pitcher_decision_slice12_6_v1.json',json.loads((OUT/'protocol.json').read_text('utf-8')))
    save_json(ROOT/'data/sample/petehub_pitcher_decision_slice12_7_v1.json',validation)
    files=[{"path":path.name,"bytes":path.stat().st_size,"sha256":digest(path)} for path in sorted(OUT.glob('*'))
           if path.is_file() and path.name!='manifest.json' and '.tmp' not in path.name]
    save_json(OUT/'manifest.json',{"version":"decision_baseline_v1.2","files":files,"protocol_sha256":digest(OUT/'protocol.json')})
    print(f"Published 12.5–12.7 evidence, {len(files)} artifact hashes",flush=True)


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=('candidates','freeze','train','score','finalize'))
    parser.add_argument('--year',type=int,choices=YEARS)
    args=parser.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    if args.stage=='candidates':
        for year in [args.year] if args.year else YEARS:candidates(year)
    elif args.stage=='freeze':freeze()
    elif args.stage=='train':train()
    elif args.stage=='score':
        for year in [args.year] if args.year else (2025,2026):score(year)
    else:finalize()


if __name__=='__main__':
    main()
