from __future__ import annotations

import re
import unicodedata

import duckdb
import numpy as np
import pandas as pd

from app.api.schemas.common import PitcherLeaderboardRow, PitcherOption
from app.core.config import settings
from app.repositories.pitch_repository import (
    get_season_duckdb_path,
    load_pitcher_master_and_appearances,
    resolve_pitch_table,
)

PITCHER_POOL_COLUMNS = ["Name", "Team", "MLBAMID", "G", "GS", "GR", "IP", "GS_over_G", "RoleClass"]


def clean_name(value: object) -> str:
    return re.sub(r"[\*\#\+\s]+$", "", str(value).replace("\xa0", " ").strip()).strip()


def normalize_name(value: object) -> str:
    text = clean_name(value)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return " ".join(text.lower().split())


def normalize_role(role: str) -> str:
    return "RP" if str(role).upper() == "RP" else "SP"


def build_pitcher_pool(
    player_master: pd.DataFrame,
    appearance_stats: pd.DataFrame,
    year: int,
    role: str = "SP",
) -> pd.DataFrame:
    if player_master.empty:
        return pd.DataFrame(columns=PITCHER_POOL_COLUMNS)

    pitchers = player_master[
        player_master.get("roles", pd.Series(dtype="object")).astype(str).str.contains("pitcher", case=False, na=False)
    ].copy()
    if pitchers.empty:
        return pd.DataFrame(columns=PITCHER_POOL_COLUMNS)

    team_col = f"pitcher_teams_{year}" if f"pitcher_teams_{year}" in pitchers.columns else None
    if team_col is None and f"teams_{year}" in pitchers.columns:
        team_col = f"teams_{year}"

    pitchers["Name"] = pitchers["player_name"].astype(str).map(clean_name)
    pitchers["Team"] = pitchers[team_col].fillna("").astype(str).str.split(",").str[0].str.strip() if team_col else ""
    pitchers["MLBAMID"] = pd.to_numeric(pitchers["player_id"], errors="coerce").astype("Int64")

    if not appearance_stats.empty:
        appearances = appearance_stats.copy()
        appearances["player_id"] = pd.to_numeric(appearances["player_id"], errors="coerce").astype("Int64")
        pitchers = pitchers.merge(appearances, on="player_id", how="left")

    default_counts = pd.Series(0, index=pitchers.index)
    pitchers["G"] = pd.to_numeric(pitchers["G"] if "G" in pitchers.columns else default_counts, errors="coerce").fillna(0)
    pitchers["GS"] = pd.to_numeric(pitchers["GS"] if "GS" in pitchers.columns else default_counts, errors="coerce").fillna(0)
    pitchers["IP"] = pd.to_numeric(pitchers["IP"] if "IP" in pitchers.columns else default_counts, errors="coerce").fillna(0)
    gr_values = pd.to_numeric(pitchers["GR"] if "GR" in pitchers.columns else default_counts, errors="coerce")
    pitchers["GR"] = gr_values.fillna(pitchers["G"] - pitchers["GS"])

    game_lines = _load_pitcher_game_lines(year)
    if not game_lines.empty and {"pitcher_id", "ip"}.issubset(game_lines.columns):
        ip_lines = game_lines[["pitcher_id", "ip"]].copy()
        ip_lines["pitcher_id"] = pd.to_numeric(ip_lines["pitcher_id"], errors="coerce")
        ip_lines = ip_lines.dropna(subset=["pitcher_id"]).copy()
        ip_lines["pitcher_id"] = ip_lines["pitcher_id"].astype(int)
        ip_lines["outs"] = ip_lines["ip"].map(_outs_from_ip)
        ip_stats = ip_lines.groupby("pitcher_id", as_index=False).agg(outs=("outs", "sum"))
        ip_stats["IP_game_lines"] = ip_stats["outs"].map(_ip_from_outs)
        pitchers = pitchers.merge(
            ip_stats[["pitcher_id", "IP_game_lines"]].rename(columns={"pitcher_id": "player_id"}),
            on="player_id",
            how="left",
        )
        pitchers["IP"] = pd.to_numeric(pitchers["IP_game_lines"], errors="coerce").fillna(pitchers["IP"])
        pitchers = pitchers.drop(columns=["IP_game_lines"])

    pitchers["GS_over_G"] = np.where(pitchers["G"] > 0, pitchers["GS"] / pitchers["G"], np.nan)
    pitchers["RoleClass"] = np.where(pitchers["GS_over_G"] > 0.3, "SP", "RP")
    pitchers = pitchers[pitchers["RoleClass"] == normalize_role(role)].copy()
    pitchers = pitchers.dropna(subset=["Name", "Team", "MLBAMID"]).copy()
    pitchers["MLBAMID"] = pitchers["MLBAMID"].astype(int)
    pitchers["G"] = pitchers["G"].astype(int)
    pitchers["GS"] = pitchers["GS"].astype(int)
    pitchers["GR"] = pitchers["GR"].clip(lower=0).astype(int)
    pitchers["IP"] = pd.to_numeric(pitchers["IP"], errors="coerce").fillna(0)

    return (
        pitchers[PITCHER_POOL_COLUMNS]
        .sort_values(["Team", "Name", "MLBAMID"])
        .drop_duplicates(subset=["Name", "Team", "MLBAMID"])
        .reset_index(drop=True)
    )


def pitcher_pool_to_options(pool_df: pd.DataFrame) -> list[PitcherOption]:
    options: list[PitcherOption] = []
    for row in pool_df.to_dict(orient="records"):
        start_rate = row.get("GS_over_G")
        options.append(
            PitcherOption(
                value=int(row["MLBAMID"]),
                label=f"{row['Name']} ({row['Team']})",
                name=str(row["Name"]),
                team=str(row["Team"]),
                role=str(row["RoleClass"]),
                games=int(row.get("G", 0)),
                starts=int(row.get("GS", 0)),
                relief_games=int(row.get("GR", 0)),
                innings_pitched=float(row["IP"]) if pd.notna(row.get("IP")) else None,
                start_rate=float(start_rate) if pd.notna(start_rate) else None,
            )
        )
    return options


def list_pitcher_options(year: int, role: str = "SP") -> list[PitcherOption]:
    player_master, appearance_stats = load_pitcher_master_and_appearances(year=year, data_dir=settings.data_dir)
    pool_df = build_pitcher_pool(player_master, appearance_stats, year=year, role=role)
    return pitcher_pool_to_options(pool_df)


def _outs_from_ip(value: object) -> int:
    if pd.isna(value):
        return 0
    text = str(value).strip()
    if not text:
        return 0
    try:
        whole_text, _, frac_text = text.partition(".")
        whole = int(float(whole_text or 0))
        frac = int((frac_text or "0")[:1] or 0)
        return whole * 3 + min(max(frac, 0), 2)
    except (TypeError, ValueError):
        return 0


def _ip_from_outs(outs: int) -> float:
    innings, remainder = divmod(int(outs), 3)
    return round(innings + remainder / 10, 1)


def _calculate_game_score(row: pd.Series) -> float | None:
    outs = int(row.get("outs", 0) or 0)
    if outs <= 0:
        return None
    hits = int(row.get("hits", 0) or 0)
    runs = int(row.get("runs", 0) or 0)
    earned_runs = int(row.get("earned_runs", 0) or 0)
    walks = int(row.get("walks", 0) or 0)
    strikeouts = int(row.get("strikeouts", 0) or 0)
    unearned_runs = max(0, runs - earned_runs)
    completed_innings_after_fourth = max(0, (outs // 3) - 4)
    return float(
        50
        + outs
        + completed_innings_after_fourth * 2
        + strikeouts
        - hits * 2
        - earned_runs * 4
        - unearned_runs * 2
        - walks
    )


def _starter_line_mask(lines: pd.DataFrame) -> pd.Series:
    if lines.empty or not {"game_pk", "team", "outs"}.issubset(lines.columns):
        return pd.Series(False, index=lines.index)
    sorted_lines = lines.sort_values(
        ["game_pk", "team", "outs", "pitches", "pitcher_id"],
        ascending=[True, True, False, False, True],
    )
    starter_indices = sorted_lines.drop_duplicates(subset=["game_pk", "team"], keep="first").index
    return pd.Series(lines.index.isin(starter_indices), index=lines.index)


def _build_all_role_pool(player_master: pd.DataFrame, appearance_stats: pd.DataFrame, year: int) -> pd.DataFrame:
    pools = [
        build_pitcher_pool(player_master, appearance_stats, year=year, role="SP"),
        build_pitcher_pool(player_master, appearance_stats, year=year, role="RP"),
    ]
    combined = pd.concat([pool for pool in pools if not pool.empty], ignore_index=True)
    if combined.empty:
        return pd.DataFrame(columns=PITCHER_POOL_COLUMNS)
    return (
        combined.sort_values(["RoleClass", "Team", "Name", "MLBAMID"])
        .drop_duplicates(subset=["MLBAMID"], keep="first")
        .reset_index(drop=True)
    )


def _load_pitcher_game_lines(year: int) -> pd.DataFrame:
    csv_path = settings.data_dir / f"MLB{int(year)}" / f"mlb_{int(year)}_pitcher_game_lines.csv.gz"
    if csv_path.exists():
        return pd.read_csv(csv_path)

    db_path = get_season_duckdb_path(year, settings.data_dir)
    if not db_path.exists():
        return pd.DataFrame()
    with duckdb.connect(str(db_path), read_only=True) as conn:
        tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
        if "pitcher_game_lines" not in tables:
            return pd.DataFrame()
        return conn.execute("SELECT * FROM pitcher_game_lines").fetchdf()


def _load_pitcher_home_runs(year: int) -> pd.DataFrame:
    db_path = get_season_duckdb_path(year, settings.data_dir)
    if not db_path.exists():
        return pd.DataFrame(columns=["pitcher_id", "home_runs"])

    try:
        with duckdb.connect(str(db_path), read_only=True) as conn:
            tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
            source_table = resolve_pitch_table(tables)
            if not source_table:
                return pd.DataFrame(columns=["pitcher_id", "home_runs"])
            columns = {row[1] for row in conn.execute(f"PRAGMA table_info('{source_table}')").fetchall()}
            if not {"pitcher", "events"}.issubset(columns):
                return pd.DataFrame(columns=["pitcher_id", "home_runs"])
            return conn.execute(
                f"""
                SELECT pitcher AS pitcher_id, COUNT(*) AS home_runs
                FROM {source_table}
                WHERE game_type = 'R'
                  AND pitcher IS NOT NULL
                  AND events = 'home_run'
                GROUP BY 1
                """
            ).fetchdf()
    except duckdb.Error:
        return pd.DataFrame(columns=["pitcher_id", "home_runs"])


def list_pitcher_leaderboard(year: int, role: str = "All", team: str = "All") -> list[PitcherLeaderboardRow]:
    player_master, appearance_stats = load_pitcher_master_and_appearances(year=year, data_dir=settings.data_dir)
    pool_df = _build_all_role_pool(player_master, appearance_stats, year=year)
    if pool_df.empty:
        return []

    lines = _load_pitcher_game_lines(year)
    stats = pd.DataFrame(columns=["MLBAMID"])
    if not lines.empty and "pitcher_id" in lines.columns:
        lines = lines.copy()
        lines["pitcher_id"] = pd.to_numeric(lines["pitcher_id"], errors="coerce")
        lines = lines.dropna(subset=["pitcher_id"]).copy()
        lines["pitcher_id"] = lines["pitcher_id"].astype(int)
        lines["outs"] = lines.get("ip", pd.Series(dtype="object")).map(_outs_from_ip)
        for col in ["hits", "runs", "earned_runs", "walks", "strikeouts", "pitches", "batters_faced"]:
            lines[col] = pd.to_numeric(lines.get(col), errors="coerce").fillna(0)
        lines["is_start_line"] = _starter_line_mask(lines)
        lines["game_score"] = lines.apply(_calculate_game_score, axis=1)

        stats = (
            lines.groupby("pitcher_id", as_index=False)
            .agg(
                outs=("outs", "sum"),
                hits=("hits", "sum"),
                runs=("runs", "sum"),
                earned_runs=("earned_runs", "sum"),
                walks=("walks", "sum"),
                strikeouts=("strikeouts", "sum"),
                pitches=("pitches", "sum"),
                batters_faced=("batters_faced", "sum"),
            )
            .rename(columns={"pitcher_id": "MLBAMID"})
        )
        stats["ip"] = stats["outs"].map(_ip_from_outs)
        stats["era"] = np.where(stats["outs"] > 0, stats["earned_runs"] * 27 / stats["outs"], np.nan)
        starter_scores = (
            lines[lines["is_start_line"] & lines["game_score"].notna()]
            .groupby("pitcher_id", as_index=False)
            .agg(avg_game_score=("game_score", "mean"))
            .rename(columns={"pitcher_id": "MLBAMID"})
        )
        if not starter_scores.empty:
            stats = stats.merge(starter_scores, on="MLBAMID", how="left")

    rows = pool_df.merge(stats, on="MLBAMID", how="left")
    home_runs = _load_pitcher_home_runs(year)
    if not home_runs.empty:
        home_runs["pitcher_id"] = pd.to_numeric(home_runs["pitcher_id"], errors="coerce")
        home_runs = home_runs.dropna(subset=["pitcher_id"]).copy()
        home_runs["pitcher_id"] = home_runs["pitcher_id"].astype(int)
        rows = rows.merge(home_runs.rename(columns={"pitcher_id": "MLBAMID"}), on="MLBAMID", how="left")
    else:
        rows["home_runs"] = np.nan

    role_value = str(role).upper()
    if role_value in {"SP", "RP"}:
        rows = rows[rows["RoleClass"] == role_value].copy()
    if str(team).upper() != "ALL":
        rows = rows[rows["Team"] == str(team)].copy()

    rows["avg_pitches"] = np.where(rows["G"] > 0, rows.get("pitches", 0) / rows["G"], np.nan)
    innings = rows.get("outs", 0) / 3
    rows["whip"] = np.where(innings > 0, (rows.get("hits", 0) + rows.get("walks", 0)) / innings, np.nan)
    rows["strikeout_rate"] = np.where(rows.get("batters_faced", 0) > 0, rows.get("strikeouts", 0) / rows.get("batters_faced", 0), np.nan)
    rows["walk_rate"] = np.where(rows.get("batters_faced", 0) > 0, rows.get("walks", 0) / rows.get("batters_faced", 0), np.nan)
    rows = rows.sort_values(["ip", "G", "Name"], ascending=[False, False, True], na_position="last")

    result: list[PitcherLeaderboardRow] = []
    int_columns = ["G", "GS", "GR", "hits", "runs", "earned_runs", "walks", "strikeouts", "home_runs", "pitches", "batters_faced"]
    for row in rows.to_dict(orient="records"):
        payload = {
            "player_id": int(row["MLBAMID"]),
            "name": str(row["Name"]),
            "team": str(row["Team"]),
            "role": str(row["RoleClass"]),
            "games": int(row.get("G", 0) or 0),
            "starts": int(row.get("GS", 0) or 0),
            "relief_games": int(row.get("GR", 0) or 0),
            "ip": float(row["ip"]) if pd.notna(row.get("ip")) else None,
            "era": round(float(row["era"]), 2) if pd.notna(row.get("era")) else None,
            "avg_pitches": round(float(row["avg_pitches"]), 1) if pd.notna(row.get("avg_pitches")) else None,
            "avg_game_score": round(float(row["avg_game_score"]), 1) if pd.notna(row.get("avg_game_score")) else None,
            "whip": round(float(row["whip"]), 3) if pd.notna(row.get("whip")) else None,
            "strikeout_rate": round(float(row["strikeout_rate"]), 4) if pd.notna(row.get("strikeout_rate")) else None,
            "walk_rate": round(float(row["walk_rate"]), 4) if pd.notna(row.get("walk_rate")) else None,
        }
        for column in int_columns:
            output_key = {
                "G": "games",
                "GS": "starts",
                "GR": "relief_games",
            }.get(column, column)
            if output_key in payload:
                continue
            value = row.get(column)
            payload[output_key] = int(value) if pd.notna(value) else None
        result.append(PitcherLeaderboardRow(**payload))
    return result
