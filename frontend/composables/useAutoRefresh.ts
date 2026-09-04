export function useAutoRefresh(refresh: () => void | Promise<void>, intervalMs = 300_000) {
  if (!import.meta.client) return

  let refreshing = false
  const run = async () => {
    if (refreshing || document.visibilityState !== 'visible') return
    refreshing = true
    try {
      await refresh()
    } catch {
      // Background refresh keeps the current dashboard visible on transient failures.
    } finally {
      refreshing = false
    }
  }
  const interval = window.setInterval(() => void run(), intervalMs)
  onBeforeUnmount(() => {
    window.clearInterval(interval)
  })
}
