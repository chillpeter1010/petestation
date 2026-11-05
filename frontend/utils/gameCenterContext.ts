import { normalizeMlbTeamCode } from '~/config/mlbTeams'

export const GAME_YEARS = [2026, 2025, 2024, 2023, 2022, 2021]
export const GAME_TABS = ['feed', 'box', 'location', 'sequence', 'movement', 'replay'] as const
export type GameTab = typeof GAME_TABS[number]
const scalar = (value: unknown) => typeof value === 'string' || typeof value === 'number' ? String(value) : ''
export function contextId(value: unknown): number | undefined {
  const n = Number(scalar(value))
  return Number.isSafeInteger(n) && n > 0 ? n : undefined
}
export function contextYear(value: unknown) { const n = Number(scalar(value)); return GAME_YEARS.includes(n) ? n : 2026 }
export function gameDate(value: unknown, year: number): string {
  const text = scalar(value)
  if (!/^\d{4}-\d{2}-\d{2}$/.test(text) || Number(text.slice(0, 4)) !== year) return ''
  const date = new Date(`${text}T00:00:00Z`)
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === text ? text : ''
}
export function gameContext(query: Record<string, unknown>) {
  const year = contextYear(query.year)
  return { year, date: gameDate(query.date, year), team: normalizeMlbTeamCode(query.team),
    gamePk: contextId(query.game_pk), pitcherId: contextId(query.pitcher_id),
    tab: GAME_TABS.includes(query.tab as GameTab) ? query.tab as GameTab : 'feed' as GameTab }
}
export function gameFitsScope(game: { game_pk?: unknown; game_date?: unknown; home_team?: unknown; away_team?: unknown } | undefined, scope: { year: number; date: string; team: string }) {
  const date = gameDate(String(game?.game_date || '').slice(0, 10), scope.year)
  return Boolean(game && contextId(game.game_pk) && date && (!scope.date || date === scope.date)
    && (!scope.team || game.home_team === scope.team || game.away_team === scope.team))
}
export function leaderboardContext(query: Record<string, unknown>) {
  const views = ['basic', 'stuff', 'location', 'pitching', 'stamina'] as const
  const tab = views.includes(query.tab as typeof views[number]) ? query.tab as typeof views[number] : 'basic'
  return { year: tab === 'stamina' ? 2026 : contextYear(query.year), team: normalizeMlbTeamCode(query.team) || 'All', tab,
    role: tab === 'stamina' ? 'SP' : query.role === 'SP' || query.role === 'RP' ? query.role : 'All' }
}
