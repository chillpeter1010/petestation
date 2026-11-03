---
name: petehub-game-performance-audit
description: Measure or review Petehub Ballpark and Classic UI bundle, loading, FPS/frame time, memory cleanup, input latency, browser/device coverage, reduced-motion, and fallback behavior. Use for explicit baselines or release gates, not routine UI debugging without performance scope.
---

# Petehub Game Performance Audit

Produce reproducible measurements, not aspirational pass claims. Baselines describe the current site; later budgets are compared against them.

## Workflow

1. Read the active Ballpark Slice and inspect the current package, Nuxt config, routes, auth flow, and available browser tooling.
2. Read [references/audit-protocol.md](references/audit-protocol.md) before collecting a baseline or release-gate result.
3. Freeze the environment, build/commit state, server mode, route, viewport, browser, cache/auth state, sample duration, and repetition count.
4. Measure Classic UI first. Then measure only the runtime or scene authorized by the active Slice.
5. Separate measured values, inferred observations, budgets, unsupported APIs, unavailable devices, and blocked auth flows.
6. Preserve raw machine-readable evidence where practical and summarize it in the Ballpark main document.

## Required Inputs

- Active Slice, current worktree identity, and server/build command.
- Browser/channel/version, viewport/device characteristics, auth state, and network/cache conditions.
- Routes/scenes and accessibility/fallback modes under test.
- Metric definition and sampling/repetition method.

## Output

Report bundle transfer/raw sizes, navigation/loading metric, FPS or frame-time samples where animation exists, idle and post-route memory observations, listener/cleanup evidence, input behavior, console errors, browser/device matrix, auth scope, limitations, reproduction commands, and future budgets as a separate field.

## Prohibited

- Do not mark a browser, device, authenticated route, or metric passed without executing it.
- Do not substitute a desktop viewport resize for real low-end device evidence.
- Do not compare dev-server timings to production-build budgets without labeling the mode.
- Do not hide failed runs, unsupported APIs, warm-cache state, or worktree changes.
- Do not start a later Section or add a runtime dependency to obtain an A4 baseline.

## Validation

Repeat samples when feasible, retain raw evidence, reconcile bundle files with the build output, check desktop/narrow keyboard and reduced-motion behavior, inspect severe console errors, and verify route unmount/cleanup. Mark gaps `limited`, `unavailable`, or `blocked` with the reason.
