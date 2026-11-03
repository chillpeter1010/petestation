# Motion data contract

Read this reference when a task maps baseball data to a camera, rig, animation clip, or event timeline.

## Mode boundary

- **Historical replay:** renders an identified recorded pitch/event from immutable source data. It may interpolate for display but must preserve the source payload and identity.
- **Synthetic simulation:** produces versioned events from explicit inputs, model version, and seed. It must not be stored or labeled as observed Statcast.
- **Presentation preview:** demonstrates an asset or interaction without claiming baseball fidelity. Use visibly generic inputs.

Mode must be explicit in the schema, cache key, UI label, and exported event log.

## Coordinates and view

Keep the canonical source coordinate system unchanged. Add a separate render transform containing units, origin, axes, handedness/view transform, camera, and calibration version. Never overwrite source coordinates with screen or engine coordinates.

Mirroring is a render or asset operation, not a mutation of field/pitch coordinates. Validate all four pitcher/batter handedness combinations. Author a separate variant when mirroring would reverse text, equipment, lead limbs, asymmetrical uniforms, or mechanics.

## Event synchronization

Animation state may emit named `release` and `contact` events. The data/physics layer owns the ball path and result; the animation layer consumes the event time and visual transform. Define behavior for miss, take, check swing, foul/contact, seek, pause, replay, and dropped frames. Do not derive a new physical result from visual frame drift.

## Fallback tiers

Use player-specific motion only with traceable source coverage. Otherwise fall back explicitly to handed generic stance/motion, then a neutral generic preset. Missing height, stance, arm slot, body shape, or clip coverage remains missing metadata and must be visible in evidence or UI disclosure.
