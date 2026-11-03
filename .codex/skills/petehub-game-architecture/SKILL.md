---
name: petehub-game-architecture
description: Design or review Petehub Ballpark integration boundaries, route ownership, lazy loading, DOM-to-game-runtime responsibilities, fallbacks, and versioned saves. Use only for Ballpark architecture work, not ordinary Nuxt feature development or engine implementation.
---

# Petehub Game Architecture

Keep Ballpark optional and isolated from Petehub's Classic UI. Apply this skill when a task changes how Nuxt, a game runtime, Babylon experiments, or FastAPI cooperate.

## Workflow

1. Read `docs/PETEHUB_BALLPARK_GAME_SYSTEM.md` and the relevant tracker Slice. Treat the tracker as the status authority.
2. Identify the route owner, render owner, data owner, persistence owner, and fallback before proposing code.
3. Read [references/boundaries-and-contracts.md](references/boundaries-and-contracts.md) when defining a runtime boundary, overlay, save/version contract, or release gate.
4. Inspect the current Nuxt route, middleware, API contract, and cleanup behavior; do not infer them from the roadmap.
5. Produce the smallest contract or implementation needed for the active Slice and record assumptions separately from verified behavior.

## Required Inputs

- Active Slice and permitted dependencies.
- Existing route/auth/API behavior and direct-link expectations.
- Target device, accessibility, and fallback requirements.
- Existing save/schema versions when persistence is involved.

## Output

State component ownership, load/unload lifecycle, URL and focus behavior, data/version boundaries, failure fallback, and verification evidence. A design must keep Classic UI deep links usable without entering Ballpark.

## Prohibited

- Do not place a game engine in the global app shell before its tracker gate passes.
- Do not make Canvas/WebGL own tables, forms, accessible text, authentication, or router state.
- Do not duplicate backend formulas or create a second semantic API for the same feature.
- Do not add Phaser before A4, or Babylon/Havok before F2; do not introduce Unity or Godot without a new approved decision.
- Do not treat walking to a zone as the only way to reach a core feature.

## Validation

Verify direct URL, refresh/back, auth redirect, keyboard focus return, reduced-motion, low-performance fallback, lazy loading, route unmount cleanup, and initial Classic UI bundle isolation. Report unavailable checks rather than claiming them passed.
