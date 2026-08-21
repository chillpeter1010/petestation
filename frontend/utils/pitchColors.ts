export const defaultPitchColor = '#8b949e'

export const pitchColors: Record<string, string> = {
  '4-Seam Fastball': '#d62828',
  Fastball: '#d62828',
  'Four-Seam': '#d62828',
  '4-Seam': '#d62828',
  FF: '#d62828',
  Sinker: '#f77f00',
  SI: '#f77f00',
  Cutter: '#7f5539',
  FC: '#7f5539',
  Slider: '#ffd166',
  SL: '#ffd166',
  Changeup: '#28c97b',
  CH: '#28c97b',
  'Split-Finger': '#00a6a6',
  Splitter: '#00a6a6',
  Forkball: '#00a6a6',
  FS: '#00a6a6',
  Curveball: '#277da1',
  Curve: '#277da1',
  CU: '#277da1',
  'Knuckle Curve': '#7b2cbf',
  KC: '#7b2cbf',
  Sweeper: '#bc8a3c',
  ST: '#bc8a3c',
  Slurve: '#607d8b',
  Unknown: '#8b949e'
}

export function normalizePitchName(pitch: string | null | undefined) {
  return String(pitch || 'Unknown')
    .replace(/^Four-Seam Fastball$/i, '4-Seam')
    .replace(/^Four-Seam$/i, '4-Seam')
    .replace(/^4-Seam Fastball$/i, '4-Seam')
    .replace(/^Split-Finger Fastball$/i, 'Split-Finger')
    .replace(/^Sweeper$/i, 'ST')
}

export function getPitchColor(pitch: string | null | undefined) {
  const raw = String(pitch || 'Unknown')
  const normalized = normalizePitchName(raw)
  return pitchColors[raw] || pitchColors[normalized] || defaultPitchColor
}
