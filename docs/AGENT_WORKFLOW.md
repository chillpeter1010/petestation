# Agent Workflow

## Ballpark manual acceptance assignment · 2026-11-02（最高優先）

- Petehub Ballpark 的所有畫面、瀏覽器、碰撞手感與互動驗收一律由使用者本人執行。
- 不得替使用者開啟或控制瀏覽器；不得使用 Playwright、playwright-interactive、CUA、computer-use 或其他瀏覽器自動化。
- 不得自行截圖、圖片比較、視覺回歸或 DOM 視覺檢查。
- 不得為畫面驗證另開 frontend server、登入 fixture、替代帳號環境或隔離 UI server。
- 不得代替使用者點擊、hover、滾動、調整視窗、改 browser zoom、走角色或測試場景碰撞。
- 不得自行宣稱畫面、碰撞、穿模、互動、響應式、路由切換或操作手感通過。只有使用者明確回報通過，才能記錄人工驗收完成。
- UI 修改完成後只回報：改了什麼、檢查網址、最多五項人工測試清單。
- TypeScript、JSON、schema、hash、syntax 或資料契約等 source-only 檢查不等於畫面驗收。
- 小型視覺修正不要反覆執行 typecheck、build 或完整 audit；只有實際涉及契約或編譯風險時才執行必要的單一檢查。
- 使用者表示驗證由他處理時，立即停止所有驗證流程並交回；不得自行開始其他 Slice。

Ballpark 工作必須保持小而精準。單一工具超過 60 秒無結果時立即止損；預估超過 10 分鐘時先拆分 Slice 並說明。未經使用者指示，不開始 D2.5、D2.6、Section E 或重新製作角色，也不得使用 subagent，除非使用者明確要求平行代理工作。

## Orchestrator

Owns scope, sequencing, and integration.

- Keeps migration slices small
- Decides which page or endpoint is next
- Checks that frontend and backend contracts match
- Prevents speculative rewrites

## Frontend Agent

Owns Nuxt UI and interaction.

- Pages and layouts
- Filter components
- Chart/table/video components
- Pinia stores
- TypeScript API types

## Backend/Data Agent

Owns API and data services.

- FastAPI routes
- Pydantic schemas
- pandas/DuckDB/PostgreSQL repositories
- Service extraction from Streamlit files
- Caching boundaries

## Model Agent

Owns model and metric logic.

- Feature engineering
- Model loading/training workflow
- Stuff/discipline/spin calculations

## QA/Debug Agent

Owns verification.

- Repro cases from old Streamlit outputs
- Backend service tests
- API smoke tests
- Frontend route and component checks

## Working Rule

For every migrated page, write the API contract before rebuilding the Nuxt page. This keeps the frontend and backend agents from coupling through hidden assumptions.

## Documentation Rule

- One small project owns one canonical human-readable Markdown document in `docs/`; Slice boundaries are sections inside that document, not separate top-level files.
- Starting or completing a Slice updates the existing project document, `PROJECT_TRACKER.json`, generated `PROJECT_TRACKER.md`, and—when cross-chat context changes—`NEXT_CHAT_HANDOFF.md`.
- Generated evidence belongs in versioned JSON, Parquet, manifests, or immutable snapshots under `data/`; builders must not generate a new `SLICE*.md` report.
- Create another top-level project document only when the tracker defines a genuinely separate project with a separate scope and lifecycle.
- Current consolidated research documents are `CATCHER_DESCRIPTIVE_METRICS.md` and `PLAYER_ARCHETYPES_PITCH_STRATEGY.md`.
