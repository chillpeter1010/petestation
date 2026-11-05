function interpolateColor(from: [number, number, number], to: [number, number, number], t: number) {
  const channels = from.map((value, index) => Math.round(value + (to[index] - value) * t))
  return `rgb(${channels[0]}, ${channels[1]}, ${channels[2]})`
}

// Shared with Personal Discipline: identical palette and eight contour levels.
export function heatColor(value: number) {
  const clamped = Math.max(0, Math.min(1, value))
  if (clamped < 0.33) return interpolateColor([15, 23, 96], [37, 99, 235], clamped / 0.33)
  if (clamped < 0.55) return interpolateColor([37, 99, 235], [239, 246, 255], (clamped - 0.33) / 0.22)
  if (clamped < 0.75) return interpolateColor([255, 237, 213], [239, 68, 68], (clamped - 0.55) / 0.2)
  return interpolateColor([239, 68, 68], [127, 29, 29], (clamped - 0.75) / 0.25)
}
export function heatStroke(value: number) { return value < 0.55 ? 'rgb(30, 64, 175)' : 'rgb(153, 27, 27)' }
export function contourLevel(value: number) {
  return [0.16, 0.28, 0.4, 0.52, 0.64, 0.76, 0.88, 1].find(level => value <= level) || 1
}
