from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from app.core.config import settings
from app.services.catcher_descriptive_xera_service import baseball_ip_to_outs


CONTRACT_VERSION = "catcher_descriptive_slice6_defense_v2"
DEFAULT_YEARS = (2021, 2022, 2023, 2024, 2025, 2026)
MIN_RANKING_OUTS = 900
DRS_SOURCE_FILENAME = "catcher_2021_2026_drs.csv"
FRV_SOURCE_FILENAME = "catcher_2021_2026_frv_statcast.csv"
TEAM_ABBREVIATION_MAP = {
    "ARI": "AZ",
    "CHW": "CWS",
    "KCR": "KC",
    "SDP": "SD",
    "SFG": "SF",
    "TBR": "TB",
    "WSN": "WSH",
}
DRS_REQUIRED_COLUMNS = (
    "Season",
    "Name",
    "Team",
    "Pos",
    "Inn",
    "rSZ",
    "rCERA",
    "rSB",
    "rGFP",
    "DRS",
    "FRM",
    "FRV",
    "Def",
    "NameASCII",
    "PlayerId",
    "MLBAMID",
)
FRV_REQUIRED_COLUMNS = (
    "Season",
    "Name",
    "Team",
    "Pos",
    "G",
    "GS",
    "Inn",
    "Throwing",
    "Blocking",
    "Framing",
    "Inf DP",
    "FRV",
    "NameASCII",
    "PlayerId",
    "MLBAMID",
)
DRS_DEFENSE_COLUMNS = ("DRS", "rSZ", "rCERA", "rSB", "rGFP", "FRM", "FRV", "Def")
FRV_DEFENSE_COLUMNS = ("Throwing", "Blocking", "Framing", "FRV")
UNAVAILABLE_SOURCE_FIELDS = (
    "rGDP",
    "rARM",
    "rPM",
    "rTS",
    "ARM",
    "DPR",
    "RngR",
    "ErrR",
    "UZR",
    "UZR/150",
    "OAA",
)


def slice6_root(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "research" / "catcher_descriptive" / "slice6_defense"


def defense_json_path(data_dir: Path | None = None) -> Path:
    return slice6_root(data_dir) / "catcher_descriptive_slice6_defense.json"


def defense_team_parquet_path(data_dir: Path | None = None) -> Path:
    return slice6_root(data_dir) / "catcher_team_defense_2021_2026.parquet"


def defense_catcher_parquet_path(data_dir: Path | None = None) -> Path:
    return slice6_root(data_dir) / "catcher_defense_2021_2026.parquet"


def canonical_team_ledger_path(data_dir: Path | None = None) -> Path:
    return (
        Path(data_dir or settings.data_dir)
        / "research"
        / "catcher_descriptive"
        / "slice1"
        / "catcher_season_team_ledger_2021_2026.parquet"
    )


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


def _number(value: float | int | None, digits: int = 6) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def _display_ip(outs: int) -> str:
    return f"{int(outs) // 3}.{int(outs) % 3}"


def _load_drs_source(source_path: Path, years: tuple[int, ...]) -> pd.DataFrame:
    frame = pd.read_csv(source_path, encoding="utf-8-sig")
    missing = sorted(set(DRS_REQUIRED_COLUMNS) - set(frame.columns))
    if missing:
        raise ValueError(f"DRS source is missing required columns: {missing}")
    frame = frame.loc[frame["Season"].astype(int).isin(years)].copy()
    found_years = tuple(sorted(frame["Season"].astype(int).unique()))
    if found_years != years:
        raise ValueError(f"DRS source seasons {found_years} do not match requested seasons {years}")
    if frame.duplicated(["Season", "MLBAMID", "Team"]).any():
        raise ValueError("Duplicate season-catcher-team keys in DRS source")
    if frame[list(DRS_REQUIRED_COLUMNS)].isna().any().any():
        nulls = frame[list(DRS_REQUIRED_COLUMNS)].isna().sum()
        raise ValueError(f"DRS source required fields contain nulls: {nulls[nulls.gt(0)].to_dict()}")
    if set(frame["Pos"].astype(str)) != {"C"}:
        raise ValueError("DRS source contains non-catcher positions")
    for column in ("Season", "MLBAMID", *DRS_DEFENSE_COLUMNS):
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    frame["season"] = frame["Season"].astype(int)
    frame["catcher_id"] = frame["MLBAMID"].astype(int)
    frame["team"] = frame["Team"].astype(str)
    frame["team_normalized"] = frame["team"].replace(TEAM_ABBREVIATION_MAP)
    frame["source_outs"] = frame["Inn"].map(baseball_ip_to_outs).astype(int)
    return frame


def _load_frv_source(source_path: Path, years: tuple[int, ...]) -> pd.DataFrame:
    frame = pd.read_csv(source_path, encoding="utf-8-sig")
    missing = sorted(set(FRV_REQUIRED_COLUMNS) - set(frame.columns))
    if missing:
        raise ValueError(f"Statcast FRV source is missing required columns: {missing}")
    frame = frame.loc[frame["Season"].astype(int).isin(years)].copy()
    found_years = tuple(sorted(frame["Season"].astype(int).unique()))
    if found_years != years:
        raise ValueError(f"Statcast FRV source seasons {found_years} do not match requested seasons {years}")
    if frame.duplicated(["Season", "MLBAMID", "Team"]).any():
        raise ValueError("Duplicate season-catcher-team keys in Statcast FRV source")
    if frame[list(FRV_REQUIRED_COLUMNS)].isna().any().any():
        nulls = frame[list(FRV_REQUIRED_COLUMNS)].isna().sum()
        raise ValueError(f"Statcast FRV source required fields contain nulls: {nulls[nulls.gt(0)].to_dict()}")
    if set(frame["Pos"].astype(str)) != {"C"}:
        raise ValueError("Statcast FRV source contains non-catcher positions")
    for column in ("Season", "MLBAMID", *FRV_DEFENSE_COLUMNS):
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    frame["season"] = frame["Season"].astype(int)
    frame["catcher_id"] = frame["MLBAMID"].astype(int)
    frame["team"] = frame["Team"].astype(str)
    frame["team_normalized"] = frame["team"].replace(TEAM_ABBREVIATION_MAP)
    frame["source_outs"] = frame["Inn"].map(baseball_ip_to_outs).astype(int)
    return frame


def _merge_defense_sources(drs: pd.DataFrame, frv: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    frv_fields = frv[
        [
            "season",
            "catcher_id",
            "team",
            "Name",
            "source_outs",
            "Throwing",
            "Blocking",
            "Framing",
            "FRV",
        ]
    ].rename(
        columns={
            "Name": "frv_source_name",
            "source_outs": "frv_source_outs",
            "Throwing": "throwing",
            "Blocking": "blocking",
            "Framing": "framing",
            "FRV": "statcast_frv",
        }
    )
    joined = drs.merge(
        frv_fields,
        on=["season", "catcher_id", "team"],
        how="outer",
        indicator=True,
        validate="one_to_one",
    )
    drs_only = int(joined["_merge"].eq("left_only").sum())
    frv_only = int(joined["_merge"].eq("right_only").sum())
    if drs_only or frv_only:
        raise ValueError(f"DRS and Statcast FRV keys differ: drs_only={drs_only}, frv_only={frv_only}")
    joined["source_outs_difference"] = joined["frv_source_outs"] - joined["source_outs"]
    joined["frv_difference"] = joined["statcast_frv"] - joined["FRV"]
    joined["frv_displayed_component_sum"] = joined[["throwing", "blocking", "framing"]].sum(axis=1)
    joined["frv_minus_displayed_component_sum"] = (
        joined["statcast_frv"] - joined["frv_displayed_component_sum"]
    )
    if joined["source_outs_difference"].ne(0).any():
        raise ValueError("DRS and Statcast FRV source innings do not match")
    if joined["frv_difference"].ne(0).any():
        raise ValueError("DRS export FRV and Statcast FRV export do not match")
    joined["FRV"] = joined["statcast_frv"]
    return joined.drop(columns=["_merge"]), {
        "drs_source_rows": int(len(drs)),
        "frv_source_rows": int(len(frv)),
        "matched_rows": int(len(joined)),
        "drs_only_rows": drs_only,
        "frv_only_rows": frv_only,
        "exact_innings_rows": int(joined["source_outs_difference"].eq(0).sum()),
        "exact_frv_rows": int(joined["frv_difference"].eq(0).sum()),
        "displayed_component_sum_exact_rows": int(joined["frv_minus_displayed_component_sum"].eq(0).sum()),
        "displayed_component_sum_differs_rows": int(joined["frv_minus_displayed_component_sum"].ne(0).sum()),
        "displayed_component_difference_min": _number(joined["frv_minus_displayed_component_sum"].min()),
        "displayed_component_difference_max": _number(joined["frv_minus_displayed_component_sum"].max()),
    }


def _load_ledger(path: Path, years: tuple[int, ...]) -> pd.DataFrame:
    ledger = pd.read_parquet(path)
    required = {
        "season",
        "pitching_team_id",
        "pitching_team_abbr",
        "catcher_id",
        "catcher_name",
        "outs",
        "display_ip",
    }
    missing = sorted(required - set(ledger.columns))
    if missing:
        raise ValueError(f"Canonical catcher-team ledger is missing columns: {missing}")
    ledger = ledger.loc[ledger["season"].astype(int).isin(years)].copy()
    ledger["season"] = ledger["season"].astype(int)
    ledger["catcher_id"] = ledger["catcher_id"].astype(int)
    if ledger.duplicated(["season", "catcher_id", "pitching_team_abbr"]).any():
        raise ValueError("Duplicate season-catcher-team keys in canonical ledger")
    return ledger


def _build_team_rows(source: pd.DataFrame, ledger: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    joined = source.merge(
        ledger,
        left_on=["season", "catcher_id", "team_normalized"],
        right_on=["season", "catcher_id", "pitching_team_abbr"],
        how="outer",
        indicator=True,
        validate="one_to_one",
    )
    source_only = int(joined["_merge"].eq("left_only").sum())
    ledger_only = int(joined["_merge"].eq("right_only").sum())
    if source_only or ledger_only:
        raise ValueError(
            f"DRS source does not fully cover the canonical catcher-team ledger: source_only={source_only}, ledger_only={ledger_only}"
        )
    joined["canonical_outs"] = joined["outs"].astype(int)
    joined["source_outs"] = joined["source_outs"].astype(int)
    joined["outs_difference"] = joined["source_outs"] - joined["canonical_outs"]
    joined["source_innings_status"] = joined["outs_difference"].eq(0).map(
        {True: "exact", False: "different_official_accounting"}
    )
    joined["drs_status"] = joined["canonical_outs"].ge(MIN_RANKING_OUTS).map(
        {True: "available", False: "limited"}
    )
    joined["frv_status"] = joined["canonical_outs"].ge(MIN_RANKING_OUTS).map(
        {True: "available", False: "limited"}
    )
    team_rows = pd.DataFrame(
        {
            "season": joined["season"].astype(int),
            "pitching_team_id": joined["pitching_team_id"].astype(int),
            "team": joined["pitching_team_abbr"].astype(str),
            "source_team": joined["team"].astype(str),
            "catcher_id": joined["catcher_id"].astype(int),
            "catcher_name": joined["catcher_name"].astype(str),
            "source_name": joined["Name"].astype(str),
            "source_innings": joined["Inn"].astype(float),
            "source_outs": joined["source_outs"].astype(int),
            "canonical_outs": joined["canonical_outs"].astype(int),
            "canonical_display_ip": joined["display_ip"].astype(str),
            "outs_difference": joined["outs_difference"].astype(int),
            "source_innings_status": joined["source_innings_status"].astype(str),
            "drs": joined["DRS"].astype(float),
            "rsz": joined["rSZ"].astype(float),
            "rcera": joined["rCERA"].astype(float),
            "rsb": joined["rSB"].astype(float),
            "rgfp": joined["rGFP"].astype(float),
            "frm": joined["FRM"].astype(float),
            "frv": joined["FRV"].astype(float),
            "throwing": joined["throwing"].astype(float),
            "blocking": joined["blocking"].astype(float),
            "framing": joined["framing"].astype(float),
            "defense_value": joined["Def"].astype(float),
            "drs_status": joined["drs_status"].astype(str),
            "frv_status": joined["frv_status"].astype(str),
            "contract_version": CONTRACT_VERSION,
        }
    )
    team_rows["displayed_drs_component_sum"] = team_rows[["rsz", "rcera", "rsb", "rgfp"]].sum(axis=1)
    team_rows["drs_minus_displayed_component_sum"] = team_rows["drs"] - team_rows["displayed_drs_component_sum"]
    team_rows["displayed_frv_component_sum"] = team_rows[["throwing", "blocking", "framing"]].sum(axis=1)
    team_rows["frv_minus_displayed_component_sum"] = team_rows["frv"] - team_rows["displayed_frv_component_sum"]
    exceptions = team_rows.loc[
        team_rows["outs_difference"].ne(0),
        [
            "season",
            "catcher_id",
            "catcher_name",
            "team",
            "source_innings",
            "canonical_display_ip",
            "source_outs",
            "canonical_outs",
            "outs_difference",
        ],
    ].to_dict("records")
    reconciliation = {
        "source_rows": int(len(source)),
        "canonical_team_rows": int(len(ledger)),
        "matched_rows": int(len(team_rows)),
        "source_only_rows": source_only,
        "canonical_only_rows": ledger_only,
        "exact_innings_rows": int(team_rows["outs_difference"].eq(0).sum()),
        "different_innings_rows": int(team_rows["outs_difference"].ne(0).sum()),
        "absolute_outs_difference": int(team_rows["outs_difference"].abs().sum()),
        "innings_exceptions": exceptions,
        "displayed_component_sum_differs_from_drs_rows": int(
            team_rows["drs_minus_displayed_component_sum"].ne(0).sum()
        ),
        "displayed_frv_component_sum_differs_rows": int(
            team_rows["frv_minus_displayed_component_sum"].ne(0).sum()
        ),
    }
    return team_rows, reconciliation


def _build_catcher_rows(team_rows: pd.DataFrame) -> pd.DataFrame:
    catcher = team_rows.groupby(["season", "catcher_id"], as_index=False).agg(
        catcher_name=("catcher_name", "first"),
        teams=("team", lambda values: ", ".join(sorted(set(values)))),
        team_count=("team", "nunique"),
        source_rows=("team", "size"),
        exact_innings_team_rows=("source_innings_status", lambda values: int((values == "exact").sum())),
        source_outs=("source_outs", "sum"),
        canonical_outs=("canonical_outs", "sum"),
        outs_difference=("outs_difference", "sum"),
        drs=("drs", "sum"),
        rsz=("rsz", "sum"),
        rcera=("rcera", "sum"),
        rsb=("rsb", "sum"),
        rgfp=("rgfp", "sum"),
        frm=("frm", "sum"),
        frv=("frv", "sum"),
        throwing=("throwing", "sum"),
        blocking=("blocking", "sum"),
        framing=("framing", "sum"),
        defense_value=("defense_value", "sum"),
        displayed_drs_component_sum=("displayed_drs_component_sum", "sum"),
        drs_minus_displayed_component_sum=("drs_minus_displayed_component_sum", "sum"),
        displayed_frv_component_sum=("displayed_frv_component_sum", "sum"),
        frv_minus_displayed_component_sum=("frv_minus_displayed_component_sum", "sum"),
    )
    catcher["display_ip"] = catcher["canonical_outs"].map(_display_ip)
    catcher["source_display_ip"] = catcher["source_outs"].map(_display_ip)
    catcher["source_innings_status"] = catcher["outs_difference"].eq(0).map(
        {True: "exact", False: "different_official_accounting"}
    )
    catcher["drs_status"] = catcher["canonical_outs"].ge(MIN_RANKING_OUTS).map(
        {True: "available", False: "limited"}
    )
    catcher["frv_status"] = catcher["canonical_outs"].ge(MIN_RANKING_OUTS).map(
        {True: "available", False: "limited"}
    )
    catcher["contract_version"] = CONTRACT_VERSION
    return catcher.sort_values(["season", "catcher_id"]).reset_index(drop=True)


def _correlation(left: pd.Series, right: pd.Series, method: str) -> float | None:
    if len(left) < 3 or left.nunique() < 2 or right.nunique() < 2:
        return None
    return _number(left.corr(right, method=method))


def _cross_year_diagnostics(catcher_rows: pd.DataFrame, years: tuple[int, ...]) -> dict[str, Any]:
    qualified = catcher_rows.loc[catcher_rows["canonical_outs"].ge(MIN_RANKING_OUTS)].copy()
    pairs: list[pd.DataFrame] = []
    for year in years:
        if year + 1 not in years:
            continue
        left = qualified.loc[qualified["season"].eq(year)]
        right = qualified.loc[qualified["season"].eq(year + 1)]
        pairs.append(left.merge(right, on="catcher_id", suffixes=("_from", "_to")))
    adjacent = pd.concat(pairs, ignore_index=True) if pairs else pd.DataFrame()
    metrics = {}
    for column in ("frv", "throwing", "blocking", "framing", "drs", "rsz", "rcera", "rsb", "rgfp"):
        metrics[column] = {
            "pearson": _correlation(adjacent[f"{column}_from"], adjacent[f"{column}_to"], "pearson")
            if not adjacent.empty
            else None,
            "spearman": _correlation(adjacent[f"{column}_from"], adjacent[f"{column}_to"], "spearman")
            if not adjacent.empty
            else None,
        }
    return {
        "population": "adjacent seasons with at least 900 canonical catcher outs in both seasons",
        "adjacent_pairs": int(len(adjacent)),
        "metrics": metrics,
        "interpretation": "Diagnostic only; persistence is not required to display the source metric and does not establish causal catcher value.",
    }


def _overlap_diagnostics(
    catcher_rows: pd.DataFrame,
    years: tuple[int, ...],
    data_dir: Path,
) -> dict[str, Any]:
    metric_rows: list[dict[str, Any]] = []
    metric_root = data_dir / "research" / "catcher_descriptive" / "slice23_preview"
    for year in years:
        path = metric_root / f"catcher_descriptive_metrics_{year}.json"
        if not path.exists():
            return {"status": "unavailable", "reason": f"Missing Slice 2–3 artifact: {path}"}
        metric_rows.extend(json.loads(path.read_text(encoding="utf-8")).get("rows", []))
    xera_path = data_dir / "research" / "catcher_descriptive" / "slice5_xera" / "catcher_xera_2021_2026.parquet"
    if not xera_path.exists():
        return {"status": "unavailable", "reason": f"Missing Slice 5 artifact: {xera_path}"}

    metrics = pd.DataFrame(metric_rows)
    required_metrics = {"season", "catcher_id", "c_save_run"}
    if not required_metrics.issubset(metrics.columns):
        return {"status": "unavailable", "reason": "Slice 2–3 artifact lacks cSaveRun join fields"}
    xera = pd.read_parquet(xera_path, columns=["season", "catcher_id", "x_runs_vs_mix"])
    qualified = catcher_rows.loc[
        catcher_rows["canonical_outs"].ge(MIN_RANKING_OUTS),
        ["season", "catcher_id", "frv", "drs"],
    ]
    joined = (
        qualified.merge(metrics[["season", "catcher_id", "c_save_run"]], on=["season", "catcher_id"])
        .merge(xera, on=["season", "catcher_id"])
    )
    return {
        "status": "available",
        "population": "catcher-seasons with at least 900 canonical catcher outs",
        "rows": int(len(joined)),
        "frv_vs_c_save_run": {
            "pearson": _correlation(joined["frv"], joined["c_save_run"], "pearson"),
            "spearman": _correlation(joined["frv"], joined["c_save_run"], "spearman"),
        },
        "frv_vs_x_runs_vs_mix": {
            "pearson": _correlation(joined["frv"], joined["x_runs_vs_mix"], "pearson"),
            "spearman": _correlation(joined["frv"], joined["x_runs_vs_mix"], "spearman"),
        },
        "drs_vs_c_save_run": {
            "pearson": _correlation(joined["drs"], joined["c_save_run"], "pearson"),
            "spearman": _correlation(joined["drs"], joined["c_save_run"], "spearman"),
        },
        "drs_vs_x_runs_vs_mix": {
            "pearson": _correlation(joined["drs"], joined["x_runs_vs_mix"], "pearson"),
            "spearman": _correlation(joined["drs"], joined["x_runs_vs_mix"], "spearman"),
        },
        "interpretation": "Overlap diagnostic only; these correlated axes are not added into a composite score.",
    }


def build_catcher_descriptive_slice6_defense(
    years: Iterable[int] = DEFAULT_YEARS,
    data_dir: Path | None = None,
    source_path: Path | None = None,
    frv_source_path: Path | None = None,
) -> dict[str, Any]:
    selected_years = tuple(sorted({int(year) for year in years}))
    if not selected_years:
        raise ValueError("At least one season is required")
    root = Path(data_dir or settings.data_dir)
    drs_source = Path(source_path or root / DRS_SOURCE_FILENAME)
    frv_source = Path(frv_source_path or root / FRV_SOURCE_FILENAME)
    ledger_path = canonical_team_ledger_path(root)
    if not drs_source.exists():
        raise FileNotFoundError(f"DRS source is unavailable: {drs_source}")
    if not frv_source.exists():
        raise FileNotFoundError(f"Statcast FRV source is unavailable: {frv_source}")
    if not ledger_path.exists():
        raise FileNotFoundError(f"Canonical catcher-team ledger is unavailable: {ledger_path}")

    drs_frame = _load_drs_source(drs_source, selected_years)
    frv_frame = _load_frv_source(frv_source, selected_years)
    source_frame, cross_source_reconciliation = _merge_defense_sources(drs_frame, frv_frame)
    ledger = _load_ledger(ledger_path, selected_years)
    team_rows, reconciliation = _build_team_rows(source_frame, ledger)
    catcher_rows = _build_catcher_rows(team_rows)
    cross_year = _cross_year_diagnostics(catcher_rows, selected_years)
    overlap = _overlap_diagnostics(catcher_rows, selected_years, root)
    source_field_coverage = {
        f"statcast.{column}": {
            "non_null_rows": int(frv_frame[column].notna().sum()),
            "null_rows": int(frv_frame[column].isna().sum()),
            "status": "available" if frv_frame[column].notna().all() else "unavailable",
        }
        for column in (*FRV_DEFENSE_COLUMNS, "Arm", "Range", "Inf DP", "1B Rec")
        if column in frv_frame.columns
    }
    source_field_coverage.update(
        {
            f"drs.{column}": {
                "non_null_rows": int(drs_frame[column].notna().sum()),
                "null_rows": int(drs_frame[column].isna().sum()),
                "status": "available" if drs_frame[column].notna().all() else "unavailable",
            }
            for column in (*DRS_DEFENSE_COLUMNS, *UNAVAILABLE_SOURCE_FIELDS)
            if column in drs_frame.columns
        }
    )
    release_gates = {
        "requested_seasons_present": sorted(frv_frame["season"].unique().tolist()) == list(selected_years),
        "frv_source_key_unique": not frv_frame.duplicated(["season", "catcher_id", "team"]).any(),
        "cross_source_key_coverage_100_pct": cross_source_reconciliation["drs_only_rows"] == 0
        and cross_source_reconciliation["frv_only_rows"] == 0,
        "cross_source_frv_exact": cross_source_reconciliation["exact_frv_rows"] == len(frv_frame),
        "canonical_team_key_coverage_100_pct": reconciliation["source_only_rows"] == 0
        and reconciliation["canonical_only_rows"] == 0,
        "required_frv_fields_complete": not frv_frame[list(FRV_DEFENSE_COLUMNS)].isna().any().any(),
        "canonical_outs_retained_as_denominator": True,
        "no_defense_adjustment_applied_to_existing_metrics": True,
        "park_factor_explicitly_deferred": True,
    }
    release_gate_passed = all(bool(value) for value in release_gates.values())

    _atomic_write_parquet(defense_team_parquet_path(root), team_rows)
    _atomic_write_parquet(defense_catcher_parquet_path(root), catcher_rows)
    row_records = []
    for row in catcher_rows.to_dict("records"):
        row_records.append(
            {
                key: (_number(value) if isinstance(value, float) else value)
                for key, value in row.items()
            }
        )
    payload = {
        "contract_version": CONTRACT_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if release_gate_passed else "failed",
        "release_gate_passed": release_gate_passed,
        "years": list(selected_years),
        "source_snapshot": {
            "path": str(frv_source),
            "sha256": _sha256(frv_source),
            "bytes": frv_source.stat().st_size,
            "last_modified_utc": datetime.fromtimestamp(frv_source.stat().st_mtime, timezone.utc).isoformat(),
            "source_name": "User-provided FanGraphs-style catcher fielding export carrying Statcast FRV and catcher components",
            "source_url": None,
            "provenance_status": "file_fingerprinted_source_url_not_embedded",
            "publication_rights_status": "internal_research_only_pending_public_redistribution_clearance",
            "grain": "season-team-catcher",
            "unique_key": ["Season", "Team", "MLBAMID"],
        },
        "comparison_source_snapshot": {
            "path": str(drs_source),
            "sha256": _sha256(drs_source),
            "bytes": drs_source.stat().st_size,
            "last_modified_utc": datetime.fromtimestamp(drs_source.stat().st_mtime, timezone.utc).isoformat(),
            "source_name": "User-provided FanGraphs-style catcher fielding export carrying Sports Info Solutions DRS",
            "source_url": None,
            "provenance_status": "file_fingerprinted_source_url_not_embedded",
            "publication_rights_status": "internal_research_only_pending_public_redistribution_clearance",
        },
        "row_counts": {
            "source_team_catcher_rows": int(len(source_frame)),
            "canonical_team_catcher_rows": int(len(team_rows)),
            "catcher_seasons": int(len(catcher_rows)),
            "ranking_eligible_catcher_seasons": int(catcher_rows["canonical_outs"].ge(MIN_RANKING_OUTS).sum()),
        },
        "source_field_coverage": source_field_coverage,
        "cross_source_reconciliation": cross_source_reconciliation,
        "reconciliation": reconciliation,
        "cross_year_diagnostics": cross_year,
        "overlap_diagnostics": overlap,
        "release_gates": release_gates,
        "definitions": {
            "frv": "Source Statcast Fielding Run Value in runs above the source-defined average for the full catcher season.",
            "throwing": "Statcast catcher throwing component in runs above the source-defined average.",
            "blocking": "Statcast catcher blocking component in runs above the source-defined average.",
            "framing": "Statcast catcher framing component in runs above the source-defined average.",
            "drs": "Comparison-only source Defensive Runs Saved above or below its source-defined average.",
            "rsz": "Sports Info Solutions Strike Zone Runs Saved component.",
            "rcera": "Sports Info Solutions catcher staff-handling component; displayed separately because it overlaps the c/t research question.",
            "rsb": "Sports Info Solutions stolen-base prevention component.",
            "rgfp": "Sports Info Solutions good-fielding-play component, including much of catcher blocking value.",
            "frm": "Comparison-only FanGraphs framing runs.",
        },
        "integration_policy": {
            "published_grain": "season-catcher; source team rows are summed for multi-team catchers",
            "rate_denominator": "canonical catcher outs; source Inn is audit-only",
            "leaderboard": "Statcast FRV, Throwing, Blocking and Framing are the primary separate defense axis",
            "drs": "retained in the artifact for source comparison but removed from the primary product display",
            "paired_duo": "unavailable because the source cannot allocate full-season FRV to pitcher-catcher pairs",
            "existing_metrics": "cERA, cRA9, cFIP, t metrics, cSaveRun, xERA, cxERA, txERA and x Runs vs Mix are unchanged",
            "composite_score": "not created; FRV already includes its catcher components and remains separate from observed pitching-result metrics",
            "park_factor": "deferred_by_user; no park adjustment is applied",
        },
        "rows": row_records,
        "warnings": [
            "FRV and DRS are source-provided runs-above-average estimates, not absolute runs prevented or causal catcher value.",
            "Throwing, Blocking and Framing are components of FRV and must not be added to FRV again.",
            "Displayed rounded Statcast components differ from source FRV by up to one run in some rows; the source FRV column remains authoritative.",
            "FRV is not added to cSaveRun or x Runs vs Mix; these remain separate descriptive axes.",
            "DRS and its components remain in the artifact only for source comparison and are not the primary product scale.",
            "Source Inn is retained for audit only. Canonical ledger outs remain the denominator, including the two documented 2024 Danny Jansen source-accounting exceptions.",
            "Park factor is intentionally deferred and no proxy adjustment is applied.",
            "The source files are fingerprinted but do not embed their download URLs or public redistribution rights.",
        ],
    }
    _atomic_write_json(defense_json_path(root), payload)
    return payload


def get_catcher_defense_rows(
    year: int,
    data_dir: Path | None = None,
) -> tuple[dict[int, dict[str, Any]], dict[str, Any] | None]:
    path = defense_json_path(data_dir)
    if not path.exists():
        return {}, None
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = {
        int(row["catcher_id"]): row
        for row in payload.get("rows", [])
        if int(row.get("season") or 0) == int(year)
    }
    return rows, payload
