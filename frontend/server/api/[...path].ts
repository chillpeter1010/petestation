import { getRequestURL, getRouterParam, proxyRequest } from 'h3'

export default defineEventHandler((event) => {
  const config = useRuntimeConfig(event)
  const path = getRouterParam(event, 'path') || ''
  const query = getRequestURL(event).search
  const base = String(config.apiInternalBase).replace(/\/$/, '')
  return proxyRequest(event, `${base}/${path}${query}`)
})
