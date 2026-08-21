# Pitcher Personal Migration

## Migrated API Surface

The Streamlit `26_pitcher_personal.py` page has been split into these backend endpoints:

| Streamlit area | New endpoint | Status |
| --- | --- | --- |
| Pitcher selector | `GET /api/pitchers` | Migrated |
| Overview cards / dashboard rows | `GET /api/personal/overview` | Migrated |
| Cached pitch data | `GET /api/personal/pitches` | Migrated |
| Movement summary / scatter payload | `GET /api/personal/movement` | Migrated |
| Discipline summary / stand split | `GET /api/personal/discipline` | Migrated |
| Sequence outcome tables | `GET /api/personal/sequence` | Migrated |
| Rotation game log / WPA / fatigue table | `GET /api/personal/rotation` | Migrated |
| Cached video links | `GET /api/personal/videos` | Migrated |
| Swing Timing / Miss Distance | `GET /api/personal/timing` | Migrated |
| Shape Lab / movement model what-if | TBD model endpoint | Deferred |

## Deferred: Shape Lab

`26_pitcher_personal.py` references `MOVEMENT_MODEL_BASE_FEATURES`, but that symbol is not imported in the page file. Search shows the likely source is `pitch_movement_models.py`, which depends on active-spin model helpers.

Treat Shape Lab as a later Model Agent slice:

- inspect `pitch_movement_models.py`
- inspect `active_spin_model.py`
- decide whether Shape Lab belongs under `/api/personal` or `/api/models`
- avoid coupling this feature into the core Pitcher Personal page until the model contract is clear

## Current Backend Coverage

The migrated endpoints intentionally return data payloads, not Streamlit plots. Frontend components should render charts/tables from:

- `summary`
- `charts`
- `tables`

This keeps matplotlib/plotly rendering out of request handlers and leaves chart implementation to Nuxt.

## Known Data Caveats

- 2026 overview source CSV currently lacks `IP`, `ERA`, `Stuff+`, and `WAR`, so those summary fields fall back to empty values.
- Timing data is available only when the yearly MissDistance CSV exists.
- Video endpoint uses cached `play_id` / `video_url`; it does not live-fetch video metadata.
