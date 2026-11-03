export type MlbTeam = { id: number; code: string; name: string }

export const MLB_TEAMS: MlbTeam[] = [
  { id: 133, code: 'ATH', name: 'Athletics' }, { id: 109, code: 'AZ', name: 'Diamondbacks' },
  { id: 144, code: 'ATL', name: 'Braves' }, { id: 110, code: 'BAL', name: 'Orioles' },
  { id: 111, code: 'BOS', name: 'Red Sox' }, { id: 112, code: 'CHC', name: 'Cubs' },
  { id: 113, code: 'CIN', name: 'Reds' }, { id: 114, code: 'CLE', name: 'Guardians' },
  { id: 115, code: 'COL', name: 'Rockies' }, { id: 145, code: 'CWS', name: 'White Sox' },
  { id: 116, code: 'DET', name: 'Tigers' }, { id: 117, code: 'HOU', name: 'Astros' },
  { id: 118, code: 'KC', name: 'Royals' }, { id: 108, code: 'LAA', name: 'Angels' },
  { id: 119, code: 'LAD', name: 'Dodgers' }, { id: 146, code: 'MIA', name: 'Marlins' },
  { id: 158, code: 'MIL', name: 'Brewers' }, { id: 142, code: 'MIN', name: 'Twins' },
  { id: 121, code: 'NYM', name: 'Mets' }, { id: 147, code: 'NYY', name: 'Yankees' },
  { id: 143, code: 'PHI', name: 'Phillies' }, { id: 134, code: 'PIT', name: 'Pirates' },
  { id: 135, code: 'SD', name: 'Padres' }, { id: 136, code: 'SEA', name: 'Mariners' },
  { id: 137, code: 'SF', name: 'Giants' }, { id: 138, code: 'STL', name: 'Cardinals' },
  { id: 139, code: 'TB', name: 'Rays' }, { id: 140, code: 'TEX', name: 'Rangers' },
  { id: 141, code: 'TOR', name: 'Blue Jays' }, { id: 120, code: 'WSH', name: 'Nationals' }
]

export function teamIdForCode(code: string) {
  return MLB_TEAMS.find(team => team.code === code)?.id ?? null
}

export function normalizeMlbTeamCode(value: unknown): string {
  const code = typeof value === 'string' ? value.trim().toUpperCase() : ''
  return MLB_TEAMS.some(team => team.code === code) ? code : ''
}
