export type SiteBrandMode = 'peteclub' | 'petehub'

export function useSiteBrand() {
  const mode = useCookie<SiteBrandMode>('site-brand-mode', {
    default: () => 'peteclub',
    maxAge: 60 * 60 * 24 * 365,
    sameSite: 'lax'
  })

  const isPetehub = computed(() => mode.value === 'petehub')
  const brandName = computed(() => isPetehub.value ? 'Petehub' : 'Peteclub')

  function toggleBrand() {
    mode.value = isPetehub.value ? 'peteclub' : 'petehub'
  }

  return { mode, isPetehub, brandName, toggleBrand }
}
