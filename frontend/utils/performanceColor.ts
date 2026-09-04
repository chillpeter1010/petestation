type Rgb = readonly [number, number, number]

const PERFORMANCE_STOPS: Array<{ value: number; color: Rgb }> = [
  { value: -1, color: [23, 55, 110] },
  { value: -0.66, color: [45, 104, 178] },
  { value: -0.33, color: [186, 217, 239] },
  { value: 0, color: [248, 250, 252] },
  { value: 0.33, color: [252, 190, 190] },
  { value: 0.66, color: [211, 61, 65] },
  { value: 1, color: [132, 24, 35] }
]

export function performanceColor(score: number) {
  const value = Math.max(-1, Math.min(1, score))
  const upperIndex = PERFORMANCE_STOPS.findIndex(stop => value <= stop.value)
  const upper = PERFORMANCE_STOPS[Math.max(1, upperIndex)]
  const lower = PERFORMANCE_STOPS[Math.max(0, upperIndex - 1)]
  const ratio = (value - lower.value) / (upper.value - lower.value || 1)
  const channels = lower.color.map((channel, index) =>
    Math.round(channel + (upper.color[index] - channel) * ratio)
  )
  return `rgb(${channels.join(', ')})`
}

export function performanceColorStyle(score: number) {
  const value = Math.max(-1, Math.min(1, score))
  return {
    background: performanceColor(value),
    color: Math.abs(value) >= 0.58 ? '#ffffff' : '#172033'
  }
}
