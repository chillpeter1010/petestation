# API Contracts

## Shared Query Parameters

Most pitcher analysis endpoints should share these parameters where possible:

| Param | Type | Notes |
| --- | --- | --- |
| `year` | integer | Season year |
| `pitcher_id` | integer | MLBAM player id |
| `team` | string | Optional team filter |
| `start_date` | string | ISO date |
| `end_date` | string | ISO date |
| `pitch_types` | string[] | Repeated query param |
| `stand` | string | `All`, `L`, `R` |
| `counts` | string[] | Count buckets or exact counts |
| `results` | string[] | Pitch or PA result buckets |

## Recommended Endpoints

### Pitchers

- `GET /api/pitchers`
- `GET /api/pitchers/{pitcher_id}`

#### `GET /api/pitchers`

Query:

| Param | Type | Notes |
| --- | --- | --- |
| `year` | integer | Defaults to `2026` |
| `role` | string | `SP` or `RP`; any non-`RP` value is treated as `SP` |

Response:

```json
[
  {
    "value": 650644,
    "label": "Aaron Civale (ATH)",
    "name": "Aaron Civale",
    "team": "ATH",
    "role": "SP",
    "games": 14,
    "starts": 14,
    "start_rate": 1.0
  }
]
```

### Pitcher Personal

- `GET /api/personal/overview`
- `GET /api/personal/pitches`
- `GET /api/personal/discipline`
- `GET /api/personal/sequence`
- `GET /api/personal/movement`
- `GET /api/personal/rotation`
- `GET /api/personal/videos`
- `GET /api/personal/timing`

### Batter Lab

- `GET /api/batters/lab/swing-timing`

#### `GET /api/batters/lab/swing-timing`

Query:

| Param | Type | Notes |
| --- | --- | --- |
| `year` | integer | Available cached season; currently `2023`–`2026` |
| `pitch_group` | string | `all`, `fastball`, `breaking`, `offspeed`, `other` |
| `pitch_type` | string | Optional Statcast pitch code such as `FF`, `SL`, `CH` |
| `pitcher_hand` | string | `All`, `L`, `R` |
| `batter_side` | string | `All`, `L`, `R` |
| `batter_team` | string | Batter's season team code or `All` |
| `pitcher_team` | string | `All` 使用 Savant summary；球隊代碼使用本機精確逐球 matchup mode |
| `minimum_swings` | integer | Qualification threshold after filters |
| `minimum_plate_appearances` | integer | Season PA qualification threshold; `5`–`700`, normalized to steps of `5` |

Returns `league`, `leaderboard`, `data_mode`, filter options and sample metadata. All percentage fields use the `0–100` scale. Distances remain in inches and timing offsets in milliseconds. Rate fields are aggregated by swings; average miss distance is weighted by estimated whiffs, and conditional directional distances are weighted by their corresponding category counts.

The request path only reads local Savant summary caches under `data/MissDistance`; refreshing those caches is an explicit offline operation and does not occur during page requests.

`batter_team` is exact in summary mode. Selecting `pitcher_team` switches to exact local pitch-level matchups (`data_mode=matchup_event`). This mode returns exact tracked swings, Whiff, Competitive Rate, Bat Speed, Swing Length and attack metrics; X/Y/Z alignment and Flawed/Perfect remain null because those event-level fields are absent locally. Current pitch-level `miss_distance` coverage is 2026 only.

#### `GET /api/batters/lab/swing-timing/player`

Lazy-loaded V2 player detail endpoint. Accepts the same pitch, hand, side and pitcher-team filters plus `batter_id`. Returns player/league summary, pitch-type matrix and Bat-Speed Gear Change fields. The Lab calls it only when a leaderboard row is expanded.

#### `GET /api/personal/overview`

Query:

| Param | Type | Notes |
| --- | --- | --- |
| `year` | integer | Season year |
| `role` | string | `SP` or `RP`; defaults to `SP` |
| `pitcher_id` | integer | MLBAM player id |

Response includes:

- `selected_pitcher`: pitcher option metadata from `/api/pitchers`
- `summary`: cards for `Team`, `GS`, `IP`, `ERA`, `Stuff+`, `WAR`
- `tables.dashboard`: the source dashboard row
- `tables.br`: the source BR / rotation row when available
- `tables.pitch_type_matrix`: pitch-level `Stuff+`, `Location+`, `Pitching+` matrix when available

#### `GET /api/personal/pitches`

Query:

| Param | Type | Notes |
| --- | --- | --- |
| `year` | integer | Season year |
| `pitcher_id` | integer | MLBAM player id |
| `start_date` | string | Optional ISO date |
| `end_date` | string | Optional ISO date |
| `limit` | integer | Sample table row limit, capped at `1000` |

Response includes:

- `summary`: pitch count, game count, first game date, last game date
- `charts.pitch_type_distribution`: pitch type counts and rates
- `tables.sample_pitches`: limited pitch-level sample rows for debugging and downstream UI wiring

#### `GET /api/personal/movement`

Returns:

- `summary`: pitch count, pitcher hand, pitch type count
- `charts.movement_scatter`: horizontal/vertical break points for all valid filtered rows
- `tables.movement_summary`: pitch-level usage, movement, and velocity summary

#### `GET /api/personal/discipline`

Returns:

- `summary`: discipline metrics including swing, whiff, CSW, zone, chase, first-pitch strike
- `tables.discipline_summary`: one-row summary table
- `tables.stand_split`: L/R batter split table

#### `GET /api/personal/sequence`

Query:

| Param | Type | Notes |
| --- | --- | --- |
| `year` | integer | Season year |
| `pitcher_id` | integer | MLBAM player id |
| `start_date` | string | Optional ISO date |
| `end_date` | string | Optional ISO date |
| `current_pitch` | string | Optional pitch filter; defaults to `All` |

Returns:

- `summary`: filtered pitch snapshot
- `tables.shallow_sequences`: shallow-count sequence outcomes
- `tables.two_strike_sequences`: two-strike sequence outcomes

#### `GET /api/personal/rotation`

Returns:

- `summary`: game count, pitch count, total WPA
- `charts.wpa_games`: game-level WPA and cumulative WPA rows
- `tables.game_log`: game-level pitch/velo/spin/batter counts
- `tables.fatigue_by_inning`: inning-level fatigue proxy for selected or latest game

#### `GET /api/personal/videos`

Returns cached video links from DuckDB columns:

- `play_id`
- `video_url`

The endpoint does not call StatsAPI or Baseball Savant at request time.

#### `GET /api/personal/timing`

Returns Swing Timing / Miss Distance payloads when a yearly CSV exists under `data/MissDistance`.

- `summary`: swings, whiff rate, pitch type count
- `charts.x_timing_points`: tied-up / centered / flail points
- `charts.y_timing_points`: late / on-time / early points
- `charts.z_timing_points`: over / lined-up / under points
- `tables.timing_by_pitch`: pitch-level timing summary

### Starter Stuff

- `GET /api/stuff/leaderboard`
- `GET /api/stuff/pitch-shapes`
- `GET /api/stuff/pitcher-detail`

### Starter Discipline

- `GET /api/discipline/leaderboard`
- `GET /api/discipline/swing-map`
- `GET /api/discipline/pitcher-detail`

### Pitcher Similarity

- `GET /api/similarity/search`
- `POST /api/similarity/manual-shape`

### Models

- `GET /api/models/movement`
- `GET /api/models/spin-breakdown`

## Standard Response Shape

```json
{
  "meta": {
    "year": 2026,
    "data_updated_at": "2026-07-02T00:00:00Z",
    "warnings": []
  },
  "summary": [],
  "charts": {},
  "tables": {}
}
```

## Versioning Rule

Keep URLs stable during MVP. If a breaking response change is needed, add a new field first, migrate frontend, then remove the old field later.
