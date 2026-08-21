export interface LinearRegressionResult {
  n: number
  correlation: number
  rSquared: number
  slope: number
  intercept: number
  pValue: number
  significant: boolean
}

export function linearRegression(points: Array<{ x: number; y: number }>): LinearRegressionResult | null {
  if (points.length < 3) return null

  const n = points.length
  const meanX = points.reduce((sum, point) => sum + point.x, 0) / n
  const meanY = points.reduce((sum, point) => sum + point.y, 0) / n
  let sumXX = 0
  let sumYY = 0
  let sumXY = 0
  for (const point of points) {
    const dx = point.x - meanX
    const dy = point.y - meanY
    sumXX += dx * dx
    sumYY += dy * dy
    sumXY += dx * dy
  }
  if (sumXX === 0 || sumYY === 0) return null

  const correlation = Math.max(-1, Math.min(1, sumXY / Math.sqrt(sumXX * sumYY)))
  const rSquared = correlation * correlation
  const slope = sumXY / sumXX
  const intercept = meanY - slope * meanX
  const tStatistic = Math.abs(correlation) === 1
    ? Number.POSITIVE_INFINITY
    : Math.abs(correlation) * Math.sqrt((n - 2) / Math.max(1 - rSquared, Number.EPSILON))
  const pValue = Number.isFinite(tStatistic) ? studentTTwoSidedPValue(tStatistic, n - 2) : 0

  return { n, correlation, rSquared, slope, intercept, pValue, significant: pValue < 0.05 }
}

function studentTTwoSidedPValue(tStatistic: number, degreesOfFreedom: number) {
  const x = degreesOfFreedom / (degreesOfFreedom + tStatistic * tStatistic)
  return regularizedIncompleteBeta(x, degreesOfFreedom / 2, 0.5)
}

function regularizedIncompleteBeta(x: number, a: number, b: number) {
  if (x <= 0) return 0
  if (x >= 1) return 1
  const logTerm = logGamma(a + b) - logGamma(a) - logGamma(b) + a * Math.log(x) + b * Math.log(1 - x)
  const factor = Math.exp(logTerm)
  if (x < (a + 1) / (a + b + 2)) return factor * betaContinuedFraction(a, b, x) / a
  return 1 - factor * betaContinuedFraction(b, a, 1 - x) / b
}

function betaContinuedFraction(a: number, b: number, x: number) {
  const maxIterations = 200
  const epsilon = 3e-12
  const tiny = 1e-30
  const qab = a + b
  const qap = a + 1
  const qam = a - 1
  let c = 1
  let d = 1 - qab * x / qap
  if (Math.abs(d) < tiny) d = tiny
  d = 1 / d
  let result = d

  for (let m = 1; m <= maxIterations; m += 1) {
    const m2 = 2 * m
    let aa = m * (b - m) * x / ((qam + m2) * (a + m2))
    d = 1 + aa * d
    if (Math.abs(d) < tiny) d = tiny
    c = 1 + aa / c
    if (Math.abs(c) < tiny) c = tiny
    d = 1 / d
    result *= d * c
    aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
    d = 1 + aa * d
    if (Math.abs(d) < tiny) d = tiny
    c = 1 + aa / c
    if (Math.abs(c) < tiny) c = tiny
    d = 1 / d
    const delta = d * c
    result *= delta
    if (Math.abs(delta - 1) < epsilon) break
  }
  return result
}

function logGamma(value: number): number {
  const coefficients = [
    676.5203681218851, -1259.1392167224028, 771.3234287776531,
    -176.6150291621406, 12.507343278686905, -0.13857109526572012,
    9.984369578019572e-6, 1.5056327351493116e-7
  ]
  if (value < 0.5) return Math.log(Math.PI) - Math.log(Math.sin(Math.PI * value)) - logGamma(1 - value)
  let adjusted = value - 1
  let series = 0.9999999999998099
  coefficients.forEach((coefficient, index) => { series += coefficient / (adjusted + index + 1) })
  const t = adjusted + coefficients.length - 0.5
  return 0.5 * Math.log(2 * Math.PI) + (adjusted + 0.5) * Math.log(t) - t + Math.log(series)
}
