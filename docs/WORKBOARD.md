# Workboard

## Current Slice

Pitcher Personal - Legacy item 7, Stuff selected pitch video and timing

## Orchestrator

Status: Done

Task:
- Implement the confirmed legacy item 7 direction inside Stuff.
- Add selected pitch detail/video behavior to the Stuff pitch-location workflow.
- Add nested Stuff timing toggle.
- Record verification results.

Done when:
- Workboard is updated.
- Stuff pitch-location scatter points can be clicked.
- Selected pitch detail appears under the Stuff scatter.
- A video link appears when the selected pitch has `video_url` or `play_id`.
- Timing can be loaded from inside Stuff with a toggle.
- Backend/Data, Frontend, and QA statuses are updated.

## Backend/Data Agent

Status: Done

Task:
- Add selected-pitch identity columns to pitch location scatter payloads.
- Preserve video metadata columns when available.
- Keep existing timing endpoint as the nested Stuff data source.

Done when:
- `python -m pytest backend\tests` passes.
- Movement scatter API returns identity and video fields needed by selected-pitch detail.
- Timing endpoint still responds.

## Frontend Agent

Status: Done

Task:
- Make `StrikeZoneScatter` emit selected points.
- Add selected pitch detail and video link in Stuff.
- Add nested Stuff timing toggle and lazy timing fetch.

Done when:
- `npm run typecheck` passes.
- `npm run build` passes.
- Nuxt dev page responds locally.

## QA/Debug Agent

Status: Done

Task:
- Run backend tests.
- Run frontend typecheck and production build.
- Restart local backend so the enriched scatter payload is active.
- Smoke test movement scatter payload, timing endpoint, and Nuxt page.

Done when:
- Verification results are listed below.

## Verification Log

- Previous slice passed: `GET /api/pitchers?year=2026&role=SP` returned 223 pitcher options from the legacy DuckDB data.
- Backend compile passed: `python -m compileall .\backend\app .\backend\tests`
- API smoke test passed: `GET /api/personal/overview?year=2025&role=SP&pitcher_id=657277`
- 2025 smoke result for Logan Webb returned dashboard row, BR row, six summary cards, and eight pitch type matrix rows.
- 2026 smoke result for Aaron Civale returned fallback `Team=ATH` and `GS=14`; detailed 2026 dashboard metrics are missing because the available 2026 source CSV does not include `IP`, `ERA`, `Stuff+`, or `WAR`.
- Focused pytest command still could not run because `pytest` is not installed in the active Python environment.
- Backend compile passed after cached pitch data slice: `python -m compileall .\backend\app .\backend\tests`
- API smoke test passed: `GET /api/personal/pitches?year=2025&pitcher_id=657277&limit=5`
- 2025 Logan Webb cached pitch data returned 3282 pitches across 34 games.
- 2026 Aaron Civale cached pitch data returned 1174 pitches across 14 games.
- `pytest` is still unavailable in the active Python environment.
- API smoke test passed for `/api/personal/movement`, `/api/personal/discipline`, and `/api/personal/sequence` for 2025 Logan Webb and 2026 Aaron Civale.
- API smoke test passed for `/api/personal/rotation` and `/api/personal/videos` for 2025 Logan Webb and 2026 Aaron Civale.
- API smoke test passed for all migrated Pitcher Personal endpoints using 2025 Logan Webb.
- 2025 timing endpoint returned five pitch-level timing rows and timing chart point payloads.
- Shape Lab is deferred because `26_pitcher_personal.py` references `MOVEMENT_MODEL_BASE_FEATURES` without importing it; likely source is `pitch_movement_models.py`.
- Frontend dependency install initially found a Pinia peer mismatch; fixed by upgrading `pinia` to `^3.0.4`.
- Added `tsconfig.json`, `vue-tsc`, and `@types/node` so Nuxt typecheck can run.
- Frontend typecheck passed: `npm run typecheck`.
- Frontend production build passed: `npm run build`.
- Backend health check passed locally at `http://127.0.0.1:8000/api/health`.
- Frontend route responded locally at `http://127.0.0.1:3000/pitcher-personal`.
- Local dev servers are running: FastAPI process `17588`, Nuxt node process `38104`.
- npm reports one moderate vulnerability and an engine warning for `rollup-plugin-visualizer` requiring Node `>=22`; current Node is `v20.20.2`. Build and typecheck still passed.
- Fixed selector reliability: backend CORS now allows `http://127.0.0.1:3000`, `http://localhost:3000`, `http://127.0.0.1:3001`, and `http://localhost:3001`.
- Fixed backend default data directory resolution to prefer the legacy desktop data folder and fall back to the project `data` directory.
- Updated Nuxt default API base to `http://127.0.0.1:8000/api`.
- Added loading, empty, and error states to `FiltersPanel`.
- Backend compile passed after selector reliability fix: `python -m compileall .\backend\app .\backend\tests`
- Frontend typecheck passed after selector reliability fix: `npm run typecheck`.
- Frontend production build passed after selector reliability fix: `npm run build`.
- CORS smoke test passed: `GET /api/pitchers?year=2026&role=SP` with `Origin: http://127.0.0.1:3000` returned 223 pitcher options and `access-control-allow-origin: http://127.0.0.1:3000`.
- Backend health check passed locally at `http://127.0.0.1:8000/api/health`.
- Frontend route responded locally at `http://127.0.0.1:3000/pitcher-personal`.
- Fixed `GET /api/personal/timing?year=2026&pitcher_id=650644` returning 500 when timing source columns such as `n_swings` are missing.
- Backend compile passed after timing fix: `python -m compileall .\backend\app .\backend\tests`
- Timing smoke test passed: `GET /api/personal/timing?year=2026&pitcher_id=650644` now returns 200 with empty timing chart/table payloads and a warning instead of failing the page fetch.
- Installed `pytest` into the active Python 3.14 environment so backend tests can run with `python -m pytest`.
- Full backend test suite passed: `python -m pytest backend\tests` returned 13 passed.
- Attempted a project `.venv`, but dependency install stalled on Python 3.14; keep using active Python for now or install Python 3.12 for a cleaner local venv later.
- Generated UI/UX Pro Max design system at `design-system/baseball-analysis-platform/MASTER.md` and Pitcher Personal overrides at `design-system/baseball-analysis-platform/pages/pitcher-personal.md`.
- Added global frontend design tokens in `frontend/assets/css/main.css` and registered them in Nuxt config.
- Polished Pitcher Personal dashboard shell, filter toolbar, summary cards, data tables, and bar-list visuals using the data-dense dashboard direction.
- Frontend typecheck passed after UI polish: `npm run typecheck`.
- Frontend production build passed after UI polish: `npm run build`.
- Frontend route responded locally after restart at `http://127.0.0.1:3000/pitcher-personal`.
- Added Pitcher Personal visualization payloads: `pitch_location_scatter` on `/api/personal/pitches` and `count_pitch_mix` on `/api/personal/sequence`.
- Added backend tests for pitch location scatter payloads and count pitch mix payloads.
- Backend tests passed after visualization payload slice: `python -m pytest backend\tests` returned 15 passed.
- Added frontend ECharts wrapper plus `StrikeZoneScatter` and `SequenceOutcomeTree` chart components.
- Wired Pitcher Personal Overview to render pitch location scatter and Sequence to render count pitch mix tree.
- Frontend typecheck passed after visualization layer: `npm run typecheck`.
- Frontend production build passed after visualization layer: `npm run build`. Build still warns that the ECharts chunk is slightly above 500 kB.
- API smoke passed at the time of the initial visualization slice: 2025 Logan Webb returned 1000 `pitch_location_scatter` points and 55 `count_pitch_mix` rows. This earlier scatter cap was later removed by the uncapped strike-zone payload slice.
- Frontend route responded locally after visualization layer at `http://127.0.0.1:3000/pitcher-personal`.
- Replaced the Overview pitch location chart with an SVG-based `StrikeZoneScatter` to avoid blank ECharts initialization states.
- Clarified pitch scatter totals in the UI during the early visualization slice. The later uncapped strike-zone payload slice removed sampled-point display as the default behavior.
- Disabled Nuxt `experimental.appManifest` in local dev config after `#app-manifest` resolution errors were blocking client hydration.
- Frontend typecheck passed after the hydration fix: `npm run typecheck`.
- Frontend production build passed after the hydration fix: `npm run build`. Build still warns that the ECharts chunk is slightly above 500 kB.
- Backend test suite passed after the hydration fix: `python -m pytest backend\tests` returned 15 passed.
- Browser verification passed with Playwright using Microsoft Edge: `http://127.0.0.1:3000/pitcher-personal` rendered the scatter plot with points for 2026 Aaron Civale.
- Corrected Pitcher Personal layout drift after comparing the legacy Streamlit file: `Pitch Location Scatter` belongs to the legacy `Stuff` tab, not `Overview`.
- Frontend tab label changed from `Movement` to `Stuff` while keeping the internal `movement` key/API wiring unchanged.
- Frontend typecheck passed after moving the scatter chart: `npm run typecheck`.
- Frontend production build passed after moving the scatter chart: `NUXT_IGNORE_LOCK=1 npm run build`. Build still warns that the ECharts chunk is slightly above 500 kB.
- Completed a full legacy structure pass for `26_pitcher_personal.py` and recorded the source-of-truth mapping in `docs/PITCHER_PERSONAL_LEGACY_MAP.md`.
- Identified that Timing is nested under legacy `Stuff`, while Videos is present but disabled behind `if False`; both need product decisions before final tab placement.
- Recommended next slice is `Stuff parity slice 1`: match the legacy Stuff top-level structure before adding more Sequence or Discipline visuals.
- Completed migration steps 1-3 for Pitcher Personal:
  - Nuxt tabs now match legacy top-level order: `Overview`, `Rotation`, `Stuff`, `Sequence`, `Discipline`.
  - Removed `Videos` and `Timing` from top-level navigation; backend endpoints remain available.
  - Cleaned Overview so it only owns dashboard and BR/rotation tables.
  - Added Rotation WPA line chart, game selector, fatigue metric cards, and fatigue bar chart.
- Frontend typecheck passed after steps 1-3: `npm run typecheck`.
- Frontend production build passed after steps 1-3: `NUXT_IGNORE_LOCK=1 npm run build`. Build still warns that the ECharts chunk is slightly above 500 kB.
- Backend test suite passed after steps 1-3: `python -m pytest backend\tests` returned 15 passed.
- Restarted Nuxt dev server and confirmed `http://127.0.0.1:3000/pitcher-personal` returns 200 with the five legacy tabs.
- Completed Stuff parity slice 1:
  - Added `stand`, `count`, `pitch`, and `pitch_result` filters to `/api/personal/movement`.
  - Added filtered Stuff snapshot payload and `run_values_by_pitch_type`.
  - Moved filtered pitch location scatter ownership to the Stuff tab data flow.
  - Added Stuff filter controls, snapshot cards, and Run Values by Pitch Type table in Nuxt.
- Backend test suite passed after Stuff parity slice 1: `python -m pytest backend\tests` returned 17 passed.
- Frontend typecheck passed after Stuff parity slice 1: `npm run typecheck`.
- Frontend production build passed after Stuff parity slice 1: `NUXT_IGNORE_LOCK=1 npm run build`. Build still warns that one ECharts chunk is larger than 500 kB.
- Restarted stale FastAPI dev process and confirmed filtered movement API returns the new payload shape.
- Filtered movement API smoke passed: `stand=R&count=0-0&pitch_result=called_strike` for 2026 Aaron Civale returned 43 filtered pitches, 43 location points, and 5 run value rows.
- Frontend route responded locally after Stuff parity slice 1 at `http://127.0.0.1:3000/pitcher-personal`.
- Completed Sequence and Discipline parity slice:
  - `/api/personal/sequence` now accepts `stand`, `count`, `pitch`, `pitch_result`, and `catcher`.
  - `/api/personal/discipline` now accepts `stand` and `count`.
  - Sequence now returns filtered `filter_snapshot` and `pitch_location_scatter`.
  - Discipline now returns filtered `filter_snapshot`, `pitch_location_scatter`, `result_panels`, and `count_panels`.
  - Frontend Sequence tab now has filters, snapshot cards, filtered location scatter, count tree, and sequence tables.
  - Frontend Discipline tab now has filters, snapshot cards, filtered location scatter, result panels, count situation panels, and summary tables.
- Confirmed legacy migration item 7:
  - `Videos` is not an active legacy tab; it is inside an `if False` block near the end of `26_pitcher_personal.py`.
  - Active video behavior in the old page is tied to selected pitch detail inside the Stuff location workflow.
  - `Timing` is not a top-level legacy tab; it is nested inside Stuff behind a `Show swing timing / miss distance` checkbox.
- Backend test suite passed after Sequence/Discipline slice: `python -m pytest backend\tests` returned 19 passed.
- Frontend typecheck passed after Sequence/Discipline slice: `npm run typecheck`.
- Frontend production build passed after Sequence/Discipline slice: `NUXT_IGNORE_LOCK=1 npm run build`. Build still warns that one ECharts chunk is larger than 500 kB.
- Sequence API smoke passed: `stand=R&count=0-0&pitch_result=called_strike` for 2026 Aaron Civale returned 43 filtered pitches, 5 tree rows, 43 location points, and 4 shallow sequence rows.
- Discipline API smoke passed: `stand=R&count=0-0` for 2026 Aaron Civale returned 131 filtered pitches, 131 location points, four result panels, and exact count panel payloads.
- Nuxt dev server is running on `http://127.0.0.1:3001/pitcher-personal` after port 3000 did not respond.
- Completed legacy item 7 implementation inside Stuff:
  - `pitch_location_scatter` now includes selected-pitch identity fields such as `game_date`, `game_pk`, `at_bat_number`, `pitch_number`, and `release_speed`.
  - `pitch_location_scatter` preserves `play_id` and `video_url` when available.
  - `StrikeZoneScatter` now emits clicked pitch points and highlights the selected point.
  - Stuff now shows a selected pitch detail panel below the location scatter.
  - Stuff shows an `Open Video` link when the selected pitch has a video URL or play ID, otherwise it shows that no mapping is available.
  - Stuff now has a nested `Swing Timing / Miss Distance` toggle that lazy-loads `/api/personal/timing`.
- Backend test suite passed after legacy item 7: `python -m pytest backend\tests` returned 19 passed.
- Frontend typecheck passed after legacy item 7: `npm run typecheck`.
- Frontend production build passed after legacy item 7: `NUXT_IGNORE_LOCK=1 npm run build`. Build still warns that one ECharts chunk is larger than 500 kB.
- Movement API smoke passed after legacy item 7: 2026 Aaron Civale scatter points now include `game_pk`, `at_bat_number`, `pitch_number`, `release_speed`, `play_id`, and `video_url`.
- Timing API smoke passed after legacy item 7: `GET /api/personal/timing?year=2026&pitcher_id=650644` returned 200 with an empty 2026 timing table, which matches current data availability.
- FastAPI is running on `http://127.0.0.1:8000`; Nuxt is running on `http://127.0.0.1:3001/pitcher-personal`.
- Removed the large standalone pitch-location scatter charts from Sequence and Discipline tabs.
- Kept Stuff as the primary selected-pitch/video interaction surface.
- Kept Discipline's smaller Result Panels and Count Situation charts.
- Frontend typecheck passed after removing Sequence/Discipline large charts: `npm run typecheck`.
- Backend test suite passed after removing Sequence/Discipline large charts: `python -m pytest backend\tests` returned 19 passed.
- Frontend production build passed after removing Sequence/Discipline large charts: `NUXT_IGNORE_LOCK=1 npm run build`. Build still warns that one ECharts chunk is larger than 500 kB.
- Frontend route responded locally at `http://127.0.0.1:3001/pitcher-personal`.
- Completed Stuff movement visualization and uncapped strike-zone payload slice:
  - Added a Stuff movement chart with scatter and average modes.
  - Kept Stuff location scatter as the selected-pitch/video interaction surface.
  - Removed backend sampling caps from `build_pitch_location_scatter`; strike-zone charts now return all valid filtered rows instead of a 1000-point sample.
  - Removed Discipline result/count panel scatter caps.
  - Removed movement scatter sampling so Stuff movement scatter uses all valid filtered movement rows.
- Backend test suite passed after uncapping scatter payloads: `python -m pytest backend\tests` returned 20 passed.
- Frontend typecheck passed after movement chart slice: `npm run typecheck`.
- Frontend production build passed after movement chart slice: `NUXT_IGNORE_LOCK=1 npm run build`. Build still warns that one ECharts chunk is larger than 500 kB.
- Movement API smoke passed after uncapping: 2026 Aaron Civale returned 1170 location points, 1170 movement points, and 1174 total pitches.
- Discipline API smoke passed after uncapping: 2026 Aaron Civale returned 1170 main location points; result/count panels now return their full filtered group sizes.
- FastAPI was restarted on `http://127.0.0.1:8000`; Nuxt is responding on `http://127.0.0.1:3001/pitcher-personal`.
- Completed Stuff filter parity and chart sizing slice:
  - Added legacy Stuff `In Play Result` filter using the old Barrel / Solid Contact / Flare-Burner / Poorly-* / Unclassified / Not In Play classification.
  - Added legacy Stuff `PA Result` filter using `events` groups such as Single, Double, Home Run, Strikeout, Walk, Out, Error, Sacrifice, Advance on Throw, Fielder's Choice, Other, and No Result.
  - Wired both filters through `/api/personal/movement` and the Nuxt Stuff filter bar.
  - Slightly reduced chart footprint across WPA, Stuff movement, strike-zone scatter, EChart defaults, and Sequence Outcomes.
- Backend test suite passed after Stuff filter parity: `python -m pytest backend\tests` returned 21 passed.
- Frontend typecheck passed after Stuff filter parity and chart sizing: `npm run typecheck`.
- Frontend production build passed after Stuff filter parity and chart sizing: `NUXT_IGNORE_LOCK=1 npm run build`. Build still warns that one ECharts chunk is larger than 500 kB.
- Movement API smoke passed after new filters: 2026 Aaron Civale returned 20 location points for `in_play_result=barrel` and 14 location points for `pa_result=pa_home_run`.
- FastAPI is running on `http://127.0.0.1:8000`; Nuxt is responding on `http://127.0.0.1:3001/pitcher-personal`.

## 2026-07-04 Status Audit

- Current Pitcher Personal migration status is also summarized in the root `WORKBOARD.md`.
- Core Pitcher Personal parity is functionally complete for the current scope:
  - Overview / Rotation
  - Stuff filters, movement chart, movement league comparison, heatmap blend, pitch location scatter, selected pitch details, video modal, timing toggle
  - Sequence outcome tree, count detail, conditioned branch, follow-up event distribution
  - Discipline summary, stand split, result panels, count situation panels
- Verification passed during this audit:
  - `python -m pytest backend\tests` returned 25 passed.
  - `npm run typecheck` passed.
  - Sequence API smoke returned 61 count-mix rows and 4 follow-up rows for 2026 pitcher `650644`.
  - Movement API smoke returned 1170 location points and 6 movement league rows for 2026 pitcher `650644`.
  - Nuxt route `http://127.0.0.1:3001/pitcher-personal` returned 200.
- Recommended next work is product hardening rather than another parity slice:
  - visually inspect desktop and mobile layouts after the SVG Sequence tree and KDE-style heatmap changes
  - split `frontend/pages/pitcher-personal.vue` into tab-level components
  - add table formatting rules for percentages, decimals, and pitch counts
  - decide whether Shape Lab belongs under Model APIs or remains deferred
  - begin the next legacy page migration only after the Pitcher Personal component split
- Completed Sequence conditioned downstream branch slice:
  - Added `condition_count` and `condition_pitch` query params to `/api/personal/sequence`.
  - Added backend conditioned branch helpers for downstream count-state samples and WPA summaries.
  - Added `charts.conditioned_count_pitch_mix`, `charts.conditioned_summary`, and `tables.conditioned_wpa_summary`.
  - Added Nuxt Sequence `Conditioned Branch` controls with count/pitch selectors, downstream summary cards, conditioned count-state tree, and conditioned WPA summary table.
  - Kept this first pass select-driven; direct pie-slice click can be added later on top of the same API contract.
- Backend test suite passed after Sequence conditioned branch: `python -m pytest backend\tests` returned 22 passed.
- Frontend typecheck passed after Sequence conditioned branch: `npm run typecheck`.
- Frontend production build passed after Sequence conditioned branch: `NUXT_IGNORE_LOCK=1 npm run build`. Build still warns that one ECharts chunk is larger than 500 kB.
- Sequence API smoke passed: 2026 Aaron Civale `condition_count=0-0&condition_pitch=Cutter` returned 470 downstream pitches, 120 downstream PA, 53 conditioned mix rows, and 6 conditioned WPA rows.
- FastAPI is running on `http://127.0.0.1:8000`; Nuxt is responding on `http://127.0.0.1:3001/pitcher-personal`.
- Completed Sequence Count Detail slice:
  - Added `detail_count` query param to `/api/personal/sequence`.
  - Added backend current-count pitch usage and next-count pitch usage summary tables.
  - Added `tables.count_detail_current` and `tables.count_detail_next`.
  - Added Nuxt Sequence `Count Detail` controls and side-by-side Current Pitch / Next Pitch tables.
- Backend test suite passed after Sequence Count Detail: `python -m pytest backend\tests` returned 23 passed.
- Frontend typecheck passed after Sequence Count Detail: `npm run typecheck`.
- Sequence API smoke passed: 2026 Aaron Civale `detail_count=0-0` returned 7 current-pitch rows and 7 next-pitch rows.
- FastAPI is running on `http://127.0.0.1:8000`; Nuxt is responding on `http://127.0.0.1:3001/pitcher-personal`.
