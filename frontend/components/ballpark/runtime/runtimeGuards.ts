// Pure lifecycle/input contracts: no DOM, rendering or saved account state.
export function createRuntimeLoadGate() {
  let active: AbortController | undefined
  return {
    start() { active?.abort(); active = new AbortController(); return active.signal },
    cancel() { active?.abort(); active = undefined },
    isCurrent(signal: AbortSignal) { return active?.signal === signal && !signal.aborted }
  }
}

export function createGamepadGate() {
  let waitingForNeutral = true, wasPressed = false
  return {
    block() { waitingForNeutral = true; wasPressed = false },
    sample(x: number, y: number, pressed: boolean) {
      x = Number.isFinite(x) && Math.abs(x) > .18 ? Math.max(-1, Math.min(1, x)) : 0
      y = Number.isFinite(y) && Math.abs(y) > .18 ? Math.max(-1, Math.min(1, y)) : 0
      if (waitingForNeutral) {
        if (!x && !y && !pressed) waitingForNeutral = false
        return { x: 0, y: 0, interact: false }
      }
      const interact = pressed && !wasPressed
      wasPressed = pressed
      return { x, y, interact }
    }
  }
}
