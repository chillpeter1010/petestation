<template>
  <section class="tag-lab" :aria-label="`${populationLabel} tag browser`">
    <section class="filter-panel" aria-label="Tag Lab filters">
      <label>Season
        <select v-model.number="year"><option v-for="option in years" :key="option" :value="option">{{ option }}</option></select>
      </label>
      <label v-if="population === 'pitcher'">Role
        <select v-model="role"><option value="All">All roles</option><option value="SP">SP</option><option value="RP">RP</option></select>
      </label>
      <label>Dimension
        <select v-model="dimension"><option value="All">All dimensions</option><option v-for="option in dimensionOptions" :key="option" :value="option">{{ dimensionLabel(option) }}</option></select>
      </label>
      <label>Tag
        <select v-model="tag"><option value="All">All tags</option><option v-for="option in tagOptions" :key="option" :value="option">{{ option }}</option></select>
      </label>
      <label>Support
        <select v-model="support"><option value="All">All samples</option><option value="supported">3+ tags</option><option value="review">1–2 tags</option><option value="unassigned">No tag</option></select>
      </label>
      <label class="search">Search
        <span><Search :size="16" aria-hidden="true" /><input v-model.trim="search" type="search" placeholder="Player, team, or tag"></span>
      </label>
    </section>

    <p v-if="pending" class="state-card" role="status"><strong>Loading Tag Lab…</strong><span>Reading the precomputed Slice 3 snapshot.</span></p>
    <p v-else-if="errorMessage" class="state-card error" role="alert"><strong>Tag Lab unavailable</strong><span>{{ errorMessage }}</span></p>

    <template v-else-if="payload">
      <section class="summary-grid" aria-label="Filtered sample summary">
        <article><span>Visible players</span><strong>{{ filteredRows.length.toLocaleString() }}</strong></article>
        <article><span>3+ supported tags</span><strong>{{ supportedCount.toLocaleString() }}</strong></article>
        <article><span>Average reliability</span><strong>{{ averageReliability }}</strong></article>
        <article><span>Selected tag</span><strong class="selected-summary">{{ tag === 'All' ? 'All' : tag }}</strong></article>
      </section>

      <aside class="scope-note">
        <Info :size="17" aria-hidden="true" />
        <p><strong>How to judge it:</strong> compare the tag with the player you know, then check sample and reliability. Retention describes adjacent-season agreement; it is not model accuracy or a talent grade.</p>
      </aside>

      <div class="lab-grid">
        <section class="distribution-panel" aria-labelledby="distribution-title">
          <header><div><span>Balance audit</span><h2 id="distribution-title">Tag distribution</h2></div><strong>{{ visibleDistribution.length }} tags</strong></header>
          <div class="distribution-list">
            <button
              v-for="item in visibleDistribution"
              :key="`${item.role}-${item.source}-${item.dimension}-${item.tag}`"
              type="button"
              :class="{ selected: dimension === item.dimension && tag === item.tag }"
              :aria-pressed="dimension === item.dimension && tag === item.tag"
              @click="selectTag(item)"
            >
              <span><small>{{ dimensionLabel(item.dimension) }} · {{ item.role }}</small><strong>{{ item.tag }}</strong></span>
              <span class="distribution-metrics"><b>{{ Number(item.count).toLocaleString() }}</b><small>{{ formatPct(item.eligible_share_pct) }}</small></span>
              <em v-if="item.review_flags">{{ String(item.review_flags).replaceAll(',', ' · ') }}</em>
              <em v-else class="is-clear">clear</em>
            </button>
          </div>
          <footer><button type="button" @click="clearTag">Clear tag selection</button></footer>
        </section>

        <section class="roster-panel" aria-labelledby="roster-title">
          <header>
            <div><span>Player review</span><h2 id="roster-title">{{ populationLabel }} roster</h2></div>
            <strong>{{ pageStart }}–{{ pageEnd }} of {{ filteredRows.length.toLocaleString() }}</strong>
          </header>
          <div class="table-shell" role="region" :aria-label="`Sortable ${populationLabel} tag roster`" tabindex="0">
            <table>
              <thead><tr>
                <th v-for="column in columns" :key="column.key" :aria-sort="ariaSort(column.key)"><button type="button" @click="setSort(column.key)">{{ column.label }} <ArrowUpDown :size="13" /></button></th>
              </tr></thead>
              <tbody><tr v-for="row in pageRows" :key="`${row.year}-${row.player_id}-${row.role}`">
                <td><NuxtLink class="player-cell" :to="playerLink(row)"><MlbPlayerHeadshot :player-id="Number(row.player_id)" :name="String(row.display_name)" :size="44" shape="circle" decorative /><span><strong>{{ row.display_name }}</strong><small>{{ row.team }}<template v-if="population === 'pitcher'"> · {{ row.role }}</template></small></span></NuxtLink></td>
                <td>{{ Number(row.sample_size).toLocaleString() }}</td>
                <td>{{ formatPct(Number(row.sample_reliability) * 100) }}</td>
                <td><span :class="['support-pill', `is-${row.support_status}`]">{{ supportLabel(row.support_status) }}</span></td>
                <td v-for="index in 4" :key="index"><span v-if="row[`tag_${index}`]" :class="['tag-pill', { selected: row[`tag_${index}`] === tag }]"><small>{{ dimensionLabel(row[`tag_${index}_dimension`]) }}</small>{{ row[`tag_${index}`] }}</span><span v-else class="missing">—</span></td>
              </tr></tbody>
            </table>
            <p v-if="!pageRows.length" class="empty-state">No players match the selected filters.</p>
          </div>
          <footer class="pagination"><button type="button" :disabled="page <= 1" @click="page--">Previous</button><span>Page {{ page }} / {{ totalPages }}</span><button type="button" :disabled="page >= totalPages" @click="page++">Next</button></footer>
        </section>
      </div>

      <details class="validation-panel">
        <summary>Slice 3 validation decisions and limits</summary>
        <div class="decision-grid"><article v-for="item in payload.release_decisions" :key="`${item.source}-${item.dimension}`"><span :class="`is-${item.decision}`">{{ item.decision }}</span><strong>{{ dimensionLabel(item.dimension) }}</strong><p>{{ formatPct(item.assigned_share_pct) }} assigned · {{ formatPct(item.retention_pct) }} retained</p></article></div>
        <ul><li v-for="warning in payload.warnings" :key="warning">{{ warning }}</li></ul>
      </details>
    </template>
  </section>
</template>

<script setup lang="ts">
import { ArrowUpDown, Info, Search } from '@lucide/vue'

type Row = Record<string, any>
const props = defineProps<{ population: 'pitcher' | 'batter' }>()
const api = useApi()
const route = useRoute()
const router = useRouter()
const years = [2026, 2025, 2024, 2023, 2022, 2021]
const year = ref(Number(route.query.year) || 2026)
const role = ref('All')
const dimension = ref('All')
const tag = ref('All')
const support = ref('All')
const search = ref('')
const payload = ref<Row | null>(null)
const pending = ref(false)
const errorMessage = ref('')
const sortKey = ref('sample_size')
const sortDirection = ref<'asc' | 'desc'>('desc')
const page = ref(1)
const pageSize = 50
const populationLabel = computed(() => props.population === 'pitcher' ? 'Pitcher' : 'Batter')
const coreDimensions = props.population === 'pitcher' ? ['arsenal_depth', 'primary_pair', 'arm_slot', 'command'] : ['decision', 'contact', 'damage', 'swing_shape']
const columns = [
  { key: 'display_name', label: 'Player' }, { key: 'sample_size', label: props.population === 'pitcher' ? 'Pitches' : 'PA' },
  { key: 'sample_reliability', label: 'Reliability' }, { key: 'support_status', label: 'Support' },
  { key: 'tag_1', label: 'Tag 1' }, { key: 'tag_2', label: 'Tag 2' }, { key: 'tag_3', label: 'Tag 3' }, { key: 'tag_4', label: 'Tag 4' }
]
const roleFilteredDistribution = computed<Row[]>(() => (payload.value?.distribution || []).filter((item: Row) => coreDimensions.includes(String(item.dimension)) && (role.value === 'All' || item.role === role.value)))
const dimensionOptions = computed(() => [...new Set(roleFilteredDistribution.value.map(item => String(item.dimension)))].sort())
const tagOptions = computed(() => [...new Set(roleFilteredDistribution.value.filter(item => dimension.value === 'All' || item.dimension === dimension.value).map(item => String(item.tag)).filter(Boolean))].sort())
const visibleDistribution = computed(() => roleFilteredDistribution.value.filter(item => dimension.value === 'All' || item.dimension === dimension.value).sort((left, right) => Number(right.count) - Number(left.count)))
const filteredRows = computed<Row[]>(() => {
  const needle = search.value.toLocaleLowerCase()
  return sortedRows((payload.value?.roster || []).filter((row: Row) => {
    const tags = [1, 2, 3, 4].map(index => ({ dimension: row[`tag_${index}_dimension`], tag: row[`tag_${index}`] }))
    const selectedDimension = dimension.value === 'All' || tags.some(item => item.dimension === dimension.value)
    const selectedTag = tag.value === 'All' || tags.some(item => item.tag === tag.value && (dimension.value === 'All' || item.dimension === dimension.value))
    const matchingText = [row.display_name, row.team, row.role, ...tags.map(item => item.tag)].some(value => String(value || '').toLocaleLowerCase().includes(needle))
    return (role.value === 'All' || row.role === role.value) && (support.value === 'All' || row.support_status === support.value) && selectedDimension && selectedTag && (!needle || matchingText)
  }))
})
const totalPages = computed(() => Math.max(1, Math.ceil(filteredRows.value.length / pageSize)))
const pageRows = computed(() => filteredRows.value.slice((page.value - 1) * pageSize, page.value * pageSize))
const pageStart = computed(() => filteredRows.value.length ? (page.value - 1) * pageSize + 1 : 0)
const pageEnd = computed(() => Math.min(page.value * pageSize, filteredRows.value.length))
const supportedCount = computed(() => filteredRows.value.filter(row => Number(row.tag_count) >= 3).length)
const averageReliability = computed(() => filteredRows.value.length ? formatPct(filteredRows.value.reduce((sum, row) => sum + Number(row.sample_reliability || 0), 0) * 100 / filteredRows.value.length) : '—')

onMounted(loadData)
watch(year, async () => { await router.replace({ query: { ...route.query, year: String(year.value) } }); await loadData() })
watch([role, dimension, tag, support, search, sortKey, sortDirection], () => { page.value = 1 })
watch(dimension, () => { if (tag.value !== 'All' && !tagOptions.value.includes(tag.value)) tag.value = 'All' })
watch(totalPages, value => { if (page.value > value) page.value = value })

async function loadData() {
  pending.value = true
  errorMessage.value = ''
  try { payload.value = await api.playerArchetypeSlice3({ year: year.value, population: props.population }) }
  catch (error) { errorMessage.value = error instanceof Error ? error.message : 'Could not load player tags.' }
  finally { pending.value = false }
}
function selectTag(item: Row) { if (props.population === 'pitcher') role.value = String(item.role); dimension.value = String(item.dimension); tag.value = String(item.tag) }
function clearTag() { dimension.value = 'All'; tag.value = 'All' }
function setSort(key: string) { if (sortKey.value === key) sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'; else { sortKey.value = key; sortDirection.value = 'asc' } }
function sortedRows(rows: Row[]) { return [...rows].sort((left, right) => { const a = left[sortKey.value]; const b = right[sortKey.value]; const result = typeof a === 'number' && typeof b === 'number' ? a - b : String(a || '').localeCompare(String(b || '')); return sortDirection.value === 'asc' ? result : -result }) }
function ariaSort(key: string) { return sortKey.value === key ? (sortDirection.value === 'asc' ? 'ascending' : 'descending') : 'none' as const }
function playerLink(row: Row) { return props.population === 'pitcher' ? { path: '/pitcher-personal', query: { year: row.year, role: row.role, team: row.team, pitcher_id: row.player_id } } : { path: '/batter-personal', query: { year: row.year, team: row.team, batter_id: row.player_id } } }
function formatPct(value: unknown) { return Number.isFinite(Number(value)) ? `${Number(value).toFixed(1)}%` : '—' }
function dimensionLabel(value: unknown) { return String(value || '').replaceAll('_', ' ').replace(/\b\w/g, letter => letter.toUpperCase()) }
function supportLabel(value: unknown) { return ({ supported: '3+ tags', review: 'Review', unassigned: 'Unassigned' } as Record<string, string>)[String(value)] || String(value) }
</script>

<style scoped>
.tag-lab { display: grid; gap: 16px; }.filter-panel { display: grid; grid-template-columns: 120px 120px 180px minmax(190px, 1fr) 150px minmax(220px, 1.2fr); gap: 12px; align-items: end; border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: 16px; background: var(--color-surface); box-shadow: var(--shadow-sm); }.filter-panel label { display: grid; gap: 6px; color: var(--color-muted-text); font-size: 11px; font-weight: 900; letter-spacing: .06em; text-transform: uppercase; }.filter-panel select, .filter-panel input { width: 100%; min-width: 0; height: 42px; border: 1px solid var(--color-border-strong); border-radius: 8px; padding: 0 11px; color: var(--color-text); background: var(--color-background); font-size: 13px; font-weight: 700; }.filter-panel .search span { position: relative; display: flex; align-items: center; }.filter-panel .search svg { position: absolute; left: 11px; color: var(--color-muted-text); }.filter-panel .search input { padding-left: 36px; }.state-card, .scope-note, .distribution-panel, .roster-panel, .validation-panel { border: 1px solid var(--color-border); border-radius: var(--radius-md); background: var(--color-surface); box-shadow: var(--shadow-sm); }.state-card { display: grid; gap: 5px; margin: 0; padding: 22px; color: var(--color-muted-text); }.state-card strong { color: var(--color-text); }.state-card.error { color: var(--color-destructive); }.summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }.summary-grid article { min-width: 0; border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: 14px 16px; background: var(--color-surface); }.summary-grid span { color: var(--color-muted-text); font-size: 11px; font-weight: 800; text-transform: uppercase; }.summary-grid strong { display: block; margin-top: 6px; color: var(--color-text); font: 900 22px "Fira Code", monospace; }.summary-grid .selected-summary { overflow: hidden; font-family: inherit; font-size: 14px; font-weight: 850; text-overflow: ellipsis; white-space: nowrap; }.scope-note { display: flex; align-items: flex-start; gap: 10px; padding: 13px 16px; color: var(--color-muted-text); }.scope-note svg { flex: 0 0 auto; color: var(--color-primary); }.scope-note p { margin: 0; font-size: 13px; line-height: 1.5; }.scope-note strong { color: var(--color-text); }.lab-grid { display: grid; grid-template-columns: minmax(270px, .72fr) minmax(0, 2.3fr); gap: 14px; align-items: start; }.distribution-panel, .roster-panel { min-width: 0; overflow: hidden; }.distribution-panel > header, .roster-panel > header { display: flex; justify-content: space-between; align-items: center; gap: 12px; min-height: 76px; padding: 16px 18px; border-bottom: 1px solid var(--color-border); }.distribution-panel header span, .roster-panel header span { color: var(--color-primary); font-size: 11px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }.distribution-panel h2, .roster-panel h2 { margin: 4px 0 0; font-size: 20px; }.distribution-panel header > strong, .roster-panel header > strong { color: var(--color-muted-text); font-size: 12px; }.distribution-list { max-height: 720px; overflow-y: auto; }.distribution-list > button { position: relative; width: 100%; display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 5px 10px; border: 0; border-bottom: 1px solid var(--color-border); padding: 12px 14px; color: var(--color-text); background: transparent; text-align: left; cursor: pointer; }.distribution-list > button:hover, .distribution-list > button:focus-visible, .distribution-list > button.selected { background: color-mix(in srgb, var(--color-primary) 9%, var(--color-surface)); }.distribution-list > button.selected { box-shadow: inset 4px 0 var(--color-primary); }.distribution-list button span:first-child { min-width: 0; }.distribution-list small { display: block; color: var(--color-muted-text); font-size: 10px; }.distribution-list strong { display: block; overflow: hidden; margin-top: 3px; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }.distribution-metrics { text-align: right; }.distribution-metrics b { display: block; color: var(--color-primary); font: 900 14px "Fira Code", monospace; }.distribution-list em { width: fit-content; border-radius: 999px; padding: 3px 7px; color: #ffd084; background: #493617; font-size: 9px; font-style: normal; font-weight: 850; text-transform: uppercase; }.distribution-list em.is-clear { color: #78dfba; background: #153d33; }.distribution-panel > footer { padding: 12px; }.distribution-panel > footer button, .pagination button { min-height: 38px; border: 1px solid var(--color-border-strong); border-radius: 8px; padding: 0 12px; color: var(--color-primary); background: var(--color-background); font-weight: 850; cursor: pointer; }.table-shell { max-height: 720px; overflow: auto; }table { width: 100%; min-width: 1120px; border-collapse: collapse; font-size: 14px; }th { position: sticky; top: 0; z-index: 2; height: 44px; padding: 0; color: var(--color-muted-text); background: var(--color-surface); font-size: 12px; text-align: left; text-transform: uppercase; }th button { width: 100%; min-height: 44px; display: flex; align-items: center; gap: 5px; border: 0; padding: 0 13px; color: inherit; background: transparent; font: inherit; font-weight: 900; cursor: pointer; }td { height: 58px; border-top: 1px solid var(--color-border); padding: 7px 13px; color: var(--color-muted-text); white-space: nowrap; }tbody tr:hover { background: color-mix(in srgb, var(--color-primary) 5%, transparent); }.player-cell { display: flex; align-items: center; gap: 10px; color: var(--color-text); text-decoration: none; }.player-cell strong { display: block; font-size: 14px; }.player-cell small { display: block; margin-top: 2px; color: var(--color-muted-text); font-size: 11px; }.tag-pill { display: inline-flex; flex-direction: column; align-items: flex-start; gap: 2px; min-height: 36px; border: 1px solid var(--color-border-strong); border-radius: 8px; padding: 5px 8px; color: var(--color-text); background: var(--color-muted); font-size: 12px; font-weight: 800; }.tag-pill small { color: var(--color-muted-text); font-size: 9px; text-transform: uppercase; }.tag-pill.selected { border-color: var(--color-primary); background: color-mix(in srgb, var(--color-primary) 14%, var(--color-surface)); }.support-pill { display: inline-flex; border-radius: 999px; padding: 5px 8px; font-size: 11px; font-weight: 850; }.support-pill.is-supported { color: #78dfba; background: #153d33; }.support-pill.is-review { color: #ffd084; background: #493617; }.support-pill.is-unassigned { color: #ffb1c3; background: #3b2630; }.missing { color: var(--color-muted-text); }.empty-state { margin: 0; padding: 24px; color: var(--color-muted-text); }.pagination { display: flex; align-items: center; justify-content: flex-end; gap: 12px; min-height: 58px; border-top: 1px solid var(--color-border); padding: 10px 16px; color: var(--color-muted-text); font-size: 12px; }.pagination button:disabled { opacity: .4; cursor: not-allowed; }.validation-panel { padding: 16px 18px; }.validation-panel summary { color: var(--color-text); font-weight: 900; cursor: pointer; }.decision-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-top: 14px; }.decision-grid article { display: grid; gap: 5px; border: 1px solid var(--color-border); border-radius: 8px; padding: 11px; }.decision-grid article > span { width: fit-content; border-radius: 999px; padding: 3px 7px; font-size: 9px; font-weight: 900; text-transform: uppercase; }.decision-grid .is-publish { color: #78dfba; background: #153d33; }.decision-grid .is-monitor { color: #ffd084; background: #493617; }.decision-grid .is-research_only { color: #ffb1c3; background: #3b2630; }.decision-grid p { margin: 0; color: var(--color-muted-text); font-size: 11px; }.validation-panel ul { margin-bottom: 0; color: var(--color-muted-text); font-size: 12px; line-height: 1.6; }
@media (max-width: 1250px) { .filter-panel { grid-template-columns: repeat(3, minmax(0, 1fr)); }.filter-panel .search { grid-column: span 2; }.lab-grid { grid-template-columns: 1fr; }.distribution-list { max-height: 360px; }.decision-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 700px) { .filter-panel, .summary-grid { grid-template-columns: 1fr 1fr; }.filter-panel .search { grid-column: 1 / -1; }.decision-grid { grid-template-columns: 1fr; } }
@media (max-width: 480px) { .filter-panel, .summary-grid { grid-template-columns: 1fr; }.filter-panel .search { grid-column: auto; } }
</style>
