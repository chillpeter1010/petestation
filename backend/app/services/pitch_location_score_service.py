from __future__ import annotations

from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from app.core.config import settings


def load_pitch_location_scores(
    data: pd.DataFrame,
    data_dir: Path | None = None,
) -> pd.Series:
    """Return cached per-pitch Location+ scores aligned to the input frame."""

    result = pd.Series(np.nan, index=data.index, dtype="float64")
    if data.empty or "game_date" not in data.columns:
        return result

    root = data_dir or settings.data_dir
    path = root / "derived" / "location_plus_scores.duckdb"
    if not path.exists():
        return result

    game_dates = pd.to_datetime(data["game_date"], errors="coerce")
    if "pitch_uid" in data.columns:
        pitch_keys = data["pitch_uid"].astype("string")
    elif {"game_pk", "at_bat_number", "pitch_number"}.issubset(data.columns):
        game_pk = pd.to_numeric(data["game_pk"], errors="coerce").astype("Int64").astype("string")
        at_bat = pd.to_numeric(data["at_bat_number"], errors="coerce").astype("Int64").astype("string")
        pitch_number = pd.to_numeric(data["pitch_number"], errors="coerce").astype("Int64").astype("string")
        pitch_keys = game_pk + "_" + at_bat + "_" + pitch_number
    else:
        return result

    try:
        with duckdb.connect(str(path), read_only=True) as connection:
            tables = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
            for year in sorted(game_dates.dropna().dt.year.astype(int).unique()):
                table = f"location_pitch_scores_{year}"
                if table not in tables:
                    continue
                year_mask = game_dates.dt.year.eq(year)
                game_ids = [
                    int(value)
                    for value in pd.to_numeric(data.loc[year_mask, "game_pk"], errors="coerce").dropna().unique()
                ] if "game_pk" in data.columns else []
                if not game_ids:
                    continue
                placeholders = ",".join("?" for _ in game_ids)
                scores = connection.execute(
                    f"""
                    SELECT pitch_uid, location_plus_pitch
                    FROM {table}
                    WHERE game_pk IN ({placeholders})
                    """,
                    game_ids,
                ).fetchdf()
                if scores.empty:
                    continue
                score_map = (
                    scores.drop_duplicates("pitch_uid", keep="last")
                    .set_index("pitch_uid")["location_plus_pitch"]
                )
                result.loc[year_mask] = pd.to_numeric(
                    pitch_keys.loc[year_mask].map(score_map),
                    errors="coerce",
                ).to_numpy()
    except duckdb.Error:
        return result

    return result
