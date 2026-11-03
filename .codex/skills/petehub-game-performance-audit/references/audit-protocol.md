# Audit protocol

Read this reference before a baseline, compatibility matrix, engine comparison, or release gate.

## Environment record

Capture date/timezone, OS, CPU, logical memory, power mode if known, display scale, repository/worktree state, Node/Nuxt version, build or dev command, backend availability, browser/channel/version, viewport, device scale factor, cache state, auth state, route, data identity, sample duration, and repetition count.

## Metric definitions

- **Bundle:** record emitted client JS/CSS raw and compressed sizes; distinguish initial route resources from all lazy chunks.
- **Loading:** prefer navigation timing and LCP. If LCP is unavailable, report the exact substitute and why.
- **Frames:** use timestamp deltas over a stated animated interval; report sample count, median/p95 frame time, approximate FPS, long frames, and whether the page actually contained continuous animation.
- **Memory:** use the browser API or tooling available and name it. Measure after a fixed idle settle, after route transitions, and after return/unmount. A heap snapshot or browser task-manager figure is not interchangeable with `performance.memory`.
- **Input:** record interaction and response definition; distinguish automated keyboard reachability from measured input latency.
- **Cleanup:** verify active timers/loops/listeners/resources through supported tooling or observable repeated-mount behavior. Do not claim a listener count from an unsupported API.

## Minimum matrix

Cover Chrome, Edge, and Firefox to the extent actually available; desktop and narrow viewports; normal and reduced-motion; keyboard-only navigation; unauthenticated login/redirect flow; and authenticated representative routes when credentials/session are available. Real low-end/mobile hardware remains unavailable unless actually tested.

Use `pass` only for an executed assertion. Use `limited` for partial or non-equivalent evidence, `unavailable` for missing browser/device/API, and `blocked` when auth or environment prevents the run.

## Evidence format

Raw evidence should include schema version, environment, commands, metric definitions, per-run samples, summary statistics, console messages, matrix status, limitations, and artifact paths. Keep future budgets separate from current measurements.
