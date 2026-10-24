# Petehub Baseball Analytics Platform

Petehub is a baseball analytics platform migrated from a Streamlit prototype into a separated Nuxt 3 frontend and FastAPI backend. The project focuses on pitcher analysis, game-level pitching lines, matchup comparison, outing reports, catcher-pitcher sequencing, and model-ready baseball data workflows.

This repository is intended as a portfolio version of the project. Full MLB pitch data, DuckDB caches, derived parquet exports, and video lookup artifacts are excluded because of size and data-source constraints.

## Project Highlights

- Pitcher Personal page with rotation, stuff, sequence, discipline, and outing report views.
- Pitcher comparison and period comparison workflows.
- Game Center with daily game pitching lines and outing-report links.
- Rotation and bullpen role modules with fatigue-lab prototypes.
- Catcher Station prototype with catcher-pitcher sequence analysis.
- Nuxt 3 + Vue 3 + TypeScript frontend separated from a FastAPI + Python backend.
- DuckDB / derived-data workflow for local analytics and model output serving.

## Tech Stack

- Frontend: Nuxt 3, Vue 3, TypeScript, Pinia, custom chart components.
- Backend: FastAPI, Python, Pydantic, DuckDB, pandas, NumPy.
- Data workflow: local DuckDB caches, derived exports, model-score tables, video lookup tables.
- Architecture style: frontend/backend separation, API-first page data, staged migration from legacy Streamlit.

## Repository Layout

```txt
frontend/       Nuxt 3 application and interactive visualizations
backend/        FastAPI application, services, tests, and API routes
docs/           migration notes, workflow docs, API contracts
design-system/  design notes and page-level UI specifications
data/           local-only data directory; see data/README.md
ARCHITECTURE.md high-level architecture notes
```

Current project and Slice status lives in `docs/PROJECT_TRACKER.json`. New conversations should start from `docs/NEXT_CHAT_HANDOFF.md`; historical workboards and long-form progress are kept under `docs/archive/` and are not current authorities.

## Local Setup

### Backend

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open:

```txt
http://127.0.0.1:3000
```

The frontend expects the backend API at:

```txt
http://127.0.0.1:8000/api
```

You can override this with `NUXT_PUBLIC_API_BASE`.

## Environment

Copy `.env.example` to `.env` for local backend settings. The frontend can use `NUXT_PUBLIC_API_BASE` when a non-default API URL is needed.

```powershell
Copy-Item .env.example .env
```

## Data Notice

Full data files are not committed to this portfolio repository. Local development expects data under:

```txt
data/
```

See [data/README.md](data/README.md) for the expected local data layout and excluded artifact types.

## Current Status

This project is under active migration from a legacy Streamlit codebase. The most complete areas are pitcher analysis, period comparison, outing reports, rotation/bullpen workflows, and game pitching lines. Hitter and fielder stations are staged for future expansion.

## Portfolio Story

This project demonstrates how a data-heavy sports analytics prototype can be refactored into a more maintainable web product:

- Streamlit prototype logic is split into frontend UI, backend services, and derived-data jobs.
- Baseball analysis modules are being converted into reusable components and API contracts.
- Long-running updates, video lookup, and model exports are being separated from public page rendering.
