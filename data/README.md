# Data Directory

This folder is intentionally treated as local runtime data and is excluded from Git by default.

The production-sized data files used by Petehub are too large and source-dependent for the portfolio repository. Keep real MLB / Statcast / video lookup / derived model artifacts on the local machine or in private storage.

## Expected Local Layout

```txt
data/
  MLB2021/
  MLB2022/
  MLB2023/
  MLB2024/
  MLB2025/
  MLB2026/
  derived/
  Starter/
  Reliever/
  Batter/
  research/
  sample/
```

Common local artifacts include:

```txt
*.duckdb
*.parquet
*.csv.gz
*_pitch_play_lookup.csv.gz
*_pitcher_game_lines.csv.gz
derived_exports.duckdb
```

These files are ignored by `.gitignore`.

## Portfolio / Demo Data

For a public GitHub demo, add small sanitized examples under:

```txt
data/sample/
```

Suggested sample files:

```txt
data/sample/pitchers_sample.parquet
data/sample/games_sample.parquet
data/sample/outing_reports_sample.parquet
data/sample/sequence_sample.parquet
```

Keep sample data small enough for GitHub and remove any private keys, local absolute paths, or unrelated personal files.

## Data Source Note

This project is designed around baseball pitch-level and game-level data. The repository does not redistribute full MLB datasets or video assets. Users who run the project locally should prepare their own data cache or connect compatible derived exports.
