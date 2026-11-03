---
name: petehub-baseball-motion
description: Define or review Petehub baseball motion contracts involving Statcast coordinates, handedness, mirroring, release/contact events, replay-versus-simulation semantics, and explicit generic fallbacks. Do not use for general chart animation or unrelated baseball analysis.
---

# Petehub Baseball Motion

Preserve source baseball data while synchronizing visual motion to it. Motion is presentation and event timing; it must not rewrite the trajectory, outcome, or research result.

## Workflow

1. Read the active Slice in `docs/PETEHUB_BALLPARK_GAME_SYSTEM.md` and inspect the current trajectory or simulation contract.
2. Classify the mode as historical replay, synthetic simulation, or presentation-only preview before naming events.
3. Read [references/motion-data-contract.md](references/motion-data-contract.md) for coordinate, mirroring, event, and fallback decisions.
4. Inventory the available handedness, bio, stance, motion, and calibration fields. Label missing fields; do not infer precision from unrelated measurements.
5. Define an event timeline and visual transform that can be tested against immutable source values.

## Required Inputs

- Mode and versioned source/event identity.
- Coordinate system, camera/view transform, handedness, and units.
- Available rig/clips and player-specific metadata coverage.
- Expected release/contact semantics and playback controls.

## Output

Provide the unchanged source fields, explicit render transform, handedness/mirroring rule, named animation events, fallback tier, and reconciliation tests. Keep historical and simulated payloads distinguishable in schemas and UI labels.

## Prohibited

- Do not alter Statcast coordinates, pitch path, contact point, outcome, or research conclusion to fit animation.
- Do not call `pitch_trajectory_statcast_v1` a motion simulation.
- Do not infer height from release point or invent stance/motion detail.
- Do not silently mirror handedness when asymmetric clips, equipment, or field coordinates require authored variants.
- Do not present a generic fallback as player-specific likeness.

## Validation

Test left/right pitchers and batters, mode labels, release/contact event ordering, pause/seek/replay determinism, source-coordinate reconciliation, missing-data fallback, and reduced-motion behavior. Record tolerances and unavailable source fields.
