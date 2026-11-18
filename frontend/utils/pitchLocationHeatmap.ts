import { heatColor, heatStroke, contourLevel } from './heatmapPalette'

export type PitchHeatPoint = { x:number; z:number; batSpeed:number|null; swung:boolean }
export type PitchHeatCell = { x:number; z:number; x0:number; x1:number; z0:number; z1:number; color:string; stroke:string; strokeOpacity:number; opacity:number }
export type PitchHeatMode = 'density'|'bat-speed'|'choice'

// Display X in Personal is -plate_x; the replay plane uses physical plate_x.
export function pitchHeatmapReplayBands(cells:PitchHeatCell[],bottom:number,top:number){
  const height=top-bottom
  if(!Number.isFinite(height)||height<=0)return []
  return cells.map((c,i)=>({id:`personal-${i}`,bounds:[(-c.x1+17/24)/(17/12),(c.z0-bottom)/height,(-c.x0+17/24)/(17/12),(c.z1-bottom)/height] as [number,number,number,number],color:c.color,opacity:c.opacity}))
}

// Shared verbatim Personal heatmap: per-pitch Gaussian smoothing, not zone aggregates.
export function buildPitchHeatmap(points:PitchHeatPoint[], options:{ blend:number; mode:PitchHeatMode; xDomain:readonly[number,number]; zDomain:readonly[number,number]; metricDomain?:readonly[number,number]|null }):PitchHeatCell[] {
  const {mode,xDomain,zDomain,metricDomain}=options
  const blend=Number.isFinite(options.blend)?Math.max(0,Math.min(1,options.blend)):0
  if (blend <= 0 || points.length < 8) {
    return []
  }
  const xBins = 64
  const zBins = 52
  const activeXDomain = xDomain
  const activeYDomain = zDomain
  const xStep = (activeXDomain[1] - activeXDomain[0]) / xBins
  const zStep = (activeYDomain[1] - activeYDomain[0]) / zBins
  const sigmaX = 0.18
  const sigmaZ = 0.2
  const usablePoints = points.filter((point) => (
    point.x >= activeXDomain[0]
    && point.x <= activeXDomain[1]
    && point.z >= activeYDomain[0]
    && point.z <= activeYDomain[1]
  ))
  const densityCells: Array<{ xi: number; zi: number; density: number; metric: number | null }> = []
  let maxDensity = 0

  for (let xi = 0; xi < xBins; xi += 1) {
    const xCenter = activeXDomain[0] + (xi + 0.5) * xStep
    for (let zi = 0; zi < zBins; zi += 1) {
      const zCenter = activeYDomain[0] + (zi + 0.5) * zStep
      let density = 0
      let metricTotal = 0
      let metricWeight = 0
      for (const point of usablePoints) {
        const dx = (xCenter - point.x) / sigmaX
        const dz = (zCenter - point.z) / sigmaZ
        const distanceSquared = dx * dx + dz * dz
        if (distanceSquared <= 9) {
          const weight = Math.exp(-0.5 * distanceSquared)
          density += weight
          const metricValue = mode === 'bat-speed'
            ? point.batSpeed
            : mode === 'choice'
              ? (point.swung ? 1 : 0)
              : null
          if (metricValue !== null) {
            metricTotal += metricValue * weight
            metricWeight += weight
          }
        }
      }
      if (density > 0 && (mode === 'density' || metricWeight > 0)) {
        densityCells.push({ xi, zi, density, metric: metricWeight ? metricTotal / metricWeight : null })
        maxDensity = Math.max(maxDensity, density)
      }
    }
  }

  if (!maxDensity) {
    return []
  }
  const metricValues = densityCells.map((cell) => cell.metric).filter((value): value is number => value !== null)
  const sharedDomain = metricDomain
  const metricMin = sharedDomain?.length === 2 ? Number(sharedDomain[0]) : (metricValues.length ? Math.min(...metricValues) : 0)
  const metricMax = sharedDomain?.length === 2 ? Number(sharedDomain[1]) : (metricValues.length ? Math.max(...metricValues) : 1)
  return densityCells.flatMap(({ xi, zi, density, metric }) => {
    const normalized = density / maxDensity
    if (normalized < 0.045) {
      return []
    }
    const rawColorValue = mode === 'density'
      ? Math.min(1, Math.pow(normalized, 0.58))
      : mode === 'choice'
        ? Number(metric)
        : (Number(metric) - metricMin) / (metricMax - metricMin || 1)
    const colorValue = mode === 'density' ? contourLevel(rawColorValue) : Math.max(0, Math.min(1, rawColorValue))
    return {
      x: xi,
      z: zi,
      x0: activeXDomain[0] + xi * xStep - xStep * 0.16,
      x1: activeXDomain[0] + (xi + 1) * xStep + xStep * 0.16,
      z0: activeYDomain[0] + zi * zStep - zStep * 0.16,
      z1: activeYDomain[0] + (zi + 1) * zStep + zStep * 0.16,
      color: heatColor(colorValue),
      stroke: heatStroke(colorValue),
      strokeOpacity: blend * 0.34,
      opacity: blend * (0.35 + 0.65 * Math.min(1, Math.pow(normalized, 0.5)))
    }
  })

}
