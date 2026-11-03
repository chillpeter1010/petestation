import type { BallparkAvatarV1 } from '~/composables/useAuth'
import kit from '~/assets/ballpark/characters/character-kit-v1.json'

// Team identity colors match backend/app/services/team_dashboard_service.py.
// These are pixel-uniform colorways, not replicas of official jersey artwork.
const TEAM_COLORS: Record<string, [string, string]> = {
  ATH: ['#003831', '#efb21e'], AZ: ['#a71930', '#000000'], ATL: ['#ce1141', '#13274f'],
  BAL: ['#df4601', '#27251f'], BOS: ['#bd3039', '#0c2340'], CHC: ['#0e3386', '#cc3433'],
  CIN: ['#c6011f', '#27251f'], CLE: ['#e50022', '#00385d'], COL: ['#33006f', '#c4ced4'],
  CWS: ['#27251f', '#c4ced4'], DET: ['#0c2340', '#fa4616'], HOU: ['#002d62', '#eb6e1f'],
  KC: ['#004687', '#bd9b60'], LAA: ['#ba0021', '#003263'], LAD: ['#005a9c', '#ef3e42'],
  MIA: ['#00a3e0', '#ef3340'], MIL: ['#12284b', '#ffc52f'], MIN: ['#002b5c', '#d31145'],
  NYM: ['#002d72', '#ff5910'], NYY: ['#0c2340', '#c4ced4'], PHI: ['#e81828', '#002d72'],
  PIT: ['#27251f', '#fdb827'], SD: ['#2f241d', '#ffc425'], SEA: ['#0c2c56', '#005c5c'],
  SF: ['#fd5a1e', '#27251f'], STL: ['#c41e3a', '#0c2340'], TB: ['#092c5c', '#8fbce6'],
  TEX: ['#003278', '#c0111f'], TOR: ['#134a8e', '#e8291c'], WSH: ['#ab0003', '#14225a']
}

export function ballparkCharacterColors(avatar: BallparkAvatarV1, favoriteTeam?: string | null) {
  const team = TEAM_COLORS[favoriteTeam || '']
  return {
    skin: kit.palettes.skin[avatar.body_id],
    uniform: team ? avatar.uniform_id === 'neutral_home' ? team[0] : '#c4ced4' : kit.palettes.uniform[avatar.uniform_id],
    accent: team ? avatar.uniform_id === 'neutral_home' ? team[1] : team[0] : kit.palettes.accent[avatar.palette_id]
  }
}
