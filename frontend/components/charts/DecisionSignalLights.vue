<script setup lang="ts">
import { assessSignalLights, SIGNAL_BANDS, SIGNAL_STATES } from '~/utils/decisionSignalLights'
import type { GateState, SignalGates, SignalLight, SignalLightsSnapshot, SignalState } from '~/utils/decisionSignalLights'

const props = defineProps<{ data: SignalLightsSnapshot }>()
const mode = ref<'observed' | 'demo'>('observed')
const selectedId = ref(props.data.cases[0]?.id ?? '')
const selected = computed(() => props.data.cases.find(item => item.id === selectedId.value) ?? props.data.cases[0])
const demoStates = ref<SignalState[]>(['red', 'red', 'yellow', 'green'])
const demoGates = ref<SignalGates>({ value: 'pass', legal: 'pass', availability: 'unknown', statePersistence: 'pass', validation: 'pass' })
const definitions = [
  { id: 'A' as const, title: '球質下降', detail: '球速、球種與Stuff同群，只算一票' },
  { id: 'B' as const, title: '位置／控球代理', detail: 'Location與Command同群，不能互相重複計分' },
  { id: 'C' as const, title: '對手接觸偏離', detail: '本輪採條件接觸率代理，尚非鎖定球種或熟悉度因果結論' },
  { id: 'D' as const, title: '負荷／恢復壓力', detail: '本場、跨場與局間恢復分開，不將用球數等同疲勞' }
]
const demoLights = computed<SignalLight[]>(() => definitions.map((item, index) => ({
  id: item.id, title: item.title, state: demoStates.value[index] ?? 'gray', calibrated: true, supportKnown: true,
  reason: '手動設定的規則示範，不代表真實球員狀態', evidence: [item.detail]
})))
const displayedLights = computed(() => mode.value === 'demo' ? demoLights.value : selected.value?.lights ?? [])
const gates = computed(() => mode.value === 'demo' ? demoGates.value : selected.value?.gates)
const assessment = computed(() => displayedLights.value.length === 4 && gates.value ? assessSignalLights(displayedLights.value, gates.value, mode.value) : null)
const gateDefinitions: { key: keyof SignalGates; title: string; note: string }[] = [
  { key: 'value', title: '替代收益', note: '有支持的WPA／RE24比較，與狀態分數分開' },
  { key: 'legal', title: '名義合法', note: '原研究邊界具兩種名義合法選擇' },
  { key: 'availability', title: '實際可用性', note: 'active、熱身、醫療與人工確認不可由名單推定' },
  { key: 'statePersistence', title: '原因持續性', note: '兩個新的相鄰10球區段確認，重讀同區段不算新證據' },
  { key: 'validation', title: '組合預測支持', note: '尾端燈色已校準，不代表兩紅就能預測惡化；兩角色本輪均未通過' }
]
const gateLabel = (value: GateState | undefined) => value === 'pass' ? '通過此項' : value === 'fail' ? '未通過' : '尚未確認'
const stateLabel = (value: SignalState) => SIGNAL_STATES.find(item => item.id === value)?.label ?? '灰 · 證據不足'
const presets = [
  { label: '資料不足', states: ['gray', 'gray', 'gray', 'gray'], availability: 'unknown', value: 'unknown' },
  { label: '未見異常', states: ['green', 'green', 'green', 'green'], availability: 'pass', value: 'fail' },
  { label: '短暫波動', states: ['yellow', 'green', 'green', 'yellow'], availability: 'pass', value: 'fail' },
  { label: '多項異常 · 可用未知', states: ['red', 'red', 'yellow', 'green'], availability: 'unknown', value: 'pass' },
  { label: '評估條件成立示範', states: ['red', 'red', 'red', 'yellow'], availability: 'pass', value: 'pass' }
] as const
function preset(index: number) {
  const item = presets[index]
  if (!item) return
  demoStates.value = [...item.states]
  demoGates.value = { value: item.value, legal: 'pass', availability: item.availability, statePersistence: 'pass', validation: 'pass' }
}
</script>

<template>
  <section id="signal-lights" class="signal-board" aria-labelledby="signal-lights-title">
    <header class="board-header"><div><span class="eyebrow">MULTI-SIGNAL MONITOR · 14.2.4</span><h2 id="signal-lights-title">多項原因，組成一盞綜合狀態燈</h2><p>像景氣燈號一樣看整體，也能往下看原因。總燈描述狀態，換投評估另外檢查替代收益與可用條件。</p></div><span class="prototype-tag">分燈尾端已校準 · 預測支持未過</span></header>
    <div class="source-controls">
      <div class="mode-switch" role="group" aria-label="選擇真實資料或規則示範"><button type="button" :aria-pressed="mode === 'observed'" @click="mode = 'observed'">實際研究資料</button><button type="button" :aria-pressed="mode === 'demo'" @click="mode = 'demo'">互動規則示範</button></div>
      <label v-if="mode === 'observed'" class="case-select">研究邊界快照（導航樣本）<select v-model="selectedId"><option v-for="item in data.cases" :key="item.id" :value="item.id">{{ item.label }}</option></select></label>
    </div>
    <p v-if="mode === 'demo'" class="demo-notice" role="status">示範模式：下方燈色由你手動指定，沒有重新預測比賽，也不代表模型驗證或真實換投建議。</p>
    <p v-else class="source-note">{{ data.scoreStatus }} 快照保留原11例，另加固定雜湊24例及明示的狀態事件；共 {{ data.counts.cases }} 例僅供導航，不能作提醒率分母。完整分母見下方回放。SP滿35球、RP滿10球為觀測成熟門檻，灰色不代表正常。</p>
    <section v-if="data.calibrationSummary" aria-labelledby="calibration-results-title">
      <h3 id="calibration-results-title">這輪實際跑出的結果</h3>
      <p>{{ data.calibrationSummary.blocks.toLocaleString() }} 個不重疊10球區段、{{ data.calibrationSummary.actorRows.toLocaleString() }} 個有機PA特徵。用進場前個人參考及正常進程分開預期變化／額外偏離，EWMA只讀已完成區段，跨局保留累積負荷。</p>
      <p>固定32場 {{ data.calibrationSummary.replay.flow.modeled }} 個可算邊界中，{{ data.calibrationSummary.replay.flow.full_four }} 個四群可判讀；{{ data.calibrationSummary.replay.flow.state_episodes }} 次持續狀態事件、{{ data.calibrationSummary.replay.flow.observed_recovery }} 次觀測解除、{{ data.calibrationSummary.replay.flow.nominal_research_alerts }} 新增換投研究候選、0對應、0正式推薦。舊14.2的11／0另行保留，兩者不能相加當新成效。</p>
      <div class="result-scroll" role="region" aria-label="角色模型新增特徵比較，可水平捲動" tabindex="0"><table><thead><tr><th>角色／2024樣本</th><th>原模型LL</th><th>共同控制LL</th><th>A</th><th>B</th><th>C</th><th>D</th><th>全部</th><th>採用</th></tr></thead><tbody><tr v-for="row in data.calibrationSummary.outcomeModels" :key="row.role"><th>{{ row.role }}／{{ row.n.toLocaleString() }}</th><td>{{ row.referenceLL.toFixed(5) }}</td><td v-for="v in row.variants" :key="v.variant">{{ v.LL.toFixed(5) }}</td><td>{{ row.selected === 'retain_previous' ? '保留原模型' : row.selected }}</td></tr></tbody></table></div>
      <details><summary>去雜訊比較與事件規則</summary><p>LL、Brier越低越好；新增方案須同時優於共同控制與實際原模型，並通過群聚區間、校準及子群檢查。本輪均未通過。正常平滑對不平滑及常數參考的2024比較也未通過完整增益門檻，不能只憑平均較低宣稱有效。</p><div class="result-scroll" role="region" aria-label="平滑與對照Brier" tabindex="0"><table><thead><tr><th>角色／群</th><th>有未來量測n</th><th>平滑</th><th>不平滑</th><th>常數</th><th>增益</th></tr></thead><tbody><tr v-for="row in data.calibrationSummary.normal2024" :key="row.role + row.group"><th>{{ row.role }}／{{ row.group }}</th><td>{{ row.n.toLocaleString() }}</td><td>{{ row.smooth_brier.toFixed(5) }}</td><td>{{ row.raw_brier.toFixed(5) }}</td><td>{{ row.constant_brier.toFixed(5) }}</td><td>{{ row.predictive_gate ? '通過' : '未通過' }}</td></tr></tbody></table></div><p>兩個新的相鄰10球區段確認，灰燈暫停不當解除；兩個新區段A/B綠、C非紅才解除，D可仍高，恢復後可重新形成事件。本次沒有實際觀測解除例，解除／重啟只有規則測試支持。沒有未來完整區段者設限，不補成沒有惡化；兩紅／三紅選擇只讀2022／23，2024已用診斷、2025封存。</p></details>
    </section>
    <div v-if="mode === 'demo'" class="preset-controls" role="group" aria-label="切換示範情境"><button v-for="(item, index) in presets" :key="item.label" type="button" @click="preset(index)">{{ item.label }}</button></div>

    <div v-if="assessment" class="monitor-grid">
      <article class="composite" :class="`tone-${assessment.color}`" aria-live="polite">
        <span class="section-kicker">綜合狀態</span>
        <div class="signal-orb" aria-hidden="true"><span /></div>
        <h3>{{ assessment.label }}</h3>
        <div class="score"><strong>{{ assessment.score === null ? '—' : assessment.score }}</strong><span>/ 8 研究分數</span></div>
        <p>{{ assessment.known }}／4群可判讀 · {{ assessment.redCount }}群紅燈</p>
        <p v-if="assessment.score === null" class="score-note">已知部分 {{ assessment.knownScore }} 分，尚缺 {{ 4 - assessment.known }} 群；不補0、不重算分母，暫不指定總燈色。</p>
        <p v-else class="score-note">綠0、黃1、紅2，每群只算一票。總分仍是待回測的等權設計。</p>
      </article>
      <div class="cause-grid" aria-label="四項原因燈">
        <article v-for="(light, index) in assessment.normalized" :key="light.id" class="cause-card" :class="`tone-${light.state}`">
          <div class="cause-heading"><span class="cause-id">{{ light.id }}</span><h3>{{ light.title }}</h3><span class="mini-orb" aria-hidden="true" /></div>
          <span class="state-label">{{ stateLabel(light.state) }}</span>
          <label v-if="mode === 'demo'" class="demo-select">指定示範燈色<select v-model="demoStates[index]"><option v-for="state in SIGNAL_STATES" :key="state.id" :value="state.id">{{ state.label }}</option></select></label>
          <p>{{ light.reason }}</p>
          <ul><li v-for="evidence in light.evidence" :key="evidence">{{ evidence }}</li></ul>
        </article>
      </div>
    </div>
    <div class="score-scale" aria-label="五級狀態燈色；資料不齊另用灰色"><div v-for="band in SIGNAL_BANDS" :key="band.color" :class="[`tone-${band.color}`, { active: assessment?.color === band.color }]"><i aria-hidden="true" /><strong>{{ band.label }}</strong><span>{{ band.range }} 分</span></div></div>

    <section v-if="gates" class="decision-layer" aria-labelledby="light-decision-title">
      <div class="decision-heading"><div><span class="section-kicker">獨立的評估條件 · 不加進總分</span><h3 id="light-decision-title">多盞異常，還要有可行的替代方案</h3></div><span class="candidate-tag">{{ assessment?.researchCandidate ? (mode === 'demo' ? '示範：評估條件成立' : '研究評估候選') : '評估條件尚未齊備' }}</span></div>
      <p>展示候選：四群皆可判讀，至少兩群紅且包含A或B、原因持續成立，組合取得預測支持，再確認收益、名義合法與實際可用性。總分高不能略過這些條件；任何狀態都不直接開啟正式推薦。</p>
      <div class="gate-grid"><article v-for="item in gateDefinitions" :key="item.key" :class="`gate-${gates[item.key]}`"><div><i aria-hidden="true" /><strong>{{ item.title }}</strong></div><span>{{ gateLabel(gates[item.key]) }}</span><label v-if="mode === 'demo'">示範條件<select v-model="demoGates[item.key]"><option value="unknown">尚未確認</option><option value="pass">通過此項</option><option value="fail">未通過</option></select></label><p>{{ item.note }}</p></article></div>
      <p v-if="mode === 'observed' && selected" class="context-note">{{ selected.valueNote }}</p>
      <details v-if="assessment && assessment.blockers.length"><summary>目前尚未滿足的條件（{{ assessment.blockers.length }}）</summary><ul><li v-for="reason in assessment.blockers" :key="reason">{{ reason }}</li></ul></details>
    </section>
    <details v-if="mode === 'observed' && selected" class="context-detail"><summary>對戰情境與資料來源</summary><p>{{ selected.matchupNote }}</p><p>局面LI代理 {{ selected.li === null ? '未知' : selected.li.toFixed(2) }}，只作局面脈絡，不增加異常票數。研究池不是已確認可調度的人選。</p><p>{{ selected.decisionId }} · 現任{{ selected.role }} · {{ selected.pitches }}球。原14.2的11則預警／0配對保留；本輪多燈回放另列，不覆寫歷史。</p></details>
    <p class="board-footnote">14.2.2–14.2.4研究完成，尚未取得正式換投支持；下一步15重疊／續投選擇偏差研究等待另行開始。綠是目前未見尾端偏離，紅是相對過去參考有明顯偏離，均不保證健康或疲勞；0–8總分仍是展示設計。畫面待使用者驗收。</p>
  </section>
</template>

<style scoped>
.result-scroll{overflow-x:auto;max-width:100%;margin:12px 0}.result-scroll table{width:100%;border-collapse:collapse;font-size:12px;white-space:nowrap}.result-scroll th,.result-scroll td{padding:9px 12px;text-align:right;border-bottom:1px solid var(--color-border);font-variant-numeric:tabular-nums}.result-scroll th:first-child{text-align:left}
.signal-board{--lamp:#8996a9;display:grid;gap:20px;min-width:0;padding:24px;border:1px solid var(--color-border);border-radius:var(--radius-md);background:var(--color-surface)}.board-header,.decision-heading{display:flex;justify-content:space-between;align-items:flex-start;gap:18px;flex-wrap:wrap}.eyebrow,.section-kicker{font-size:11px;letter-spacing:.08em;font-weight:800;color:var(--color-muted-text)}.eyebrow{color:var(--color-primary)}h2{font-size:24px;margin:8px 0}h3{font-size:17px;margin:0}p,li{color:var(--color-muted-text);font-size:13px;line-height:1.7}p{margin:8px 0}.prototype-tag,.candidate-tag{border:1px solid var(--color-border);border-radius:99px;padding:7px 11px;font-size:12px;line-height:1.5}.source-controls{display:flex;gap:20px;align-items:end;flex-wrap:wrap}.mode-switch,.preset-controls{display:flex;gap:8px;flex-wrap:wrap}button,select{font:inherit;color:var(--color-foreground);background:var(--color-surface);border:1px solid var(--color-border);border-radius:8px;padding:9px 12px}button{cursor:pointer;font-size:13px}button[aria-pressed=true]{background:var(--color-primary);border-color:var(--color-primary);color:var(--color-on-primary)}select{max-width:100%;font-size:13px;width:100%}label{display:grid;gap:7px;font-size:12px;color:var(--color-muted-text)}.case-select{flex:1;min-width:min(100%,260px)}.demo-notice{padding:12px 15px;border-left:3px solid #e9b75e;background:rgb(233 183 94 / 8%);color:var(--color-foreground)}.source-note{margin:0}.preset-controls button{font-size:12px}.monitor-grid{display:grid;grid-template-columns:minmax(230px,.8fr) minmax(0,2fr);gap:16px}.composite{display:grid;justify-items:center;align-content:center;gap:8px;text-align:center;min-width:0;border:1px solid var(--lamp);border-radius:16px;padding:24px 18px;background:linear-gradient(160deg,rgb(255 255 255 / 3%),transparent)}.signal-orb{width:126px;height:126px;display:grid;place-items:center;border:1px solid var(--lamp);border-radius:50%;margin:12px 0;background:radial-gradient(circle,rgb(255 255 255 / 4%),transparent 70%)}.signal-orb span{display:block;width:70px;height:70px;background:var(--lamp);border-radius:50%;box-shadow:0 0 34px -13px var(--lamp)}.composite h3{font-size:21px;color:var(--lamp)}.score{display:flex;align-items:baseline;gap:9px}.score strong{font-size:46px;line-height:1.2;font-variant-numeric:tabular-nums}.score span{font-size:12px;color:var(--color-muted-text)}.composite p{margin:0}.score-note{max-width:260px}.cause-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.cause-card{min-width:0;padding:17px;border:1px solid var(--color-border);border-left:3px solid var(--lamp);border-radius:10px}.cause-heading{display:flex;align-items:center;gap:9px}.cause-heading h3{flex:1;font-size:16px}.cause-id{font-weight:800;color:var(--lamp);font-size:12px}.mini-orb{display:inline-block;width:12px;height:12px;border-radius:50%;background:var(--lamp);flex-shrink:0}.state-label{display:inline-block;color:var(--lamp);font-size:12px;font-weight:700;margin:10px 0 3px}.cause-card ul{padding-left:18px;margin:8px 0 0}.cause-card li{font-size:12px}.demo-select{margin:8px 0}.score-scale{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:5px}.score-scale>div{display:grid;gap:5px;padding:10px 9px;border:1px solid var(--color-border);border-radius:7px;opacity:.65}.score-scale>div.active{opacity:1;border-color:var(--lamp)}.score-scale i{height:5px;background:var(--lamp);border-radius:9px}.score-scale strong{font-size:12px}.score-scale span{font-size:11px;color:var(--color-muted-text)}.decision-layer{border-top:1px solid var(--color-border);padding-top:20px}.decision-heading h3{margin-top:6px}.gate-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:15px 0}.gate-grid article{--gate:#8996a9;min-width:0;border:1px solid var(--color-border);border-radius:9px;padding:13px}.gate-grid article.gate-pass{--gate:#83d7ad}.gate-grid article.gate-fail{--gate:#ef9292}.gate-grid article>div{display:flex;align-items:center;gap:8px;font-size:13px}.gate-grid i{display:block;width:8px;height:8px;border-radius:50%;background:var(--gate)}.gate-grid article>span{display:block;color:var(--gate);font-size:12px;margin-top:9px}.gate-grid label{margin-top:10px}.gate-grid p{font-size:12px;margin-bottom:0}.context-note{padding:12px;border-left:2px solid var(--color-primary)}summary{cursor:pointer;font-size:13px;color:var(--color-foreground);line-height:1.6}details ul{padding-left:22px}.context-detail,.board-footnote{padding-top:12px;border-top:1px solid var(--color-border)}.board-footnote{font-size:12px;margin:0}.tone-gray{--lamp:#98a5b7}.tone-green{--lamp:#83d7ad}.tone-lime{--lamp:#bfdb80}.tone-yellow{--lamp:#f1d16d}.tone-orange{--lamp:#efaa6c}.tone-red{--lamp:#ef9292}:focus-visible{outline:2px solid var(--color-primary);outline-offset:4px}@media(max-width:1050px){.gate-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:760px){.signal-board{padding:17px}.monitor-grid{grid-template-columns:1fr}.composite{padding:20px}.signal-orb{width:96px;height:96px;margin:5px 0}.signal-orb span{width:54px;height:54px}.cause-grid{grid-template-columns:1fr}.score-scale strong{font-size:10px}.score-scale>div{padding:8px 5px}.source-controls{align-items:stretch}.mode-switch{width:100%}.mode-switch button{flex:1}.case-select{width:100%}.gate-grid{grid-template-columns:1fr}}
</style>
