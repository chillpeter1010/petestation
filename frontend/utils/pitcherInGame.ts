export type InGameRow = Record<string, unknown>
// A PA comparison must not reveal future pitches, even in the same PA.
export function replayComparisonRows(rows:InGameRow[],selected:InGameRow|null,scope:'pa'|'game'):InGameRow[]{
  if(!selected)return []
  return rows.filter(row=>{
    if(String(row.game_pk)!==String(selected.game_pk)||String(row.pitcher)!==String(selected.pitcher))return false
    if(scope==='game')return true
    const pitch=Number(row.pitch_number),current=Number(selected.pitch_number)
    return String(row.at_bat_number)===String(selected.at_bat_number)&&Number.isInteger(pitch)&&pitch>0&&Number.isInteger(current)&&pitch<current
  })
}
// Use unfiltered game rows and exact pitch_number-1; never jump across a PA or a gap.
export function previousReplayPitch(rows:InGameRow[],selected:InGameRow):{key:string|null;label:string}{
  const number=Number(selected.pitch_number)
  if(number===1)return {key:'__first__',label:'First pitch · no previous pitch'}
  if(!Number.isInteger(number)||number<2)return {key:null,label:'Previous pitch unavailable'}
  const previous=rows.find(row=>Number(row.game_pk)===Number(selected.game_pk)&&Number(row.pitcher)===Number(selected.pitcher)&&Number(row.at_bat_number)===Number(selected.at_bat_number)&&Number(row.pitch_number)===number-1)
  const name=typeof previous?.pitch_name==='string'?previous.pitch_name.trim():''
  return name?{key:name,label:name}:{key:null,label:'Previous pitch unavailable'}
}
export type InGameOuting = { gamePk: number; date: string; label: string }
export type InGameFilters = Record<'stand' | 'count' | 'pitch' | 'pitchResult' | 'inPlayResult' | 'paResult' | 'catcher', string>

export function inGamePitchDetails(row: InGameRow | null) {
  const fields = [
    ['game_date', 'Date'], ['game_pk', 'Game'], ['at_bat_number', 'PA'], ['pitch_number', 'Pitch #'],
    ['pitcher_name', 'Pitcher'], ['batter_name', 'Batter'], ['pitch_name', 'Pitch'], ['release_speed', 'Velocity (mph)'],
    ['balls', 'Balls'], ['strikes', 'Strikes'], ['description', 'Pitch result'], ['events', 'PA result'],
    ['stand', 'Batter side'], ['p_throws', 'Throws'], ['catcher_name', 'Catcher'],
    ['release_extension', 'Extension (ft)'], ['release_pos_x', 'Release X (ft)'],
    ['release_pos_y', 'Release Y (ft)'], ['release_pos_z', 'Release Z (ft)'],
    ['plate_x', 'Plate X (ft)'], ['plate_z', 'Plate Z (ft)'],
    ['pitch_stuff_plus', 'Stuff+'], ['location_plus_pitch', 'Location+'], ['stamina_plus_trait', 'Stamina+'],
    ['stamina_expected_retention_delta', 'Expected delta'], ['stamina_expected_stuff_plus', 'Expected Stuff+']
  ]
  return fields.map(([key, label]) => {
    const value = row?.[key]
    return { key, label, value: value === null || value === undefined || value === '' || ['None', 'nan', 'NaN', 'null'].includes(String(value))
      ? '—' : typeof value === 'number' && !Number.isInteger(value) ? value.toFixed(3) : String(value) }
  })
}

export function inGamePitchVideoUrl(row: InGameRow | null): string {
  const valid = (value: unknown) => { const text = String(value || '').trim(); return text && !['None', 'nan', 'NaN', 'null'].includes(text) ? text : '' }
  const direct = valid(row?.video_url), playId = valid(row?.play_id)
  return direct || (playId ? `https://baseballsavant.mlb.com/sporty-videos?playId=${encodeURIComponent(playId)}` : '')
}

export function inGameOutings(rows: InGameRow[]): InGameOuting[] {
  const sorted = rows.flatMap(row => {
    const gamePk = Number(row['Game PK'])
    if (!Number.isSafeInteger(gamePk) || gamePk <= 0) return []
    const date = String(row.Date || '').slice(0, 10)
    const label = String(row.Label || `${date || 'Unknown date'} vs ${row.Opponent || '—'}`)
    return [{ gamePk, date, label: `${label} · Game ${gamePk}` }]
  }).sort((left, right) => right.date.localeCompare(left.date) || right.gamePk - left.gamePk)
  return sorted.filter((row, index) => sorted.findIndex(other => other.gamePk === row.gamePk) === index)
}

export function initialInGameOuting(rows: InGameOuting[], requested?: number): number | null {
  return rows.find(row => row.gamePk === requested)?.gamePk ?? rows[0]?.gamePk ?? null
}

export function matchesInGameFilters(row: InGameRow, filters: InGameFilters): boolean {
  const selected = (value: string) => value === 'All' || !value ? [] : value.split(',').map(item => item.trim()).filter(Boolean)
  const columns: Array<[keyof InGameFilters, string]> = [
    ['stand', 'stand'], ['pitch', 'pitch_name'], ['pitchResult', 'pitch_result_group'],
    ['inPlayResult', 'in_play_result_group'], ['paResult', 'pa_result_group'], ['catcher', 'catcher_name']
  ]
  for (const [filter, column] of columns) {
    const values = selected(filters[filter])
    const value = String(row[column] || (filter.endsWith('Result') ? 'Other' : ''))
    if (values.length && !values.includes(filter === 'stand' ? value.toUpperCase() : value)) return false
  }
  const counts = selected(filters.count)
  if (!counts.length) return true
  const balls = Number(row.balls), strikes = Number(row.strikes)
  return counts.some(value => value === 'Pitcher Ahead' ? strikes > balls
    : value === 'Hitter Ahead' ? balls > strikes
    : value === 'Two Strikes' ? strikes === 2 : value === `${balls}-${strikes}`)
}
