import type { LocationQuery } from 'vue-router'

export const PANEL_QUERY_KEYS = ['object','year','player','game','date','mode'] as const
export function baseWalkQuery(query: LocationQuery): LocationQuery {
  const result={...query}
  for(const key of PANEL_QUERY_KEYS)delete result[key]
  return result
}
export function safeWalkReturn(path: unknown): path is string {
  if(typeof path!=='string' || !path.startsWith('/ballpark/play'))return false
  try {const url=new URL(path,'https://petehub.invalid');return url.origin==='https://petehub.invalid' && url.pathname==='/ballpark/play'}catch{return false}
}
