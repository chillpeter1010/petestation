<template>
  <main class="attack-page">
    <header class="page-hero">
      <div><nav><NuxtLink to="/batters">Batters</NuxtLink><span>/</span><NuxtLink to="/batters/lab">Lab</NuxtLink><span>/</span><b>Stuff Attack</b></nav><span class="eyebrow">Batter Lab · Pitch quality response</span><h1>Stuff Attack</h1><p>Who chooses to attack premium fastballs—and who still creates value when they do?</p></div>
      <details class="rules-card">
        <summary><span>Rules</span><strong>研究定義與統計口徑</strong><ChevronDown :size="18" aria-hidden="true" /></summary>
        <div class="rules-popover">
          <header><span>Stuff Attack Rules</span><h2>怎麼閱讀這份研究</h2></header>
          <section v-for="group in ruleGroups" :key="group.title"><h3>{{ group.title }}</h3><dl><div v-for="item in group.items" :key="item.term"><dt>{{ item.term }}</dt><dd>{{ item.definition }}</dd></div></dl></section>
          <p>所有百分比都使用畫面標示的分母。Adjusted 指標是依球種、球數、左右投打與粗略位置校正後再置中到聯盟平均，並不是新的 Plus 模型。</p>
        </div>
      </details>
    </header>

    <section class="filter-panel" aria-label="Stuff Attack filters">
      <label><span>Season</span><select v-model.number="year"><option v-for="option in yearOptions" :key="option" :value="option">{{ option }}</option></select></label>
      <div class="pitch-filter"><span>Pitch types</span><details><summary>{{ activePitchLabel }}<ChevronDown :size="16" aria-hidden="true" /></summary><div class="pitch-menu"><section v-for="group in pitchTypeGroups" :key="group.key"><label class="pitch-group-option"><input type="checkbox" :checked="isGroupSelected(group)" :indeterminate="isGroupPartial(group)" @change="togglePitchGroup(group)"><strong>{{ group.label }}</strong><small>{{ selectedInGroup(group) }}/{{ group.options.length }}</small></label><label v-for="option in group.options" :key="option.value" class="pitch-option"><input type="checkbox" :checked="selectedPitchTypes.includes(option.value)" :disabled="selectedPitchTypes.length === 1 && selectedPitchTypes[0] === option.value" @change="togglePitchType(option.value)"><span>{{ option.label }}</span><small>{{ option.value }}</small></label></section><p>至少保留一個球種；可跨群組複選。</p></div></details></div>
      <label><span>Pitcher hand</span><select v-model="pitcherHand"><option value="All">All pitchers</option><option value="L">LHP</option><option value="R">RHP</option></select></label>
      <label><span>Stuff+ band</span><select v-model="stuffBin"><option v-for="option in stuffBinOptions" :key="option.value" :value="option.value">{{ option.label }}</option></select></label>
      <label><span>Minimum seen</span><select v-model.number="minimumPitches"><option :value="25">25 pitches</option><option :value="50">50 pitches</option><option :value="100">100 pitches</option><option :value="150">150 pitches</option></select></label>
      <label class="search"><span>Find hitter</span><div><Search :size="16" aria-hidden="true" /><input v-model.trim="searchText" type="search" placeholder="Player or team" /></div></label>
    </section>

    <p v-if="pending" class="state-card">Building the Stuff+ response surface…</p>
    <p v-else-if="error" class="state-card error">Unable to load Stuff Attack.</p>
    <template v-else-if="response">
      <p v-for="warning in response.warnings" :key="warning" class="state-card warning">{{ warning }}</p>

      <section class="summary-grid" aria-label="Study summary">
        <article><span>Matched pitches</span><strong>{{ integer(response.matched_pitches) }}</strong><small>{{ activePitchLabel }} · {{ activeHandLabel }} · {{ activeStuffLabel }}</small></article>
        <article><span>Qualified hitters</span><strong>{{ integer(response.qualifying_batters) }}</strong><small>Minimum {{ minimumPitches }} seen</small></article>
        <article><span>League swing</span><strong>{{ percent(response.league.swing_pct) }}</strong><small>{{ percent(response.league.chase_pct) }} chase</small></article>
        <article><span>League contact</span><strong>{{ percent(response.league.contact_pct) }}</strong><small>{{ percent(response.league.whiff_pct) }} whiff / swing</small></article>
        <article><span>League RV / 100</span><strong :class="valueTone(response.league.rv_per_100_seen)">{{ signed(response.league.rv_per_100_seen) }}</strong><small>{{ response.join_coverage_pct?.toFixed(1) }}% Stuff+ coverage</small></article>
      </section>

      <section class="quadrant-card">
        <header class="section-heading chart-heading"><div><span>Player trait explorer</span><h2>Build your own hitter lens</h2></div><div class="axis-controls"><label><span>X axis</span><select v-model="xMetric"><option v-for="option in axisOptions" :key="`x-${option.key}`" :value="option.key">{{ option.label }}</option></select></label><label><span>Y axis</span><select v-model="yMetric"><option v-for="option in axisOptions" :key="`y-${option.key}`" :value="option.key">{{ option.label }}</option></select></label><button type="button" class="regression-button" :disabled="plotRows.length < 3 || xMetric === yMetric" @click="runRegression"><Calculator :size="17" aria-hidden="true" />執行回歸</button></div></header>
        <section v-if="regressionResult" class="regression-result" aria-live="polite">
          <div><span>樣本</span><strong>{{ regressionResult.n }} 位打者</strong></div>
          <div><span>Pearson r</span><strong>{{ regressionResult.correlation.toFixed(3) }}</strong></div>
          <div><span>R²</span><strong>{{ regressionResult.rSquared.toFixed(3) }}</strong></div>
          <div><span>斜率</span><strong>{{ regressionResult.slope.toFixed(3) }}</strong></div>
          <div><span>p-value</span><strong>{{ pValueLabel(regressionResult.pValue) }}</strong></div>
          <div class="significance" :class="{ significant: regressionResult.significant }"><span>雙尾檢定</span><strong>{{ regressionResult.significant ? '達統計顯著' : '未達統計顯著' }}</strong><small>門檻 p &lt; 0.05</small></div>
          <p>每位打者等權重；相關不代表因果。重複嘗試許多軸會提高偽陽性的機率。</p>
        </section>
        <div class="chart-wrap">
          <svg viewBox="0 0 760 420" role="img" aria-labelledby="quadrant-title quadrant-description">
            <title id="quadrant-title">{{ xOption.label }} and {{ yOption.label }}</title>
            <desc id="quadrant-description">Each headshot represents a qualified hitter. Right is higher on the selected X metric; up is higher on the selected Y metric.</desc>
            <defs>
              <clipPath id="attack-plot-area"><rect x="64" y="24" width="672" height="340" rx="10" /></clipPath>
              <clipPath v-for="row in plotRows" :id="`attack-headshot-${row.batter_id}`" :key="`clip-${row.batter_id}`">
                <circle :cx="xPosition(metricValue(row, xMetric))" :cy="yPosition(metricValue(row, yMetric))" :r="pointRadius(row.pitches_seen)" />
              </clipPath>
            </defs>
            <rect x="64" y="24" width="672" height="340" rx="10" class="plot-bg" />
            <line :x1="xPosition(leagueX)" y1="24" :x2="xPosition(leagueX)" y2="364" class="axis-reference" />
            <line x1="64" :y1="yPosition(leagueY)" x2="736" :y2="yPosition(leagueY)" class="axis-reference" />
            <line v-if="regressionLine" :x1="regressionLine.x1" :y1="regressionLine.y1" :x2="regressionLine.x2" :y2="regressionLine.y2" class="regression-line" clip-path="url(#attack-plot-area)" />
            <text x="70" y="43">Lower X · higher Y</text><text x="730" y="43" text-anchor="end">Higher X · higher Y</text>
            <text x="70" y="354">Lower X · lower Y</text><text x="730" y="354" text-anchor="end">Higher X · lower Y</text>
            <g v-for="row in plotRows" :key="row.batter_id" class="plot-point" :class="{ selected: batterId === row.batter_id }" tabindex="0" role="button" @click="selectBatter(row.batter_id)" @keydown.enter="selectBatter(row.batter_id)">
              <circle class="headshot-backdrop" :cx="xPosition(metricValue(row, xMetric))" :cy="yPosition(metricValue(row, yMetric))" :r="pointRadius(row.pitches_seen)" />
              <image
                :href="headshotUrl(row.batter_id)"
                :x="xPosition(metricValue(row, xMetric)) - pointRadius(row.pitches_seen)"
                :y="yPosition(metricValue(row, yMetric)) - pointRadius(row.pitches_seen)"
                :width="pointRadius(row.pitches_seen) * 2"
                :height="pointRadius(row.pitches_seen) * 2"
                :clip-path="`url(#attack-headshot-${row.batter_id})`"
                preserveAspectRatio="xMidYMid slice"
              />
              <title>{{ row.name }} — {{ xOption.label }} {{ formatMetric(metricValue(row, xMetric), xOption.unit) }}, {{ yOption.label }} {{ formatMetric(metricValue(row, yMetric), yOption.unit) }}</title>
            </g>
            <text x="400" y="405" text-anchor="middle" class="axis-label">{{ xOption.label }} →</text>
            <text x="18" y="194" text-anchor="middle" class="axis-label" transform="rotate(-90 18 194)">{{ yOption.label }} →</text>
          </svg>
        </div>
        <footer><span><i /> Top 200 by usable axis sample</span><span><i class="selected-dot" /> Selected hitter</span><small>X: {{ xOption.population }} · Y: {{ yOption.population }}. Dashed lines are league averages.</small></footer>
      </section>

      <section v-if="response.selected_batter" class="profile-card">
        <header class="section-heading"><div><span>Selected hitter</span><h2>{{ response.selected_batter.name }} <small>{{ response.selected_batter.team }}</small></h2></div><NuxtLink :to="personalLink(response.selected_batter)">Open player report</NuxtLink></header>
        <div class="profile-metrics">
          <div><span>Seen</span><strong>{{ response.selected_batter.pitches_seen }}</strong></div><div><span>Adj Swing</span><strong>{{ percent(response.selected_batter.adjusted_swing_pct) }}</strong></div><div><span>Adj Contact</span><strong>{{ percent(response.selected_batter.adjusted_contact_pct) }}</strong></div><div><span>Adj RV / 100 swings</span><strong :class="valueTone(response.selected_batter.adjusted_rv_per_100_swings)">{{ signed(response.selected_batter.adjusted_rv_per_100_swings) }}</strong></div>
        </div>
        <div class="curve-grid">
          <article v-for="point in response.response_curve" :key="point.key"><header><strong>{{ point.label }}</strong><span>{{ point.pitches_seen }} seen</span></header><div><span>Swing</span><b>{{ percent(point.swing_pct) }}</b><i><em :style="{ width: curveWidth(point.swing_pct) }" /></i><small>Lg {{ percent(point.league_swing_pct) }}</small></div><div><span>Contact</span><b>{{ percent(point.contact_pct) }}</b><i><em :style="{ width: curveWidth(point.contact_pct) }" /></i><small>Lg {{ percent(point.league_contact_pct) }}</small></div><footer><span>RV / 100 seen</span><strong :class="valueTone(point.rv_per_100_seen)">{{ signed(point.rv_per_100_seen) }}</strong></footer></article>
        </div>
      </section>

      <section class="leaderboard-card">
        <header class="section-heading"><div><span>Research leaderboard</span><h2>Premium fastball response</h2></div><div class="mode-toggle" role="group" aria-label="Metric mode"><button type="button" :class="{ active: mode === 'adjusted' }" @click="mode = 'adjusted'">Adjusted</button><button type="button" :class="{ active: mode === 'raw' }" @click="mode = 'raw'">Raw</button></div></header>
        <div class="table-scroll">
          <table>
            <thead><tr><th>Hitter</th><th>Seen</th><th>{{ mode === 'adjusted' ? 'Adj Swing%' : 'Swing%' }}</th><th>Chase%</th><th>{{ mode === 'adjusted' ? 'Adj Contact%' : 'Contact%' }}</th><th>HardHit%</th><th>Barrel%</th><th>xwOBAcon</th><th>{{ mode === 'adjusted' ? 'Adj RV/100 swings' : 'RV/100 swings' }}</th><th>Sample</th></tr></thead>
            <tbody><tr v-for="row in visibleRows" :key="row.batter_id" :class="{ selected: batterId === row.batter_id }"><td><button type="button" @click="selectBatter(row.batter_id)"><strong>{{ row.name }}</strong><small>{{ row.team }}</small></button></td><td>{{ row.pitches_seen }}</td><td>{{ percent(mode === 'adjusted' ? row.adjusted_swing_pct : row.swing_pct) }}</td><td>{{ percent(row.chase_pct) }}</td><td>{{ percent(mode === 'adjusted' ? row.adjusted_contact_pct : row.contact_pct) }}</td><td>{{ percent(row.hard_hit_pct) }}</td><td>{{ percent(row.barrel_pct) }}</td><td>{{ rate(row.xwoba_contact) }}</td><td :class="valueTone(mode === 'adjusted' ? row.adjusted_rv_per_100_swings : row.rv_per_100_swings)">{{ signed(mode === 'adjusted' ? row.adjusted_rv_per_100_swings : row.rv_per_100_swings) }}</td><td><span class="sample" :class="row.sample_status.toLowerCase().replace(' ', '-')">{{ row.sample_status }}</span></td></tr></tbody>
          </table>
        </div>
      </section>

      <aside class="method-note"><strong>How to read this study</strong><p>Contact and whiff use swings as the denominator. HardHit, Barrel, and xwOBAcon use fair batted balls. RV / 100 seen includes takes; RV / 100 swings isolates pitches the hitter chose to attack. Adjusted values are league-recentered residuals, not a new Plus model.</p><span>Data through {{ response.data_updated_at || '—' }}</span></aside>
    </template>
  </main>
</template>

<script setup lang="ts">
import { Calculator, ChevronDown, Search } from '@lucide/vue'
import type { StuffAttackAxisOption, StuffAttackLeaderboardRow } from '~/types/api'
import { linearRegression, type LinearRegressionResult } from '~/utils/linearRegression'

const api = useApi()
const year = ref(2026)
const pitchGroup = 'all_fastballs'
const selectedPitchTypes = ref(['FF', 'SI', 'FC'])
const pitcherHand = ref<'All' | 'L' | 'R'>('All')
const stuffBin = ref('115_plus')
const minimumPitches = ref(50)
const batterId = ref<number | null>(null)
const searchText = ref('')
const mode = ref<'raw' | 'adjusted'>('adjusted')
const xMetric = ref('avg_bat_speed')
const yMetric = ref('avg_exit_velocity')
const regressionResult = ref<LinearRegressionResult | null>(null)
type PitchTypeGroup = { key: string; label: string; options: Array<{ value: string; label: string }> }
const fallbackPitchTypeGroups: PitchTypeGroup[] = [
  { key: 'fastball', label: 'Fastball', options: [{ value: 'FF', label: 'Four-Seam Fastball' }, { value: 'SI', label: 'Sinker' }, { value: 'FC', label: 'Cutter' }] },
  { key: 'breaking', label: 'Breaking Ball', options: [{ value: 'SL', label: 'Slider' }, { value: 'ST', label: 'Sweeper' }, { value: 'CU', label: 'Curveball' }, { value: 'KC', label: 'Knuckle Curve' }, { value: 'SV', label: 'Slurve' }] },
  { key: 'offspeed', label: 'Offspeed', options: [{ value: 'CH', label: 'Changeup' }, { value: 'FS', label: 'Split-Finger' }, { value: 'FO', label: 'Forkball' }] },
  { key: 'specialty', label: 'Specialty', options: [{ value: 'KN', label: 'Knuckleball' }, { value: 'EP', label: 'Eephus' }, { value: 'CS', label: 'Slow Curve' }] }
]
const fallbackStuffBins = [{ value: 'lt95', label: '< 95' }, { value: '95_104', label: '95–104' }, { value: '105_114', label: '105–114' }, { value: '115_plus', label: '>= 115' }]
const ruleGroups = [
  { title: '篩選與樣本', items: [
    { term: 'Pitch types', definition: '可跨 Fastball、Breaking Ball、Offspeed 與 Specialty 群組複選球種。' },
    { term: 'Pitcher hand', definition: '可只保留左投或右投的對戰；All 代表兩者皆納入。' },
    { term: 'Stuff+ band', definition: '在完成球種與投手慣用手篩選後，只保留所選 Stuff+ 區間內的球；預設 115 以上。' },
    { term: 'Minimum seen', definition: '打者至少面對所選條件的球數，才會進入圖表與排行榜。' },
    { term: 'Competitive swing', definition: '打者最快的 90% 揮棒，加上棒速至少 60 mph 且擊球初速至少 90 mph 的揮棒。' }
  ] },
  { title: '攻擊決策與接觸', items: [
    { term: 'Swing%', definition: '揮棒數除以面對球數。' },
    { term: 'Chase%', definition: '對好球帶外球揮棒的比例。' },
    { term: 'Contact%', definition: '有碰到球的揮棒除以全部揮棒。' },
    { term: 'Whiff%', definition: '揮空數除以全部揮棒。' },
    { term: 'Adjusted', definition: '控制球種、球數、投打慣用手與粗略進壘位置後，重新置中至聯盟平均。' }
  ] },
  { title: '球棒與揮棒路徑', items: [
    { term: 'Avg Bat Speed', definition: '競爭性揮棒中，球棒甜蜜點的平均速度。' },
    { term: 'Fast Swing Rate', definition: '競爭性揮棒中，棒速達 75 mph 以上的比例。' },
    { term: 'Avg Swing Length', definition: '球棒頭從追蹤開始到接觸點移動的平均距離。' },
    { term: 'Avg Attack Angle', definition: '接觸或最接近球時，球棒甜蜜點移動方向的垂直角度。' },
    { term: 'Ideal Attack Angle Rate', definition: 'Attack Angle 落在 5° 到 20° 的比例。' },
    { term: 'Avg Swing Path Tilt', definition: '接觸前約 40 毫秒內，揮棒平面相對地面的平均傾角。' }
  ] },
  { title: '擊球與結果', items: [
    { term: 'Avg Exit Velocity', definition: '形成場內擊球時的平均擊球初速。' },
    { term: 'Hard-Hit Rate', definition: '場內擊球中，擊球初速達 95 mph 以上的比例。' },
    { term: 'Barrel Rate', definition: '場內擊球中符合 Statcast Barrel 條件的比例。' },
    { term: 'xwOBA on Contact', definition: '只看形成場內擊球時，依擊球品質估計的平均 xwOBA。' },
    { term: 'Avg Launch Angle', definition: '形成場內擊球時的平均仰角。' },
    { term: 'Avg Miss Distance', definition: '揮空時，球棒上半部與球在最接近瞬間的平均距離。' },
    { term: 'RV / 100 swings', definition: '打者每 100 次揮棒產生的平均 Run Value；正值對打者較有利。' }
  ] },
  { title: '回歸分析', items: [
    { term: 'Pearson r', definition: '衡量兩軸的線性相關方向與強度，範圍為 -1 到 1。' },
    { term: 'R²', definition: '單變量線性回歸可解釋的 Y 軸變異比例。' },
    { term: 'p-value', definition: '雙尾檢定虛無假設「母體相關係數為 0」；本站以 p < 0.05 標示顯著。' }
  ] }
]
const pitchSelectionKey = computed(() => selectedPitchTypes.value.slice().sort().join('-'))

const { data: response, pending, error } = await useAsyncData(
  () => `stuff-attack-${year.value}-${pitchSelectionKey.value}-${pitcherHand.value}-${stuffBin.value}-${minimumPitches.value}-${batterId.value || 'all'}`,
  () => api.batterStuffAttack({ year: year.value, pitchGroup, pitchTypes: selectedPitchTypes.value, pitcherHand: pitcherHand.value, stuffBin: stuffBin.value, minimumPitches: minimumPitches.value, batterId: batterId.value }),
  { watch: [year, pitchSelectionKey, pitcherHand, stuffBin, minimumPitches, batterId] }
)

watch([pitchSelectionKey, pitcherHand, stuffBin, minimumPitches], () => { batterId.value = null })
watch([year, pitchSelectionKey, pitcherHand, stuffBin, minimumPitches, xMetric, yMetric], () => { regressionResult.value = null })
const yearOptions = computed(() => response.value?.filters.available_years.length ? response.value.filters.available_years : [2026])
const pitchTypeGroups = computed<PitchTypeGroup[]>(() => response.value?.filters.pitch_type_groups.length ? response.value.filters.pitch_type_groups : fallbackPitchTypeGroups)
const stuffBinOptions = computed(() => response.value?.filters.stuff_bins.length ? response.value.filters.stuff_bins : fallbackStuffBins)
const fallbackAxisOptions: StuffAttackAxisOption[] = [{ key: 'adjusted_swing_pct', label: 'Adjusted Swing%', unit: '%', population: 'Pitches seen', description: '' }, { key: 'adjusted_rv_per_100_swings', label: 'Adjusted RV / 100 swings', unit: 'RV', population: 'Swings', description: '' }]
const axisOptions = computed(() => response.value?.filters.axis_options.length ? response.value.filters.axis_options : fallbackAxisOptions)
const xOption = computed(() => axisOptions.value.find(option => option.key === xMetric.value) || axisOptions.value[0]!)
const yOption = computed(() => axisOptions.value.find(option => option.key === yMetric.value) || axisOptions.value[1] || axisOptions.value[0]!)
const activePitchLabel = computed(() => {
  const exactGroup = pitchTypeGroups.value.find(group => group.options.length === selectedPitchTypes.value.length && group.options.every(option => selectedPitchTypes.value.includes(option.value)))
  if (exactGroup) return exactGroup.label
  if (selectedPitchTypes.value.length <= 2) return selectedPitchTypes.value.join(' + ')
  return `${selectedPitchTypes.value.length} pitch types`
})
const activeHandLabel = computed(() => pitcherHand.value === 'L' ? 'vs LHP' : pitcherHand.value === 'R' ? 'vs RHP' : 'vs All')
const activeStuffLabel = computed(() => stuffBinOptions.value.find(item => item.value === stuffBin.value)?.label || stuffBin.value)
const visibleRows = computed(() => {
  const needle = searchText.value.toLowerCase()
  return (response.value?.leaderboard || []).filter(row => !needle || `${row.name} ${row.team}`.toLowerCase().includes(needle))
})
const plotRows = computed(() => (response.value?.leaderboard || [])
  .filter(row => metricValue(row, xMetric.value) !== null && metricValue(row, yMetric.value) !== null)
  .slice()
  .sort((left, right) => usableSample(right) - usableSample(left))
  .slice(0, 200))
const leagueX = computed(() => response.value?.league_axis_metrics[xMetric.value] ?? 0)
const leagueY = computed(() => response.value?.league_axis_metrics[yMetric.value] ?? 0)
const xDomain = computed(() => domain(plotRows.value.map(row => metricValue(row, xMetric.value) as number), leagueX.value))
const yDomain = computed(() => domain(plotRows.value.map(row => metricValue(row, yMetric.value) as number), leagueY.value))
const regressionLine = computed(() => {
  if (!regressionResult.value) return null
  const [minX, maxX] = xDomain.value
  return { x1: xPosition(minX), y1: yPosition(regressionResult.value.intercept + regressionResult.value.slope * minX), x2: xPosition(maxX), y2: yPosition(regressionResult.value.intercept + regressionResult.value.slope * maxX) }
})

function domain(values: number[], anchor: number): [number, number] { const min = Math.min(anchor, ...values); const max = Math.max(anchor, ...values); const span = Math.max(max - min, Math.abs(anchor) * 0.08, 1); const padding = span * 0.08; return [min - padding, max + padding] }
function metricValue(row: StuffAttackLeaderboardRow, key: string) { return row.axis_metrics[key] ?? null }
function usableSample(row: StuffAttackLeaderboardRow) { return Math.min(row.axis_samples[xMetric.value] || 0, row.axis_samples[yMetric.value] || 0) }
function selectedInGroup(group: PitchTypeGroup) { return group.options.filter(option => selectedPitchTypes.value.includes(option.value)).length }
function isGroupSelected(group: PitchTypeGroup) { return selectedInGroup(group) === group.options.length }
function isGroupPartial(group: PitchTypeGroup) { const selected = selectedInGroup(group); return selected > 0 && selected < group.options.length }
function togglePitchGroup(group: PitchTypeGroup) {
  const values = group.options.map(option => option.value)
  if (isGroupSelected(group)) {
    const remaining = selectedPitchTypes.value.filter(value => !values.includes(value))
    if (remaining.length) selectedPitchTypes.value = remaining
  } else {
    selectedPitchTypes.value = [...new Set([...selectedPitchTypes.value, ...values])]
  }
}
function togglePitchType(value: string) {
  if (selectedPitchTypes.value.includes(value)) {
    if (selectedPitchTypes.value.length > 1) selectedPitchTypes.value = selectedPitchTypes.value.filter(option => option !== value)
  } else {
    selectedPitchTypes.value = [...selectedPitchTypes.value, value]
  }
}
function runRegression() {
  regressionResult.value = linearRegression(plotRows.value.map(row => ({ x: metricValue(row, xMetric.value) as number, y: metricValue(row, yMetric.value) as number })))
}
function xPosition(value: number | null) { const [min, max] = xDomain.value; return 64 + ((Number(value) - min) / Math.max(max - min, 1)) * 672 }
function yPosition(value: number | null) { const [min, max] = yDomain.value; return 364 - ((Number(value) - min) / Math.max(max - min, 1)) * 340 }
function pointRadius(pitches: number) { return Math.max(4.2, Math.min(9, 3.2 + Math.sqrt(pitches) / 3)) }
function headshotUrl(playerId: number) { return `https://img.mlbstatic.com/mlb-photos/image/upload/w_160,q_auto:eco,f_auto/v1/people/${playerId}/headshot/silo/current` }
function selectBatter(id: number) { batterId.value = id }
function personalLink(row: StuffAttackLeaderboardRow) { return { path: '/batter-personal', query: { year: year.value, team: row.team, batter_id: row.batter_id } } }
function integer(value: number) { return value.toLocaleString() }
function percent(value: number | null | undefined) { return value == null ? '—' : `${value.toFixed(1)}%` }
function signed(value: number | null | undefined) { return value == null ? '—' : `${value > 0 ? '+' : ''}${value.toFixed(2)}` }
function rate(value: number | null | undefined) { return value == null ? '—' : value.toFixed(3) }
function formatMetric(value: number | null, unit: string) { if (value == null) return '—'; if (unit === '%') return `${value.toFixed(1)}%`; if (unit === 'rate') return value.toFixed(3); if (unit === 'RV') return signed(value); return `${value.toFixed(1)} ${unit}` }
function pValueLabel(value: number) { return value < 0.001 ? '< 0.001' : value.toFixed(3) }
function valueTone(value: number | null | undefined) { return value == null ? '' : value > 0 ? 'positive' : value < 0 ? 'negative' : '' }
function curveWidth(value: number | null) { return `${Math.max(0, Math.min(100, value || 0))}%` }
</script>

<style scoped>
.attack-page { max-width: 1480px; min-height: 100vh; margin: 0 auto; padding: 88px clamp(14px, 2.5vw, 36px) 64px; color: var(--color-text); }
.page-hero, .filter-panel, .summary-grid article, .quadrant-card, .profile-card, .leaderboard-card, .state-card, .method-note { border: 1px solid var(--color-border); background: var(--color-surface); box-shadow: var(--shadow-sm); }
.page-hero { display: flex; align-items: end; justify-content: space-between; gap: 28px; border-radius: 20px; padding: clamp(22px, 4vw, 40px); background: radial-gradient(circle at top right, color-mix(in srgb, var(--color-primary) 22%, transparent), transparent 34%), var(--color-surface); }
.page-hero nav { display: flex; gap: 8px; margin-bottom: 20px; color: var(--color-muted-text); font-size: 12.65px; }.page-hero nav a { color: inherit; }.page-hero nav b { color: var(--color-foreground); }
.eyebrow, .section-heading > div > span { color: var(--color-primary); font-weight: 900; letter-spacing: .1em; text-transform: uppercase; }.eyebrow { font-size: 11.5px; }.section-heading > div > span { font-size: 10px; }
.page-hero h1 { margin: 7px 0 0; color: var(--color-foreground); font-size: clamp(37.4px, 5.95vw, 69.7px); line-height: .9; letter-spacing: -.06em; }.page-hero p { max-width: 720px; margin-bottom: 0; color: var(--color-muted-text); font-size: 16px; }
.rules-card { position: relative; width: min(330px, 100%); flex: 0 0 auto; }.rules-card summary { display: grid; grid-template-columns: 1fr auto; gap: 4px 12px; border: 1px solid color-mix(in srgb, var(--color-primary) 65%, var(--color-border)); border-radius: 12px; padding: 14px 16px; color: var(--color-foreground); background: color-mix(in srgb, var(--color-primary) 7%, var(--color-background)); cursor: pointer; list-style: none; }.rules-card summary::-webkit-details-marker { display: none; }.rules-card summary span { grid-column: 1; color: var(--color-primary); font-size: 8.5px; font-weight: 900; letter-spacing: .1em; text-transform: uppercase; }.rules-card summary strong { grid-column: 1; font-size: 13.6px; }.rules-card summary svg { grid-column: 2; grid-row: 1 / 3; align-self: center; color: var(--color-primary); transition: transform 160ms ease; }.rules-card[open] summary svg { transform: rotate(180deg); }.rules-popover { position: absolute; z-index: 20; top: calc(100% + 9px); right: 0; width: min(620px, calc(100vw - 44px)); max-height: min(70vh, 720px); overflow-y: auto; border: 1px solid var(--color-border); border-radius: 14px; padding: 20px; background: var(--color-surface); box-shadow: 0 18px 50px rgb(0 0 0 / 35%); }.rules-popover header { border-bottom: 1px solid var(--color-border); padding-bottom: 13px; }.rules-popover header span { color: var(--color-primary); font-size: 10px; font-weight: 900; letter-spacing: .1em; text-transform: uppercase; }.rules-popover h2 { margin: 4px 0 0; color: var(--color-foreground); font-size: 24px; }.rules-popover section { margin-top: 18px; }.rules-popover h3 { margin: 0 0 7px; color: var(--color-primary); font-size: 13px; }.rules-popover dl { margin: 0; }.rules-popover dl div { display: grid; grid-template-columns: 150px 1fr; gap: 14px; border-top: 1px solid var(--color-border); padding: 8px 0; }.rules-popover dt { color: var(--color-foreground); font-size: 12px; font-weight: 850; }.rules-popover dd, .rules-popover > p { margin: 0; color: var(--color-muted-text); font-size: 12px; line-height: 1.55; }.rules-popover > p { margin-top: 16px; border-left: 2px solid var(--color-primary); padding-left: 12px; }
.filter-panel { display: grid; grid-template-columns: 105px 220px 125px 135px 135px minmax(190px, 1fr); gap: 11px; margin-top: 16px; border-radius: 14px; padding: 13px; }.filter-panel label { display: grid; gap: 6px; }.filter-panel label > span, .pitch-filter > span { color: var(--color-muted-text); font-size: 9px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }.filter-panel select, .filter-panel input { width: 100%; min-height: 42px; border: 1px solid var(--color-border); border-radius: 8px; padding: 0 10px; color: var(--color-text); background: var(--color-background); font-weight: 700; }.pitch-filter { position: relative; display: grid; gap: 6px; min-width: 0; }.pitch-filter details { min-width: 0; }.pitch-filter summary { display: flex; align-items: center; justify-content: space-between; gap: 8px; min-height: 42px; overflow: hidden; border: 1px solid var(--color-border); border-radius: 8px; padding: 0 10px; color: var(--color-foreground); background: var(--color-background); cursor: pointer; font-size: 13px; font-weight: 800; list-style: none; white-space: nowrap; }.pitch-filter summary::-webkit-details-marker { display: none; }.pitch-filter summary svg { flex: 0 0 auto; transition: transform 150ms ease; }.pitch-filter details[open] summary svg { transform: rotate(180deg); }.pitch-menu { position: absolute; z-index: 18; top: calc(100% + 7px); left: 0; display: grid; grid-template-columns: repeat(2, minmax(210px, 1fr)); gap: 13px; width: min(520px, calc(100vw - 40px)); max-height: min(68vh, 600px); overflow-y: auto; border: 1px solid var(--color-border); border-radius: 12px; padding: 14px; background: var(--color-surface); box-shadow: 0 16px 45px rgb(0 0 0 / 35%); }.pitch-menu section { min-width: 0; }.filter-panel .pitch-group-option, .filter-panel .pitch-option { display: grid; grid-template-columns: 18px minmax(0, 1fr) auto; align-items: center; gap: 8px; min-height: 34px; color: var(--color-text); font-size: 12px; font-weight: 700; text-transform: none; cursor: pointer; }.filter-panel .pitch-group-option { border-bottom: 1px solid var(--color-border); margin-bottom: 3px; }.filter-panel .pitch-group-option strong { color: var(--color-primary); }.filter-panel .pitch-group-option small, .filter-panel .pitch-option small { color: var(--color-muted-text); font-size: 10px; }.filter-panel .pitch-option { padding-left: 5px; }.filter-panel .pitch-option span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.filter-panel .pitch-group-option input, .filter-panel .pitch-option input { width: 16px; min-height: 16px; height: 16px; margin: 0; border-radius: 3px; padding: 0; accent-color: var(--color-primary); }.filter-panel .pitch-option input:disabled { opacity: .45; cursor: not-allowed; }.pitch-menu > p { grid-column: 1 / -1; margin: 0; border-top: 1px solid var(--color-border); padding-top: 9px; color: var(--color-muted-text); font-size: 10px; }.search div { position: relative; }.search svg { position: absolute; top: 13px; left: 11px; color: var(--color-muted-text); }.search input { padding-left: 35px; }
.summary-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 11px; margin-top: 12px; }.summary-grid article { border-radius: 13px; padding: 15px; }.summary-grid span, .summary-grid small { display: block; color: var(--color-muted-text); }.summary-grid span { font-size: 11.9px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }.summary-grid strong { display: block; margin: 7px 0 4px; color: var(--color-foreground); font-size: clamp(23.46px, 2.93vw, 33.24px); }.summary-grid small { font-size: 13.225px; }
.quadrant-card, .profile-card, .leaderboard-card { margin-top: 12px; border-radius: 16px; overflow: hidden; }.section-heading { display: flex; align-items: end; justify-content: space-between; gap: 20px; padding: 19px 20px; }.section-heading h2 { margin: 5px 0 0; color: var(--color-foreground); font-size: clamp(25.3px, 3.45vw, 35.65px); }.section-heading h2 small { color: var(--color-muted-text); font-size: 14.95px; }.section-heading p { max-width: 560px; margin: 0; color: var(--color-muted-text); font-size: 12.65px; text-align: right; }.section-heading > a { border-radius: 999px; padding: 8px 13px; color: var(--color-on-primary); background: var(--color-primary); font-size: 12.65px; font-weight: 800; text-decoration: none; }
.axis-controls { display: grid; grid-template-columns: repeat(2, minmax(190px, 1fr)) auto; gap: 10px; align-items: end; }.axis-controls label { display: grid; gap: 5px; }.axis-controls label > span { color: var(--color-muted-text); font-size: 10px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }.axis-controls select { min-height: 42px; border: 1px solid var(--color-border); border-radius: 8px; padding: 0 34px 0 10px; color: var(--color-foreground); background: var(--color-background); font-size: 13px; font-weight: 800; }.regression-button { display: inline-flex; align-items: center; justify-content: center; gap: 7px; min-height: 42px; border: 0; border-radius: 8px; padding: 0 15px; color: var(--color-on-primary); background: var(--color-primary); cursor: pointer; font-size: 13px; font-weight: 900; white-space: nowrap; }.regression-button:disabled { opacity: .45; cursor: not-allowed; }.regression-result { display: grid; grid-template-columns: repeat(5, minmax(90px, 1fr)) minmax(150px, 1.25fr); gap: 1px; border-top: 1px solid var(--color-border); background: var(--color-border); }.regression-result > div { padding: 12px 15px; background: var(--color-surface); }.regression-result span, .regression-result small { display: block; color: var(--color-muted-text); font-size: 11.5px; font-weight: 800; text-transform: uppercase; }.regression-result strong { display: block; margin-top: 4px; color: var(--color-foreground); font-size: 19.55px; }.regression-result .significance.significant strong { color: #16834d; }.regression-result .significance:not(.significant) strong { color: #c2413b; }.regression-result > p { grid-column: 1 / -1; margin: 0; padding: 8px 15px; color: var(--color-muted-text); background: var(--color-background); font-size: 12.65px; }
.chart-wrap { overflow-x: auto; border-top: 1px solid var(--color-border); border-bottom: 1px solid var(--color-border); padding: 8px 14px; background: var(--color-background); }.chart-wrap svg { display: block; min-width: 720px; width: 100%; height: auto; }.plot-bg { fill: var(--color-surface); stroke: var(--color-border); }.axis-reference { stroke: var(--color-muted-text); stroke-width: 1; stroke-dasharray: 5 5; opacity: .65; }.regression-line { stroke: var(--color-primary); stroke-width: 2.3; opacity: .95; }.chart-wrap text { fill: var(--color-muted-text); font-size: 11.5px; }.axis-label { font-weight: 800; }.plot-point { cursor: pointer; outline: none; transform-box: fill-box; transform-origin: center; transition: transform 150ms ease; }.plot-point .headshot-backdrop { fill: #b9def0; stroke: var(--color-surface); stroke-width: 1.2; }.plot-point image { pointer-events: none; }.plot-point:hover, .plot-point:focus { transform: scale(1.28); }.plot-point:hover .headshot-backdrop, .plot-point:focus .headshot-backdrop { stroke: var(--color-foreground); stroke-width: 2; }.plot-point.selected .headshot-backdrop { fill: var(--color-primary); stroke: var(--color-primary); stroke-width: 2.8; }.quadrant-card > footer { display: flex; align-items: center; gap: 16px; padding: 11px 18px; color: var(--color-muted-text); font-size: 11.5px; }.quadrant-card > footer span { display: flex; align-items: center; gap: 6px; }.quadrant-card > footer i { width: 10px; height: 10px; border-radius: 50%; background: #b9def0; }.quadrant-card > footer i.selected-dot { background: var(--color-primary); box-shadow: 0 0 0 2px var(--color-foreground); }.quadrant-card > footer small { margin-left: auto; }
.profile-metrics { display: grid; grid-template-columns: repeat(4, 1fr); border-top: 1px solid var(--color-border); }.profile-metrics div { padding: 14px 20px; border-right: 1px solid var(--color-border); }.profile-metrics div:last-child { border-right: 0; }.profile-metrics span { display: block; color: var(--color-muted-text); font-size: 10.35px; font-weight: 900; text-transform: uppercase; }.profile-metrics strong { display: block; margin-top: 5px; color: var(--color-foreground); font-size: 26.45px; }.curve-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; border-top: 1px solid var(--color-border); padding: 14px; background: var(--color-background); }.curve-grid article { border: 1px solid var(--color-border); border-radius: 11px; padding: 13px; background: var(--color-surface); }.curve-grid article > header, .curve-grid article > footer { display: flex; justify-content: space-between; gap: 8px; }.curve-grid article > header { margin-bottom: 13px; }.curve-grid article > header span, .curve-grid small { color: var(--color-muted-text); font-size: 10.35px; }.curve-grid article > div { display: grid; grid-template-columns: 1fr auto; gap: 4px 8px; margin-top: 9px; font-size: 11.5px; }.curve-grid i { grid-column: 1 / -1; height: 4px; overflow: hidden; border-radius: 4px; background: var(--color-muted); }.curve-grid em { display: block; height: 100%; background: var(--color-primary); }.curve-grid article > footer { margin-top: 13px; border-top: 1px solid var(--color-border); padding-top: 10px; font-size: 11.5px; }
.mode-toggle { display: flex; border: 1px solid var(--color-border); border-radius: 9px; padding: 3px; background: var(--color-background); }.mode-toggle button { border: 0; border-radius: 6px; padding: 7px 11px; color: var(--color-muted-text); background: transparent; cursor: pointer; font-size: 15px; font-weight: 800; }.mode-toggle button.active { color: var(--color-on-primary); background: var(--color-primary); }.table-scroll { overflow-x: auto; border-top: 1px solid var(--color-border); }table { width: 100%; min-width: 1120px; border-collapse: collapse; }th, td { border-bottom: 1px solid var(--color-border); padding: 12.65px 13.8px; text-align: right; white-space: nowrap; }th { color: var(--color-muted-text); background: var(--color-background); font-size: 10.35px; letter-spacing: .06em; text-transform: uppercase; }th:first-child, td:first-child { position: sticky; left: 0; z-index: 1; text-align: left; background: var(--color-surface); }tbody tr:hover td, tbody tr.selected td { background: color-mix(in srgb, var(--color-primary) 8%, var(--color-surface)); }td { font-size: 13.8px; }td button { border: 0; padding: 0; color: inherit; background: transparent; cursor: pointer; text-align: left; font-size: inherit; }td button strong, td button small { display: block; }td button strong { color: var(--color-foreground); }td button small { color: var(--color-muted-text); }.sample { border-radius: 999px; padding: 4px 8px; color: var(--color-muted-text); background: var(--color-muted); font-size: 10.35px; }.sample.stable { color: #166534; background: #dcfce7; }.positive { color: #16834d !important; }.negative { color: #c2413b !important; }
.method-note, .state-card { margin-top: 12px; border-radius: 13px; padding: 16px 18px; }.method-note strong { color: var(--color-foreground); }.method-note p { margin: 6px 0; color: var(--color-muted-text); font-size: 12.65px; line-height: 1.6; }.method-note span { color: var(--color-muted-text); font-size: 11.5px; }.state-card { color: var(--color-muted-text); }.state-card.error { color: #c2413b; }.state-card.warning { border-color: #d59b2d; color: #8a5b08; }
@media (max-width: 1050px) { .filter-panel { grid-template-columns: repeat(2, minmax(0, 1fr)); }.filter-panel .search { grid-column: 1 / -1; }.summary-grid { grid-template-columns: repeat(3, 1fr); }.curve-grid { grid-template-columns: repeat(2, 1fr); }.axis-controls { grid-template-columns: repeat(2, minmax(180px, 1fr)); }.regression-button { grid-column: 1 / -1; }.regression-result { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 680px) { .attack-page { padding-top: 28px; }.page-hero, .section-heading { align-items: flex-start; flex-direction: column; }.rules-card { max-width: none; width: 100%; }.rules-popover { position: static; width: auto; max-height: none; margin-top: 8px; }.rules-popover dl div { grid-template-columns: 1fr; gap: 3px; }.filter-panel, .summary-grid, .profile-metrics, .curve-grid, .axis-controls, .regression-result { grid-template-columns: 1fr; width: 100%; }.pitch-menu { position: static; grid-template-columns: 1fr; width: auto; max-height: none; margin-top: 7px; }.regression-button { grid-column: auto; }.filter-panel .search { grid-column: auto; }.section-heading p { text-align: left; }.profile-metrics div { border-right: 0; border-bottom: 1px solid var(--color-border); }.quadrant-card > footer { flex-wrap: wrap; }.quadrant-card > footer small { width: 100%; margin-left: 0; } }
@media (prefers-reduced-motion: reduce) { .plot-point circle { transition: none; } }
</style>
