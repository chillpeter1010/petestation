# Module Candidates

This file records duplicated logic found during migration slices and where it should eventually live.

## Already Seen

### Personal reference CSV loading

Repeated in:
- `26_pitcher_personal.py`
- Pitcher Personal overview backend service

Candidate module:
- `backend/app/repositories/reference_repository.py`

Suggested functions:
- `personal_reference_paths`
- `load_personal_reference_data`

### Name normalization

Repeated in:
- `26_pitcher_personal.py`
- Pitcher selector backend service
- Pitcher Personal overview backend service

Candidate module:
- `backend/app/utils/names.py`

Suggested functions:
- `clean_name`
- `normalize_name`
- `normalize_player_frame`

### Pitcher role classification

Repeated in:
- `26_pitcher_personal.py`
- `22_starter_stuff.py`
- Pitcher selector backend service

Candidate module:
- `backend/app/services/role_service.py`

Suggested functions:
- `classify_pitcher_role`
- `build_appearance_stats`

### Cached season pitch data

Repeated in:
- `26_pitcher_personal.py`
- future Pitcher Personal movement, discipline, sequence, and video endpoints
- likely Starter Stuff / Starter Discipline detail views

Candidate module:
- `backend/app/repositories/pitch_repository.py`

Current shared functions:
- `load_pitcher_cached_season`
- `resolve_pitch_table`

Future service helpers:
- `prepare_pitch_detail_frame`
- `filter_pitch_df_by_date`
- `summarize_pitch_type_distribution`

### Video lookup

Found in:
- `pitch_video.py`
- cached DuckDB columns `play_id` and `video_url`

Current migration decision:
- Use cached `play_id` / `video_url` first.
- Do not call StatsAPI or Baseball Savant from request-time API handlers unless a later product requirement needs live backfill.

### Shape Lab / movement model features

Found in:
- `26_pitcher_personal.py`
- `pitch_movement_models.py`
- `active_spin_model.py`
- `28_pitch_spin_breakdown.py`

Current migration decision:
- Do not migrate Shape Lab into Pitcher Personal API yet.
- `26_pitcher_personal.py` references `MOVEMENT_MODEL_BASE_FEATURES`, but that symbol is not imported in the page file.
- Treat this as a Model Agent slice after the core Pitcher Personal page APIs are stable.

### Table payload conversion

Repeated need:
- dashboard row
- BR row
- pitch type matrix
- future leaderboards

Candidate module:
- `backend/app/utils/table_payloads.py`

Suggested functions:
- `dataframe_to_table_payload`
- `series_to_clean_dict`

## Keep For Later

Do not extract these modules until at least two migrated endpoints use them. This keeps the first migration passes small and avoids inventing abstractions too early.
