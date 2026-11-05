import type { BatterZoneRatesResponse } from '~/types/api'
import { heatColor } from './heatmapPalette'

export type BatterHeatmapOverlay = { data: BatterZoneRatesResponse; metric: string; context: string }

export function zoneRateScale(metric: string): number { return metric === 'woba' ? 2 : metric === 'avg' ? 1 : 100 }

export function formatZoneRate(value: number | null | undefined, metric: string): string {
  if (value == null || !Number.isFinite(value)) return '—'
  return metric === 'avg' || metric === 'woba' ? value.toFixed(3).replace(/^0\./, '.') : `${value.toFixed(1)}%`
}

// Fixed scale per metric; zero is a real cool color, null is no data.
export function zoneRateColor(value: number | null, metric = 'swing'): string {
  if (value === null || !Number.isFinite(value)) return '#64748b'
  return heatColor(Math.max(0, Math.min(1, value / zoneRateScale(metric))))
}

export type ZoneContourBand = { id: string; bounds: [number, number, number, number]; color: string; opacity: number }

// In game PR palette is deliberately more saturated; Personal's palette stays intact.
export function zonePRColor(pr: number): string {
  const t = Math.max(0, Math.min(1, pr / 100))
  const from = t < .5 ? [0, 80, 255] : [250, 250, 255]
  const to = t < .5 ? [250, 250, 255] : [255, 20, 45]
  const blend = t < .5 ? t * 2 : (t - .5) * 2
  return `rgb(${from.map((v, i) => Math.round(v + (to[i] - v) * blend)).join(',')})`
}

// Display interpolation of zone aggregates, not pitch-level KDE or new statistics.
// Smooth comparable same-zone PR values; never paint missing/low-support cells.
export function buildZoneRateContours(cells: BatterZoneRatesResponse['cells'], metric: string): ZoneContourBand[] {
  const valid = cells.filter(c => c.rates[metric]?.color_pr != null && c.rates[metric].benchmark_status === 'ready')
  if (!valid.length) return []
  const xMin = Math.min(...valid.map(c => c.bounds[0])), xMax = Math.max(...valid.map(c => c.bounds[2]))
  const zMin = Math.min(...valid.map(c => c.bounds[1])), zMax = Math.max(...valid.map(c => c.bounds[3]))
  const bins = 48, dx = (xMax - xMin) / bins, dz = (zMax - zMin) / bins
  const bands: ZoneContourBand[] = []
  for (let row = 0; row < bins; row++) {
    const z = zMin + (row + .5) * dz
    let run: ZoneContourBand | null = null
    for (let col = 0; col < bins; col++) {
      const x = xMin + (col + .5) * dx
      const host = valid.find(c => x >= c.bounds[0] && x <= c.bounds[2] && z >= c.bounds[1] && z <= c.bounds[3])
      if (!host) { run = null; continue }
      // Outside aggregates are a narrow context halo, not a full painted wall.
      const outsideDistance = Math.hypot(Math.max(0, -x, x-1), Math.max(0, -z, z-1))
      if (host.region === 'outside' && outsideDistance >= .28) { run = null; continue }
      let score = 0, totalWeight = 0
      for (const cell of valid) {
        if (cell.region !== host.region) continue
        const [a, b, c, d] = cell.bounds
        const distance = ((x - (a+c)/2) / .22) ** 2 + ((z - (b+d)/2) / .22) ** 2
        if (distance > 9) continue
        const weight = Math.exp(-distance / 2) / ((c-a) * (d-b)) * Math.min(cell.rates[metric].denominator, 50)
        score += cell.rates[metric].color_pr! * weight
        totalWeight += weight
      }
      if (!totalWeight) { run = null; continue }
      const level = Math.round(Math.max(0, Math.min(100, score / totalWeight)) / 10) * 10
      const fade = host.region === 'outside' ? .55 * (1 - outsideDistance / .28) ** 1.2 : 1
      const color = zonePRColor(level), opacity = Math.round(.86 * fade * 24) / 24
      if (!opacity) { run = null; continue }
      if (run && run.color === color && run.opacity === opacity) run.bounds[2] = xMin + (col+1) * dx
      else {
        run = { id: `${row}-${col}`, bounds: [xMin+col*dx, zMin+row*dz, xMin+(col+1)*dx, zMin+(row+1)*dz], color, opacity }
        bands.push(run)
      }
    }
  }
  return bands
}
