# Agent Workboard

## Current Orchestrator Focus

Pitcher Personal migration from Streamlit prototype to Nuxt 3 + FastAPI.

## Active Agents

| Agent | Current Work | Status |
| --- | --- | --- |
| Orchestrator | Coordinate migration slices, keep scope aligned with legacy Pitcher Personal behavior | Active |
| Backend/Data Agent | FastAPI payloads for selector, movement, discipline, sequence, rotation, timing, videos | Active |
| Frontend Agent | Nuxt page tabs, filters, tables, charts, hover/click/video interactions | Active |
| Model Agent | Shape Lab / movement-model what-if deferred out of Pitcher Personal | Deferred |
| QA/Debug Agent | Backend pytest, frontend typecheck/build, API smoke checks | Active |

## Completed Pitcher Personal Slices

| Slice | Notes | Status |
| --- | --- | --- |
| Pitcher selector API | Year/role/team/pitcher selector backed by FastAPI | Done |
| Overview / Rotation | Dashboard, BR/rotation rows, WPA and fatigue views | Done |
| Stuff filters | Stand, count, pitch, pitch result, in-play result, PA result | Done |
| Movement summary | Movement table, movement chart, usage and pitch mix | Done |
| Pitch location scatter | Full filtered payload, hover details, click selection, video modal | Done |
| Pitch location heatmap | Heatmap Blend slider added to Stuff location chart | Done |
| Pitch location orientation | Displayed horizontal location uses `plate_x * -1`; raw payload remains unchanged | Done |
| Movement vs League | Same-hand league benchmark comparison table added | Done |
| Discipline | Summary, stand split, result panels, count situation panels | Done |
| Sequence outcome map | Count-state pitch mix tree with clickable pitch branches | Done |
| Sequence count detail | Current pitch and next pitch tables by exact count | Done |
| Sequence conditioned branch | Downstream branch metrics, conditioned tree, WPA summary | Done |
| Sequence follow-up events | Immediate event distribution after selected count and pitch | Done |
| Timing | Optional timing payload and table toggle | Done |

## Pitcher Personal Outing Report

Target reference: Pitcher List style single-outing report inside Pitcher Personal. HAVAA and PLV / plvStuff+ are intentionally deferred.

| Slice | Notes | Status |
| --- | --- | --- |
| 1. Outing selector | Select one game outing from the pitcher season page | Done |
| 2. Single-game pitch metrics | Pitch type metrics, pitch mix, summary cards, and pitch log | Done |
| 3. Usage splits | Overall outing usage compared with LHB/RHB usage, including up/down direction | Done |
| 4. Primary fastball + locations | Primary fastball profile and LHB/RHB strike-zone location panels | Done |
| 5. Movement profile | Reused Personal `MovementChart` average/scatter module with same-hand league reference | Done |
| 6. Movement table | Added outing movement summary and league comparison payload/table | Done |
| 7. PLV / Stuff model grades | Deferred per product scope | Deferred |
| 8. HAVAA | Deferred per product scope | Deferred |

## Lab Hub / Model Workbench

Purpose: keep experimental fatigue, Stuff+, and Location+ work outside stable product pages until each model has a clear API contract and QA path.

| Slice | Scope | Reuse Target | Status |
| --- | --- | --- | --- |
| 1. Lab hub shell | Add `/lab` route and homepage Lab entry | Existing Nuxt routing and Petehub card style | Done |
| 2. Starter Fatigue Lab entry | Link existing starter fatigue prototype from Lab | `/rotation/fatigue-lab` | Done |
| 3. Bullpen Fatigue Lab entry | Link existing reliever fatigue prototype from Lab | `/rotation/reliever-fatigue-lab` | Done |
| 4. Stuff Lab shell | Add planning page for Stuff+ migration | Research model notes from legacy `5_research_model.py` | Done |
| 5. Location Lab shell | Add planning page for Location+ migration | Shared zone/discipline geometry | Done |
| 6. Stuff feature module | Ported pitch-type feature table: velo, IVB, HB, release, spin vector, fastball deltas | Future backend model service | Done |
| 7. Stuff scoring API | Added `/api/stuff/score` with prototype proxy score and feature coverage diagnostics; trained artifacts still pending | Personal / Comparison / Outing Report grades | Prototype Done |
| 8. Location feature module | Ported red-zone, heart, shadow, chase, waste, edge, count, and O-Swing features | Personal and Comparison Discipline | Done |
| 9. Location scoring API | Added `/api/location/score` with prototype proxy score and feature coverage diagnostics; trained artifacts still pending | Outing Report model grade | Prototype Done |
| 10. Product integration | Wired date-scoped prototype Stuff/Location score payloads into Pitcher Personal Outing Report model grades; trained artifacts remain pending | Pitcher Personal Outing Report, Lab pages | Prototype Done |
| 11. Legacy Stuff+ model migration | Staged supervised-model slices from legacy `5_research_model.py`: training frame, artifact loader, artifact prediction, holdout diagnostics, and export tables | Stuff Lab first, then product pages | Planned |
| 12. Legacy Location+ model migration | Staged supervised-model slices from legacy `5_research_model.py`: training frame, artifact loader, artifact prediction, diagnostics, and product export table | Location Lab first, then product pages | Planned |
| 13. Official outing game line | Added StatsAPI boxscore parser so Outing Report can prefer official IP/H/R/ER/BB/K/pitches over pitch-row fallbacks | Pitcher Personal Outing Report | Done |
| 14. 2026 pitcher game-line cache | Built `pitcher_game_lines` for all current 2026 pitch-cache games: 1,444 games, 12,235 pitcher lines, 0 failed games | DuckDB + CSV cache | Done |

Model migration rule: product pages can consume Stuff+/Location+ only after Lab has a versioned artifact, feature schema, and diagnostic summary. Until then, product pages must label scores as prototype/fallback.

## Latest QA

| Check | Result |
| --- | --- |
| `python -m pytest backend\tests` | 51 passed |
| `npm run typecheck` | Passed |
| `NUXT_IGNORE_LOCK=1 npm run build` | Passed, with chunk-size warning |
| API smoke: sequence follow-up | 200, returned follow-up rows |
| API smoke: movement benchmark | 200, returned movement league rows |
| Pitcher game-line cache | 2026 complete: 1,444 games / 12,235 pitcher lines / 0 failed games |

## Remaining Product Follow-Ups

| Area | Next Step |
| --- | --- |
| Visual QA | Open the running frontend and visually inspect Stuff/Sequence/Discipline at desktop and narrow widths |
| Performance | Consider lazy-loading ECharts-heavy views or manual chunks if bundle size matters |
| UX polish | Add clearer table column formatting for benchmark/follow-up percentages |
| Architecture | Split the large `pitcher-personal.vue` into tab-level components after behavior stabilizes |

## Pitcher Comparison Migration

Legacy sources:
- `pages/24_pitcher_comparison.py` for Personal pitcher-vs-pitcher comparison.
- `pages/25_pitcher_period_comparison.py` for single-pitcher period-vs-period comparison.

| Slice | Notes | Status |
| --- | --- | --- |
| Personal selector API | Cross-year left/right season, team, and pitcher selectors | Done |
| Personal percentile cards | Savant-style mirrored cards using season-specific percentile pools | Done |
| Personal comparison table | Shared metric table with left/right values, percentiles, gap, and edge | Done |
| Personal advantage summary | Top percentile-gap edges for each side | Done |
| Period comparison API | Loads one pitcher across two date windows and computes legacy 25 period metrics | Done |
| Period comparison page | New `/comparison/period` route with selectors, percentile cards, table, and advantage summary | Done |
| Comparison UI module | Extracted shared page header, loading status, percentile grid, metric details, advantage summary, notes, and advantage composable | Done |
| Period location slice | Added period A/B pitch location payloads and reused `StrikeZoneScatter` on `/comparison/period` | Done |
| Period movement slice | Added period A/B movement payloads and reused `MovementChart` scatter/average modes on `/comparison/period` | Done |
| Period pitch mix slice | Added period A/B pitch mix payloads and reusable usage bar panels on `/comparison/period` | Done |
| Period discipline slice | Added period A/B discipline panel payloads and reused `DisciplinePanelBoard` on `/comparison/period` | Done |
| Period video slice | Added period A/B video row payloads and link panels; rows appear when source data has video mappings | Done |
| Slice 1-3 polish | Fixed Period display-label separator and compact strike-zone hover placement | Done |
| Stuff detail migration | Heavy legacy 24 detail panels are intentionally deferred | Deferred |
| Period detail panels | Core movement, pitch mix, discipline, and video modules are now connected; remaining work is visual QA and deeper legacy-only charts if needed | Done |

## Starter Discipline Module Breakdown

Legacy source: `pages/23_starter_discipline.py` is the richer discipline prototype. It should become a shared Discipline module rather than being copied page-by-page.

| Layer | Legacy Behavior | Target Module |
| --- | --- | --- |
| Domain metrics | Overall + pitch-type rows: Strike%, Zone%, Swing%, Contact%, Z/O-Swing, Z/O-Contact, Whiff%, Edge%, 1st Strike%, Heart Ball%, CStr%, SwStr%, CSW% | `backend/app/services/discipline_service.py::build_pitcher_discipline_table` |
| Panel groups | Result, PA result, batted-ball type, count situation, count swings, exact count grid | `build_discipline_panel_groups` |
| Panel payload | Per-panel location rows, pitch count, pitch mix, side metrics | `build_panel_payload` |
| Zone chart | Plate locations use `plate_x * -1`, heart/shadow/chase guides, optional RdBu heatmap contours | Frontend `StrikeZoneScatter` / future `DisciplineZonePanel` |
| Panel board UI | `Panel Group` switch: Result / Discipline / Situation; side mode: pitch legend vs info panel | Future `frontend/components/discipline/DisciplinePanelBoard.vue` |
| Starter page | Overview leaderboard + player detail workflow | Future `/starter-discipline` API + page |

Completed first module slice:

| Slice | Notes | Status |
| --- | --- | --- |
| Backend Discipline domain module | Extracted pure calculations and panel payload builders from Starter Discipline concept without Streamlit/matplotlib dependencies | Done |
| Module tests | Added coverage for discipline table, panel metrics, panel groups, starter-style payload | Done |
| Frontend Discipline board module | Added reusable `DisciplinePanelBoard`, `DisciplinePanelSection`, and `DisciplineZonePanel`; Pitcher Personal Discipline now consumes the board | Done |

Next Discipline module slices:

| Slice | Notes | Status |
| --- | --- | --- |
| Starter Discipline API | Build `/api/discipline/*` endpoints for overview leaderboard and selected pitcher detail using `discipline_service.py` | Pending |
| Starter Discipline page | Replace placeholder page with filters, leaderboard, player selector, and reusable board | Pending |
| Personal Discipline API alignment | Optionally switch Personal Discipline panels to the richer `panel_groups` payload for PA Result / Batted Ball / Count Swings | Pending |

## Starter Rotation / Bullpen Role Modularization

Legacy sources:
- `pages/21_starter_rotation.py`
- `pages/11_bullpen_role.py`

| Module | Legacy Behavior | Target Module |
| --- | --- | --- |
| Starter rotation table | BR starter rows joined with dashboard IDs; filters GS > 3 and IP/GS > 3 | `backend/app/services/rotation_service.py::build_starter_rotation_table` |
| Starter workload | IP/GS, Pit/GS, short/deep rest, pitch-count buckets, QS/Game Score style columns | `rotation_service.py::build_workload_payload` |
| Starter game log | Per-game WPA, cumulative WPA, opponent, pitches, rest days | Shared game-log API + frontend line chart |
| Starter pitch profile | Pitch mix, velo/spin/movement summaries from cached Statcast | Reuse Personal movement/pitch mix modules |
| Bullpen role table | Reliever BR + standard + advanced merge: GR, GF, SVSit, SV, Hold, IR, IS%, aLI | `backend/app/services/bullpen_service.py::build_bullpen_role_table` |
| Bullpen leverage | High/medium/low leverage, ahead/tie/behind, runners/empty, first inning/multi-inning use | `bullpen_service.py::build_role_usage_payload` |
| Bullpen freshness | Last 3 days usage bars and yesterday workload | Future `BullpenUsageStrip.vue` |

Suggested migration slices:

| Slice | Notes | Status |
| --- | --- | --- |
| Rotation hub shell | `/rotation` route with Starter Rotation and Bullpen Role entry cards | Done |
| Starter page shell | `/rotation/starter` route created; now upgraded into the first functional starter rotation page | Done |
| Reliever page shell | `/rotation/reliever` placeholder with planned migration checklist | Done |
| Rotation service + tests | Reads legacy Starter BR/dashboard CSVs, joins IDs, filters GS/IP-GS, returns typed table/workload/game-log payloads | Done |
| Rotation page shell | `/rotation/starter` has season/team/min GS/min IP-GS filters, starter selector, summary cards, and rotation table | Done |
| Rotation game-log module | Selected starter workload table plus WPA/cumulative WPA trend and game log are connected | Done |
| Bullpen service + tests | Read Reliever CSVs and expose role/leverage table payload | Pending |
| Bullpen role page shell | `/bullpen-role` filters, table, selected reliever panel | Pending |
| Shared workload components | Small reusable bars/chips for rest, leverage, pitch-count buckets | Pending |

Next rotation/bullpen slices:

| Slice | Scope | Reuse Target | Status |
| --- | --- | --- | --- |
| 6. Starter pitch profile | Added selected-starter pitch profile table with usage, velo, HB, VB from cached Statcast | Reuses shared table payload | Done |
| 7. Starter game detail | Added rest days to game log while preserving WPA/cumulative WPA trend | Extends rotation service game-log payload | Done |
| 8. Bullpen role service | Added reliever role API from legacy Reliever CSVs: GR, GF, SVSit, SV, Hold, IR, IS%, aLI | Implemented in `rotation_service.py` for now | Done |
| 9. Bullpen role page | `/rotation/reliever` now has filters, summary cards, bullpen role table, selected reliever card, role usage table | Reuses DataTable and SummaryCards | Done |
| 10. Shared rotation components | Reused existing shared table/summary/header modules; deeper extraction deferred until more pages repeat the pattern | Use in starter, reliever, and future team pages | Done |

## Batter Swing Timing / Team Hitting Roadmap

Detailed plan: `docs/BATTER_SWING_TIMING_ROADMAP.md`.

| Slice | Scope | Status |
| --- | --- | --- |
| V1 Swing Timing leaderboard | Batter Savant summary cache/API, definition-correct leaderboard, X/Y/Z dimension views, Rules | Done |
| V2 Timing visuals + Batter Personal | Exact distributions when source bins exist; otherwise honest summary visuals, timing fingerprint, pitch matrix, bat-speed gear change | Pending |
| V3 Team Hitting Intelligence | Team Timing Map, pitch-family matchup matrix, lineup skill strip, compact team hitting API | Pending |
| Batting-order impact | Player/team performance by lineup slot with minimum samples and non-causal labeling | Pending |
| Position/role impact | Same-hitter batting splits by field position, DH and PH after lineup-position data audit | Pending |
| Platoon lineup prediction | Rank available hitters against projected LHP/RHP with roster, defense and rest constraints | Pending |
| Lineup optimization | Candidate batting orders and expected-run simulation after prediction inputs are stable | Pending |

## Leaderboard Roadmap

Initial leaderboard groups should combine basic readable stats with the advanced metrics already used in Pitcher Personal and Comparison.

| Group | Candidate Columns | Why |
| --- | --- | --- |
| Basic run prevention | ERA, IP, G, GS, WAR | Familiar entry point for users |
| Estimators | FIP, xFIP, xERA / SIERA if available | Better pitcher-quality signal than ERA |
| Plate discipline | K%, BB%, K-BB%, Whiff%, CSW%, Chase% | Core pitcher skill and can link to Discipline |
| Contact quality | xBA, wOBA/xwOBA, Hard-Hit%, Barrel%, Avg EV | Contact management and damage allowed |
| Stuff / shape | Stuff+, fastball velo, IVB/HB by pitch, pitch usage | Links directly to Stuff and Movement modules |
| Role / workload | GS, IP/GS, pitches/GS for starters; GR, Hold, SVSit, aLI for relievers | Separates starter and bullpen value |

Recommended first slice:
- Build `/api/leaderboards/pitchers?year=&role=&metric=&min_pitches=` using comparison CSV + cached season aggregates.
- Frontend table with sortable columns, role filter, metric group tabs, and row links to Pitcher Personal / Comparison.
