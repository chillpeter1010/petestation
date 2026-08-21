import type { ComparisonOverviewResponse } from '~/types/api'

export function useComparisonAdvantages(overview: Ref<ComparisonOverviewResponse | null>) {
  const leftAdvantages = computed<Record<string, unknown>[]>(() => {
    const advantages = overview.value?.charts?.advantages as { left?: Record<string, unknown>[] } | undefined
    return advantages?.left || []
  })

  const rightAdvantages = computed<Record<string, unknown>[]>(() => {
    const advantages = overview.value?.charts?.advantages as { right?: Record<string, unknown>[] } | undefined
    return advantages?.right || []
  })

  return { leftAdvantages, rightAdvantages }
}
