from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import duckdb
import pandas as pd

from app.core.config import settings
from app.repositories.pitch_repository import get_season_duckdb_path, resolve_pitch_table
from app.services.game_line_service import fetch_json, load_pitcher_game_lines


MLB_STATS_URL = "https://statsapi.mlb.com/api/v1/stats"
DASHBOARD_COLUMNS = [
    "Season", "Name", "Team", "W", "L", "SV", "G", "GS", "IP", "K/9", "BB/9", "HR/9",
    "BABIP", "LOB%", "GB%", "HR/FB", "vFA (pi)", "ERA", "xERA", "FIP", "xFIP", "WAR",
    "NameASCII", "PlayerId", "MLBAMID",
]
BR_COLUMNS = [
    "Rk", "Name", "Age", "Tm", "IP", "G", "GS", "Wgs", "Lgs", "ND", "Wchp", "Ltuf",
    "Wtm", "Ltm", "tmW-L%", "Wlst", "Lsv", "CG", "SHO", "QS", "QS%", "GmScA", "Best",
    "Wrst", "BQR", "BQS", "sDR", "lDR", "RS/GS", "RS/IP", "IP/GS", "Pit/GS", "<80",
    "80-99", "100-119", ">=120", "Max", "Name-additional",
]


def refresh_starter_reference_data(year: int = 2026, data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    official = fetch_official_pitching_stats(int(year))
    if official.empty:
        raise RuntimeError(f"MLB Stats API returned no pitching rows for {year}.")

    pitches = load_starter_source_pitches(int(year), root)
    lines = load_pitcher_game_lines(int(year), root)
    dashboard = build_starter_dashboard(int(year), official, pitches, lines, root)
    starter_br = build_starter_br(int(year), official, pitches, lines)
    if dashboard.empty or starter_br.empty:
        raise RuntimeError(f"Starter reference rebuild produced no rows for {year}.")

    starter_dir = root / "Starter"
    starter_dir.mkdir(parents=True, exist_ok=True)
    yearly_dashboard_path = starter_dir / f"{int(year)}_starter_dashboard.csv"
    br_path = starter_dir / f"{int(year)}_starter_BR.csv"
    combined_path = starter_dir / "2021_2026_starter_dashboard.csv"

    _write_csv_atomic(dashboard, yearly_dashboard_path)
    _write_csv_atomic(starter_br, br_path)

    historical = pd.read_csv(combined_path, low_memory=False) if combined_path.exists() else pd.DataFrame()
    if not historical.empty and "Season" in historical.columns:
        historical = historical[pd.to_numeric(historical["Season"], errors="coerce").ne(int(year))]
    combined = pd.concat([historical, dashboard], ignore_index=True, sort=False)
    if "Season" in combined.columns:
        combined["_ip_sort"] = pd.to_numeric(combined.get("IP"), errors="coerce")
        combined = combined.sort_values(["Season", "GS", "_ip_sort"], ascending=[True, False, False]).drop(columns="_ip_sort")
    _write_csv_atomic(combined, combined_path)

    return {
        "year": int(year),
        "dashboard_rows": int(len(dashboard)),
        "starter_rows": int(len(starter_br)),
        "latest_pitch_date": str(pd.to_datetime(pitches["game_date"]).max().date()),
        "dashboard_path": str(yearly_dashboard_path),
        "br_path": str(br_path),
        "combined_path": str(combined_path),
    }


def fetch_official_pitching_stats(year: int) -> pd.DataFrame:
    params = {
        "stats": "season", "group": "pitching", "season": int(year), "sportIds": 1,
        "playerPool": "ALL", "limit": 5000, "hydrate": "team",
    }
    payload = fetch_json(f"{MLB_STATS_URL}?{urlencode(params)}", timeout=60)
    splits = ((payload.get("stats") or [{}])[0].get("splits") or [])
    rows: list[dict[str, Any]] = []
    for split in splits:
        stat = split.get("stat") or {}
        player = split.get("player") or {}
        team = split.get("team") or {}
        rows.append({
            "MLBAMID": player.get("id"),
            "Name": player.get("fullName"),
            "Team": team.get("abbreviation"),
            "Age": stat.get("age"),
            "W": stat.get("wins"),
            "L": stat.get("losses"),
            "SV": stat.get("saves"),
            "G": stat.get("gamesPlayed"),
            "GS": stat.get("gamesStarted"),
            "IP": stat.get("inningsPitched"),
            "K/9": stat.get("strikeoutsPer9Inn"),
            "BB/9": stat.get("walksPer9Inn"),
            "HR/9": stat.get("homeRunsPer9"),
            "ERA": stat.get("era"),
            "CG": stat.get("completeGames"),
            "SHO": stat.get("shutouts"),
        })
    frame = pd.DataFrame(rows)
    for column in ["MLBAMID", "Age", "W", "L", "SV", "G", "GS", "CG", "SHO"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    for column in ["IP", "K/9", "BB/9", "HR/9", "ERA"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.dropna(subset=["MLBAMID", "Name"]).drop_duplicates("MLBAMID", keep="last")


def load_starter_source_pitches(year: int, data_dir: Path) -> pd.DataFrame:
    db_path = get_season_duckdb_path(year, data_dir)
    if not db_path.exists():
        raise FileNotFoundError(f"Missing season pitch database: {db_path}")
    with duckdb.connect(str(db_path), read_only=True) as connection:
        table = resolve_pitch_table({row[0] for row in connection.execute("SHOW TABLES").fetchall()})
        if not table:
            raise RuntimeError(f"No pitch table found in {db_path}")
        return connection.execute(
            f"""
            SELECT game_pk, game_date, pitcher, player_name, pitcher_team, home_team, away_team,
                   inning, inning_topbot, at_bat_number, pitch_number, pitch_type, release_speed,
                   events, bb_type, post_home_score, post_away_score
            FROM {table}
            WHERE game_type = 'R' AND pitcher IS NOT NULL
            """
        ).fetchdf()


def build_starter_dashboard(
    year: int,
    official: pd.DataFrame,
    pitches: pd.DataFrame,
    lines: pd.DataFrame,
    data_dir: Path,
) -> pd.DataFrame:
    ordered = pitches.sort_values(["game_date", "game_pk", "inning", "at_bat_number", "pitch_number"])
    starter_ids = set(
        pd.to_numeric(
            ordered.drop_duplicates(["game_pk", "pitcher_team"], keep="first")["pitcher"], errors="coerce"
        ).dropna().astype(int)
    )
    starters = official[pd.to_numeric(official["MLBAMID"], errors="coerce").isin(starter_ids)].copy()
    previous_path = data_dir / "Starter" / "2021_2026_starter_dashboard.csv"
    previous = pd.read_csv(previous_path, low_memory=False) if previous_path.exists() else pd.DataFrame()
    id_columns = [column for column in ["MLBAMID", "PlayerId"] if column in previous]
    if len(id_columns) == 2:
        id_lookup = previous[id_columns].dropna(subset=["MLBAMID"]).drop_duplicates("MLBAMID", keep="last")
        starters = starters.merge(id_lookup, on="MLBAMID", how="left")
    else:
        starters["PlayerId"] = pd.NA

    advanced = _local_pitcher_rates(pitches)
    starters = starters.merge(advanced, on="MLBAMID", how="left")
    local_lines = lines.copy()
    local_lines["MLBAMID"] = pd.to_numeric(local_lines.get("pitcher_id"), errors="coerce")
    local_lines["outs"] = local_lines.get("ip", pd.Series(index=local_lines.index, dtype=object)).map(_outs_from_ip)
    for column in ["earned_runs", "walks", "strikeouts"]:
        local_lines[column] = pd.to_numeric(local_lines.get(column), errors="coerce").fillna(0)
    local_totals = local_lines.groupby("MLBAMID").agg(
        local_g=("game_pk", "nunique"), local_outs=("outs", "sum"), local_er=("earned_runs", "sum"),
        local_bb=("walks", "sum"), local_k=("strikeouts", "sum"),
    ).reset_index()
    start_counts = (
        ordered.drop_duplicates(["game_pk", "pitcher_team"], keep="first")
        .assign(MLBAMID=lambda frame: pd.to_numeric(frame["pitcher"], errors="coerce"))
        .groupby("MLBAMID")["game_pk"].nunique().rename("local_gs").reset_index()
    )
    starters = starters.merge(local_totals, on="MLBAMID", how="left").merge(start_counts, on="MLBAMID", how="left")
    innings = pd.to_numeric(starters["local_outs"], errors="coerce") / 3
    starters["G"] = starters["local_g"]
    starters["GS"] = starters["local_gs"]
    starters["IP"] = starters["local_outs"].fillna(0).astype(int).map(_baseball_innings)
    starters["ERA"] = 9 * starters["local_er"] / innings.where(innings.gt(0))
    starters["K/9"] = 9 * starters["local_k"] / innings.where(innings.gt(0))
    starters["BB/9"] = 9 * starters["local_bb"] / innings.where(innings.gt(0))
    starters["HR/9"] = 9 * starters["local_hr"] / innings.where(innings.gt(0))
    estimators_path = data_dir / f"{int(year)}_pitching_estimators.csv"
    if estimators_path.exists():
        estimators = pd.read_csv(estimators_path, low_memory=False).rename(
            columns={"player_id": "MLBAMID", "fip": "FIP", "xfip": "xFIP"}
        )
        starters = starters.merge(estimators[["MLBAMID", "FIP", "xFIP"]], on="MLBAMID", how="left")
    else:
        starters["FIP"] = pd.NA
        starters["xFIP"] = pd.NA
    xera_path = data_dir / f"{int(year)}_pitcher_comparison_with_est_xera.csv"
    if xera_path.exists():
        xera = pd.read_csv(xera_path, low_memory=False).rename(columns={"player_id": "MLBAMID", "est_xERA": "xERA"})
        starters = starters.merge(xera[["MLBAMID", "xERA"]], on="MLBAMID", how="left")
    else:
        starters["xERA"] = pd.NA

    starters["Season"] = int(year)
    starters["NameASCII"] = starters["Name"]
    starters["LOB%"] = pd.NA
    starters["WAR"] = pd.NA
    for column in DASHBOARD_COLUMNS:
        if column not in starters:
            starters[column] = pd.NA
    starters["_ip_sort"] = pd.to_numeric(starters["local_outs"], errors="coerce")
    return starters[DASHBOARD_COLUMNS + ["_ip_sort"]].sort_values(
        ["GS", "_ip_sort"], ascending=[False, False]
    ).drop(columns="_ip_sort").reset_index(drop=True)


def build_starter_br(year: int, official: pd.DataFrame, pitches: pd.DataFrame, lines: pd.DataFrame) -> pd.DataFrame:
    if pitches.empty or lines.empty:
        return pd.DataFrame(columns=BR_COLUMNS)
    ordered = pitches.sort_values(["game_date", "game_pk", "inning", "at_bat_number", "pitch_number"])
    starts = ordered.drop_duplicates(["game_pk", "pitcher_team"], keep="first")[
        ["game_pk", "pitcher", "pitcher_team"]
    ].rename(columns={"pitcher": "pitcher_id", "pitcher_team": "Tm"})
    working = lines.copy()
    working["game_pk"] = pd.to_numeric(working["game_pk"], errors="coerce")
    working["pitcher_id"] = pd.to_numeric(working["pitcher_id"], errors="coerce")
    starts["game_pk"] = pd.to_numeric(starts["game_pk"], errors="coerce")
    starts["pitcher_id"] = pd.to_numeric(starts["pitcher_id"], errors="coerce")
    start_lines = starts.merge(working, on=["game_pk", "pitcher_id"], how="inner", suffixes=("", "_line"))
    if start_lines.empty:
        return pd.DataFrame(columns=BR_COLUMNS)
    start_lines["outs"] = start_lines["ip"].map(_outs_from_ip)
    for column in ["hits", "runs", "earned_runs", "walks", "strikeouts", "pitches"]:
        start_lines[column] = pd.to_numeric(start_lines[column], errors="coerce").fillna(0)
    start_lines["quality_start"] = start_lines["outs"].ge(18) & start_lines["earned_runs"].le(3)
    start_lines["game_score"] = (
        50 + start_lines["outs"] + (start_lines["outs"] - 12).clip(lower=0)
        + start_lines["strikeouts"] - 2 * start_lines["hits"] - 4 * start_lines["earned_runs"]
        - 2 * (start_lines["runs"] - start_lines["earned_runs"]).clip(lower=0) - start_lines["walks"]
    )

    final_scores = ordered.drop_duplicates("game_pk", keep="last").set_index("game_pk")
    start_lines["team_runs"] = start_lines.apply(
        lambda row: _team_final_score(row, final_scores), axis=1
    )
    official_lookup = official.set_index("MLBAMID")
    rows: list[dict[str, Any]] = []
    for pitcher_id, group in start_lines.groupby("pitcher_id", sort=False):
        player = official_lookup.loc[int(pitcher_id)] if int(pitcher_id) in official_lookup.index else pd.Series(dtype=object)
        outs = int(group["outs"].sum())
        innings = outs / 3
        starts_count = int(len(group))
        pitch_counts = group["pitches"]
        row = {
            "Name": player.get("Name") or group["pitcher_name"].dropna().iloc[-1],
            "Age": player.get("Age"), "Tm": player.get("Team") or group["Tm"].iloc[-1],
            "IP": _baseball_innings(outs), "G": player.get("G", starts_count), "GS": starts_count,
            "Wgs": player.get("W"), "Lgs": player.get("L"), "CG": player.get("CG"), "SHO": player.get("SHO"),
            "QS": int(group["quality_start"].sum()),
            "QS%": round(float(group["quality_start"].mean() * 100), 1),
            "GmScA": round(float(group["game_score"].mean()), 1),
            "Best": int(group["game_score"].max()), "Wrst": int(group["game_score"].min()),
            "RS/GS": round(float(group["team_runs"].mean()), 1),
            "RS/IP": round(float(group["team_runs"].sum() * 9 / innings), 1) if innings else None,
            "IP/GS": round(float(innings / starts_count), 1), "Pit/GS": round(float(pitch_counts.mean())),
            "<80": int(pitch_counts.lt(80).sum()), "80-99": int(pitch_counts.between(80, 99).sum()),
            "100-119": int(pitch_counts.between(100, 119).sum()), ">=120": int(pitch_counts.ge(120).sum()),
            "Max": int(pitch_counts.max()), "Name-additional": pd.NA,
        }
        rows.append(row)
    result = pd.DataFrame(rows).sort_values(["GS", "IP"], ascending=[False, False]).reset_index(drop=True)
    result.insert(0, "Rk", range(1, len(result) + 1))
    for column in BR_COLUMNS:
        if column not in result:
            result[column] = pd.NA
    return result[BR_COLUMNS]


def _local_pitcher_rates(pitches: pd.DataFrame) -> pd.DataFrame:
    working = pitches.copy()
    working["MLBAMID"] = pd.to_numeric(working["pitcher"], errors="coerce")
    terminal = working[working["events"].notna()].copy()
    terminal["is_hit"] = terminal["events"].isin({"single", "double", "triple", "home_run"})
    terminal["is_hr"] = terminal["events"].eq("home_run")
    terminal["is_k"] = terminal["events"].isin({"strikeout", "strikeout_double_play"})
    terminal["is_sf"] = terminal["events"].eq("sac_fly")
    terminal["is_ab"] = ~terminal["events"].isin({"walk", "intent_walk", "hit_by_pitch", "sac_fly", "sac_bunt", "catcher_interf"})
    totals = terminal.groupby("MLBAMID").agg(hits=("is_hit", "sum"), hr=("is_hr", "sum"), k=("is_k", "sum"), sf=("is_sf", "sum"), ab=("is_ab", "sum"))
    denominator = totals["ab"] - totals["k"] - totals["hr"] + totals["sf"]
    totals["BABIP"] = (totals["hits"] - totals["hr"]) / denominator.where(denominator.gt(0))
    batted = terminal[terminal["bb_type"].notna()].copy()
    batted["gb"] = batted["bb_type"].eq("ground_ball")
    batted["fb"] = batted["bb_type"].eq("fly_ball")
    batted_rates = batted.groupby("MLBAMID").agg(bbe=("bb_type", "size"), gb=("gb", "sum"), fb=("fb", "sum"), hr=("is_hr", "sum"))
    batted_rates["GB%"] = batted_rates["gb"] / batted_rates["bbe"].where(batted_rates["bbe"].gt(0))
    batted_rates["HR/FB"] = batted_rates["hr"] / batted_rates["fb"].where(batted_rates["fb"].gt(0))
    fastballs = working[working["pitch_type"].isin({"FF", "FA"})].groupby("MLBAMID")["release_speed"].mean().rename("vFA (pi)")
    return totals[["BABIP", "hr"]].rename(columns={"hr": "local_hr"}).join(
        batted_rates[["GB%", "HR/FB"]], how="outer"
    ).join(fastballs, how="outer").reset_index()


def _outs_from_ip(value: Any) -> int:
    text = str(value or "0").strip()
    if "." not in text:
        return int(float(text)) * 3
    innings, partial = text.split(".", 1)
    return int(innings or 0) * 3 + min(2, max(0, int(partial[:1] or 0)))


def _baseball_innings(outs: int) -> str:
    return f"{int(outs) // 3}.{int(outs) % 3}"


def _team_final_score(row: pd.Series, scores: pd.DataFrame) -> float:
    if row["game_pk"] not in scores.index:
        return float("nan")
    game = scores.loc[row["game_pk"]]
    return float(game["post_home_score"] if row["Tm"] == game["home_team"] else game["post_away_score"])


def _write_csv_atomic(frame: pd.DataFrame, path: Path) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temporary, index=False)
    temporary.replace(path)
