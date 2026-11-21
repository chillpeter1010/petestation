<script setup lang="ts">
import type { DecisionTimelineGame } from '~/types/decisionResearch'

const props = defineProps<{ games: DecisionTimelineGame[] }>()
const chartId = `decision-we-${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`
const gameIndex = ref(0)
const pointIndex = ref(0)
const game = computed(() => props.games[gameIndex.value])
const point = computed(() => game.value?.points[pointIndex.value])
const comparison = computed(() => game.value?.researchPoints.find(row => row.decision_id === point.value?.decisionId))
const scenario = computed(() => point.value?.phase === 'anchor' ? game.value?.scenarios?.find(row => row.decision_id === point.value?.decisionId) : undefined)
const shadow = computed(() => point.value?.phase === 'anchor' ? game.value?.shadowWarnings?.find(row => row.decision_id === point.value?.decisionId) : undefined)
const pointPhase = (phase: string) => phase === 'anchor' ? '共同截點（預定打者）' : phase === 'before' ? '實際決策前' : '打席後'
watch(gameIndex, () => { pointIndex.value = 0 })
const left = 66, right = 1010, top = 35, bottom = 275
const maxX = computed(() => Math.max(1, ...(game.value?.points.map(p => p.x) || [1])))
const x = (value: number) => left + value / maxX.value * (right - left)
const y = (value: number) => top + (1 - value) * (bottom - top)
const signed = (value: number, digits = 3) => `${value > 0 ? '+' : ''}${value.toFixed(digits)}`
const path = computed(() => {
  let pen = false
  return game.value?.points.map(p => {
    if (p.phase === 'anchor') return ''
    if (p.homeWe === null) { pen = false; return '' }
    const segment = `${pen ? 'L' : 'M'}${x(p.x)},${y(p.homeWe)}`
    pen = true
    return segment
  }).join(' ') || ''
})
const inningTicks = computed(() => game.value?.points.filter((p, i, points) => i === 0 || p.inning !== points[i - 1]?.inning) || [])
const anchor = (id: string) => game.value?.points.find(p => p.decisionId === id && p.phase === 'before')
const selectX = (value: number) => {
  if (!game.value) return
  let closest = 0
  game.value.points.forEach((p, i) => { if (Math.abs(p.x - value) < Math.abs(game.value!.points[closest]!.x - value)) closest = i })
  pointIndex.value = closest
}
const selectAnchor = (id: string) => {
  const index = game.value?.points.findIndex(p => p.decisionId === id && p.phase === 'anchor') ?? -1
  if (index >= 0) pointIndex.value = index
}
const direction = (value: string) => ({ pool_higher: '替代池研究估計較高', continue_higher: '續投研究估計較高', uncertain_or_unsupported: '差異不明或模擬支持不足' }[value] || value)
</script>

<template>
  <section v-if="game" class="research-timeline" :aria-labelledby="`${chartId}-title`">
    <div class="timeline-heading"><div><h3 :id="`${chartId}-title`">單場勝率與調度研究時間軸</h3><p>參考 Momentum 呈現：50% 中線、逐打席查看。曲線為實際局面對應的凍結研究 WE；WPA 是相鄰局面的勝率變化。</p></div>
      <label>歷史範例<select v-model.number="gameIndex"><option v-for="(item, index) in games" :key="item.gamePk" :value="index">{{ item.date }} · {{ item.away }} @ {{ item.home }}</option></select></label>
    </div>
    <p class="legend"><span><i class="actual-key" /> 官方實際換投（上軌）</span><span v-if="game.exploratory"><i class="shadow-key" /> 影子風險提醒（下軌，非換投建議）</span><span v-else><i class="research-key" /> 決策前研究比較點（下軌，非建議）</span></p>
    <div class="chart-scroll" tabindex="0" role="region" aria-label="單場研究勝率圖，可水平捲動">
      <svg viewBox="0 0 1040 325" role="img" :aria-label="`${game.away} 對 ${game.home} 主隊勝率時間軸`">
        <defs><clipPath :id="`${chartId}-upper`"><rect :x="left" :y="top" :width="right - left" :height="(bottom - top) / 2" /></clipPath><clipPath :id="`${chartId}-lower`"><rect :x="left" :y="(top + bottom) / 2" :width="right - left" :height="(bottom - top) / 2" /></clipPath></defs>
        <g v-for="tick in [0, .25, .5, .75, 1]" :key="tick"><line :x1="left" :x2="right" :y1="y(tick)" :y2="y(tick)" class="grid-line" :class="{ center: tick === .5 }" /><text :x="left - 10" :y="y(tick) + 4" text-anchor="end">{{ tick * 100 }}%</text></g>
        <g v-for="tick in inningTicks" :key="tick.inning"><line :x1="x(tick.x)" :x2="x(tick.x)" :y1="top" :y2="bottom" class="inning-line" /><text :x="x(tick.x)" y="321" text-anchor="middle">{{ tick.inning }}局</text></g>
        <path :d="path" class="we-line home-line" :clip-path="`url(#${chartId}-upper)`" /><path :d="path" class="we-line away-line" :clip-path="`url(#${chartId}-lower)`" />
        <g v-for="change in game.actualChanges" :key="change.eventId" role="button" tabindex="0" :aria-label="change.description" class="marker" @click="selectX(change.x)" @keydown.enter="selectX(change.x)" @keydown.space.prevent="selectX(change.x)">
          <title>{{ change.description }} · {{ change.at }}</title><line :x1="x(change.x)" :x2="x(change.x)" :y1="top" :y2="bottom" class="actual-line" /><rect :x="x(change.x) - 5" y="15" width="10" height="10" class="actual-marker" />
        </g>
        <g v-for="row in game.researchPoints" :key="row.decision_id" role="button" tabindex="0" :aria-label="`${row.inning}局${row.half === 'top' ? '上' : '下'}，${direction(row.research_direction)}`" class="marker" @click="selectX(anchor(row.decision_id)?.x || 0)" @keydown.enter="selectX(anchor(row.decision_id)?.x || 0)" @keydown.space.prevent="selectX(anchor(row.decision_id)?.x || 0)">
          <title>決策前研究估計 ΔxWPA {{ signed(100 * row.wpa_delta) }}pp；{{ direction(row.research_direction) }}</title><path :transform="`translate(${x(anchor(row.decision_id)?.x || 0)} 295)`" d="M0,-5 L5,0 L0,5 L-5,0 Z" class="research-marker" />
        </g>
        <g v-for="warning in game.shadowWarnings || []" :key="warning.decisionId" role="button" tabindex="0" :aria-label="`${warning.role}研究提醒，下一PA失分風險${(warning.risk * 100).toFixed(1)}%`" class="marker" @click="selectAnchor(warning.decisionId)" @keydown.enter="selectAnchor(warning.decisionId)" @keydown.space.prevent="selectAnchor(warning.decisionId)"><title>下一PA失分風險 {{ (100 * warning.risk).toFixed(1) }}%；非換投建議</title><circle :cx="x(warning.x)" cy="295" r="5" class="shadow-marker" /></g>
        <circle v-for="p in game.points.filter(p => p.homeWe !== null)" :key="`${p.decisionId}-${p.phase}`" :cx="x(p.x)" :cy="y(p.homeWe ?? .5)" r="7" class="point-hit" @click="pointIndex = game.points.indexOf(p)" @mouseenter="pointIndex = game.points.indexOf(p)"><title>{{ p.inning }}局{{ p.half === 'top' ? '上' : '下' }} · {{ pointPhase(p.phase) }} · {{ p.pitcherName }}</title></circle>
        <g v-if="point && point.homeWe !== null"><line :x1="x(point.x)" :x2="x(point.x)" :y1="top" :y2="bottom" class="cursor-line" /><circle :cx="x(point.x)" :cy="y(point.homeWe)" r="4" class="active-point" /></g>
      </svg>
    </div>
    <label class="point-control">逐點查看（可用方向鍵）<input v-model.number="pointIndex" type="range" min="0" :max="game.points.length - 1" aria-label="選擇決策前或打席後的時間點" /></label>
    <div v-if="point" class="point-detail" aria-live="polite">
      <p><strong>{{ point.inning }}局{{ point.half === 'top' ? '上' : '下' }} · {{ pointPhase(point.phase) }}</strong>　{{ game.away }} {{ point.awayScore }}：{{ point.homeScore }} {{ game.home }}</p>
      <p>投手 {{ point.pitcherName }} · 打者 {{ point.batterName }} · {{ point.outs ?? '未知' }} 出局 · 主隊 WE {{ point.homeWe === null ? '無可靠局面' : `${(100 * point.homeWe).toFixed(1)}%` }} · 事後本打席主隊 WPA {{ point.homeWpa === null ? '未知' : `${signed(100 * point.homeWpa, 2)}pp` }}</p>
      <p>{{ point.phase === 'anchor' ? '截點說明' : '實際打席結果（事後）' }}：{{ point.description }}</p>
      <p v-if="shadow">影子提醒：下一PA失分風險 {{ (100 * shadow.risk).toFixed(1) }}%，門檻 {{ (100 * shadow.threshold).toFixed(1) }}%。原投手後續{{ shadow.targetObserved ? '可觀測' : '未知，不能算誤報' }}。這不是換投合理性判定。</p>
      <div v-if="comparison" class="comparison-detail"><strong>該打席決策前的固定半局研究比較</strong><p>續投 xWPA {{ signed(100 * comparison.wpa_continue) }}pp；替代池 {{ signed(100 * comparison.wpa_pool) }}pp；差 {{ signed(100 * comparison.wpa_delta) }}pp。ΔxRE24 {{ signed(comparison.re24_delta) }} 分。</p><p>配對模擬誤差範圍（95%）：[{{ signed(100 * comparison.wpa_mc95_low) }}, {{ signed(100 * comparison.wpa_mc95_high) }}]pp；模型重抽樣範圍（中央80%）：[{{ signed(100 * comparison.wpa_bootstrap80_low) }}, {{ signed(100 * comparison.wpa_bootstrap80_high) }}]pp。</p><p>{{ direction(comparison.research_direction) }}。這些範圍未涵蓋完整模型與選擇偏差，不是換投建議。</p></div>
      <div v-else-if="scenario" class="comparison-detail"><strong>共同截點模型情境 · {{ scenario.pool_n }}位名義後援均勻池</strong><p>下一PA：ΔxWPA {{ signed(100 * scenario.pa_wpa_delta) }}pp，ΔxRE24 {{ signed(scenario.pa_re24_delta) }}分；{{ scenario.pa_supported ? '通過本輪模擬支持檢查' : '外推或轉移支持不足' }}。</p><p>留到半局末：ΔxWPA {{ signed(100 * scenario.half_wpa_delta) }}pp，ΔxRE24 {{ signed(scenario.half_re24_delta) }}分；{{ scenario.half_supported ? '通過本輪模擬支持檢查' : '外推、截尾或轉移支持不足' }}。</p><p>半局差值配對MC95範圍 [{{ signed(100 * scenario.half_wpa_mc95_low) }}, {{ signed(100 * scenario.half_wpa_mc95_high) }}]pp，只含模擬誤差，未涵蓋模型及選擇偏差。</p></div>
      <p v-else>此時間點沒有本批可用的角色替代池比較，保留未知。</p>
      <small>{{ point.decisionId }} · game_pk={{ game.gamePk }} · 官方 PA={{ point.atBat }}。同場逐球同步留 Slice 19，尚未接入 In game。</small>
    </div>
    <p v-if="game.exploratory" class="scope-note">曲線沿實際歷史，並非照提醒換投後的整場預測；提醒後仍使用實際投手資料。前三棒由過去棒次推估，後續回聯盟先驗；半局情境兩方案皆留所選投手至局末，未納IBB／獨立跑者事件。名義池熱身／健康未知，推薦關閉。標記為官方順序，非真實時間間距。</p>
    <p v-else class="scope-note">替代池只有名義規則與歷史支持，熱身／健康未知。第一位打者使用當時資料，後續使用相同的訓練期聯盟打者抽樣；兩方案皆投至半局結束。標記按官方事件順序排列，非真實時間間距；線段保持原始模型點、不作平滑。</p>
  </section>
</template>

<style scoped>
.shadow-key,.shadow-marker{background:#fbbf24;fill:#fbbf24}
.research-timeline{min-width:0}.timeline-heading{display:flex;justify-content:space-between;gap:18px;flex-wrap:wrap}.timeline-heading h3{margin:0 0 8px}.timeline-heading p,.scope-note{color:var(--color-muted-text);font-size:13px;line-height:1.7}.timeline-heading label{display:grid;gap:7px;font-size:13px}select{max-width:100%;padding:9px;background:var(--color-surface);border:1px solid var(--color-border);border-radius:6px;color:var(--color-foreground)}.legend{display:flex;gap:20px;flex-wrap:wrap;font-size:12px}.legend span{display:flex;gap:8px;align-items:center}.legend i{width:9px;height:9px;display:inline-block}.actual-key,.actual-marker{background:#60a5fa;fill:#60a5fa}.research-key{border:1px solid var(--color-primary);transform:rotate(45deg)}.chart-scroll{overflow-x:auto}svg{width:100%;min-width:740px;display:block}svg text{font-size:11px;fill:var(--color-muted-text)}.grid-line,.inning-line{stroke:var(--color-border);stroke-width:1}.center{stroke:var(--color-muted-text);stroke-width:1.3}.inning-line{stroke-dasharray:4 6}.we-line{fill:none;stroke-width:2.5;stroke-linejoin:round}.home-line{stroke:var(--color-primary)}.away-line{stroke:#60a5fa}.actual-line{stroke:#60a5fa;stroke-dasharray:3 6;opacity:.25}.research-marker{fill:var(--color-surface);stroke:var(--color-primary);stroke-width:1.5}.marker,.point-hit{cursor:pointer}.point-hit{fill:transparent}.cursor-line{stroke:var(--color-muted-text);stroke-dasharray:3 4;pointer-events:none}.active-point{fill:var(--color-primary);pointer-events:none}.point-control{display:grid;gap:10px;font-size:12px;margin:10px 0 16px}.point-control input{width:100%;accent-color:var(--color-primary)}.point-detail{border:1px solid var(--color-border);border-radius:8px;padding:14px;line-height:1.7;font-size:13px}.point-detail p{margin:4px 0}.point-detail small{color:var(--color-muted-text);overflow-wrap:anywhere}.comparison-detail{border-top:1px solid var(--color-border);margin-top:12px;padding-top:12px}.scope-note{margin-bottom:0}:focus-visible{outline:2px solid var(--color-primary);outline-offset:3px}@media(max-width:700px){.timeline-heading label{width:100%}}
</style>
