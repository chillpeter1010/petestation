export function stuffLetterGrade(value: unknown) {
  const score = Number(value)
  if (!Number.isFinite(score)) return '—'
  if (score >= 125) return 'A+'
  if (score >= 115) return 'A'
  if (score >= 110) return 'A−'
  if (score >= 105) return 'B+'
  if (score >= 100) return 'B'
  if (score >= 95) return 'B−'
  if (score >= 90) return 'C+'
  if (score >= 85) return 'C'
  if (score >= 80) return 'C−'
  return 'D'
}

export function stuffGradeTone(value: unknown) {
  const score = Number(value)
  if (!Number.isFinite(score)) return 'neutral'
  if (score >= 110) return 'elite'
  if (score >= 100) return 'plus'
  if (score >= 90) return 'average'
  return 'below'
}
