# Boundaries and contracts

Read this reference only for Ballpark integration, overlay, persistence, or release-gate work.

## Ownership matrix

| Concern | Owner | Boundary |
|---|---|---|
| Website shell, navigation, auth, forms, tables, accessible content | Nuxt/Vue | Remains usable as Classic UI and direct URL |
| Optional 2D/2.5D world, movement, camera, collision, zone prompts | Lazy-loaded Phaser candidate | Mount only inside the Ballpark route after the relevant gate |
| Experimental 3D motion scene | Lazy-loaded Babylon candidate | Consider only after F2; never a global dependency |
| APIs, source data, ratings, deterministic simulation, Monte Carlo | FastAPI/Python | No browser frame loop or presentation ownership |
| Overlay routing, focus, close/back and deep links | Nuxt bridge | One URL owner; world pauses or yields input while overlay is active |

## Lifecycle contract

- The Ballpark route owns creation and destruction of its runtime instance.
- Lazy chunks, animation loops, observers, input listeners, timers, audio, workers, and GPU resources need explicit cleanup evidence.
- Leaving the route must not leave a second router state, active input handler, or background loop.
- Runtime failure, unsupported capability, reduced-motion preference, or a low-performance gate returns the user to an equivalent Classic UI path.

## Save/version contract

Persist only versioned domain state, never live engine objects. Include a schema version, migration rule, safe default, invalid-save recovery, and server/client ownership. Keep secrets and authoritative competitive outcomes off client saves. Refresh, re-login, and application upgrade must have specified reconciliation behavior.

## Decision record minimum

Record the active Slice, evidence, chosen owner, lazy-load boundary, fallback URL, cleanup checks, schema/version impact, and rejected alternatives. Future targets are budgets, not measured passes.
