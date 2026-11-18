export type ReleasePerspective = 'front' | 'back'
export function releaseNumber(value: unknown): number | null {
  if ((typeof value !== 'number' && typeof value !== 'string') || (typeof value === 'string' && !value.trim())) return null
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

// Canonical Statcast feet, catcher perspective. Views change display only.
export function pitchReleaseGuide(row: Record<string, unknown>, perspective: ReleasePerspective) {
  const raw = releaseNumber(row.arm_angle)
  const angle = raw != null && raw >= -90 && raw <= 90 ? raw : null
  const x = releaseNumber(row.release_pos_x), y = releaseNumber(row.release_pos_y), z = releaseNumber(row.release_pos_z)
  const extension = releaseNumber(row.release_extension)
  const hand = row.p_throws === 'R' || row.p_throws === 'L' ? row.p_throws : null
  const mirror = perspective === 'front' ? 1 : -1
  const project = (px: number, pz: number) => ({ x: 200 + mirror * px * 25, y: 295 - pz * 25 })
  const release = x != null && z != null ? project(x, z) : null
  // Only the ball point and angle are measured. Shoulder and 2-ft arm are a diagram.
  const radians = angle == null ? null : angle * Math.PI / 180
  const direction = hand === 'R' ? -1 : 1
  const shoulder = release && radians != null && hand ? project(x! - direction * 2 * Math.cos(radians), z! - 2 * Math.sin(radians)) : null
  const centreX = shoulder ? shoulder.x - mirror * direction * .55 * 25 : null
  return { angle, hand, x, y, z, extension, release, shoulder, centreX, mirror }
}
