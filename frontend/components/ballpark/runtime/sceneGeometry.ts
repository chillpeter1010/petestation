export type Point = readonly [number, number]
export type CollisionShape = { id: string; polygon: readonly Point[] }
export type Footprint = { half_width: number; height: number }

export function pointInPolygon(x: number, y: number, polygon: readonly Point[]) {
  let inside = false
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const [ax, ay] = polygon[i]!
    const [bx, by] = polygon[j]!
    if ((ay > y) !== (by > y) && x < (bx - ax) * (y - ay) / (by - ay) + ax) inside = !inside
  }
  return inside
}

export function canStand(x: number, y: number, shapes: readonly CollisionShape[], foot: Footprint, world: readonly number[]) {
  const left = x - foot.half_width, right = x + foot.half_width, top = y - foot.height
  if (left < 0 || right > world[0]! || top < 0 || y > world[1]!) return false
  return !shapes.some(({ polygon }) => {
    if (polygon.every(p => p[0] <= left) || polygon.every(p => p[0] >= right) ||
        polygon.every(p => p[1] <= top) || polygon.every(p => p[1] >= y)) return false
    if ([[left, top], [right, top], [right, y], [left, y]].some(p => pointInPolygon(p[0]!, p[1]!, polygon))) return true
    // Clip each polygon edge against the foot rectangle. Handles concave polygons,
    // thin fences and crossings with no vertex inside the other shape.
    return polygon.some(([ax, ay], i) => {
      const [bx, by] = polygon[(i + 1) % polygon.length]!
      let low = 0, high = 1
      for (const [origin, delta, min, max] of [[ax, bx - ax, left, right], [ay, by - ay, top, y]]) {
        if (delta === 0) { if (origin! <= min! || origin! >= max!) return false }
        else {
          const a = (min! - origin!) / delta!, b = (max! - origin!) / delta!
          low = Math.max(low, Math.min(a, b)); high = Math.min(high, Math.max(a, b))
          if (low >= high) return false
        }
      }
      return low < high
    })
  })
}

export function moveOnScene(x: number, y: number, dx: number, dy: number, shapes: readonly CollisionShape[], foot: Footprint, world: readonly number[]) {
  const steps = Math.max(1, Math.ceil(Math.max(Math.abs(dx), Math.abs(dy)) / 2))
  for (let i = 0; i < steps; i++) {
    if (canStand(x + dx / steps, y, shapes, foot, world)) x += dx / steps
    if (canStand(x, y + dy / steps, shapes, foot, world)) y += dy / steps
  }
  return { x, y }
}
