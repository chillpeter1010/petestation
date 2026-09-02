<template>
  <main class="timing-page">
    <header class="page-hero">
      <div>
        <nav><NuxtLink to="/batters">Batters</NuxtLink><span>/</span><NuxtLink to="/batters/lab">Lab</NuxtLink><span>/</span><b>Swing Timing</b></nav>
        <span class="eyebrow">Batter Lab · Bat-to-ball alignment</span>
        <h1>Swing Timing</h1>
        <p>Measure how often hitters arrive centered, on time, and lined up—and how they miss when they do not.</p>
      </div>
      <details class="rules-card">
        <summary><span>Rules</span><strong>研究定義與統計口徑</strong><ChevronDown :size="18" aria-hidden="true" /></summary>
        <div class="rules-popover">
          <header><span>Swing Timing Rules</span><h2>怎麼閱讀這份研究</h2></header>
          <section v-for="group in ruleGroups" :key="group.title"><h3>{{ group.title }}</h3><dl><div v-for="item in group.items" :key="item.term"><dt>{{ item.term }}</dt><dd>{{ item.definition }}</dd></div></dl></section>
          <p>本頁使用 Savant 已彙總的 batter × pitch type 資料。比例皆以全部合格揮棒為分母；跨球種時依各球種 swings 加權。這些 summary 無法還原完整逐揮棒分布。</p>
        </div>
      </details>
    </header>

    <section class="filter-panel" aria-label="Swing Timing filters">
      <label><span>Season</span><select v-model.number="year"><option v-for="option in yearOptions" :key="option" :value="option">{{ option }}</option></select></label>
      <label><span>Pitch group</span><select v-model="pitchGroup"><option v-for="option in pitchGroupOptions" :key="option.value" :value="option.value">{{ option.label }}</option></select></label>
      <label><span>Pitch type</span><select v-model="pitchType"><option value="All">All in group</option><optgroup v-for="group in visiblePitchTypeGroups" :key="group.key" :label="group.label"><option v-for="option in group.options" :key="option.value" :value="option.value">{{ option.label }}</option></optgroup></select></label>
      <label><span>Pitcher hand</span><select v-model="pitcherHand"><option value="All">All pitchers</option><option value="L">LHP</option><option value="R">RHP</option></select></label>
      <label><span>Batter side</span><select v-model="batterSide"><option value="All">All hitters</option><option value="L">Left-handed</option><option value="R">Right-handed</option></select></label>
      <label><span>Minimum swings</span><select v-model.number="minimumSwings"><option :value="25">25 swings</option><option :value="50">50 swings</option><option :value="100">100 swings</option><option :value="200">200 swings</option></select></label>
    </section>

    <section class="filter-panel matchup-filters" aria-label="Team and season sample filters">
      <label><span>Batter team</span><select v-model="batterTeam"><option v-for="option in batterTeamOptions" :key="option.value" :value="option.value">{{ option.label }}</option></select></label>
      <label><span>Pitcher team</span><select v-model="pitcherTeam"><option v-for="option in pitcherTeamOptions" :key="option.value" :value="option.value">{{ option.label }}</option></select></label>
      <label class="pa-slider"><span>Season PA sample <b>{{ minimumPaDraft }} PA</b></span><input v-model.number="minimumPaDraft" type="range" min="5" max="700" step="5" aria-label="Minimum season plate appearances" @change="minimumPlateAppearances = minimumPaDraft"><small><i>5</i><i>Minimum {{ minimumPaDraft }} PA</i><i>700</i></small></label>
    </section>

    <p v-if="pending" class="state-card">Loading batter timing profiles…</p>
    <p v-else-if="error" class="state-card error">Unable to load Swing Timing.</p>
    <template v-else-if="response">
      <p v-for="warning in response.warnings" :key="warning" class="state-card warning">{{ warning }}</p>
      <p class="mode-banner"><b>{{ response.data_mode === 'summary' ? 'Savant summary mode' : 'Exact matchup event mode' }}</b><span>{{ response.data_mode === 'summary' ? '完整 X／Y／Z timing 指標' : '依投手球隊精確篩選；X／Y／Z timing 欄位顯示 —' }}</span></p>

      <section class="summary-grid" aria-label="Swing Timing summary">
        <article><span>Matched swings</span><strong>{{ integer(response.matched_swings) }}</strong><small>{{ activePitchLabel }} · {{ activeHandLabel }}</small></article>
        <article><span>Qualified hitters</span><strong>{{ integer(response.qualified_hitters) }}</strong><small>Minimum {{ minimumSwings }} swings · {{ minimumPlateAppearances }} season PA</small></article>
        <article><span>Perfect contact</span><strong>{{ percent(response.league?.perfect_pct) }}</strong><small>Contact + all three aligned</small></article>
        <article><span>Flawed swing</span><strong>{{ percent(response.league?.flawed_pct) }}</strong><small>Whiff + none aligned</small></article>
        <article><span>Competitive rate</span><strong>{{ percent(response.league?.competitive_pct) }}</strong><small>League weighted rate</small></article>
      </section>

      <section class="leaderboard-card">
        <header class="board-heading">
          <div><span>Research leaderboard</span><h2>Batter alignment profile</h2><p>主欄位固定；切換 X／Y／Z 維度查看失誤方向與平均偏差。</p></div>
          <div class="board-controls">
            <div class="dimension-tabs" role="group" aria-label="Timing dimension">
              <button v-for="option in dimensionOptions" :key="option.value" type="button" :class="{ active: dimension === option.value }" @click="dimension = option.value">{{ option.label }}</button>
            </div>
            <div class="display-control"><span>Display</span><div class="mode-toggle" role="group" aria-label="Metric display"><button type="button" :class="{ active: displayMode === 'actual' }" @click="displayMode = 'actual'">實際數據</button><button type="button" :class="{ active: displayMode === 'percentile' }" @click="displayMode = 'percentile'">PR值</button></div></div>
            <div class="display-control"><span>Heat map</span><div class="mode-toggle heat-toggle" role="group" aria-label="Heat map"><button type="button" :class="{ active: !heatmapEnabled }" @click="heatmapEnabled = false">Off</button><button type="button" :class="{ active: heatmapEnabled }" @click="heatmapEnabled = true">On</button></div></div>
            <label class="search"><span>Find hitter</span><div><Search :size="16" aria-hidden="true" /><input v-model.trim="searchText" type="search" placeholder="Player or team" /></div></label>
          </div>
        </header>

        <div class="table-scroll">
          <table>
            <colgroup>
              <col class="col-hitter">
              <col class="col-age">
              <col class="col-team">
              <col class="col-hand">
              <col class="col-pa">
              <col class="col-swings">
              <col v-for="column in tableColumns" :key="`col-${column.key}`" class="col-metric">
            </colgroup>
            <thead><tr>
              <th :aria-sort="ariaSort('name')"><button class="sort-button" type="button" title="打者姓名；點擊可依姓名排序。" @click="sortBy('name')"><span>Hitter</span><component :is="sortIcon('name')" v-if="sortIcon('name')" :size="12" aria-hidden="true" /></button></th>
              <th :aria-sort="ariaSort('age')"><button class="sort-button" type="button" title="球員在該球季的年齡。點擊可排序。" @click="sortBy('age')"><span>Age</span><component :is="sortIcon('age')" v-if="sortIcon('age')" :size="12" aria-hidden="true" /></button></th>
              <th :aria-sort="ariaSort('team')"><button class="sort-button" type="button" title="球員在該球季效力的球隊；多隊球員可展開查看。點擊可排序。" @click="sortBy('team')"><span>Team</span><component :is="sortIcon('team')" v-if="sortIcon('team')" :size="12" aria-hidden="true" /></button></th>
              <th :aria-sort="ariaSort('batter_side')"><button class="sort-button" type="button" title="打者慣用側：L、R 或左右開弓 S。點擊可排序。" @click="sortBy('batter_side')"><span>Hand</span><component :is="sortIcon('batter_side')" v-if="sortIcon('batter_side')" :size="12" aria-hidden="true" /></button></th>
              <th :aria-sort="ariaSort('plate_appearances')"><button class="sort-button" type="button" title="該球季總打席數，僅代表樣本量，不套用 PR 或 Heatmap。點擊可排序。" @click="sortBy('plate_appearances')"><span>PA</span><component :is="sortIcon('plate_appearances')" v-if="sortIcon('plate_appearances')" :size="12" aria-hidden="true" /></button></th>
              <th :aria-sort="ariaSort('n_swings')"><button class="sort-button" type="button" title="目前篩選條件下的揮棒數，僅代表樣本量，不套用 PR 或 Heatmap。點擊可排序。" @click="sortBy('n_swings')"><span>Swing</span><component :is="sortIcon('n_swings')" v-if="sortIcon('n_swings')" :size="12" aria-hidden="true" /></button></th>
              <th v-for="column in tableColumns" :key="column.key" :aria-sort="ariaSort(column.key)"><button class="sort-button" type="button" :title="`${column.definition} 點擊可排序。`" @click="sortBy(column.key)"><span>{{ column.label }}</span><component :is="sortIcon(column.key)" v-if="sortIcon(column.key)" :size="12" aria-hidden="true" /></button></th>
            </tr></thead>
            <tbody>
              <template v-for="row in visibleRows" :key="row.batter_id">
                <tr :class="{ selected: expandedBatterId === row.batter_id }">
                  <td><button class="player-button" type="button" :aria-expanded="expandedBatterId === row.batter_id" @click="toggleProfile(row.batter_id)"><MlbPlayerHeadshot :player-id="row.batter_id" :name="row.name" :size="42" shape="circle" decorative /><span><strong>{{ row.name }}</strong></span><ChevronDown :size="15" :class="{ rotated: expandedBatterId === row.batter_id }" aria-hidden="true" /></button></td>
                  <td class="sample-cell">{{ row.age ?? '—' }}</td>
                  <td class="sample-cell team-cell">
                    <details v-if="teamCodes(row).length > 1" class="team-menu">
                      <summary :aria-label="`${row.name} played for ${teamCodes(row).length} teams`">{{ teamCodes(row).length }} TM</summary>
                      <div class="team-popover">
                        <NuxtLink v-for="team in teamCodes(row)" :key="team" :to="teamLink(team)">{{ team }}</NuxtLink>
                      </div>
                    </details>
                    <NuxtLink v-else-if="teamCodes(row)[0]" class="team-link" :to="teamLink(teamCodes(row)[0])">{{ teamCodes(row)[0] }}</NuxtLink>
                    <span v-else>—</span>
                  </td>
                  <td class="sample-cell">{{ row.batter_side }}</td>
                  <td class="sample-cell">{{ row.plate_appearances == null ? '—' : integer(row.plate_appearances) }}</td>
                  <td class="sample-cell">{{ integer(row.n_swings) }}</td>
                  <td v-for="column in tableColumns" :key="`${row.batter_id}-${column.key}`" :style="heatmapStyle(row, column)">{{ metric(row, column) }}</td>
                </tr>
                <tr v-if="expandedBatterId === row.batter_id" class="profile-row"><td :colspan="6 + tableColumns.length"><div class="profile-panel">
                  <header><div><span>Selected hitter</span><h3>{{ row.name }} <small>{{ row.team }}</small></h3></div><NuxtLink :to="personalLink(row)">Open player report <ArrowUpRight :size="15" aria-hidden="true" /></NuxtLink></header>
                  <p v-if="detailPending" class="profile-state">Loading V2 player analysis…</p>
                  <p v-else-if="detailError" class="profile-state error">Unable to load player analysis.</p>
                  <template v-else-if="playerDetail">
                    <SwingTimingDimensionChart v-if="playerDetail.player && playerDetail.league && playerDetail.data_mode === 'summary'" :player="playerDetail.player" :league="playerDetail.league" />
                    <BatterPitchTimingMatrix :rows="playerDetail.pitch_matrix" />
                    <BatSpeedGearChange :rows="playerDetail.pitch_matrix" />
                  </template>
                </div></td></tr>
              </template>
            </tbody>
          </table>
        </div>
        <footer class="board-footer"><span>Showing {{ visibleRows.length }} of {{ filteredRows.length }} hitters</span><button v-if="visibleRows.length < filteredRows.length" type="button" @click="displayLimit += 100">Show 100 more</button><span>Data refreshed {{ response.data_updated_at || '—' }}</span><a v-if="response.source_url" :href="response.source_url" target="_blank" rel="noreferrer">Open source <ArrowUpRight :size="13" aria-hidden="true" /></a></footer>
      </section>

      <aside class="method-note"><strong>V1 summary view</strong><p>灰色區間不代表估計的 KDE。Centered 為水平 ±4 inches、On Time 為完美 timing ±7 ms、Lined Up 為垂直 ±2 inches。平均偏差只在相對應的 miss category 內計算。</p></aside>
    </template>
  </main>
</template>

<script setup lang="ts">
import { ArrowDown, ArrowUp, ArrowUpRight, ChevronDown, Search } from '@lucide/vue'
import type { SwingTimingLeaderboardRow, SwingTimingPlayerDetailResponse } from '~/types/api'

type Dimension = 'horizontal' | 'timing' | 'vertical'
type MetricKey = keyof SwingTimingLeaderboardRow
type SortDirection = 'asc' | 'desc'
type TableColumn = { key: MetricKey; label: string; format: 'percent' | 'distance' | 'ms' | 'integer'; definition: string }

const api = useApi()
const route = useRoute()
const year = ref(queryNumber(route.query.year, 2026))
const pitchGroup = ref(queryText(route.query.timing_pitch_group, 'all'))
const pitchType = ref(queryText(route.query.timing_pitch_type, 'All'))
const pitcherHand = ref<'All' | 'L' | 'R'>(['L', 'R'].includes(queryText(route.query.timing_pitcher_hand, 'All')) ? queryText(route.query.timing_pitcher_hand, 'All') as 'L' | 'R' : 'All')
const batterSide = ref<'All' | 'L' | 'R'>('All')
const batterTeam = ref('All')
const pitcherTeam = ref('All')
const minimumSwings = ref(50)
const minimumPlateAppearances = ref(100)
const minimumPaDraft = ref(100)
const searchText = ref(queryText(route.query.find, ''))
const dimension = ref<Dimension>('timing')
const rankMetric = ref<MetricKey>('perfect_pct')
const sortDirection = ref<SortDirection>('desc')
const displayMode = ref<'actual' | 'percentile'>('actual')
const heatmapEnabled = ref(true)
const displayLimit = ref(200)
const expandedBatterId = ref<number | null>(null)
const playerDetail = ref<SwingTimingPlayerDetailResponse | null>(null)
const detailPending = ref(false)
const detailError = ref(false)
let detailRequestId = 0

const fallbackPitchTypeGroups = [
  { key: 'fastball', label: 'Fastball', options: [{ value: 'FF', label: 'Four-Seam Fastball' }, { value: 'SI', label: 'Sinker' }, { value: 'FC', label: 'Cutter' }] },
  { key: 'breaking', label: 'Breaking Ball', options: [{ value: 'SL', label: 'Slider' }, { value: 'ST', label: 'Sweeper' }, { value: 'CU', label: 'Curveball' }, { value: 'KC', label: 'Knuckle Curve' }, { value: 'SV', label: 'Slurve' }] },
  { key: 'offspeed', label: 'Offspeed', options: [{ value: 'CH', label: 'Changeup' }, { value: 'FS', label: 'Splitter' }, { value: 'FO', label: 'Forkball' }] },
  { key: 'other', label: 'Other', options: [{ value: 'KN', label: 'Knuckleball' }, { value: 'EP', label: 'Eephus' }, { value: 'CS', label: 'Slow Curve' }] }
]
const fallbackPitchGroups = [{ value: 'all', label: 'All pitch types' }, ...fallbackPitchTypeGroups.map(group => ({ value: group.key, label: group.label }))]
const dimensionOptions: Array<{ value: Dimension; label: string }> = [{ value: 'horizontal', label: 'Horizontal' }, { value: 'timing', label: 'Timing' }, { value: 'vertical', label: 'Vertical' }]
const coreColumns: TableColumn[] = [
  { key: 'miss_distance', label: 'Avg Miss Dist.', format: 'distance', definition: '揮空時，球棒 barrel half 與球在最接近瞬間的平均距離。' },
  { key: 'flawed_pct', label: 'Flawed Swing%', format: 'percent', definition: '揮空且 Centered、On Time、Lined Up 三項全部未達標的揮棒比例。' },
  { key: 'perfect_pct', label: 'Perfect Contact%', format: 'percent', definition: '有碰到球且 Centered、On Time、Lined Up 三項同時達標的揮棒比例。' },
  { key: 'whiff_pct', label: 'Whiff%', format: 'percent', definition: '全部揮棒中沒有碰到球的比例。' },
  { key: 'competitive_pct', label: 'Competitive%', format: 'percent', definition: '最快 90% 的揮棒，加上棒速至少 60 mph 且擊球初速至少 90 mph 的揮棒比例。' }
]
const columnsByDimension: Record<Dimension, TableColumn[]> = {
  horizontal: [
    { key: 'tied_up_pct', label: 'Tied Up%', format: 'percent', definition: '水平方向上，barrel 相對球太靠近打者的揮棒比例。' },
    { key: 'avg_tied_up_distance', label: 'Avg Tied-up Dist.', format: 'distance', definition: '只計算 Tied Up 揮棒的平均水平偏差。' },
    { key: 'centered_pct', label: 'Centered%', format: 'percent', definition: 'barrel 水平位置在球的 ±4 inches 內的揮棒比例。' },
    { key: 'flail_pct', label: 'Flail%', format: 'percent', definition: '水平方向上，barrel 相對球太遠離打者的揮棒比例。' },
    { key: 'avg_flail_distance', label: 'Avg Flail Dist.', format: 'distance', definition: '只計算 Flail 揮棒的平均水平偏差。' }
  ],
  timing: [
    { key: 'late_pct', label: 'Late%', format: 'percent', definition: 'barrel 比完美 timing 晚超過 7 ms 抵達的揮棒比例。' },
    { key: 'avg_late_ms', label: 'Avg Late', format: 'ms', definition: '只計算 Late 揮棒的平均時間偏差。' },
    { key: 'on_time_pct', label: 'On Time%', format: 'percent', definition: 'barrel 抵達時間在完美 timing ±7 ms 內的揮棒比例。' },
    { key: 'early_pct', label: 'Early%', format: 'percent', definition: 'barrel 比完美 timing 早超過 7 ms 抵達的揮棒比例。' },
    { key: 'avg_early_ms', label: 'Avg Early', format: 'ms', definition: '只計算 Early 揮棒的平均時間偏差。' }
  ],
  vertical: [
    { key: 'over_pct', label: 'Over%', format: 'percent', definition: '垂直方向上，barrel 通過球上方的揮棒比例。' },
    { key: 'avg_over_distance', label: 'Avg Over Dist.', format: 'distance', definition: '只計算 Over 揮棒的平均垂直偏差。' },
    { key: 'lined_up_pct', label: 'Lined Up%', format: 'percent', definition: 'barrel 垂直位置在球的 ±2 inches 內的揮棒比例。' },
    { key: 'under_pct', label: 'Under%', format: 'percent', definition: '垂直方向上，barrel 通過球下方的揮棒比例。' },
    { key: 'avg_under_distance', label: 'Avg Under Dist.', format: 'distance', definition: '只計算 Under 揮棒的平均垂直偏差。' }
  ]
}
const performanceDirection: Partial<Record<MetricKey, 'higher' | 'lower'>> = {
  miss_distance: 'lower', flawed_pct: 'lower', perfect_pct: 'higher', whiff_pct: 'lower', competitive_pct: 'higher',
  tied_up_pct: 'lower', avg_tied_up_distance: 'lower', centered_pct: 'higher', flail_pct: 'lower', avg_flail_distance: 'lower',
  late_pct: 'lower', avg_late_ms: 'lower', on_time_pct: 'higher', early_pct: 'lower', avg_early_ms: 'lower',
  over_pct: 'lower', avg_over_distance: 'lower', lined_up_pct: 'higher', under_pct: 'lower', avg_under_distance: 'lower'
}
const ruleGroups = [
  { title: '三維對位', items: [
    { term: 'Centered', definition: '球棒 barrel 在水平方向距離球 ±4 inches 內。' },
    { term: 'On Time', definition: '球棒相對完美 timing 在 ±7 ms 內。' },
    { term: 'Lined Up', definition: '球棒在垂直方向距離球 ±2 inches 內。' },
    { term: 'Tied Up / Flail', definition: '水平方向上，球棒相對球太靠近打者／太遠離打者。' },
    { term: 'Over / Under', definition: '垂直方向上，球棒通過球的上方／下方。' }
  ] },
  { title: '結果分類', items: [
    { term: 'Flawed Swing%', definition: '全部揮棒中，打者揮空，而且 Lined Up、Centered、On Time 三項全部未達標的比例。' },
    { term: 'Perfect Contact%', definition: '全部揮棒中，打者有碰到球，而且三項同時達標的比例。' },
    { term: 'Competitive Rate', definition: '打者最快 90% 的揮棒，加上棒速至少 60 mph 且造成至少 90 mph 擊球初速的揮棒比例。' },
    { term: 'Miss Distance', definition: '球棒遠離雙手的 barrel half 與球在最接近瞬間的距離；短打嘗試排除。' }
  ] },
  { title: '篩選與彙總', items: [
    { term: 'Pitcher hand', definition: '左右投使用各自的 Savant 來源 cache；不是從缺少投手手別的 summary 推算。' },
    { term: 'Minimum swings', definition: '完成球種、投手手別與打者側篩選後，打者至少需要的揮棒數。' },
    { term: 'Avg distance / ms', definition: '只在該分類內計算的條件平均。例如 Avg Late 只使用 Late swings。' }
  ] }
]

const requestKey = computed(() => `${year.value}-${pitchGroup.value}-${pitchType.value}-${pitcherHand.value}-${batterSide.value}-${batterTeam.value}-${pitcherTeam.value}-${minimumSwings.value}-${minimumPlateAppearances.value}`)
const { data: response, pending, error } = await useAsyncData(
  () => `batter-swing-timing-${requestKey.value}`,
  () => api.batterSwingTiming({ year: year.value, pitchGroup: pitchGroup.value, pitchType: pitchType.value, pitcherHand: pitcherHand.value, batterSide: batterSide.value, batterTeam: batterTeam.value, pitcherTeam: pitcherTeam.value, minimumSwings: minimumSwings.value, minimumPlateAppearances: minimumPlateAppearances.value }),
  { watch: [requestKey] }
)

const yearOptions = computed(() => response.value?.filters.available_years.length ? response.value.filters.available_years : [2026, 2025, 2024, 2023])
const pitchTypeGroups = computed(() => response.value?.filters.pitch_type_groups.length ? response.value.filters.pitch_type_groups : fallbackPitchTypeGroups)
const pitchGroupOptions = computed(() => response.value?.filters.pitch_groups.length ? response.value.filters.pitch_groups : fallbackPitchGroups)
const batterTeamOptions = computed(() => response.value?.filters.batter_teams.length ? response.value.filters.batter_teams : [{ value: 'All', label: 'All teams' }])
const pitcherTeamOptions = computed(() => response.value?.filters.pitcher_teams.length ? response.value.filters.pitcher_teams : [{ value: 'All', label: 'All pitcher teams' }])
const visiblePitchTypeGroups = computed(() => pitchGroup.value === 'all' ? pitchTypeGroups.value : pitchTypeGroups.value.filter(group => group.key === pitchGroup.value))
const dimensionColumns = computed(() => columnsByDimension[dimension.value])
const tableColumns = computed(() => [...coreColumns, ...dimensionColumns.value])
const percentileMaps = computed(() => {
  const result = new Map<MetricKey, Map<number, number>>()
  const rows = response.value?.leaderboard || []
  for (const key of Object.keys(performanceDirection) as MetricKey[]) {
    const entries = rows.map(row => ({ id: row.batter_id, value: skillValue(key, row[key]) })).filter((entry): entry is { id: number; value: number } => entry.value != null)
    entries.sort((a, b) => a.value - b.value)
    const map = new Map<number, number>()
    let index = 0
    while (index < entries.length) {
      let end = index + 1
      while (end < entries.length && entries[end].value === entries[index].value) end++
      const rawPr = entries.length === 1 ? 50 : (((index + end - 1) / 2) / (entries.length - 1)) * 100
      const pr = performanceDirection[key] === 'lower' ? 100 - rawPr : rawPr
      for (let position = index; position < end; position++) map.set(entries[position].id, pr)
      index = end
    }
    result.set(key, map)
  }
  return result
})
const activePitchLabel = computed(() => pitchType.value === 'All' ? pitchGroupOptions.value.find(option => option.value === pitchGroup.value)?.label || 'All pitch types' : pitchTypeGroups.value.flatMap(group => group.options).find(option => option.value === pitchType.value)?.label || pitchType.value)
const activeHandLabel = computed(() => {
  const hand = pitcherHand.value === 'L' ? 'LHP' : pitcherHand.value === 'R' ? 'RHP' : 'All pitchers'
  return pitcherTeam.value === 'All' ? `vs ${hand}` : `vs ${pitcherTeam.value} · ${hand}`
})
const filteredRows = computed(() => {
  const needle = searchText.value.toLowerCase()
  return (response.value?.leaderboard || [])
    .filter(row => !needle || `${row.name} ${row.team} ${row.teams.join(' ')}`.toLowerCase().includes(needle))
    .slice()
    .sort(compareRows)
})
const visibleRows = computed(() => filteredRows.value.slice(0, displayLimit.value))

watch(pitchGroup, () => {
  const allowed = new Set(visiblePitchTypeGroups.value.flatMap(group => group.options.map(option => option.value)))
  if (pitchType.value !== 'All' && !allowed.has(pitchType.value)) pitchType.value = 'All'
})
watch(year, () => { batterTeam.value = 'All'; pitcherTeam.value = 'All' })
watch([requestKey, dimension], () => { expandedBatterId.value = null; playerDetail.value = null })
watch([requestKey, searchText, rankMetric, sortDirection], () => { displayLimit.value = 200 })

function compareRows(left: SwingTimingLeaderboardRow, right: SwingTimingLeaderboardRow) {
  const prMap = displayMode.value === 'percentile' ? percentileMaps.value.get(rankMetric.value) : null
  const leftValue = prMap?.get(left.batter_id) ?? left[rankMetric.value]
  const rightValue = prMap?.get(right.batter_id) ?? right[rankMetric.value]
  if (leftValue == null && rightValue == null) return right.n_swings - left.n_swings
  if (leftValue == null) return 1
  if (rightValue == null) return -1
  const comparison = typeof leftValue === 'string' && typeof rightValue === 'string'
    ? leftValue.localeCompare(rightValue)
    : Number(leftValue) - Number(rightValue)
  return (sortDirection.value === 'asc' ? comparison : -comparison) || right.n_swings - left.n_swings
}
function sortBy(key: MetricKey) { if (rankMetric.value === key) sortDirection.value = sortDirection.value === 'desc' ? 'asc' : 'desc'; else { rankMetric.value = key; sortDirection.value = key === 'name' ? 'asc' : 'desc' } }
function sortIcon(key: MetricKey) { return rankMetric.value === key ? (sortDirection.value === 'asc' ? ArrowUp : ArrowDown) : null }
function ariaSort(key: MetricKey): 'ascending' | 'descending' | 'none' { return rankMetric.value === key ? (sortDirection.value === 'asc' ? 'ascending' : 'descending') : 'none' }
async function toggleProfile(playerId: number) {
  if (expandedBatterId.value === playerId) { expandedBatterId.value = null; return }
  expandedBatterId.value = playerId
  playerDetail.value = null
  detailError.value = false
  detailPending.value = true
  const requestId = ++detailRequestId
  try {
    const result = await api.batterSwingTimingPlayer({ year: year.value, batterId: playerId, pitchGroup: pitchGroup.value, pitchType: pitchType.value, pitcherHand: pitcherHand.value, batterSide: batterSide.value, pitcherTeam: pitcherTeam.value })
    if (requestId === detailRequestId) playerDetail.value = result
  } catch {
    if (requestId === detailRequestId) detailError.value = true
  } finally {
    if (requestId === detailRequestId) detailPending.value = false
  }
}
function personalLink(row: SwingTimingLeaderboardRow) { return { path: '/batter-personal', query: { year: year.value, team: row.team, batter_id: row.batter_id, timing_pitch_group: pitchGroup.value, timing_pitch_type: pitchType.value, timing_pitcher_hand: pitcherHand.value } } }
function teamCodes(row: SwingTimingLeaderboardRow) { return row.teams?.length ? row.teams : row.team && row.team !== '-' ? [row.team] : [] }
function teamLink(team: string) { return { path: `/teams/${team}`, query: { year: year.value } } }
function integer(value: number) { return Number(value || 0).toLocaleString() }
function percent(value: number | null | undefined) { return value == null ? '—' : `${value.toFixed(1)}%` }
function distance(value: number | null | undefined) { return value == null ? '—' : `${Math.abs(value).toFixed(1)} in` }
function milliseconds(value: number | null | undefined) { return value == null ? '—' : `${Math.abs(value).toFixed(1)} ms` }
function skillValue(key: MetricKey, value: SwingTimingLeaderboardRow[MetricKey]) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return null
  return key.startsWith('avg_') || key === 'miss_distance' ? Math.abs(value) : value
}
function percentile(row: SwingTimingLeaderboardRow, key: MetricKey) { return percentileMaps.value.get(key)?.get(row.batter_id) ?? null }
function metric(row: SwingTimingLeaderboardRow, column: TableColumn) {
  const value = row[column.key] as number | null
  const pr = percentile(row, column.key)
  if (displayMode.value === 'percentile' && pr != null) return `${Math.round(pr)}`
  return column.format === 'percent' ? percent(value) : column.format === 'ms' ? milliseconds(value) : column.format === 'integer' ? integer(value || 0) : distance(value)
}
function heatmapStyle(row: SwingTimingLeaderboardRow, column: TableColumn) {
  if (!heatmapEnabled.value) return undefined
  const pr = percentile(row, column.key)
  if (pr == null) return undefined
  const white = [246, 247, 249]
  const blue = [51, 104, 164]
  const red = [181, 55, 66]
  const start = pr < 50 ? blue : white
  const end = pr < 50 ? white : red
  const ratio = pr < 50 ? pr / 50 : (pr - 50) / 50
  const color = start.map((value, index) => Math.round(value + (end[index] - value) * ratio))
  const luminance = color[0] * 0.299 + color[1] * 0.587 + color[2] * 0.114
  return {
    backgroundColor: `rgb(${color.join(' ')})`,
    color: luminance < 145 ? '#fff' : '#111827'
  }
}
function profiles(row: SwingTimingLeaderboardRow) {
  return [
    { axis: 'Horizontal · inches', title: 'Tied Up / Centered / Flail', parts: [{ label: 'Tied Up', value: row.tied_up_pct, tone: 'negative' }, { label: 'Centered', value: row.centered_pct, tone: 'neutral' }, { label: 'Flail', value: row.flail_pct, tone: 'negative' }], note: `Avg miss: ${distance(row.avg_tied_up_distance)} tied up · ${distance(row.avg_flail_distance)} flail` },
    { axis: 'Timing · milliseconds', title: 'Late / On Time / Early', parts: [{ label: 'Late', value: row.late_pct, tone: 'negative' }, { label: 'On Time', value: row.on_time_pct, tone: 'neutral' }, { label: 'Early', value: row.early_pct, tone: 'negative' }], note: `Avg miss: ${milliseconds(row.avg_late_ms)} late · ${milliseconds(row.avg_early_ms)} early` },
    { axis: 'Vertical · inches', title: 'Over / Lined Up / Under', parts: [{ label: 'Over', value: row.over_pct, tone: 'negative' }, { label: 'Lined Up', value: row.lined_up_pct, tone: 'neutral' }, { label: 'Under', value: row.under_pct, tone: 'negative' }], note: `Avg miss: ${distance(row.avg_over_distance)} over · ${distance(row.avg_under_distance)} under` }
  ]
}
function queryText(value: unknown, fallback: string) { const raw = Array.isArray(value) ? value[0] : value; return typeof raw === 'string' && raw ? raw : fallback }
function queryNumber(value: unknown, fallback: number) { const parsed = Number(Array.isArray(value) ? value[0] : value); return Number.isFinite(parsed) ? parsed : fallback }
</script>

<style scoped>
.timing-page { max-width: 1560px; min-height: 100vh; margin: 0 auto; padding: 88px clamp(14px, 2.5vw, 36px) 64px; color: var(--color-text); }
.page-hero, .filter-panel, .summary-grid article, .leaderboard-card, .state-card, .method-note { border: 1px solid var(--color-border); background: var(--color-surface); box-shadow: var(--shadow-sm); }
.mode-banner { display: flex; align-items: center; gap: 12px; margin: 10px 0 0; border: 1px solid var(--color-border); border-radius: 10px; padding: 9px 13px; color: var(--color-muted-text); background: var(--color-surface); font-size: 11px; }.mode-banner b { color: var(--color-primary); }.profile-state { margin: 14px 0 0; border: 1px solid var(--color-border); border-radius: 10px; padding: 16px; color: var(--color-muted-text); }.profile-state.error { color: var(--color-destructive); }
.page-hero { display: flex; align-items: end; justify-content: space-between; gap: 28px; border-radius: 20px; padding: clamp(22px, 4vw, 40px); background: radial-gradient(circle at top right, color-mix(in srgb, #8fd3f4 25%, transparent), transparent 36%), var(--color-surface); }
.page-hero nav { display: flex; gap: 8px; margin-bottom: 20px; color: var(--color-muted-text); font-size: 12px; }.page-hero nav a { color: inherit; }.page-hero nav b { color: var(--color-foreground); }
.eyebrow, .board-heading > div > span { color: var(--color-primary); font-size: 11px; font-weight: 900; letter-spacing: .1em; text-transform: uppercase; }
.page-hero h1 { margin: 10px 0 0; color: var(--color-foreground); font-size: clamp(40px, 5vw, 64px); font-weight: 750; line-height: 1.06; letter-spacing: -.012em; }.page-hero p { max-width: 760px; margin: 15px 0 0; color: var(--color-muted-text); font-size: 16px; line-height: 1.55; }
.rules-card { position: relative; width: min(330px, 100%); flex: 0 0 auto; }.rules-card summary { display: grid; grid-template-columns: 1fr auto; gap: 4px 12px; border: 1px solid color-mix(in srgb, var(--color-primary) 65%, var(--color-border)); border-radius: 12px; padding: 14px 16px; background: color-mix(in srgb, var(--color-primary) 7%, var(--color-background)); cursor: pointer; list-style: none; }.rules-card summary::-webkit-details-marker { display: none; }.rules-card summary span { grid-column: 1; color: var(--color-primary); font-size: 9px; font-weight: 900; letter-spacing: .1em; text-transform: uppercase; }.rules-card summary strong { grid-column: 1; color: var(--color-foreground); font-size: 14px; }.rules-card summary svg { grid-column: 2; grid-row: 1 / 3; align-self: center; color: var(--color-primary); transition: transform 160ms ease; }.rules-card[open] summary svg { transform: rotate(180deg); }
.rules-popover { position: absolute; z-index: 30; top: calc(100% + 9px); right: 0; width: min(660px, calc(100vw - 44px)); max-height: min(72vh, 760px); overflow-y: auto; border: 1px solid var(--color-border); border-radius: 14px; padding: 20px; background: var(--color-surface); box-shadow: 0 18px 50px rgb(0 0 0 / 35%); }.rules-popover header { border-bottom: 1px solid var(--color-border); padding-bottom: 13px; }.rules-popover header span { color: var(--color-primary); font-size: 10px; font-weight: 900; letter-spacing: .1em; text-transform: uppercase; }.rules-popover h2 { margin: 4px 0 0; color: var(--color-foreground); font-size: 24px; }.rules-popover section { margin-top: 18px; }.rules-popover h3 { margin: 0 0 7px; color: var(--color-primary); font-size: 13px; }.rules-popover dl { margin: 0; }.rules-popover dl div { display: grid; grid-template-columns: 150px 1fr; gap: 14px; border-top: 1px solid var(--color-border); padding: 8px 0; }.rules-popover dt { color: var(--color-foreground); font-size: 12px; font-weight: 850; }.rules-popover dd, .rules-popover > p { margin: 0; color: var(--color-muted-text); font-size: 12px; line-height: 1.55; }.rules-popover > p { margin-top: 16px; border-left: 2px solid var(--color-primary); padding-left: 12px; }
.filter-panel { display: grid; grid-template-columns: 100px repeat(4, minmax(145px, 1fr)) 145px; gap: 11px; margin-top: 16px; border-radius: 14px; padding: 13px; }.filter-panel label { display: grid; gap: 6px; }.filter-panel label > span, .board-controls label > span { color: var(--color-muted-text); font-size: 9px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }.filter-panel select, .board-controls select, .board-controls input { width: 100%; min-height: 42px; border: 1px solid var(--color-border); border-radius: 8px; padding: 0 10px; color: var(--color-text); background: var(--color-background); font-weight: 750; }
.matchup-filters { grid-template-columns: minmax(220px, 1fr) minmax(220px, 1fr) minmax(360px, 2fr); margin-top: 10px; }.matchup-filters label > small { color: var(--color-muted-text); font-size: 9px; }.matchup-filters select:disabled { cursor: not-allowed; opacity: .58; }.pa-slider > span { display: flex; align-items: center; justify-content: space-between; }.pa-slider > span b { color: var(--color-primary); font-size: 12px; letter-spacing: 0; }.pa-slider input[type="range"] { width: 100%; height: 42px; margin: 0; accent-color: var(--color-primary); cursor: pointer; }.pa-slider > small { display: flex; justify-content: space-between; }.pa-slider > small i { color: var(--color-muted-text); font-size: 9px; font-style: normal; }.pa-slider > small i:nth-child(2) { color: var(--color-primary); font-weight: 800; }
.state-card { margin-top: 12px; border-radius: 13px; padding: 20px; }.state-card.error { color: var(--color-destructive); }.state-card.warning { color: var(--color-primary); }
.summary-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 11px; margin-top: 12px; }.summary-grid article { border-radius: 13px; padding: 15px; }.summary-grid span, .summary-grid small { display: block; color: var(--color-muted-text); }.summary-grid span { font-size: 11px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }.summary-grid strong { display: block; margin: 7px 0 4px; color: var(--color-foreground); font-size: clamp(25px, 3vw, 36px); }.summary-grid small { font-size: 12px; }
.leaderboard-card { margin-top: 12px; border-radius: 16px; overflow: hidden; }.board-heading { display: flex; align-items: end; justify-content: space-between; gap: 24px; padding: 20px; }.board-heading h2 { margin: 5px 0 0; color: var(--color-foreground); font-size: clamp(27px, 3vw, 38px); }.board-heading p { margin: 7px 0 0; color: var(--color-muted-text); font-size: 12px; }.board-controls { display: flex; align-items: end; gap: 10px; }.board-controls label { display: grid; gap: 5px; min-width: 165px; }.board-controls .search { min-width: 220px; }.search div { position: relative; }.search svg { position: absolute; top: 13px; left: 11px; color: var(--color-muted-text); }.search input { padding-left: 35px; }.dimension-tabs, .mode-toggle { display: flex; border: 1px solid var(--color-border); border-radius: 9px; padding: 3px; background: var(--color-background); }.dimension-tabs button, .mode-toggle button { min-height: 34px; border: 0; border-radius: 6px; padding: 0 11px; color: var(--color-muted-text); background: transparent; cursor: pointer; font-size: 11px; font-weight: 850; }.dimension-tabs button.active, .mode-toggle button.active { color: var(--color-on-primary); background: var(--color-primary); }.display-control { display: grid; gap: 5px; }.display-control > span { color: var(--color-muted-text); font-size: 9px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }.heat-toggle { background: linear-gradient(90deg, rgb(69 132 188 / 18%), var(--color-background) 48%, rgb(190 68 75 / 18%)); }.heat-toggle button.active { color: #fff; background: color-mix(in srgb, var(--color-primary) 82%, #111827); }
.table-scroll { overflow-x: auto; border-top: 1px solid var(--color-border); }.table-scroll table { width: 1182px; table-layout: fixed; border-collapse: collapse; }.table-scroll col.col-hitter { width: 180px; }.table-scroll col.col-age, .table-scroll col.col-hand { width: 38px; }.table-scroll col.col-team { width: 50px; }.table-scroll col.col-pa { width: 44px; }.table-scroll col.col-swings { width: 52px; }.table-scroll col.col-metric { width: 78px; }.table-scroll th, .table-scroll td { border-bottom: 1px solid var(--color-border); padding: 9px 4px; text-align: center; }.table-scroll td { overflow: hidden; font-size: 14px; text-overflow: ellipsis; white-space: nowrap; }.table-scroll th { position: sticky; top: 0; z-index: 2; height: 64px; color: var(--color-muted-text); background: var(--color-background); font-size: 9.45px; font-weight: 900; letter-spacing: .025em; line-height: 1.2; text-transform: uppercase; white-space: normal; }.table-scroll th:first-child, .table-scroll td:first-child { position: sticky; left: 0; z-index: 1; text-align: left; background: var(--color-surface); }.table-scroll thead th:first-child { z-index: 3; background: var(--color-background); }.table-scroll tbody tr:hover > td { background: color-mix(in srgb, var(--color-primary) 5%, var(--color-surface)); }.table-scroll tbody tr.selected > td { background: color-mix(in srgb, #8fd3f4 10%, var(--color-surface)); }.sample-cell { color: var(--color-text); background: var(--color-surface); font-variant-numeric: tabular-nums; }
.sort-button { position: relative; display: inline-flex; align-items: center; justify-content: center; gap: 2px; width: 100%; max-width: 70px; border: 0; padding: 4px 0; color: inherit; background: transparent; cursor: pointer; font: inherit; font-weight: inherit; letter-spacing: inherit; line-height: inherit; text-transform: inherit; white-space: normal; }.sort-button > span:first-child { min-width: 0; overflow-wrap: normal; text-align: center; }.sort-button:hover, .sort-button:focus-visible { color: var(--color-primary); }.sort-button:focus-visible { border-radius: 4px; outline: 2px solid color-mix(in srgb, var(--color-primary) 70%, transparent); outline-offset: 2px; }.table-scroll th:first-child .sort-button { max-width: none; justify-content: flex-start; }.table-scroll th:first-child .sort-button > span:first-child { text-align: left; }
.player-button { display: flex; align-items: center; justify-content: flex-start; gap: 8px; width: 100%; border: 0; padding: 0; color: inherit; background: transparent; cursor: pointer; text-align: left; }.player-button > span { display: grid; min-width: 0; }.player-button strong { overflow: hidden; color: var(--color-foreground); font-size: 14px; text-overflow: ellipsis; white-space: nowrap; }.player-button > svg { flex: 0 0 auto; color: var(--color-muted-text); transition: transform 150ms ease; }.player-button > svg.rotated { transform: rotate(180deg); }
.team-cell { position: relative; overflow: visible !important; }.team-link, .team-menu summary { color: var(--color-primary); font-size: 11px; font-weight: 850; text-decoration: none; }.team-link:hover, .team-link:focus-visible, .team-menu summary:hover, .team-menu summary:focus-visible { color: var(--color-foreground); }.team-menu { position: relative; }.team-menu summary { cursor: pointer; list-style: none; }.team-menu summary::-webkit-details-marker { display: none; }.team-menu summary:focus-visible { border-radius: 4px; outline: 2px solid var(--color-primary); outline-offset: 3px; }.team-popover { position: absolute; z-index: 8; top: calc(100% + 8px); left: 50%; display: flex; gap: 5px; min-width: max-content; transform: translateX(-50%); border: 1px solid var(--color-border); border-radius: 8px; padding: 6px; background: var(--color-background); box-shadow: 0 10px 28px rgb(0 0 0 / 35%); }.team-popover a { border-radius: 5px; padding: 5px 7px; color: var(--color-primary); background: var(--color-surface); font-size: 10px; font-weight: 900; text-decoration: none; }.team-popover a:hover, .team-popover a:focus-visible { color: var(--color-on-primary); background: var(--color-primary); outline: none; }
.profile-row > td { position: static !important; padding: 0 !important; white-space: normal !important; background: var(--color-background) !important; }.profile-panel { padding: 18px 20px 20px; }.profile-panel > header { display: flex; align-items: center; justify-content: space-between; gap: 18px; }.profile-panel > header span, .profile-grid article > header span { color: var(--color-primary); font-size: 9px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }.profile-panel h3 { margin: 3px 0 0; color: var(--color-foreground); font-size: 22px; }.profile-panel h3 small { color: var(--color-muted-text); font-size: 13px; }.profile-panel > header a { display: inline-flex; align-items: center; gap: 6px; border-radius: 999px; padding: 8px 13px; color: var(--color-on-primary); background: var(--color-primary); font-size: 11px; font-weight: 850; text-decoration: none; }.profile-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-top: 14px; }.profile-grid article { border: 1px solid var(--color-border); border-radius: 12px; padding: 14px; background: var(--color-surface); }.profile-grid h4 { margin: 4px 0 0; color: var(--color-foreground); font-size: 15px; }.profile-bar { display: flex; height: 18px; overflow: hidden; margin-top: 14px; border-radius: 6px; background: var(--color-muted); }.profile-bar i { display: grid; place-items: center; min-width: 1px; color: #fff; font-size: 8px; font-style: normal; font-weight: 900; }.profile-bar i.negative { background: color-mix(in srgb, var(--color-destructive) 70%, #6b7280); }.profile-bar i.neutral { background: #4d9ec2; }.profile-labels { display: grid; grid-template-columns: repeat(3, 1fr); gap: 5px; margin-top: 9px; }.profile-labels span { display: grid; gap: 2px; }.profile-labels span:nth-child(2) { text-align: center; }.profile-labels span:last-child { text-align: right; }.profile-labels b { color: var(--color-foreground); font-size: 10px; }.profile-labels small { color: var(--color-muted-text); font-size: 10px; }.profile-grid footer { margin-top: 12px; border-top: 1px solid var(--color-border); padding-top: 9px; color: var(--color-muted-text); font-size: 10px; }
.board-footer { display: flex; align-items: center; gap: 18px; padding: 11px 18px; color: var(--color-muted-text); font-size: 10px; }.board-footer button { border: 1px solid var(--color-border); border-radius: 999px; padding: 6px 10px; color: var(--color-primary); background: var(--color-background); cursor: pointer; font-size: 10px; font-weight: 850; }.board-footer button:hover, .board-footer button:focus-visible { border-color: var(--color-primary); }.board-footer a { display: inline-flex; align-items: center; gap: 4px; margin-left: auto; color: var(--color-primary); font-weight: 800; }.method-note { margin-top: 12px; border-radius: 13px; padding: 16px 18px; }.method-note strong { color: var(--color-foreground); }.method-note p { margin: 5px 0 0; color: var(--color-muted-text); font-size: 12px; line-height: 1.55; }
@media (max-width: 1180px) { .filter-panel { grid-template-columns: repeat(3, minmax(0, 1fr)); }.matchup-filters { grid-template-columns: 1fr 1fr; }.pa-slider { grid-column: 1 / -1; }.board-heading { align-items: flex-start; flex-direction: column; }.board-controls { width: 100%; flex-wrap: wrap; }.summary-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 760px) { .timing-page { padding-top: 28px; }.page-hero { align-items: flex-start; flex-direction: column; }.rules-card { width: 100%; }.filter-panel, .matchup-filters { grid-template-columns: 1fr 1fr; }.pa-slider { grid-column: 1 / -1; }.summary-grid { grid-template-columns: 1fr 1fr; }.board-controls { align-items: stretch; flex-direction: column; }.board-controls label, .board-controls .search { width: 100%; min-width: 0; }.dimension-tabs { display: grid; grid-template-columns: repeat(3, 1fr); }.profile-grid { grid-template-columns: 1fr; }.board-footer { align-items: flex-start; flex-direction: column; }.board-footer a { margin-left: 0; } }
@media (max-width: 480px) { .filter-panel, .summary-grid { grid-template-columns: 1fr; } }
@media (prefers-reduced-motion: reduce) { .rules-card summary svg, .player-button > svg { transition: none; } }
</style>
