export const useAnalysisFilters = defineStore('analysisFilters', {
  state: () => ({
    year: 2026,
    role: 'SP',
    team: '',
    pitcherId: null as number | null,
    pitchTypes: [] as string[],
    stand: 'All'
  })
})
