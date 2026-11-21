<script setup lang="ts">
import snapshot from '~/data/pitcherDecisionPlan.json'
import DecisionResearchTimeline from '~/components/charts/DecisionResearchTimeline.vue'
import type { DecisionAlertResearch } from '~/types/decisionAlerts'
import DecisionSignalLights from '~/components/charts/DecisionSignalLights.vue'
import type { SignalLightsSnapshot } from '~/utils/decisionSignalLights'
import type { DecisionTimelineGame } from '~/types/decisionResearch'

const plan = snapshot.project
const route = useRoute()
const historyOpen = (...ids: string[]) => ids.some(id => route.hash === `#${id}`)
const alertResearch = snapshot.alertResearch as DecisionAlertResearch | null
const signalLights = snapshot.signalLights as SignalLightsSnapshot | null
const overlapResearch = snapshot.overlapResearch
const overlapRevision = snapshot.overlapRevision
const rpTargets = snapshot.rpTargetResearch
const entryReview = snapshot.entryReview
const peRevision = snapshot.peRevision
const exploration = snapshot.exploratoryReplay
const explorationGames = exploration?.timeline as unknown as DecisionTimelineGame[] | undefined
const explorationVariant = (value: string) => ({ full_pool: '完整名義支持池', rest24: '至少休息24小時', load72_le40: '近72小時≤40球', other_model: '未選用模型敏感度' }[value] ?? value)
const peModelNames: Record<string, string> = { hgb_base: 'HGB共同基準', hgb_pe: 'HGB加近期PE', hgb_full: 'HGB完整群', linear_full: '正則化線性完整群', rf_full: 'Random Forest完整群', frozen15_3_binary: '原15.3二元研究模型' }
const peModelLabel = (value: string) => peModelNames[value] ?? value
const ratioPercent = (value: number | null | undefined) => value == null ? '未知' : `${(100 * value).toFixed(2)}%`
const pe2024 = peRevision?.folds.filter(x => x.year === 2024)
const entryNames: Record<string, string> = { comparison_balance: '時間前推比較平衡', multilight_predictive_support: '多燈組合預測支持', common_clock_four_reason_value_replay: '共同截點四群／價值回放', candidate_joint_support_availability: '人選聯合支持與實際可用性', aligned_half_endpoint_followup: '同半局終點與共同後續策略', balance_smd: 'SMD未過', effective_sample_size: 'ESS不足', action_calibration: '行動機率校準未過', fit_warning: '擬合警告', outside_fixed_population: '不在固定主要母體', past_cell_unsupported: '過去分格支持不足', invalid_propensity: '機率無效', development_comparison_failed: '開發年度比較未過', annual_comparison_failed: '該年度比較未過', pipeline_not_ready: '研究實作尚未就緒' }
const entryLabel = (value: string) => entryNames[value] ?? value
const crossesZero = (bounds: number[]) => (bounds[0] ?? Infinity) <= 0 && (bounds[1] ?? -Infinity) >= 0
const rpNames: Record<string, string> = { next_pa: '下一完整PA：非出局類結果', future_ten: '未來完整十球：狀態偏離', all: '全部RP', known_history: '歷史已知', short_profile: '短型歷史', extended_profile: '延長型歷史', short_load: '短型且相對負荷≤1.5', frozen15_2: '原15.2 HGB', history_enriched: '新增歷史HGB' }
const rpLabel = (value: string) => rpNames[value] ?? value
const researchNumber = (value: number | null | undefined, digits = 3) => value == null ? '未知／不適用' : value.toFixed(digits)
const rpPrimaryTasks = rpTargets?.task_results.filter(x => x.year === 2024 && x.phase === 'within_inning' && x.subset === 'short_profile')
const rpPrimarySensitivity = rpTargets?.sensitivity2024.filter(x => x.phase === 'within_inning' && x.subset === 'short_profile')
const phaseLabel = (value: string) => value === 'between_innings' ? '局間' : '局中'
const balanceModelNames: Record<string, string> = { hgb_full: '完整HGB', logit_core: '核心樣條logit', logit_full: '完整樣條logit', balance_logit: '矩條件平衡logit' }
const balanceModelLabel = (value: string) => balanceModelNames[value] ?? value
const missingNames: Record<string, string> = { observed: '有合格後續量測', immediate_change: '當下換投', insufficient_future_pitch_opportunity: '後續投球機會不足', outside_predeclared_support: '超出原支持範圍', measurement_or_reference_insufficient: '量測或個人參考不足', incomplete_block_or_session_gap: '區段／時段缺口' }
const missingLabel = (value: string) => missingNames[value] ?? value
const alertReasonLabels: Record<string, string> = {
  qualifies: '單點合格', emitted: '已發出研究預警', awaiting_persistence: '尚未連續兩點', cooldown: '同隊冷卻中',
  dedup_same_appearance: '同登板已有預警', cooldown_other_appearance: '新登板仍在同隊冷卻',
  simulation_censor_or_extrapolation: '模擬截尾或範圍外推', rare_transition_mass: '缺轉移機率超過1%',
  below_minimum_gain: '優勢未達0.5pp', mc_interval_includes_zero: '模擬區間下界未大於0',
  bootstrap_interval_includes_zero: '模型區間下界未大於0', nonfinite_value: '估值缺失',
  same_boundary: '同邊界對應', advance_window: '提前窗口對應',
  no_official_change_for_appearance: '該登板無官方換投紀錄', one_to_one_event_consumed: '事件已被其他預警配對',
  official_clock_or_boundary_unknown: '事件時鐘或邊界不明', official_event_before_alert: '官方事件早於預警',
  no_completed_pa_lead_or_different_boundary: '尚無完整PA間隔或非同一邊界', outside_2pa_window: '超過兩PA窗口',
  outside_600s_window: '超過十分鐘窗口', unknown_outgoing_appearance: '離場登板身分不明',
  no_modeled_boundary_in_fixed_window: '固定窗口內沒有可算邊界', no_persistent_alert_for_appearance: '該登板沒有持續預警',
  alert_outside_fixed_window: '已有預警但超出配對窗口',
  'cohort:initial_start': '初始先發邊界', 'cohort:no_legal_choice': '無兩種合法選擇',
  'cohort:compound_prelude': '複合前置事件', 'cohort:forced_or_injury': '強制或受傷事件',
  'cohort:not_completed_batter_play': '非完整打者play', 'cohort:mid_pa_change_or_nonzero_count': '打席中換投或非0球0好球',
  'cohort:unknown_state_or_clock': '局面或時鐘不足', 'cohort:uncertain_batter': '打者身分不足',
  'cohort:observed_replacement_outside_nominal_set': '實際接任者不在名義池（回溯cohort限制）',
  'option_support:current_left_truncated_history': '現任負荷歷史不足', 'option_support:current_ability_support': '現任能力支持不足',
  'option_support:fewer_than_two_nominal_RP': '名義後援不足兩人'
}
const alertReason = (value: string) => alertReasonLabels[value] || value
const alertBound = (value: number | undefined) => value === undefined ? '缺值' : (value * 100).toFixed(2)
const phase = ref('all')
const visiblePhases = computed(() => plan.phases.filter(item => phase.value === 'all' || item.id === phase.value))
const completed = plan.slices.filter(item => item.status === 'done').length
const total = (key: 'pitches' | 'pa' | 'changes') => snapshot.coverage.reduce((sum, row) => sum + row[key], 0).toLocaleString('en-US')
const format = (value: number | null) => value === null ? '尚無成績檔' : value.toLocaleString('en-US')
const percent = (value: number) => `${value.toFixed(2)}%`
const statusLabels: Record<string, string> = { done: '已完成', in_progress: '進行中', planned: '待開始', deferred: '後續擴充' }
const status = (value: string) => statusLabels[value] || value
const slicesFor = (id: string) => plan.slices.filter(item => item.phase === id).sort((a, b) => a.id === 'P0' ? -1 : b.id === 'P0' ? 1 : a.id.localeCompare(b.id, 'en', { numeric: true }))
const baselineLabels: Record<string, string> = { situation: '局面', workload: '局面＋負荷', matchup: '再加投打能力' }
const ablationLabels: Record<string, string> = { baseline: '相同支持基準', plus: '加 Stuff／Location', quality: '加 Quality', physical: '加 Physical', command: '加 Command', three_signals: '加三項狀態', all: '加 Plus＋三項狀態', without_quality: 'All 移除 Quality', without_physical: 'All 移除 Physical', without_command: 'All 移除 Command' }
const revisionLabels: Record<string, string> = {
  baseline: '修訂共同基準', ability_only: '局面＋投打能力', load_extended: '加五日負荷／季內序號', plus: '再加 Stuff／Location',
  states: '再加當場／近期狀態', exposure: '再加曝光／前推風險', attack: '再加前序出棒／掌握', all: '全部＋BvP／類型／交互項',
  without_plus: '移除 Plus 及派生項', without_live: '移除當場狀態及派生項', without_recent: '移除近期窗／候選歷史先驗',
  without_exposure: '移除 BF／輪次與派生項', without_risk: '移除前推下降風險', without_attack: '移除前序輪廓及交互項',
  without_bvp: '移除直接 BvP', without_type: '移除類型／相性及交互項', without_interactions: '移除交互項', without_season: '移除季內序號',
  without_72h: '移除72小時用球及派生風險', without_120h: '移除120小時用球及派生風險', without_streak: '移除連投日',
  load_without_72h: '純負荷：移除72小時用球', load_without_120h: '純負荷：移除120小時用球',
  load_without_streak: '純負荷：移除連投日', load_without_season: '純負荷：移除季內序號', repaired_global_matchup: '13.1修訂基準'
}
const revisionLabel = (value: string) => revisionLabels[value] || value
const patchGroups: Record<string, string> = { base: '共同基準', current: '加本場觀測', recent: '加近期／負荷', batter: '加打者／相性', rich: '精簡完整群' }
const directionLabels: Record<string, string> = { pool_higher: '替代池較高', continue_higher: '續投較高', uncertain_or_unsupported: '不明或支持不足' }
const directionLabel = (value: string) => directionLabels[value] || value
const poolLabel = (value: string) => {
  if (value === 'role') return '角色池'
  if (value === 'hand_L') return '左投池'
  if (value === 'hand_R') return '右投池'
  const [hand, family, velocity] = value.replace('type_', '').split(':')
  const families: Record<string, string> = { fastball: '速球主導', breaking: '變化球主導', offspeed: '變速／分指等主導', mixed: '混合球系' }
  const velocities: Record<string, string> = { under90: '速球<90mph', '90to95': '速球90–95mph', '95plus': '速球95+mph', unknown: '速球球速未知' }
  return `${hand === 'L' ? '左投' : '右投'}／${families[family ?? ''] || family}／${velocities[velocity ?? ''] || velocity}`
}
const metrics = [
  { name: 'xWPA', text: '某選項在固定評估終點的預期己方勝率，減去當前勝率；以百分點呈現。' },
  { name: 'xRE24', text: '當前 RE 減去預期期間失分及終點剩餘 RE；先限定當前半局，守方越高越好。' },
  { name: 'ΔxWPA / ΔxRE24', text: '換投選項減去續投的預期價值；用相同終點與後續策略比較，附上不確定區間。' }
]
</script>

<template>
  <main class="decision-plan">
    <ComparisonPageHeader eyebrow="Pitcher Lab · Research roadmap" title="換投決策與預警研究" description="從資料補齊，到比較續投與換投的預期價值，再把有證據支持的結果帶進單場儀表板。" back-to="/lab?area=pitcher" back-label="Pitcher Lab" secondary-to="/lab/stamina" secondary-label="Stamina Lab" />

    <section class="overview panel" aria-labelledby="plan-status">
      <div><span class="eyebrow">研究規劃 · {{ plan.updated_at }}</span><h2 id="plan-status">先把資料與時點對齊，再談最佳決策</h2><p>{{ plan.summary }}</p></div>
      <div class="progress"><strong>{{ completed }} / {{ plan.slices.length }}</strong><span>任務完成 · 非模型準確率</span><progress :value="completed" :max="plan.slices.length" aria-label="研究任務完成進度" /></div>
      <p class="next-step"><strong>下一步</strong> {{ plan.next_step }}</p>
    </section>

    <nav class="reading-nav" aria-label="研究頁閱讀捷徑"><NuxtLink to="#exploratory-replay">16.1–3探索回測</NuxtLink><NuxtLink to="#pe-revision">15.5預測修訂</NuxtLink><NuxtLink to="#entry-review">15.4原正式資格</NuxtLink><NuxtLink to="#rp-target-research">15.3 RP目標與母體</NuxtLink><NuxtLink to="#overlap-revision">15.1–15.2修訂結果</NuxtLink><NuxtLink to="#signal-lights">多燈研究版本</NuxtLink><NuxtLink to="#overlap-research">原15重疊結果</NuxtLink><NuxtLink to="#next-validation">下一步與驗證</NuxtLink><NuxtLink to="#slice-list">完整Slice清單</NuxtLink><NuxtLink to="#research-history">依序看研究歷程</NuxtLink></nav>

    <details id="slice-list" class="research-group" :open="route.hash.startsWith('#slice-') || route.hash === '#slice-list'">
      <summary>完整Slice清單 · 五階段／{{ plan.slices.length }}項（依編號展開）</summary>
    <section aria-labelledby="roadmap-heading" class="roadmap">
      <div class="section-heading"><div><span class="eyebrow">Slice roadmap</span><h2 id="roadmap-heading">五階段研究流程 · Slice依編號排列</h2></div><span class="tag">半局研究比較完成 · 正式建議待驗證</span></div>
      <p class="footnote">P0 → 0–10 → 11–14.2.4 → 15–21；子項緊接主項，實際執行仍依各項依賴。完成表示工作已交付，不代表模型成效通過。</p>
      <nav class="phase-nav" aria-label="篩選研究階段">
        <button type="button" :aria-pressed="phase === 'all'" @click="phase = 'all'">全部階段</button>
        <button v-for="item in plan.phases" :key="item.id" type="button" :aria-pressed="phase === item.id" @click="phase = item.id">{{ item.title }}</button>
      </nav>
      <section v-for="stage in visiblePhases" :key="stage.id" :aria-labelledby="`phase-${stage.id}`" class="stage">
        <header><h3 :id="`phase-${stage.id}`">{{ stage.title }}</h3><p>{{ stage.description }}</p></header>
        <details v-for="item in slicesFor(stage.id)" :id="`slice-${item.id}`" :key="item.id" class="slice panel" :open="item.id === '16.3' || route.hash === `#slice-${item.id}`" :class="{ 'sub-slice': item.id.includes('.') }">
          <summary><span>{{ item.label }}</span><span class="tag" :class="item.status">{{ status(item.status) }}</span></summary>
          <div class="slice-body"><p>{{ item.deliverable }}</p><dl><dt>依賴</dt><dd v-if="item.depends_on.length"><NuxtLink v-for="dependency in item.depends_on" :key="dependency" :to="{ path: '/lab/decision-support', hash: `#slice-${dependency}` }" @click="phase = 'all'">{{ dependency === 'P0' ? dependency : `Slice ${dependency}` }}</NuxtLink></dd><dd v-else>無</dd><dt>完成條件</dt><dd>{{ item.acceptance }}</dd><dt>目前證據</dt><dd>{{ item.verification === 'Pending' ? '待開始；尚無驗證結果。' : item.verification === 'Deferred' ? '暫緩；待投手主線完成後另行展開。' : item.verification }}</dd></dl></div>
        </details>
      </section>
    </section>
    </details>

    <div id="research-history" class="research-history" aria-label="依Slice順序排列的研究歷程">
    <details id="history-data" class="research-group" :open="historyOpen('history-data')">
      <summary>01 · Slice 0–10｜資料盤點、補齊與時間一致特徵（歷史）</summary>
    <section class="audit-stats" aria-label="本機例行賽初步盤點">
      <article class="panel"><span>Slice 0 補齊前逐球快照</span><strong>{{ total('pitches') }}</strong></article>
      <article class="panel"><span>觀測打席</span><strong>{{ total('pa') }}</strong></article>
      <article class="panel"><span>可辨識投手更換</span><strong>{{ total('changes') }}</strong></article>
    </section>

    <section class="panel" aria-labelledby="coverage-heading">
      <div class="section-heading"><div><span class="eyebrow">資料起點 · {{ snapshot.auditDate }}</span><h2 id="coverage-heading">初始覆蓋快照（補齊前）</h2></div><span class="tag">本機例行賽 · 初步盤點</span></div>
      <p>換投由相鄰投手 ID 辨識，尚未等同完整官方事件。WPA 是邊界重建，RE24 是來源差值完整率；LI 是 2023 參考局面樣本至少 30 筆的支持率，並非官方 LI 覆蓋率。</p>
      <div class="table-scroll" role="region" aria-label="逐年指標覆蓋表，可水平捲動" tabindex="0">
        <table><caption>逐球快取、打席結果與現行合格先發場次</caption><thead><tr><th scope="col">年份</th><th scope="col">觀測 PA</th><th scope="col">換投</th><th scope="col">WPA</th><th scope="col">RE24</th><th scope="col">LI 支持</th><th scope="col">Stuff+</th><th scope="col">Location+</th><th scope="col">Quality 場次</th><th scope="col">Physical 場次</th><th scope="col">Command 場次</th></tr></thead>
          <tbody><tr v-for="row in snapshot.coverage" :key="row.year"><th scope="row">{{ row.year }}</th><td>{{ format(row.pa) }}</td><td>{{ format(row.changes) }}</td><td>{{ percent(row.wpa) }}</td><td>{{ percent(row.re24) }}</td><td>{{ percent(row.liSupported) }}</td><td>{{ percent(row.stuff) }}</td><td>{{ percent(row.location) }}</td><td>{{ format(row.quality) }}</td><td>{{ format(row.physical) }}</td><td>{{ format(row.command) }}</td></tr></tbody>
        </table>
      </div>
      <p class="footnote">百分比依各欄分母計算，四捨五入到小數二位；WPA 仍有 4 筆缺值。Quality／Physical／Command 欄為現行合格先發場次，缺檔不表示原始資料無法研究。現有 Plus 用過 2025 資料訓練，須另建時間一致版本。</p>
    </section>

    <section v-if="snapshot.sourceAudit" class="panel" aria-labelledby="source-audit-heading">
      <div class="section-heading"><div><span class="eyebrow">Slice 1 · 2026-11-12 原始盤點</span><h2 id="source-audit-heading">原始缺漏清單（補齊前）</h2></div><span class="tag done">歷史盤點</span></div>
      <p>當時 14,577 場均有本機 game ID 與官方 feed，另有兩場逐球缺口。下列保留補齊前的證據；最新處理結果請看 Slice 2–5。</p>
      <div class="table-scroll" role="region" aria-label="Slice 1 逐年官方賽程核對表，可水平捲動" tabindex="0">
        <table><caption>排除取消賽，以唯一 game ID 核對；實投鍵差異另行檢查</caption><thead><tr><th scope="col">年份</th><th scope="col">完成賽程</th><th scope="col">本機場次</th><th scope="col">缺場</th><th scope="col">既有 feed</th><th scope="col">實投鍵差異</th><th scope="col">官方換投事件</th></tr></thead>
          <tbody><tr v-for="row in snapshot.sourceAudit.years" :key="row.year"><th scope="row">{{ row.year }}</th><td>{{ format(row.completedGames) }}</td><td>{{ format(row.localGames) }}</td><td>{{ row.missingGames }}</td><td>{{ format(row.cachedFeeds) }}</td><td>{{ row.missingPitchKeys }}</td><td>{{ format(row.officialPitchingSubstitutions) }}</td></tr></tbody>
        </table>
      </div>
      <ul><li v-for="game in snapshot.sourceAudit.pitch_backfill_queue" :key="game.game_pk"><strong>{{ game.date }} · {{ game.game_pk }}</strong>：本機 {{ game.local_pitch_rows }} 球，官方 feed {{ game.official_pitch_events }} 顆實投，{{ game.missing_official_pitch_keys }} 個實投鍵待查。{{ game.classification === 'partial_game' ? '已定位為單場資料截斷。' : '單球需核對來源修訂。' }}</li></ul>
      <p>另有三場比分差異來自再見投手犯規；14,017 個本機鍵涉及自動球、編號及來源語意差異，不能直接當缺球或刪除。完整 feed 已有 96,391 筆換投事件，後續仍需建立一致的決策事件帳本。</p>
      <p class="footnote">以上是 Slice 1 當時的清單；兩場來源已在 Slice 2 補齊。舊 Plus／Stamina 等衍生成績仍保留版本，未因補齊而重訓或直接取代。</p>
    </section>

    <section v-if="snapshot.dataFoundation" class="panel" aria-labelledby="foundation-heading">
      <div class="section-heading"><div><span class="eyebrow">Slices 2–5 · {{ snapshot.dataFoundation.updatedAt }}</span><h2 id="foundation-heading">來源補齊、事件、負荷與名義候選</h2></div><span class="tag done">研究資料層</span></div>
      <div class="metric-grid">
        <article><h3>來源補齊</h3><p v-for="game in snapshot.dataFoundation.repairs" :key="game.game_pk">{{ game.year }} · {{ game.game_pk }}：{{ game.before_rows }} → {{ game.after_rows }} 筆</p><p class="footnote">保存原始備份；其他比賽指紋不變，缺追蹤不補造。</p></article>
        <article><h3>按事件時間累積</h3><p>{{ format(snapshot.dataFoundation.ledger.physical_pitches) }} 顆實投；近 1／3／7／14 天只計決策前資料。</p><p class="footnote">跨隊、跨角色與同日多場共用歷史；連續登板按紐約日期，生涯 2021 年前與春訓未知。</p></article>
        <article><h3>候選仍有信心分級</h3><p>72 組指定日期名單：66 一致、6 衝突；其他日期未逐日驗證。</p><p class="footnote">名義候選不等於實際可用牛棚。熱身、醫療與同日異動未知，個別排名關閉。</p></article>
      </div>
      <div class="table-scroll" role="region" aria-label="Slices 2 到 5 逐年資料層結果，可水平捲動" tabindex="0">
        <table><caption>官方 play 含零球及非完成打席；登板段含重新上丘，並非正式 G／GS 統計</caption><thead><tr><th scope="col">年份</th><th scope="col">實投</th><th scope="col">官方 play</th><th scope="col">登板段</th><th scope="col">零球段</th><th scope="col">有名義候選的邊界</th></tr></thead><tbody><tr v-for="row in snapshot.dataFoundation.years" :key="row.year"><th scope="row">{{ row.year }}</th><td>{{ format(row.pitches) }}</td><td>{{ format(row.plays) }}</td><td>{{ format(row.appearances) }}</td><td>{{ row.zeroPitchAppearances }}</td><td>{{ format(row.withCandidates) }}</td></tr></tbody></table>
      </div>
      <p>WPA／RE 結果只在 play 層存一次，不重複貼到每球或前置特徵。仍有 {{ snapshot.dataFoundation.ledger.unpriced_wpa_plays }} 個勝率邊界保留缺值；{{ snapshot.dataFoundation.workload.source_clock_issue_games }} 場來源時間異常與未知壘包均有旗標，不能當成可靠的決策樣本。</p>
      <p class="footnote">候選附近期用球、前次用球、連續登板、同日登板、距離先發／長局數的歷史。曾先發不自動加體力。後續打席基準見下方；半局行動價值、換投燈號與最佳人選仍待研究。</p>
    </section>

    <section v-if="snapshot.temporalResearch" class="panel" aria-labelledby="temporal-heading">
      <div class="section-heading"><div><span class="eyebrow">Slices 6–10 · Historical features</span><h2 id="temporal-heading">時點一致的歷史特徵已建立</h2></div><span class="tag">研究版本 · 正式模型保留</span></div>
      <div class="metric-grid">
        <article><h3>歷史 Plus 與暖機</h3><p>主要速球只取此前已結束的登板；模型、參考表與標準化都限定過去資料。2024–2026 使用截至 2023 年底的凍結模型。</p><p class="footnote">研究 Stuff 採扣除位置／情境後的物理殘差模型，與現行正式分數分開，不能直接混用。</p></article>
        <article><h3>先發與牛棚分開觀測</h3><p>先發至少 {{ snapshot.temporalResearch.minimumPrefix.SP }} 球、牛棚至少 {{ snapshot.temporalResearch.minimumPrefix.RP }} 球後，依支援程度產生三項 prefix 狀態。前段不足、短登板及中斷重啟皆保留缺值。</p><p class="footnote">控制最近打席邊界的近期用球、休息、連續登板、過去角色與 PA-LI；候選只附本次登板前已結束的歷史狀態。</p></article>
        <article><h3>WE／RE／PA-LI 參考</h3><p>以先前已完成比賽建立中性勝率、壘包出局得分期望，以及預期勝率波動。七局、再見、終局及延長賽跑者另有規則。</p><p class="footnote">PA-LI 是獨立研究近似，非 FanGraphs 精確復刻；未知不補 1。前置特徵與實現結果分檔，尚無行動效益模型。</p></article>
      </div>
      <div class="table-scroll" role="region" aria-label="Slices 6 到 10 逐年研究特徵覆蓋，可水平捲動" tabindex="0">
        <table><caption>2021 Plus／參考模型由 7 月開始，狀態模型由 9 月開始；登板數代表至少一個可評分 prefix，不代表每項訊號皆完整。</caption><thead><tr><th scope="col">年份</th><th scope="col">研究 Stuff／全部實投</th><th scope="col">研究 Location／全部實投</th><th scope="col">SP 有 prefix 登板</th><th scope="col">RP 有 prefix 登板</th><th scope="col">WE／RE／PA-LI 邊界</th></tr></thead><tbody><tr v-for="row in snapshot.temporalResearch.years" :key="row.year"><th scope="row">{{ row.year }}</th><td>{{ percent(100 * row.stuff_available / row.physical_pitches) }}</td><td>{{ percent(100 * row.location_available / row.physical_pitches) }}</td><td>{{ format(row.spAppearances) }}</td><td>{{ format(row.rpAppearances) }}</td><td>{{ format(row.context.we) }}／{{ format(row.context.decisions) }}</td></tr></tbody></table>
      </div>
      <p><strong>三項訊號各自解讀：</strong>Quality 看球質維持、Physical 看公開測量的穩定程度、Command 看位置價值維持。各依過去參考尺度呈現 100+，當年中位數不保證 100，收縮後的分布也不必相同；目前沒有合成電量百分比。</p>
      <p class="footnote">區間是近似 80% 抽樣區間，未包含完整模型不確定性；可靠度欄位為收縮權重，不是校準後的正確機率。Physical 不是生理體能量測。先發評估至 100 球、牛棚至 60 球，超出範圍不沿用過期分數；短登板、熱身與醫療未知也不補成體力。</p>
      <details><summary>2024 固定驗證與目前限制</summary><p>中性 WE Brier：{{ snapshot.temporalResearch.weValidation.brier.toFixed(4) }}；常數主場勝率基準：{{ snapshot.temporalResearch.weValidation.constant_train_home_win_brier.toFixed(4) }}。這只檢查勝率參考，沒有證明換投建議有效。</p><p>Plus 參考目標 RMSE：位置／情境 {{ snapshot.temporalResearch.plusValidation.location_rmse.toFixed(6) }}，加入物理殘差 {{ snapshot.temporalResearch.plusValidation.location_plus_residual_stuff_rmse.toFixed(6) }}；目前增量很小，維持研究狀態。</p><p class="footnote">SP／RP 與純用球數基準的比較保存在 Slice 8／9 證據；重疊 prefix 的持續度只作描述。2025／2026 僅評分與覆蓋，沒有用結果挑選模型。新模型尚未晉升，也沒有個別牛棚排名、電池條或換投燈號。</p></details>
    </section>
    </details>

    <details id="history-baselines" class="research-group" :open="historyOpen('history-baselines')">
      <summary>02 · Slice 11–12.7｜決策樣本、時間切分與基準（歷史）</summary>
    <section v-if="snapshot.decisionSample" class="panel" aria-labelledby="sample-heading">
      <div class="section-heading"><div><span class="eyebrow">Slice 11 · 歷史決策樣本</span><h2 id="sample-heading">續投與換投的研究分母</h2></div></div>
      <p>例行賽打席邊界同時符合續投與換投的名義規則，才納入比較。候選的實際熱身、健康與當日異動仍未知。</p>
      <div class="table-scroll" role="region" aria-label="逐年續投與換投樣本，可水平捲動" tabindex="0">
        <table><caption>SP／RP 依決策前的現任投手角色。半局 WPA 只計有效標籤。</caption>
          <thead><tr><th scope="col">年份</th><th scope="col">全部邊界</th><th scope="col">納入</th><th scope="col">SP 續投</th><th scope="col">SP 換投</th><th scope="col">RP 續投</th><th scope="col">RP 換投</th><th scope="col">有半局 WPA</th></tr></thead>
          <tbody><tr v-for="row in snapshot.decisionSample" :key="row.year"><th scope="row">{{ row.year }}</th><td>{{ format(row.all) }}</td><td>{{ format(row.included) }}</td><td>{{ format(row.spContinue) }}</td><td>{{ format(row.spChange) }}</td><td>{{ format(row.rpContinue) }}</td><td>{{ format(row.rpChange) }}</td><td>{{ format(row.halfWpa) }}</td></tr></tbody>
        </table>
      </div>
      <p class="footnote">前置特徵、名義候選與實際結果分檔。上表計的是歷史實際行動；角色替代池研究見下方 Slice 14，正式效益仍待後續驗證。</p>
    </section>

    <section class="timeline" aria-label="模型時間切分">
      <article v-for="window in plan.experiment" :key="window.years" class="panel"><strong>{{ window.years }}</strong><h3>{{ window.role }}</h3><p>{{ window.detail }}</p></article>
    </section>

    <section v-if="snapshot.baselineResearch" class="panel" aria-labelledby="baseline-heading">
      <div class="section-heading"><div><span class="eyebrow">Slices 12.5–12.7 · Next PA baselines</span><h2 id="baseline-heading">候選歷史與下一打席基準</h2></div><span class="tag">研究結果 · 待人工畫面驗收</span></div>
      <p>使用 2021–2023 訓練、2024 選設定與診斷。三層模型在相同打席比較，數值越低越好；目前保留「{{ baselineLabels[snapshot.baselineResearch.retained] }}」。2025 最終測試結果保留，2026 僅回溯評分。</p>
      <div class="table-scroll" role="region" aria-label="2024 三層基準驗證，可水平捲動" tabindex="0">
        <table><caption>WPA 誤差以勝率百分點呈現，RE24 以分呈現；僅為下一打席預測。</caption>
          <thead><tr><th scope="col">基準</th><th scope="col">有效打席</th><th scope="col">PA log loss</th><th scope="col">多類 Brier</th><th scope="col">轉移 log loss</th><th scope="col">WPA RMSE（pp）</th><th scope="col">RE24 RMSE</th><th scope="col">校準 ECE</th></tr></thead>
          <tbody><tr v-for="model in snapshot.baselineResearch.models" :key="model.level"><th scope="row">{{ baselineLabels[model.level] }}</th><td>{{ format(model.validation.n) }}</td><td>{{ model.validation.log_loss.toFixed(5) }}</td><td>{{ model.validation.brier.toFixed(5) }}</td><td>{{ model.transitions.joint_log_loss.toFixed(5) }}</td><td>{{ (100 * model.transitions.wpa_rmse).toFixed(3) }}</td><td>{{ model.transitions.re24_rmse.toFixed(4) }}</td><td>{{ model.validation.ece.toFixed(4) }}</td></tr></tbody>
        </table>
      </div>
      <p class="footnote">換投樣本使用實際接任投手的決策前特徵。三項狀態與 Plus 未加入這組原始基準；Slice 13 增益與 Slice 14 半局研究見下方。這些誤差不能解讀為換投因果效益。</p>
      <details><summary>名義候選 coverage 與有效樣本流向</summary>
        <p>能力有值包含自身歷史與訓練參考回退；三項狀態須同時有 Quality／Physical／Command。百分比分母為該年決策數，候選列是決策×候選。熱身與醫療仍未知，沒有個別牛棚排名。</p>
        <div class="table-scroll" role="region" aria-label="逐年候選歷史覆蓋，可水平捲動" tabindex="0">
          <table><thead><tr><th scope="col">年份</th><th scope="col">決策</th><th scope="col">候選列</th><th scope="col">至少一位有能力</th><th scope="col">全部有能力</th><th scope="col">至少一位有三狀態</th><th scope="col">全部有三狀態</th></tr></thead>
            <tbody><tr v-for="row in snapshot.baselineResearch.years" :key="row.year"><th scope="row">{{ row.year }}</th><td>{{ format(row.decisions) }}</td><td>{{ format(row.candidate_rows) }}</td><td>{{ percent(100 * row.any_candidate_ability / row.decisions) }}</td><td>{{ percent(100 * row.all_candidate_ability / row.decisions) }}</td><td>{{ percent(100 * row.any_candidate_state / row.decisions) }}</td><td>{{ percent(100 * row.all_candidate_state / row.decisions) }}</td></tr></tbody>
          </table>
        </div>
        <p v-for="row in snapshot.baselineResearch.flow" :key="row.year" class="footnote">{{ row.year }}：可靠一般打席 {{ format(row.before) }}，跑者守恆排除 {{ format(row.runner_conservation_excluded) }}，最終 {{ format(row.after) }}。</p>
      </details>
      <details><summary>群聚差異與凍結設定</summary>
        <p v-for="model in snapshot.baselineResearch.models" :key="model.level" class="footnote">{{ baselineLabels[model.level] }}：L2 α={{ model.alpha }}，能力收縮={{ model.pooling }}；相對局面 log loss 差 {{ model.cluster.mean_challenger_minus_baseline.toFixed(6) }}，按比賽群聚 95% 區間 [{{ model.cluster.game_cluster_95pct[0]?.toFixed(6) }}, {{ model.cluster.game_cluster_95pct[1]?.toFixed(6) }}]。{{ model.convergenceWarning ? '迭代上限警告，保留研究限制。' : '未觸發迭代上限警告。' }}</p>
        <p class="footnote">區間使用 100 次 paired game bootstrap；2024 同時參與設定選擇，這不是獨立測試證據。補值、標準化及轉移參考只 fit 訓練資料；逐類校準與稀有事件支持留在版本化離線證據。</p>
        <p class="footnote">{{ snapshot.baselineResearch.version }} · 協定 SHA {{ snapshot.baselineResearch.protocolHash }}</p>
      </details>
    </section>

    <section class="metric-grid" aria-label="預期價值定義"><article v-for="metric in metrics" :key="metric.name" class="panel"><h3>{{ metric.name }}</h3><p>{{ metric.text }}</p></article></section>
    </details>

    <details id="history-models" class="research-group" :open="historyOpen('history-models', 'role-revision', 'matchup-revision', 'model-patch')">
      <summary>03 · Slice 13–14.1.1｜狀態觀測、模型修訂與半局價值（歷史）</summary>
    <section v-if="snapshot.signalAblation" class="panel" aria-labelledby="ablation-heading">
      <div class="section-heading"><div><span class="eyebrow">Slice 13 · Incremental value</span><h2 id="ablation-heading">哪些訊號改善下一打席預測？</h2></div><span class="tag">完整保留未通過結果</span></div>
      <p>實際續投使用當次 prefix，換投使用接任投手此前已結束登板的狀態；每個對照控制相同的歷史支持、年齡與缺值資訊。完整支持樣本目前保留「{{ ablationLabels[snapshot.signalAblation.winner] }}」。</p>
      <p>三項狀態單獨或合併未通過增益門檻；All 的改善需與 Plus-only 及移除單項的結果一起解讀，不能歸給三項狀態。</p>
      <div v-for="(cohort, name) in snapshot.signalAblation.cohorts" :key="name" class="table-scroll" role="region" :aria-label="`${name} 特徵消融，可水平捲動`" tabindex="0">
        <table><caption>{{ name === 'complete' ? '完整支持、相同分母' : '全分母、缺值保留' }}：訓練 {{ format(cohort.trainingN) }}／2024 驗證 {{ format(cohort.validationN) }}。</caption>
          <thead><tr><th scope="col">特徵組合</th><th scope="col">log loss</th><th scope="col">Brier</th><th scope="col">相對支持基準差值</th><th scope="col">按比賽群聚95%區間</th><th scope="col">增益門檻</th></tr></thead>
          <tbody><tr v-for="model in cohort.models" :key="model.name"><th scope="row">{{ ablationLabels[model.name] }}</th><td>{{ model.logLoss.toFixed(6) }}</td><td>{{ model.brier.toFixed(6) }}</td><td>{{ model.delta.mean_challenger_minus_baseline.toFixed(6) }}</td><td>[{{ model.delta.game_cluster_95pct[0]?.toFixed(6) }}, {{ model.delta.game_cluster_95pct[1]?.toFixed(6) }}]</td><td>{{ model.name === 'baseline' ? '對照' : model.incrementGate ? '通過' : '未通過' }}</td></tr></tbody>
        </table>
      </div>
      <p class="footnote">2024 同時作設定診斷，並非獨立測試。全分母 All 相較自己的支持基準有改善，但對 Slice 12 原始基準的 Brier 未改善。三項分數沒有被合成電量，也未推定能預測換投效益。</p>
    </section>

    <section v-if="snapshot.roleObservationRevision" id="role-revision" class="panel" aria-labelledby="role-revision-heading">
      <div class="section-heading"><div><span class="eyebrow">Slices 13.1–13.4 · Role observation revision</span><h2 id="role-revision-heading">修訂負荷、近期狀態與壓制力曲線</h2></div><span class="tag">研究觀測 · 非換投門檻</span></div>
      <p>重建 {{ format(snapshot.roleObservationRevision.optionRows) }} 個現任／候選連結。原連投欄位改為實際／假定進場前的連續登板日；決策日曝光、本場與跨場用球、進場前休息及本場等待時間分開保存。2024 現任後援 {{ format(snapshot.roleObservationRevision.streakAudit.current_rp_rows) }} 列中，{{ format(snapshot.roleObservationRevision.streakAudit.legacy_vs_repaired) }} 列與原欄位不同。</p>
      <div class="table-scroll" role="region" aria-label="修訂版逐年當場觀測覆蓋，可水平捲動" tabindex="0"><table>
        <caption>分母為已納入的原決策點。近期候選另有近3／5日及最近1／3／5次同角色已結束登板摘要；缺資料不補成狀態正常。</caption>
        <thead><tr><th scope="col">年份</th><th scope="col">SP 有 Stuff／決策</th><th scope="col">SP 有 Quality</th><th scope="col">RP 有 Stuff／決策</th><th scope="col">RP 有 Quality</th><th scope="col">去重近期狀態組合</th></tr></thead>
        <tbody><tr v-for="row in snapshot.roleObservationRevision.years" :key="row.year"><th scope="row">{{ row.year }}</th><td>{{ format(row.sp.stuff) }}／{{ format(row.sp.n) }}</td><td>{{ format(row.sp.quality) }}</td><td>{{ format(row.rp.stuff) }}／{{ format(row.rp.n) }}</td><td>{{ format(row.rp.quality) }}</td><td>{{ format(row.recentProfiles) }}</td></tr></tbody>
      </table></div>
      <h3>先看整體輪次／面對打者數，再估個人差異</h3>
      <p>圖中是2024實際仍在投球者的條件曲線，控制球數、對手、球路等因素。預先定義的連續區段、支持量、實務幅度與次年重現門檻，共有 {{ snapshot.roleObservationRevision.replicatedPanels.length }} 個面板通過；目前不能據此設定通用換投球數／輪次。這不表示所有下降都不存在。</p>
      <div class="revision-figures"><figure v-for="role in ['SP', 'RP']" :key="role"><a :href="`/research/decision-role-observation-v2/decline_${role}_2024.svg`" target="_blank" rel="noopener"><img :src="`/research/decision-role-observation-v2/decline_${role}_2024.svg`" :alt="`${role} 的2024條件壓制力變化與群聚區間，非換投閾值`" loading="lazy" /></a><figcaption>{{ role === 'SP' ? '先發' : '後援' }} · 點圖可開啟完整研究圖；空心點為支持不足。</figcaption></figure></div>
      <h3>下一十球條件風險：與球數基準比較</h3>
      <p class="footnote">目標是未來十球均值較前十球下降至少5個研究Plus點，各窗至少8個有效測量。它包含抽樣波動與回歸均值，不等於低於個人基準、疲勞、失分或換投優勢；下一PA消融結果見上方13.6。</p>
      <div class="table-scroll" role="region" aria-label="2024下一十球條件風險驗證，可水平捲動" tabindex="0"><table>
        <thead><tr><th scope="col">角色／目標</th><th scope="col">有未來標籤／達球數樣本</th><th scope="col">未觀測或測量不足</th><th scope="col">球數基準 Brier</th><th scope="col">狀態＋負荷 Brier</th><th scope="col">AUC</th></tr></thead>
        <tbody><tr v-for="row in snapshot.roleObservationRevision.risk" :key="`${row.role}-${row.metric}`"><th scope="row">{{ row.role }}／{{ row.metric === 'stuff' ? 'Stuff' : 'Location' }}</th><td>{{ format(row.observed) }}／{{ format(row.eligible) }}</td><td>{{ format(row.unobserved) }}</td><td>{{ row.brierCount.toFixed(5) }}</td><td>{{ row.brierState.toFixed(5) }}</td><td>{{ row.auc?.toFixed(4) ?? '無法計算' }}</td></tr></tbody>
      </table></div>
      <details><summary>13.1–13.4當時基準、支持與版本限制</summary><p v-for="model in snapshot.roleObservationRevision.baseline" :key="model.level">{{ baselineLabels[model.level] }}：2024 n={{ format(model.n) }}，log loss={{ model.logLoss.toFixed(6) }}，Brier={{ model.brier.toFixed(6) }}。此版本只修正原白名單資料口徑，後續新增特徵結果見13.6。</p><p>近期狀態只用已結束且可用的觀測，包含資料年齡與近似區間；沒有近五日資料不表示健康、已熱身或可實際登板。被換下後的續投不可觀測，風險驗證不能推廣成所有投手的因果效果。</p><p class="footnote">2025／2026只輸出凍結機率，不檢視結果指標。下方原v1半局比較及時間軸保留；重跑見上方14.1，14.2未開始。</p></details>
    </section>

    <section v-if="snapshot.actionResearch" class="panel" aria-labelledby="action-heading">
      <div class="section-heading"><div><span class="eyebrow">Slice 14 · Fixed-half scenarios</span><h2 id="action-heading">續投與角色替代池：初步研究成果</h2></div><span class="tag">研究比較 · 建議功能未開放</span></div>
      <p>2024 分層抽樣加兩場固定範例共 {{ format(snapshot.actionResearch.attempted_cases) }} 個邊界，{{ format(snapshot.actionResearch.modeled_cases) }} 個有名義角色池與歷史支持，{{ format(snapshot.actionResearch.simulation_supported) }} 個在本批全部模擬中沒有截尾或球數範圍外推。這不是聯盟平均調度效果。</p>
      <DecisionResearchTimeline :games="snapshot.actionResearch.games" />
      <details><summary>固定半局策略與區間如何定義？</summary>
        <p>現任續投至半局結束，對比現在從至少兩位有歷史支持的名義 RP 池均勻選一人投至半局結束；之後不再換人。第一個打者已知，後續使用相同的訓練期聯盟打者抽樣。用球依過去分布累加，未推演未觀測的三項狀態。</p>
        <p>每方案 {{ snapshot.actionResearch.paths }} 條配對路徑，{{ snapshot.actionResearch.bootstrap_models }} 次按比賽重抽樣分類器。MC95 是模擬數量造成的誤差；中央80%模型範圍固定前處理、轉移及 WE／RE，兩者都不涵蓋完整模型與選擇偏差。</p>
        <p class="footnote">先用 Slice 12 完整覆蓋基準；長期牛棚成本、實際未來打序、熱身與醫療未知。個別人選排名與正式推薦維持關閉。時間軸只在 Lab 示範，同場 In game 同步留 Slice 19；未開始 Slices 15–20。</p>
      </details>
    </section>

    <section v-if="snapshot.matchupRevision" id="matchup-revision" class="panel" aria-labelledby="matchup-revision-heading">
      <div class="section-heading"><div><span class="eyebrow">Slices 13.5 · 13.6 · 14.1</span><h2 id="matchup-revision-heading">打者輪廓、特徵增益與半局比較修訂</h2></div><span class="tag">研究結果 · 正式推薦關閉</span></div>
      <p>本區保留13.5／13.6／14.1交付時的歷史快照；最新多燈結果見下方14.2.1–14.2.4，原14.2另列歷史區。</p>
      <p>打者前1／2／3個已完成打席的收到球種、出棒組成與掌握表現分開保存；同場對該投手、其他投手、全隊與歷史相性各有自己的範圍及分母。粗球路類型只用過去已結束登板，不採同季整季標籤。</p>
      <p>熟悉度描述分析共 {{ snapshot.matchupRevision.associationPanels }} 個面板，2024有支持且區間排除0的變化區段 {{ snapshot.matchupRevision.associationSupportedChanges2024 }} 個；目前不能認定多看幾次就一定掌握更好，也不能由出棒認定心理鎖定。</p>
      <div class="table-scroll" role="region" aria-label="2024打者輪廓及相性覆蓋，可水平捲動" tabindex="0"><table>
        <caption>2024特徵分母 {{ format(snapshot.matchupRevision.featureRows2024) }}，依實際投球actor分SP／RP；模型另排除不合格結果／轉移。類型n是打者對過去粗類型的自身歷史，無自身支持會保留回退標記。</caption>
        <thead><tr><th scope="col">角色</th><th scope="col">特徵列</th><th scope="col">本場先前PA</th><th scope="col">本場同投手PA</th><th scope="col">歷史BvP</th><th scope="col">已知粗類型</th><th scope="col">打者自身類型PA</th></tr></thead>
        <tbody><tr v-for="row in snapshot.matchupRevision.coverage2024" :key="row.role"><th scope="row">{{ row.role }}</th><td>{{ format(row.n) }}</td><td>{{ format(row.same_game_pa) }}</td><td>{{ format(row.same_pitcher_pa) }}</td><td>{{ format(row.historical_pair) }}</td><td>{{ format(row.known_type) }}</td><td>{{ format(row.type_own_pa) }}</td></tr></tbody>
      </table></div>
      <h3>下一打席：相同分母、分角色驗證</h3>
      <p class="footnote">共同目標是九類下一打席結果：K、BB、HBP、HR、1B、2B、3B、其他出局與其他上壘。這裡的多類Brier，不能直接與下方「下一十球下降」的二元Brier比較，也不是錯誤率百分比。</p>
      <p>各角色25個預定設定，共用相同訓練／2024驗證分母與缺值支持控制。選擇需通過比賽×投手群聚、多設定同時區間、Brier及分群門檻；2024仍是診斷選模，2025最終測試保留。</p>
      <div class="table-scroll" role="region" aria-label="13.6角色模型診斷選擇，可水平捲動" tabindex="0"><table>
        <thead><tr><th scope="col">角色</th><th scope="col">2024 n</th><th scope="col">選擇</th><th scope="col">基準LL → 選定LL</th><th scope="col">基準Brier → 選定Brier</th><th scope="col">完整訊號支持n</th></tr></thead>
        <tbody><tr v-for="row in snapshot.matchupRevision.roles" :key="row.role"><th scope="row">{{ row.role }}</th><td>{{ format(row.validationN) }}</td><td>{{ revisionLabel(row.selected) }}</td><td>{{ row.baselineLL.toFixed(6) }} → {{ row.selectedLL.toFixed(6) }}</td><td>{{ row.baselineBrier.toFixed(6) }} → {{ row.selectedBrier.toFixed(6) }}</td><td>{{ format(row.supportedN) }}</td></tr></tbody>
      </table></div>
      <details><summary>查看逐組加入與移除特徵的完整消融</summary>
        <p class="footnote">下列區間是相對共同基準的LL差，負值較好；逐組設定才可被選擇。移除來源時同步移除派生risk／交互項。純負荷對照不含後續複合風險，不能將條件預測差異直接稱疲勞因果。</p>
        <div v-for="role in snapshot.matchupRevision.roles" :key="role.role" class="table-scroll" role="region" :aria-label="`${role.role} 全部25個設定，可水平捲動`" tabindex="0"><table>
          <caption>{{ role.role }} · 訓練 {{ format(role.trainingN) }}／驗證 {{ format(role.validationN) }}</caption>
          <thead><tr><th scope="col">設定</th><th scope="col">LL</th><th scope="col">Brier</th><th scope="col">LL差同時區間</th><th scope="col">相對基準門檻</th></tr></thead>
          <tbody><tr v-for="row in role.rows" :key="row.variant"><th scope="row">{{ revisionLabel(row.variant) }}{{ row.candidate ? '（逐組）' : '（對照）' }}</th><td>{{ row.logLoss.toFixed(6) }}</td><td>{{ row.brier.toFixed(6) }}</td><td>[{{ row.familyInterval[0]?.toFixed(6) }}, {{ row.familyInterval[1]?.toFixed(6) }}]</td><td>{{ row.variant === 'baseline' ? '參考' : row.incrementGate ? '通過' : '未通過' }}</td></tr></tbody>
        </table></div>
        <div v-for="role in snapshot.matchupRevision.roles" :key="`${role.role}-load`" class="table-scroll" role="region" :aria-label="`${role.role} 純負荷對照，可水平捲動`" tabindex="0"><table>
          <caption>{{ role.role }} · 純負荷移除對照，相對完整負荷設定；正值表示移除後LL變差，仍是條件預測差異。</caption>
          <thead><tr><th scope="col">移除項目</th><th scope="col">LL差</th><th scope="col">群聚95%區間</th></tr></thead>
          <tbody><tr v-for="row in role.loadContrasts" :key="row.variant"><th scope="row">{{ revisionLabel(row.variant) }}</th><td>{{ row.mean.toFixed(6) }}</td><td>[{{ row.paired_two_way95[0]?.toFixed(6) }}, {{ row.paired_two_way95[1]?.toFixed(6) }}]</td></tr></tbody>
        </table></div>
      </details>
      <h3>同一批484點：續投 vs 替代池投到半局結束</h3>
      <p>原 {{ snapshot.matchupRevision.action.originalCases }} 個比較點全部保留，有 {{ snapshot.matchupRevision.action.supported }} 個通過模擬支持。第一打席依角色使用 <span v-for="(row, index) in snapshot.matchupRevision.action.firstModels" :key="row.role">{{ index ? '、' : '' }}{{ row.role }}：{{ revisionLabel(row.model) }}</span>；後續打席一律回修訂基準，沒有把目前球質或前次登板狀態固定到局末。</p>
      <p class="footnote">以下研究方向依ΔxWPA的模擬／模型區間判斷；xRE24另列，沒有把兩者合成加權分數。此處模擬支持指未觸發截尾／外推旗標；稀有轉移另列，不等於正式推薦門檻。</p>
      <div class="table-scroll" role="region" aria-label="原版與修訂版484個研究方向比較，可水平捲動" tabindex="0"><table>
        <thead><tr><th scope="col">研究方向</th><th scope="col">原v1</th><th scope="col">修訂v2</th></tr></thead>
        <tbody><tr v-for="row in snapshot.matchupRevision.action.directions" :key="row.direction"><th scope="row">{{ directionLabel(row.direction) }}</th><td>{{ format(row.old) }}</td><td>{{ format(row.new) }}</td></tr></tbody>
      </table></div>
      <details><summary>查看固定12個案例的價值差與預計用球</summary>
        <p class="footnote">依decision ID固定取前12點，包含支持不足，沒有依結果挑例子。Δ為替代池減續投，WPA以百分點（pp）呈現。MC95為模擬誤差、模型80為固定其他環節下8個分類器的描述範圍。缺失轉移欄是每PA平均被排除的類別機率質量，並非整個半局的失敗機率。</p>
        <div class="table-scroll" role="region" aria-label="固定案例的xWPA與xRE24比較及預計用球，可水平捲動" tabindex="0"><table>
          <thead><tr><th scope="col">比賽／局面</th><th scope="col">原ΔxWPA → 新ΔxWPA（pp）</th><th scope="col">新ΔxWPA MC95／模型80（pp）</th><th scope="col">原ΔxRE24 → 新ΔxRE24</th><th scope="col">預計新增球數：續投／替代池</th><th scope="col">缺失轉移機率</th><th scope="col">截尾／外推支持</th></tr></thead>
          <tbody><tr v-for="row in snapshot.matchupRevision.action.examples" :key="row.decision_id"><th scope="row">{{ row.game_pk }} · {{ row.inning }}{{ row.half === 'top' ? '上' : '下' }}／{{ row.outs }}出局／壘碼{{ row.base_state }}</th><td>{{ (row.wpa_delta_old * 100).toFixed(2) }} → {{ (row.wpa_delta_new * 100).toFixed(2) }}</td><td>[{{ (row.wpa_mc95_low_new * 100).toFixed(2) }}, {{ (row.wpa_mc95_high_new * 100).toFixed(2) }}]／[{{ (row.wpa_bootstrap80_low_new * 100).toFixed(2) }}, {{ (row.wpa_bootstrap80_high_new * 100).toFixed(2) }}]</td><td>{{ row.re24_delta_old.toFixed(3) }} → {{ row.re24_delta_new.toFixed(3) }}</td><td>{{ row.pitches_continue.toFixed(1) }}／{{ row.pitches_pool.toFixed(1) }}</td><td>{{ (row.unsupported_mass_new * 100).toFixed(3) }}%</td><td>{{ row.simulation_supported_new ? '通過此項' : '不足' }}</td></tr></tbody>
        </table></div>
      </details>
      <details><summary>查看手別／粗類型條件池與原方向的變動</summary>
        <p>另有 {{ format(snapshot.matchupRevision.action.conditionalComparisons) }} 個條件池比較；每池至少兩位有過去支持的名義候選，池內均勻抽人。本輪粗類型用於分組，未通過增益的相性分數沒有加入價值模型；結果不能解讀成該打者特別怕某種球路。這些是探索性情境，沒有挑選最佳池或個別人選。</p>
        <div class="table-scroll" role="region" aria-label="條件替代池研究摘要，可水平捲動" tabindex="0"><table><thead><tr><th scope="col">池</th><th scope="col">比較數</th><th scope="col">有模擬支持</th></tr></thead><tbody><tr v-for="row in snapshot.matchupRevision.action.poolSummary" :key="row.pool"><th scope="row">{{ poolLabel(row.pool) }}</th><td>{{ format(row.n) }}</td><td>{{ format(row.supported) }}</td></tr></tbody></table></div>
        <div class="table-scroll" role="region" aria-label="484個原研究方向與新方向交叉表，可水平捲動" tabindex="0"><table><thead><tr><th scope="col">原方向</th><th scope="col">新方向</th><th scope="col">點數</th></tr></thead><tbody><tr v-for="row in snapshot.matchupRevision.action.directionTransitions" :key="`${row.old}-${row.new}`"><th scope="row">{{ directionLabel(row.old) }}</th><td>{{ directionLabel(row.new) }}</td><td>{{ format(row.n) }}</td></tr></tbody></table></div>
      </details>
      <p class="footnote">每方案 {{ snapshot.matchupRevision.action.paths }} 路徑、{{ snapshot.matchupRevision.action.bootstrapModels }} 次共同比賽分類器重抽樣；MC95及中央80模型範圍不涵蓋完整模型或隱藏混雜。首位打者已知，後續打線無時點證明，{{ snapshot.matchupRevision.action.futureLineupFallback }} 個全部明示聯盟池回退。預計用球／BF另列，長期牛棚成本尚未定價；game名單、法定合法、熱身、醫療及人工確認可用性分開。這些點不是獨立預警或合理性驗證；14.2去重／官方事件對應未開始。</p>
    </section>

    <section v-if="snapshot.modelPatchRevision" id="model-patch" class="panel" aria-labelledby="model-patch-heading">
      <div class="section-heading"><div><span class="eyebrow">13.6.1–13.6.3 · 14.1.1</span><h2 id="model-patch-heading">模型診斷補丁：哪些資訊真的改善預測</h2></div><span class="tag">補丁交付時快照 · 2025 測試封存</span></div>
      <p>只用 2022／2023 時間前推結果挑選設定：L2 正則化、訓練內溫度校準，以及一種淺層樹模型。每角色先凍結六族候選，再用完整訓練資料確認；2024 已使用過，只作診斷，不能當新獨立測試。</p>
      <p>本場狀態僅給現任投手；候補使用已結束同角色歷史。共同支持／年齡控制保留，有效球數與有效登板數分開，缺值不補成狀態正常。Log loss、Brier 越低越好；更換演算法的效果與新增特徵的效果分開判斷。</p>
      <div v-for="role in snapshot.modelPatchRevision.roles" :key="role.role" class="table-scroll" role="region" :aria-label="`${role.role} 補丁候選比較，可水平捲動`" tabindex="0"><table>
        <caption>{{ role.role }} · fit {{ format(role.fitN) }}／校準 {{ format(role.calibrationN) }}／2024 {{ format(role.validationN) }} · 保留 {{ role.selected }}；原基準 LL {{ role.referenceLL.toFixed(6) }}／Brier {{ role.referenceBrier.toFixed(6) }}</caption>
        <thead><tr><th scope="col">候選</th><th scope="col">特徵</th><th scope="col">機率</th><th scope="col">內層 LL</th><th scope="col">2024 LL</th><th scope="col">Brier</th><th scope="col">LL 差同時區間</th><th scope="col">整體門檻</th></tr></thead>
        <tbody><tr v-for="row in role.candidates" :key="row.config"><th scope="row">{{ row.config }}</th><td>{{ patchGroups[row.group] }}</td><td>{{ row.mode === 'raw' ? '原始' : '溫度校準' }}</td><td>{{ row.innerLL.toFixed(6) }}</td><td>{{ row.logLoss.toFixed(6) }}</td><td>{{ row.brier.toFixed(6) }}</td><td>[{{ row.familyInterval[0]?.toFixed(6) }}, {{ row.familyInterval[1]?.toFixed(6) }}]</td><td>{{ row.incrementGate ? '通過研究門檻' : '未通過' }}</td></tr></tbody>
      </table></div>
      <details><summary>訓練誤差與固定模型群組置換</summary>
        <p>訓練誤差是曾看過的資料，只用於診斷。置換把同月、現任／歷史及過去角色內的整群欄位一起打亂，保留基準控制；數值是模型對輸入的依賴，相關資訊可互相替代，不能解讀成疲勞或熟悉度因果。</p>
        <div class="table-scroll" role="region" aria-label="訓練與2024誤差，可水平捲動" tabindex="0"><table><thead><tr><th scope="col">舊模型</th><th scope="col">訓練 LL</th><th scope="col">2024 LL</th><th scope="col">差距</th></tr></thead><tbody><tr v-for="row in snapshot.modelPatchRevision.apparentErrors" :key="`${row.role}-${row.variant}`"><th scope="row">{{ row.role }}／{{ row.variant }}</th><td>{{ row.trainingLL.toFixed(6) }}</td><td>{{ row.validationLL.toFixed(6) }}</td><td>{{ row.gap.toFixed(6) }}</td></tr></tbody></table></div>
        <div v-for="role in snapshot.modelPatchRevision.roles" :key="`${role.role}-reliance`" class="table-scroll" role="region" :aria-label="`${role.role} 群組置換，可水平捲動`" tabindex="0"><table><thead><tr><th scope="col">固定模型</th><th scope="col">置換群</th><th scope="col">LL 增加</th><th scope="col">同時區間</th></tr></thead><tbody><tr v-for="row in role.groupReliance" :key="`${row.config}-${row.group}`"><th scope="row">{{ role.role }}／{{ row.config }}</th><td>{{ patchGroups[row.group] }}</td><td>{{ row.delta.toFixed(6) }}</td><td>[{{ row.interval[0]?.toFixed(6) }}, {{ row.interval[1]?.toFixed(6) }}]</td></tr></tbody></table></div>
      </details>
      <details><summary>2024 同分母訊號覆蓋</summary><p>現任為本場訊號，接任為已閉合歷史；不跨scope比較分數。pair_n／type_n的非缺值含0，代表計數有保存，不代表有自身對戰支持；原13.5支持數列在同組歷史摘要。</p><div class="table-scroll" role="region" aria-label="2024訊號覆蓋，可水平捲動" tabindex="0"><table><thead><tr><th scope="col">角色／範圍</th><th scope="col">欄位</th><th scope="col">有效／分母</th><th scope="col">缺值率</th></tr></thead><tbody><tr v-for="row in snapshot.modelPatchRevision.coverage2024" :key="`${row.role}-${row.is_current}-${row.field}`"><th scope="row">{{ row.role }}／{{ row.is_current ? '本場' : '歷史' }}</th><td>{{ row.field }}</td><td>{{ format(row.valid_n) }}／{{ format(row.n) }}</td><td>{{ percent(row.missing_pct) }}</td></tr></tbody></table></div></details>
      <p>484 點覆核：{{ snapshot.modelPatchRevision.impact.status }}。研究方向為替代池較高 {{ snapshot.modelPatchRevision.impact.directionCounts.pool_higher }}／續投較高 {{ snapshot.modelPatchRevision.impact.directionCounts.continue_higher }}／不明或不足 {{ snapshot.modelPatchRevision.impact.directionCounts.uncertain_or_unsupported }}。</p>
      <p class="footnote">同時區間以比賽×投手配對重抽樣，並校正角色內多候選；新增特徵另需勝過同演算法調整基準，校準、分群傷害與年度穩定也列入門檻。484點第一PA未通過補丁的角色仍用原13.1 global基準，後續PA皆回該基準。研究方向仍受可用性、狀態演化與後續打線限制，不是正式換投建議；同組保留原13.5／13.6／14.1歷史紀錄。本區記錄補丁交付時的14.1.1狀態；最新14.2.4成果見下方多燈區，畫面待使用者驗收。</p>
    </section>
    </details>

    <details id="history-alerts" class="research-group" :open="historyOpen('history-alerts', 'alert-research')">
      <summary>04 · Slice 14.2｜原32場預警與官方對應（歷史11／0）</summary>
    <section v-if="alertResearch" id="alert-research" class="panel" aria-labelledby="alert-research-heading">
      <div class="section-heading"><div><span class="eyebrow">Slice 14.2 · 固定32場2024凍結快照</span><h2 id="alert-research-heading">從連續比較點，到獨立研究預警</h2></div><span class="tag">保留原11預警／0配對 · 正式推薦關閉</span></div>
      <p>完整保留 {{ format(alertResearch.flow.raw_boundaries) }} 個原始邊界；既有cohort {{ format(alertResearch.flow.prepared_boundaries) }} 個，其中 {{ format(alertResearch.flow.modeled) }} 個有可計算替代池，{{ format(alertResearch.flow.simulation_supported) }} 個通過模擬支持。選場依固定雜湊，沒有依換投或收益挑選；這是32場研究分母，不能換算全季提醒量。</p>
      <p>研究規則先凍結：替代池優勢至少 {{ (alertResearch.rules.minimum_wpa_gain * 100).toFixed(1) }} 個勝率百分點，MC95／模型中央80區間下界皆大於0，全部9模型無截尾或外推、缺轉移機率不超過1%。同登板／同守備半局連續 {{ alertResearch.rules.persistence_boundaries }} 個相鄰原始邊界合格才發，任何缺口重置；同登板最多一則，同隊發出後冷卻 {{ alertResearch.rules.cooldown_defensive_pa }} 個已完成守備PA。</p>
      <div class="table-scroll" role="region" aria-label="研究點與獨立預警及官方事件分母，可水平捲動" tabindex="0"><table><thead><tr><th scope="col">單點合格</th><th scope="col">達持續條件的點</th><th scope="col">去重後研究預警</th><th scope="col">全部官方換投</th><th scope="col">同邊界對應</th><th scope="col">提前窗口對應</th><th scope="col">未配對預警／事件</th></tr></thead><tbody><tr><td>{{ format(alertResearch.flow.qualifying_points) }}</td><td>{{ format(alertResearch.flow.persistent_points) }}</td><td>{{ format(alertResearch.flow.independent_alerts) }}</td><td>{{ format(alertResearch.flow.official_changes) }}</td><td>{{ format(alertResearch.flow.same_boundary) }}</td><td>{{ format(alertResearch.flow.advance_window) }}</td><td>{{ format(alertResearch.flow.unmatched_alerts) }}／{{ format(alertResearch.flow.unmatched_events) }}</td></tr></tbody></table></div>
      <p>官方事件中，{{ format(alertResearch.flow.official_modeled_exact) }} 次有模型同邊界、{{ format(alertResearch.flow.official_modeled_window) }} 次在固定窗口內有可算機會。配對要求同場、同隊、同一離場登板；先同邊界，否則提前1–{{ alertResearch.rules.advance_defensive_pa }}個已完成守備PA且不超過 {{ alertResearch.rules.advance_seconds / 60 }} 分鐘。依預警順序取最早合格事件，一對一；同邊界是回溯對齊，不宣稱提前偵測。</p>
      <p>規則診斷：實際換投同邊界有 {{ alertResearch.rule_review.exact_qualified_points }} 個單點合格，但 {{ alertResearch.rule_review.exact_qualified_persistent_points }} 個達連續條件。原固定窗口內，{{ alertResearch.rule_review.events_with_qualified_point_in_original_window }} 次事件曾有合格點、{{ alertResearch.rule_review.events_with_persistent_point_in_original_window }} 次有持續合格點；已同登板發過的仍受去重限制。發出預警中 {{ alertResearch.rule_review.early_alerts_innings_1_to_3 }} 則在1–3局，與同一投手離場的中位間隔為 {{ format(alertResearch.rule_review.median_lead_pa) }} 個守備PA。這些僅解釋原結果，不增加配對；短半局替代池優勢尚不能當作先發疲勞或最佳換投切點。</p>
      <div class="table-scroll" role="region" aria-label="各角色研究預警，可水平捲動" tabindex="0"><table><thead><tr><th scope="col">被觀察角色</th><th scope="col">可計算</th><th scope="col">單點合格</th><th scope="col">獨立預警</th><th scope="col">同邊界</th><th scope="col">提前窗口</th></tr></thead><tbody><tr v-for="row in alertResearch.roles" :key="row.role"><th scope="row">{{ row.role }}</th><td>{{ format(row.modeled) }}</td><td>{{ format(row.qualifying) }}</td><td>{{ format(row.alerts) }}</td><td>{{ format(row.same_boundary) }}</td><td>{{ format(row.advance) }}</td></tr></tbody></table></div>
      <details><summary>每則研究預警與官方事件對應（全部列出）</summary>
        <p>投手是正在比較續投的現任；替代選項為名義後援均勻池，沒有個別人選推薦。差值均為換投池減續投，WPA用百分點、RE24用分。</p>
        <p v-if="!alertResearch.alerts.length">本次固定門檻沒有產生獨立研究預警，保留此結果，不回頭調整門檻或配對窗口。</p>
        <div v-else class="table-scroll" role="region" aria-label="每則研究預警，可水平捲動" tabindex="0"><table><thead><tr><th scope="col">場次／局面／現任</th><th scope="col">ΔxWPA pp</th><th scope="col">MC95／模型80 pp</th><th scope="col">ΔxRE24</th><th scope="col">對應</th><th scope="col">提前PA／秒</th><th scope="col">官方事件鍵</th></tr></thead><tbody><tr v-for="row in alertResearch.alerts" :key="row.decision_id"><th scope="row">{{ row.game_pk }} · {{ row.inning }}{{ row.half === 'top' ? '上' : '下' }} · {{ row.pitcher_name }}（{{ row.role }}）</th><td>{{ (row.wpa_delta * 100).toFixed(2) }}</td><td>[{{ alertBound(row.mc95[0]) }}, {{ alertBound(row.mc95[1]) }}]／[{{ alertBound(row.bootstrap80[0]) }}, {{ alertBound(row.bootstrap80[1]) }}]</td><td>{{ row.re24_delta.toFixed(3) }}</td><td>{{ alertReason(row.match_reason) }}</td><td>{{ row.lead_pa ?? '—' }}／{{ row.lead_seconds?.toFixed(1) ?? '—' }}</td><td>{{ row.event_id ?? '未配對' }}</td></tr></tbody></table></div>
      </details>
      <details><summary>32場完整流向與拒絕／未配對原因</summary>
        <div class="table-scroll" role="region" aria-label="各場研究流向，可水平捲動" tabindex="0"><table><thead><tr><th scope="col">日期／場次／客場→主場</th><th scope="col">原始／可算／支持</th><th scope="col">合格點／預警</th><th scope="col">官方換投</th><th scope="col">同邊界／提前</th><th scope="col">未配對預警</th></tr></thead><tbody><tr v-for="row in alertResearch.games" :key="row.game_pk"><th scope="row">{{ row.date }} · {{ row.game_pk }} · {{ row.away }} → {{ row.home }}</th><td>{{ row.boundaries }}／{{ row.modeled }}／{{ row.supported }}</td><td>{{ row.qualifying }}／{{ row.alerts }}</td><td>{{ row.official_changes }}</td><td>{{ row.same_boundary }}／{{ row.advance }}</td><td>{{ row.unmatched_alerts }}</td></tr></tbody></table></div>
        <div v-for="group in [{ label: '原始點主要拒絕／合格原因', rows: alertResearch.point_reasons }, { label: '持續／冷卻／去重', rows: alertResearch.alert_reasons }, { label: '未配對預警', rows: alertResearch.unmatched_alert_reasons }, { label: '全部官方事件流向', rows: alertResearch.event_reasons }]" :key="group.label" class="table-scroll" role="region" :aria-label="group.label" tabindex="0"><table><caption>{{ group.label }}</caption><thead><tr><th scope="col">原因</th><th scope="col">數量</th></tr></thead><tbody><tr v-for="(n, reason) in group.rows" :key="reason"><th scope="row">{{ alertReason(String(reason)) }}</th><td>{{ format(n) }}</td></tr></tbody></table></div>
      </details>
      <p class="footnote">對應率不代表合理率，未配對預警也不直接判錯。舊cohort包含回溯身分／實際接替者核對，不能冒充部署coverage；點區間不保證序列整體錯警率。第一PA以後仍回基準，後續打線回聯盟池，active／熱身／醫療與人工可用性未知；操作推薦 {{ alertResearch.flow.operational_recommendations }}。此區保留14.2歷史結果，最新14.2.4多燈回放見下方；選擇偏差／重疊及策略效益留15–16。畫面由使用者本人驗收。</p>
    </section>
    </details>
    </div>

    <p v-if="overlapResearch" class="footnote">以下保留14.2.4交付時的多燈研究版本與當時進度說明；最新進度以本頁總覽及16.1–3區為準。原多燈組合預測支持仍未通過，新PA預測與探索回測另列。</p>
    <DecisionSignalLights v-if="signalLights" :data="signalLights" />

    <details id="history-overlap" class="research-group" :open="historyOpen('history-overlap', 'overlap-research')"><summary>05 · Slice15｜原選擇偏差與重疊（歷史版本）</summary>
    <section v-if="overlapResearch" id="overlap-research" class="panel" aria-labelledby="overlap-heading">
      <div class="section-heading"><div><span class="eyebrow">Slice 15 · 時間前推選擇偏差與重疊</span><h2 id="overlap-heading">哪些情境有資料可比較，哪些仍不能下結論？</h2></div><span class="tag">研究工作完成 · 主要平衡未過</span></div>
      <p>{{ format(overlapResearch.flow.boundaries) }} 個2021–24回溯邊界、{{ format(overlapResearch.flow.changes) }} 次換投，恢復原 {{ overlapResearch.flow.restored }} 次池外接任事件。{{ overlapResearch.flow.models }} 個模型分開估計調度、後續量測、RP池歸屬與池內人選；2025結果封存。</p>
      <p>{{ overlapResearch.conclusion }}</p>
      <div class="table-scroll" role="region" aria-label="2024主要重疊與加權平衡" tabindex="0"><table><thead><tr><th scope="col">離場角色</th><th scope="col">全部邊界／換投</th><th scope="col">初步重疊</th><th scope="col">換投／續投ESS</th><th scope="col">最大絕對SMD</th><th scope="col">主要門檻</th></tr></thead><tbody><tr v-for="row in overlapResearch.roles.filter(x => x.year === 2024)" :key="row.role"><th scope="row">{{ row.role }}</th><td>{{ format(row.action.n) }}／{{ format(row.action.events) }}</td><td>{{ format(row.primary.retained) }}（{{ (row.primary.retained_fraction * 100).toFixed(1) }}%）</td><td>{{ row.primary.change.ess.toFixed(0) }}／{{ row.primary.continue.ess.toFixed(0) }}</td><td>{{ row.primary.max_abs_smd_after.toFixed(3) }}</td><td>{{ row.primary.diagnostic_gate ? '通過此項' : '未過0.1平衡' }}</td></tr></tbody></table></div>
      <p class="footnote">主要重疊要求換投傾向介於.05–.95，且過去同角色／局數／球數／LI分格的兩種行動各至少10次。ESS是權重折算的樣本量，不是獨立比賽數；SMD越接近0，已測特徵均值越接近，仍不能證明沒有隱藏混雜。{{ overlapResearch.interpretation }}</p>
      <h3>後續沒投，不能補成「狀態正常」</h3>
      <div class="table-scroll" role="region" aria-label="後續量測缺失與觀測權重" tabindex="0"><table><thead><tr><th scope="col">角色</th><th scope="col">監測機會</th><th scope="col">缺後續量測</th><th scope="col">四群／觀測支持母體</th><th scope="col">有量測／ESS</th><th scope="col">觀測加權最大SMD</th></tr></thead><tbody><tr v-for="row in overlapResearch.roles.filter(x => x.year === 2024)" :key="row.role"><th scope="row">{{ row.role }}</th><td>{{ format(row.monitoring_n) }}</td><td>{{ format(row.missing_future) }}（{{ (100 * row.missing_future / row.monitoring_n).toFixed(1) }}%）</td><td>{{ format(row.observation_balance[0]?.target_n ?? 0) }}</td><td>{{ format(row.observation_balance[0]?.observed_n ?? 0) }}／{{ row.observation_balance[0]?.observed_ess.toFixed(0) }}</td><td>{{ row.observation_balance[0]?.max_abs_smd_after?.toFixed(3) }}</td></tr></tbody></table></div>
      <p class="footnote">每個完整10球區段只取第一個合法邊界；目標區段必須全部在決策後。換下、續投太短、量測不足都可能使目標缺失，不能一律叫疲勞或誤報。觀測支持母體另要求四群可判讀及預測觀測機率至少.1；加權仍依賴無法由資料證明的觀測假設。</p>
      <details><summary>查看個別候選初篩、權重與多燈敏感度</summary>
        <div class="table-scroll" role="region" aria-label="2024名義RP候選初篩及有效樣本" tabindex="0"><table><thead><tr><th scope="col">離場角色</th><th scope="col">實際換投</th><th scope="col">接任者在RP池外</th><th scope="col">實際接任者過初篩</th><th scope="col">未截斷聯合權重ESS</th><th scope="col">權重上限10後ESS</th></tr></thead><tbody><tr v-for="row in overlapResearch.candidate_support.filter(x => x.year === 2024)" :key="row.role"><th scope="row">{{ row.role }}</th><td>{{ format(row.changes) }}</td><td>{{ format(row.changes_outside_rp_pool) }}</td><td>{{ format(row.chosen_supported) }}</td><td>{{ row.joint_weight_sensitivity[0]?.ess.toFixed(0) }}</td><td>{{ row.joint_weight_sensitivity[1]?.ess.toFixed(0) }}</td></tr></tbody></table></div>
        <p>候選機率包含「換投 × 進入RP池 × 選中該人」，保留池外機率。初篩還看候選自己的過去被選次數及RP登板，不能借現任投手的支持；整體平衡未過、熱身／醫療／實際可用性未知，仍沒有可操作人選推薦。截斷提高ESS會改變權重與偏差，不能只挑ESS最好看的結果。</p>
        <div class="table-scroll" role="region" aria-label="2024兩紅組合觀測加權敏感度" tabindex="0"><table><thead><tr><th scope="col">角色／權重cap</th><th scope="col">有量測／兩紅</th><th scope="col">偏離率差pp</th><th scope="col">描述性95%區間pp</th></tr></thead><tbody><tr v-for="row in overlapResearch.combination_observation_sensitivity2024" :key="row.role + String(row.cap)"><th scope="row">{{ row.role }}／{{ row.cap ?? '不截斷' }}</th><td>{{ format(row.n) }}／{{ row.flagged }}</td><td>{{ row.difference === null ? '不足' : (row.difference * 100).toFixed(2) }}</td><td>{{ row.interval ? row.interval.map(x => (x * 100).toFixed(2)).join(' ～ ') : '樣本不足，不計區間' }}</td></tr></tbody></table></div>
        <p>SP加權差區間仍跨0，RP在觀測支持範圍內沒有足夠兩紅。這是未來量測偏離的描述敏感度，並非換投策略收益；200次比賽×投手重抽樣重算比率，少樣本不硬給區間。主要觀測機率至少.1使權重至多10，所以10／20／50 cap相同是限制的必然，不能當穩健性證明。</p>
      </details>
      <p>原32場 {{ overlapResearch.fixed32.modeled }} 個可算點中，{{ overlapResearch.fixed32.modeled_in_primary_overlap }} 個通過初步重疊；整體平衡未過，不能稱為有效換投建議。原11／0、多燈0有效研究候選與xWPA模型保留。</p>
      <p class="footnote">下一步先修傾向平衡或預先限定比較母體，再明定16的策略與終點。研究工作完成40／47；16未開始，畫面待使用者驗收。</p>
    </section>
    </details>

    <section v-if="overlapRevision" id="overlap-revision" class="panel" aria-labelledby="overlap-revision-heading">
      <div class="section-heading"><div><span class="eyebrow">Slice 15.1–15.2 · 共同時點與平衡修訂</span><h2 id="overlap-revision-heading">先對齊觀測時點，再分局間／局中比較</h2></div><span class="tag">42／51研究工作 · 平衡仍未通過</span></div>
      <p>{{ format(overlapRevision.flow.original) }} 個原邊界中，{{ overlapRevision.flow.excluded }} 個無法確認共同截點嚴格早於行動而排除；{{ format(overlapRevision.flow.included) }} 個重取截點前球數、負荷、能力與原因。共同截點為前一個已完成play結束後，原官方事件時間留作回放；未知打者與較晚特徵不回填。</p>
      <h3>15.1：時點差異與缺失原因</h3>
      <div class="table-scroll" role="region" aria-label="2024後援兩種行動與共同截點的時間差" tabindex="0"><table><thead><tr><th scope="col">RP情境</th><th scope="col">行動</th><th scope="col">納入邊界</th><th scope="col">原時點晚於共同截點中位秒</th></tr></thead><tbody><tr v-for="row in overlapRevision.clock2024.filter(x => x.role === 'RP')" :key="row.phase + row.changed"><th scope="row">{{ phaseLabel(row.phase) }}</th><td>{{ row.changed ? '換投' : '續投' }}</td><td>{{ format(row.included) }}</td><td>{{ row.gap_seconds_median?.toFixed(1) }}</td></tr></tbody></table></div>
      <p>時間差的方向會隨局間／局中改變，不能直接當生理疲勞。所有特徵重新按共同截點取得；個人負荷基準固定進場前、牛棚只用更早的名義快照，實際熱身與健康仍未知。</p>
      <div class="table-scroll" role="region" aria-label="原15後援後續量測原因對帳" tabindex="0"><table><thead><tr><th scope="col">2024 RP原監測目標</th><th scope="col">機會數</th></tr></thead><tbody><tr v-for="row in overlapRevision.missing2024.filter(x => x.role === 'RP')" :key="row.reason"><th scope="row">{{ missingLabel(row.reason) }}</th><td>{{ format(row.n) }}</td></tr></tbody></table></div>
      <p class="footnote">機會不足包含稍後換下或原固定球塊需要10–19顆後續球；不能都叫量測缺檔。這是舊15目標的事後稽核，原因不入預測模型。15.3的新RP任務另列下方，未觀測仍留空值。</p>
      <h3>15.2：固定模型與特徵對照</h3>
      <p>共 {{ overlapRevision.flow.models }} 個模型。只以2022／2023前推結果排序，兩角色均以完整HGB作最穩定研究對照，但內層完整門檻未過；排序凍結後才檢查2024，沒有依2024改選。所有設定都用相同豐富欄位檢查平衡，核心特徵版也不能略過被移除欄位。</p>
      <div class="table-scroll" role="region" aria-label="凍結對照的2024主要overlap平衡" tabindex="0"><table><thead><tr><th scope="col">角色／情境</th><th scope="col">研究對照</th><th scope="col">初步母體</th><th scope="col">換投／續投ESS</th><th scope="col">最大SMD</th><th scope="col">完整門檻</th></tr></thead><tbody><tr v-for="row in overlapRevision.primary2024" :key="row.role + row.phase"><th scope="row">{{ row.role }}／{{ phaseLabel(row.phase) }}</th><td>{{ balanceModelLabel(row.variant) }}</td><td>{{ format(row.retained) }}</td><td>{{ row.change.ess.toFixed(0) }}／{{ row.continue.ess.toFixed(0) }}</td><td>{{ row.max_abs_smd_after?.toFixed(3) }}</td><td>{{ row.full_gate ? '通過此項' : '未通過' }}</td></tr></tbody></table></div>
      <p>主要overlap權重評估歷史上兩種行動都可能發生的情境，IPW另列不同母體。局中較接近0.1研究門檻，仍沒有通過；新舊時點、分組與欄位不同，數字應分別解讀，不能直接宣稱改善百分比。</p>
      <details><summary>查看全部2024 overlap對照與方法限制</summary>
        <div class="table-scroll" role="region" aria-label="2024四種固定模型全部overlap結果" tabindex="0"><table><thead><tr><th scope="col">角色／情境</th><th scope="col">模型</th><th scope="col">最大SMD</th><th scope="col">ECE</th><th scope="col">收斂警告</th></tr></thead><tbody><tr v-for="row in overlapRevision.all_results.filter(x => x.year === 2024 && x.scheme === 'overlap')" :key="row.role + row.phase + row.variant"><th scope="row">{{ row.role }}／{{ phaseLabel(row.phase) }}</th><td>{{ balanceModelLabel(row.variant) }}</td><td>{{ row.max_abs_smd_after?.toFixed(3) }}</td><td>{{ row.metrics.ece.toFixed(3) }}</td><td>{{ row.warning ? '有，阻擋晉升' : '無' }}</td></tr></tbody></table></div>
        <p>本輪矩條件平衡logit是受限研究對照，並非官方CBPS或精確平衡保證；{{ overlapRevision.convergence_warnings }} 個模型有收斂警告，沒有加迭代調到2024過。2024部分logit較低也不回頭改選，不能由本次結果否定整類平衡方法。</p>
        <ul><li v-for="note in overlapRevision.methodNotes" :key="note">{{ note }}</li></ul>
      </details>
      <p class="footnote">此區保留15.1–15.2歷史研究版本。原PA／xWPA／燈號、原11／0與多燈0有效研究候選保留；15.3及15.4另列下方，16仍未開始、2025封存。畫面由使用者驗收。</p>
    </section>

    <section v-if="rpTargets" id="rp-target-research" class="panel" aria-labelledby="rp-target-heading">
      <div class="section-heading"><div><span class="eyebrow">Slice 15.3 · RP觀測目標與受限母體</span><h2 id="rp-target-heading">短登板不一定看得到十球後；先分清楚要預測什麼</h2></div><span class="tag">43／51研究工作 · 未取得策略資格</span></div>
      <p>主要母體在擬合前指定為「局中、短型歷史RP」。短型依進場前最近10次已結束登板、至少5次，歷史BF中位≤4且球數中位≤20；沒有用本場最後投多久挑樣本。下一PA與未來十球是兩種不同任務，不能把跨任務Brier差異當模型改善。</p>
      <p>三個前推年度共 {{ rpTargets.flow.task_artifacts }} 個任務產物：{{ rpTargets.flow.hgb }} 個HGB、{{ rpTargets.flow.constant }} 個樣本不足的常數退路。觀測模型使用全部監測機會；結果模型只學有標籤者。換下者未知後續維持空值，不能借用接任者結果。</p>
      <h3>2024主要母體：相同監測分母下的可觀測率</h3>
      <div class="table-scroll" role="region" aria-label="後援兩項目標配對監測覆蓋" tabindex="0"><table><thead><tr><th scope="col">任務</th><th scope="col">監測機會</th><th scope="col">有結果</th><th scope="col">覆蓋率</th><th scope="col">自身常數Brier</th><th scope="col">結果模型Brier</th><th scope="col">AUC</th><th scope="col">ECE</th></tr></thead><tbody><tr v-for="row in rpPrimaryTasks" :key="row.target"><th scope="row">{{ rpLabel(row.target) }}</th><td>{{ format(row.n) }}</td><td>{{ format(row.observed) }}</td><td>{{ researchNumber((row.rate ?? 0) * 100, 2) }}%</td><td>{{ researchNumber(row.outcome_metrics?.constant_brier, 5) }}</td><td>{{ researchNumber(row.outcome_metrics?.brier, 5) }}</td><td>{{ researchNumber(row.outcome_metrics?.auc) }}</td><td>{{ researchNumber(row.outcome_metrics?.ece) }}</td></tr></tbody></table></div>
      <p class="footnote">同一已知球塊只留首個監測邊界，無完整塊時每登板留首個起始機會；同投手／同場／重複未來球塊不是獨立樣本。PA為既有分類的非K／非other_out結果，不等同純OBP；十球是研究殘差偏離，不等同生理疲勞。Brier越低越好，這裡尚無群聚區間支持晉升。</p>
      <h3>相同主要母體與豐富欄位：平衡有沒有過？</h3>
      <div class="table-scroll" role="region" aria-label="短型歷史後援新舊行動模型同母體平衡" tabindex="0"><table><thead><tr><th scope="col">行動模型</th><th scope="col">初步比較點</th><th scope="col">換投／續投ESS</th><th scope="col">最大SMD（≤0.1）</th><th scope="col">ECE（≤0.03）</th><th scope="col">完整診斷</th></tr></thead><tbody><tr v-for="row in rpTargets.primary2024" :key="row.model"><th scope="row">{{ rpLabel(row.model) }}</th><td>{{ format(row.retained) }}</td><td>{{ researchNumber(row.change.ess, 0) }}／{{ researchNumber(row.continue.ess, 0) }}</td><td>{{ researchNumber(row.max_abs_smd_after) }}</td><td>{{ researchNumber(row.action_metrics?.ece) }}</td><td>{{ row.full_gate ? '通過此項，非策略驗證' : '未通過' }}</td></tr></tbody></table></div>
      <h3>缺失者仍未知：假設不同，總體風險會變多少？</h3>
      <div class="table-scroll" role="region" aria-label="後援未觀測結果敏感度，非已確認風險" tabindex="0"><table><thead><tr><th scope="col">任務</th><th scope="col">未知機會</th><th scope="col">觀測者事件率</th><th scope="col">g≥0.1加權率</th><th scope="col">最壞情況界限</th><th scope="col">未知者odds×0.5／1／2情境</th></tr></thead><tbody><tr v-for="row in rpPrimarySensitivity" :key="row.target"><th scope="row">{{ rpLabel(row.target) }}</th><td>{{ format(row.missing) }}</td><td>{{ researchNumber((row.observed_rate ?? 0) * 100, 1) }}%</td><td>{{ researchNumber((row.ip_observation_rate ?? 0) * 100, 1) }}%</td><td>{{ row.worst_case_bounds.map(x => researchNumber(x * 100, 1) + '%').join('～') }}</td><td>{{ row.missing_scenarios.map(x => researchNumber(x.scenario_rate * 100, 1) + '%').join('／') }}</td></tr></tbody></table></div>
      <p class="footnote">情境值依賴缺失假設，沒有補成訓練標籤，也不是換下後的反事實。g≥0.1時權重上限10／20／50相同是預期結果。結果模型的Brier改善只適用已觀測者，不能直接推廣到被換下者。</p>
      <details><summary>展開固定母體對照、四年覆蓋與方法限制</summary>
        <div class="table-scroll" role="region" aria-label="全部固定後援母體2024overlap診斷" tabindex="0"><table><thead><tr><th scope="col">情境／母體</th><th scope="col">模型</th><th scope="col">最大SMD</th><th scope="col">換投ESS</th><th scope="col">續投ESS</th></tr></thead><tbody><tr v-for="row in rpTargets.balance_results.filter(x => x.year === 2024 && x.scheme === 'overlap')" :key="row.phase + row.subset + row.model"><th scope="row">{{ phaseLabel(row.phase) }}／{{ rpLabel(row.subset) }}</th><td>{{ rpLabel(row.model) }}</td><td>{{ researchNumber(row.max_abs_smd_after) }}</td><td>{{ researchNumber(row.change.ess, 0) }}</td><td>{{ researchNumber(row.continue.ess, 0) }}</td></tr></tbody></table></div>
        <div v-for="year in rpTargets.preparation" :key="year.year"><h4>{{ year.year }}：全部PA邊界與配對監測分母</h4><div class="table-scroll" role="region" :aria-label="`${year.year}全部後援目標覆蓋`" tabindex="0"><table><thead><tr><th scope="col">情境／任務</th><th scope="col">分母</th><th scope="col">觀測數／總數</th><th scope="col">覆蓋率</th></tr></thead><tbody><tr v-for="row in year.coverage.filter(x => x.subset === 'all')" :key="row.scope + row.phase + row.target"><th scope="row">{{ phaseLabel(row.phase) }}／{{ rpLabel(row.target) }}</th><td>{{ row.scope === 'paired_monitoring' ? '配對監測' : '全部PA邊界' }}</td><td>{{ format(row.observed) }}／{{ format(row.n) }}</td><td>{{ researchNumber((row.rate ?? 0) * 100, 2) }}%</td></tr></tbody></table></div></div>
        <ul><li v-for="note in rpTargets.methodNotes" :key="note">{{ note }}</li></ul>
      </details>
      <p class="footnote">此區保留15.3研究版本。2024是診斷資料，首次事件映射錯誤已完整留版並修正重跑，不稱獨立測試；15.4覆核另列下方，2025封存，畫面由使用者驗收。</p>
    </section>

    <section v-if="entryReview" id="entry-review" class="panel" aria-labelledby="entry-review-heading">
      <div class="section-heading"><div><span class="eyebrow">Slice 15.4 · 凍結前推與16資格覆核</span><h2 id="entry-review-heading">研究覆核已交付；策略效益評估仍未取得進入資格</h2></div><span class="tag">44／51研究工作 · 16待開始</span></div>
      <p>沿用固定的SP／RP模型、母體、特徵與門檻，重算 {{ format(entryReview.flow.reviewed_rows) }} 個前推邊界，沒有訓練新模型。{{ format(entryReview.flow.initial_support) }} 個點過初步支持，仍須通過整體比較及研究實作條件；主要年度／情境完整門檻 {{ entryReview.flow.primary_passed }}／{{ entryReview.flow.primary_folds }}，正式推薦保持關閉。</p>
      <p class="footnote">初步點數不是有效建議數。年度資格是事後研究稽核，不是當時已知訊號或歷史預警回放；2024已被診斷，這輪不是新的獨立確認。</p>
      <h3>固定主要母體：三年前推的平衡、樣本與校準</h3>
      <div class="table-scroll" role="region" aria-label="三年固定主要母體完整門檻" tabindex="0"><table><thead><tr><th scope="col">年份／情境</th><th scope="col">最大SMD（≤0.1）</th><th scope="col">換投／續投ESS（各≥500）</th><th scope="col">ECE（≤0.03）</th><th scope="col">拒絕原因</th></tr></thead><tbody><tr v-for="row in entryReview.primary_folds" :key="row.year + row.role + row.phase"><th scope="row">{{ row.year }}／{{ row.role }}／{{ phaseLabel(row.phase) }}</th><td>{{ researchNumber(row.max_abs_smd_after) }}</td><td>{{ researchNumber(row.change.ess, 0) }}／{{ researchNumber(row.continue.ess, 0) }}</td><td>{{ researchNumber(row.ece) }}</td><td>{{ row.failures.length ? row.failures.map(entryLabel).join('、') : '通過此項' }}</td></tr></tbody></table></div>
      <h3>改善有多確定？把同場／同投手的相關性納入</h3>
      <div class="table-scroll" role="region" aria-label="後援條件結果配對Brier群聚區間" tabindex="0"><table><thead><tr><th scope="col">年份／RP目標</th><th scope="col">有結果／監測機會</th><th scope="col">Brier模型－自身常數</th><th scope="col">探索性95%區間</th><th scope="col">是否跨0</th></tr></thead><tbody><tr v-for="row in entryReview.targets" :key="row.year + row.target"><th scope="row">{{ row.year }}／{{ rpLabel(row.target) }}</th><td>{{ format(row.observed) }}／{{ format(row.n) }}</td><td>{{ researchNumber(row.cluster_brier.delta, 6) }}</td><td>{{ row.cluster_brier.interval.map(x => researchNumber(x, 6)).join('～') }}</td><td>{{ crossesZero(row.cluster_brier.interval) ? '是，改善仍不確定' : '否，仍非策略效益' }}</td></tr></tbody></table></div>
      <p class="footnote">負值代表模型Brier較低；每個任務只與自身過去常數配對。300次比賽×投手重抽樣，只條件於固定模型與已觀測結果，不含重訓不確定性，也不能補出被換下投手的反事實；這些是探索性區間。</p>
      <h3>16進入資格：哪幾項還沒有證據？</h3>
      <ul><li v-for="gate in entryReview.barriers" :key="gate.id"><strong>{{ entryLabel(gate.id) }}</strong>：{{ gate.passed ? '通過此項' : gate.status === 'not_ready' ? '尚未就緒' : '未通過' }}</li></ul>
      <details><summary>查看16策略／同半局終點契約及逐點拒絕對帳</summary>
        <p>同一合法決策邊界比較續投與既有多燈條件觸發的換投：兩紅須包含球質或位置，並通過成熟度、fresh-block持續性、價值、合法、可用性與支持。接任從當時確認可用且有自身歷史／聯合機率支持的名義RP池等機率抽樣；關鍵證據未知則保留未知，這不是最佳人選排名。</p>
        <p>主要終點為同一當前／即將開始半局自然結束時的守方勝率減去共同截點勝率；次要為RE(anchor)減失分再減RE(同終點)。兩臂用相同後續策略，包含中間IBB、跑壘與終局。下一PA非出局及十球偏離另作觀測任務，不能代替策略WPA／RE24。</p>
        <p>共同截點的四群／價值回放、人選聯合行為與實際可用性、半局終點及共同後續策略仍需修訂，不能直接代入原較晚時點模型。策略尚未執行或估值；16仍須先取得資格再做direct／SNIPS／DR及群聚區間與敏感度。</p>
        <div class="table-scroll" role="region" aria-label="三年研究資格拒絕對帳" tabindex="0"><table><thead><tr><th scope="col">年份／情境</th><th scope="col">全部邊界</th><th scope="col">固定母體</th><th scope="col">初步支持</th><th scope="col">研究覆核通過</th><th scope="col">互斥拒絕原因</th></tr></thead><tbody><tr v-for="row in entryReview.flows" :key="row.year + row.role + row.phase"><th scope="row">{{ row.year }}／{{ row.role }}／{{ phaseLabel(row.phase) }}</th><td>{{ format(row.boundaries) }}</td><td>{{ format(row.population) }}</td><td>{{ format(row.initial_support) }}</td><td>{{ format(row.review_eligible) }}</td><td>{{ Object.entries(row.rejections).filter(([, n]) => n).map(([key, n]) => `${entryLabel(key)}：${n}`).join('；') }}</td></tr></tbody></table></div>
        <ul><li v-for="note in entryReview.methodNotes" :key="note">{{ note }}</li></ul>
      </details>
      <p class="footnote">此區保留15.4資格覆核，新15.5預測修訂另列下方；原比較平衡與16拒絕清單保留，不放寬門檻或依2024換母體、不開封2025。D為負荷／恢復，下一打者另列；舊文字勘誤不改原數值。畫面使用者驗收。</p>
    </section>

    <section v-if="peRevision" id="pe-revision" class="panel" aria-labelledby="pe-revision-heading">
      <div class="section-heading"><div><span class="eyebrow">Slice 15.5.1–15.5.4 · PE、個人參考與預定打線</span><h2 id="pe-revision-heading">近期表現摘要能否帶來額外的預測訊號？</h2></div><span class="tag">48／55研究工作 · 正式推薦未開啟</span></div>
      <p>{{ format(peRevision.flow.features_boundaries) }} 個共同截點重建特徵；{{ peRevision.flow.models_pa }} 個九類PA模型、{{ peRevision.flow.models_run }} 個PA期間失分模型。PE是固定權重的PA代理，個人參考鎖在進場前，預定下三棒只用先前已完成PA的棒次球員推估。預測身分不是事後實際打者，D負荷與相性分開。</p>
      <h3>先看2022／23凍結的研究對照，再看2024診斷</h3>
      <div class="table-scroll" role="region" aria-label="凍結設定的2024主要PA預測結果" tabindex="0"><table><thead><tr><th scope="col">主要母體</th><th scope="col">內層選定設定</th><th scope="col">九類log loss</th><th scope="col">非出局AUC／ECE</th><th scope="col">對共同基準ΔLL及探索性95%區間</th><th scope="col">2022／23支持</th><th scope="col">2024此項診斷</th></tr></thead><tbody><tr v-for="row in peRevision.primary2024" :key="row.role"><th scope="row">{{ row.role === 'SP' ? 'SP全部共同邊界' : 'RP局中短型歷史' }}</th><td>{{ peModelLabel(row.config) }}</td><td>{{ researchNumber(row.metrics.log_loss, 5) }}</td><td>{{ researchNumber(row.metrics.nonout.auc) }}／{{ researchNumber(row.metrics.nonout.ece) }}</td><td>{{ researchNumber(row.delta_log_loss.delta, 6) }} [{{ row.delta_log_loss.interval.map(x => researchNumber(x, 6)).join('，') }}]</td><td>{{ row.development_predictive_support ? '通過預測研究條件' : '未通過' }}</td><td>{{ row.predictive_gate ? '通過此項' : '未通過此項' }}</td></tr></tbody></table></div>
      <p class="footnote">log loss越低越好，ΔLL為模型減HGB共同基準，負值有利。區間為固定模型／已觀測結果的比賽×投手重抽樣，非重訓不確定性；2024先前已看過，這輪不是新的獨立驗證。這些是PA預測條件，不能代替SMD或策略效益條件。</p>
      <details><summary>查看PE消融及相同完整特徵的全部模型對照</summary><div v-for="fold in pe2024" :key="fold.role"><h4>{{ fold.role }}：同一主要驗證母體、相同訓練分段</h4><div class="table-scroll" role="region" :aria-label="`${fold.role}五項固定PA對照`" tabindex="0"><table><thead><tr><th scope="col">設定</th><th scope="col">九類LL</th><th scope="col">非出局Brier／AUC</th><th scope="col">對基準ΔLL</th><th scope="col">探索性95%區間</th><th scope="col">擬合警告</th></tr></thead><tbody><tr v-for="row in fold.pa" :key="row.config"><th scope="row">{{ peModelLabel(row.config) }}</th><td>{{ researchNumber(row.metrics.log_loss, 5) }}</td><td>{{ researchNumber(row.metrics.nonout.brier, 5) }}／{{ researchNumber(row.metrics.nonout.auc) }}</td><td>{{ researchNumber(row.delta_log_loss.delta, 6) }}</td><td>{{ row.delta_log_loss.interval.map(x => researchNumber(x, 6)).join('～') }}</td><td>{{ row.fit_warning ? '有，阻擋此項支持' : '無' }}</td></tr></tbody></table></div></div><p>HGB共同基準→加PE→完整群可觀察特徵增量；完整群同時加入個人參考與預定打線，無法只憑總增益歸因某一欄。線性／RF用相同完整特徵比較演算法，沒有依2024回頭改選。</p></details>
      <h3>下一PA期間失分：研究風險提醒，不是正式換投建議</h3>
      <div class="table-scroll" role="region" aria-label="2024角色別風險提醒與未知結果" tabindex="0"><table><thead><tr><th scope="col">角色／設定</th><th scope="col">提醒數</th><th scope="col">每100登板提醒</th><th scope="col">有／無可觀測後續</th><th scope="col">已觀測PPV</th><th scope="col">前三局提醒</th><th scope="col">同邊界／提前配對</th></tr></thead><tbody><template v-for="fold in pe2024" :key="fold.role"><tr v-for="row in fold.warnings" :key="fold.role + row.config"><th scope="row">{{ row.role }}／{{ peModelLabel(row.config) }}</th><td>{{ format(row.alerts) }}</td><td>{{ researchNumber(row.alerts_per100_appearances, 1) }}</td><td>{{ format(row.known_alerts) }}／{{ format(row.unknown_alerts) }}</td><td>{{ ratioPercent(row.precision_observed) }}</td><td>{{ format(row.early_alerts) }}</td><td>{{ format(row.same_boundary_change) }}／{{ format(row.advance_change_2pa600s) }}</td></tr></template></tbody></table></div>
      <p class="footnote">用過去全部cal邊界風險的90百分位取門檻，連續兩個同半局／登板PA才提醒，一登板一次；角色流內冷卻兩PA，未整合SP轉RP全域策略。未知後續不算誤報。提前配對限1–2完整PA且600秒內，同邊界另列；配對僅涵蓋既有合法母體，不代表全部官方事件召回或策略正確。提醒統計為角色全部母體，RP預測主表是局中短型歷史，分母不同。</p>
      <details><summary>查看失分模型指標、原RP二元配對對照及特徵coverage</summary>
        <div v-for="fold in pe2024" :key="fold.role"><h4>{{ fold.role }}輔助失分任務</h4><div class="table-scroll" role="region" :aria-label="`${fold.role}PA期間失分預測`" tabindex="0"><table><thead><tr><th scope="col">設定</th><th scope="col">Brier／自身常數</th><th scope="col">AUC／ECE</th><th scope="col">對HGB基準ΔBrier區間</th></tr></thead><tbody><tr v-for="row in fold.run" :key="row.config"><th scope="row">{{ peModelLabel(row.config) }}</th><td>{{ researchNumber(row.metrics.brier, 5) }}／{{ researchNumber(row.metrics.constant_brier, 5) }}</td><td>{{ researchNumber(row.metrics.auc) }}／{{ researchNumber(row.metrics.ece) }}</td><td>{{ row.delta_brier.interval.map(x => researchNumber(x, 6)).join('～') }}</td></tr></tbody></table></div></div>
        <template v-for="fold in pe2024" :key="'paired-' + fold.role"><div v-if="fold.paired_binary_reference.length"><h4>RP相同配對監測案例：與原15.3二元模型對照</h4><div class="table-scroll" role="region" aria-label="RP相同監測案例二元對照" tabindex="0"><table><thead><tr><th scope="col">設定</th><th scope="col">樣本</th><th scope="col">非出局Brier</th><th scope="col">AUC</th><th scope="col">對原二元ΔBrier區間</th></tr></thead><tbody><tr v-for="row in fold.paired_binary_reference" :key="row.config"><th scope="row">{{ peModelLabel(row.config) }}</th><td>{{ format(row.metrics.n) }}</td><td>{{ researchNumber(row.metrics.brier, 5) }}</td><td>{{ researchNumber(row.metrics.auc) }}</td><td>{{ row.delta_brier.interval.map(x => researchNumber(x, 6)).join('～') }}</td></tr></tbody></table></div><p>驗證案例相同，但原二元與新九類模型的訓練母體／任務不同；只作補充對照，不是純演算法消融。</p></div></template>
        <div class="table-scroll" role="region" aria-label="四年新特徵及標籤覆蓋" tabindex="0"><table><thead><tr><th scope="col">年份／角色</th><th scope="col">共同邊界</th><th scope="col">原投手可觀測PA</th><th scope="col">有效PE3</th><th scope="col">進場前FF參考</th><th scope="col">下一棒身分未知</th><th scope="col">已知預測身分吻合／有結果</th></tr></thead><tbody><template v-for="year in peRevision.coverage" :key="year.year"><tr v-for="row in year.coverage" :key="year.year + row.role"><th scope="row">{{ year.year }}／{{ row.role }}</th><td>{{ format(row.n) }}</td><td>{{ format(row.target_observed) }}</td><td>{{ format(row.feature_nonmissing.pe_last3) }}</td><td>{{ format(row.feature_nonmissing.ff_entry_mean) }}</td><td>{{ format(row.lineup_status.slot_unobserved ?? 0) }}</td><td>{{ format(row.forecast_agreement) }}／{{ format(row.forecast_agreement_n) }}</td></tr></template></tbody></table></div>
        <ul><li v-for="note in peRevision.methodNotes" :key="note">{{ note }}</li></ul>
      </details>
      <p class="footnote">本輪沒有重訓行動傾向、降低SMD或估換投策略收益；原15.4九個主要比較門檻與16實作／識別缺口保留。停15.5.4，2025封存，畫面使用者驗收。</p>
    </section>

    <section v-if="exploration" id="exploratory-replay" class="panel" aria-labelledby="exploratory-heading">
      <div class="section-heading"><div><span class="eyebrow">Slice16.1–16.3 · 探索回測</span><h2 id="exploratory-heading">提醒何時出現，替代人選的模型情境如何？</h2></div><span class="tag">51／58工作交付 · 正式效益未通過</span></div>
      <p>固定{{ exploration.caseFlow.games }}場、{{ format(exploration.caseFlow.boundaries) }}個共同截點；{{ format(exploration.caseFlow.modeled) }}點可估、{{ format(exploration.caseFlow.excluded) }}點保留未知。{{ exploration.caseFlow.alerts }}次影子風險提醒，其中{{ exploration.caseFlow.alerts_half_supported }}點有本輪支持的半局情境估值；這些都不是已驗證的換投建議。</p>
      <div class="table-scroll" role="region" aria-label="整合角色風險提醒與實際換投對應" tabindex="0"><table><thead><tr><th>年份／角色</th><th>截點</th><th>提醒</th><th>前三局</th><th>後續未知</th><th>可觀測失分比例</th><th>同邊界／提前</th></tr></thead><tbody><template v-for="year in exploration.replay" :key="year.year"><tr v-for="row in year.groups" :key="row.role"><th>{{ year.year }}／{{ row.role }}</th><td>{{ format(row.boundaries) }}</td><td>{{ row.alerts }}</td><td>{{ row.early_alerts }}</td><td>{{ row.unknown }}</td><td>{{ ratioPercent(row.observed_ppv) }}</td><td>{{ row.same_boundary }}／{{ row.advance }}</td></tr></template></tbody></table></div>
      <p>比較模型納入實際接任案例，候補只用自身過去能力／負荷／近期已結束登板。2022／23平均LL：共同基準{{ researchNumber(exploration.selection.development_mean_log_loss.base, 6) }}、加入現任狀態{{ researchNumber(exploration.selection.development_mean_log_loss.rich, 6) }}；依開發年選{{ exploration.selection.selected === 'base' ? '共同基準' : '完整版本' }}，不依2024改選。</p>
      <p>候補{{ format(exploration.candidateCoverage.nominal_rows) }}列，{{ format(exploration.candidateCoverage.own_history_supported) }}列有自身歷史支持；已結束近期狀態{{ format(exploration.candidateCoverage.recent_known) }}列。當場狀態未借現任、熱身與醫療仍未知。</p>
      <div class="table-scroll" role="region" aria-label="下一PA與固定半局情境支持及敏感度" tabindex="0"><table><thead><tr><th>情境</th><th>可估點</th><th>PA／半局支持</th><th>半局池較高／續投較高</th><th>支持點平均ΔxWPA</th><th>比賽群聚描述95%範圍</th></tr></thead><tbody><tr v-for="row in exploration.scenarios" :key="row.variant"><th>{{ explorationVariant(row.variant) }}</th><td>{{ row.modeled }}</td><td>{{ row.pa.supported }}／{{ row.half.supported }}</td><td>{{ row.half.directions.pool_higher ?? 0 }}／{{ row.half.directions.continue_higher ?? 0 }}</td><td>{{ researchNumber(row.half.wpa.mean === null ? null : 100 * row.half.wpa.mean) }}pp</td><td>{{ row.half.wpa.interval ? row.half.wpa.interval.map(x => researchNumber(100 * x)).join(' ～ ') : '未知' }}pp</td></tr></tbody></table></div>
      <p class="footnote">平均是固定案例的模型情境描述，重疊決策點不可相加成球隊／整季效益；不同敏感度池的分母可能不同。單點範圍只含配對MC，未涵蓋模型與選擇偏差。</p>
      <p>外推拒絕的主要來源包含歷史打席數超過訓練期上限，並不代表缺少該打者或投手資料；本輪保留原範圍門檻，沒有為了增加支持點而放寬。</p>
      <details><summary>共同支持案例的敏感度與限制</summary><p v-for="row in exploration.sensitivity" :key="`${row.variant}-${row.horizon}`">{{ explorationVariant(row.variant) }}／{{ row.horizon === 'pa' ? '下一PA' : '半局' }}：共同支持{{ row.common_supported }}點，方向分類改變{{ row.direction_changed }}點，平均差值變化{{ researchNumber(row.mean_delta_change === null ? null : 100 * row.mean_delta_change) }}pp。</p><ul><li v-for="note in exploration.methodNotes" :key="note">{{ note }}</li></ul></details>
      <DecisionResearchTimeline v-if="explorationGames" :games="explorationGames" />
    </section>

    <section id="next-validation" class="panel" aria-labelledby="next-validation-heading">
      <div class="section-heading"><h2 id="next-validation-heading">接下來做什麼，哪一步能驗證？</h2><span class="tag">16.1–3探索研究完成 · 正式效益待覆核</span></div>
      <p>已可檢查整場提醒、實際換投及共同截點情境估值。原比較平衡、四群／價值、人選實際可用性與共同後續策略資格保留；探索工作完成不代表換投有效。</p>
      <div class="table-scroll" role="region" aria-label="後續Slice工作與驗證里程碑，可水平捲動" tabindex="0"><table class="next-slices"><thead><tr><th scope="col">步驟</th><th scope="col">要回答的問題</th><th scope="col">交付與能驗證的內容</th></tr></thead><tbody>
        <tr><th scope="row">15 · 已完成研究評估</th><td>留下繼續投的人，是否本來就比較好？相似情境有沒有兩種決策？</td><td>已交付調度／人選／量測傾向、重疊、權重及有效樣本；兩角色主要平衡未過，需另行修訂後才談策略成效。</td></tr>
        <tr><th scope="row">15.1–15.2 · 已完成修訂研究</th><td>兩組時點是否一致？分情境與改平衡模型能否改善可比性？</td><td>共同截點特徵與缺失對帳、48固定模型已交付；完整平衡門檻仍未過。</td></tr>
        <tr><th scope="row">15.3 · 已完成目標／母體研究</th><td>RP下一PA與十球目標各有多少能觀測？歷史型態能否改善可比性？</td><td>兩任務前推、固定受限母體、新舊模型平衡及缺失敏感度已交付；主要平衡未過，未知仍保留。</td></tr>
        <tr><th scope="row">15.4 · 已完成資格覆核</th><td>哪些比較母體／終點有支持、能進16？</td><td>固定門檻與三年前推覆核完成，9個主要門檻全未過；策略／終點已明定，先另立修訂補拒絕清單。</td></tr>
        <tr><th scope="row">15.5.1–4 · 已完成預測修訂研究</th><td>近期PE、個人參考、預定打線與換模型，各能帶來多少增益？</td><td>42個固定擬合、同樣本消融／演算法對照、前推增益區間、風險提醒負擔／未知／提前配對；不以預測提升跳過SMD及策略資格。</td></tr>
        <tr><th scope="row">16.1–3 · 探索回測已交付</th><td>提醒何時出現？在同一截點，續投與名義替代池的模型結果有何不同？</td><td>整合SP／RP影子回放、32場時間軸、下一PA與固定半局模型情境、支持／負荷與休息敏感度；畫面由你驗收。</td></tr>
        <tr><th scope="row">16主項 · 正式效益仍進行中</th><td>能否在足夠可比、有人選與後續策略支持的族群，估計採用策略的效益？</td><td>需另行修訂共同人選行動機率／可用性、平衡與後續策略；SNIPS／DR未估，不能把模擬差值當已證實收益。</td></tr>
        <tr><th scope="row">17 · 凍結2025測試</th><td>鎖定規則後，效果能否延伸到保留年度？</td><td>凍結模型、門檻及評估範圍後做一次年度保留測試；結果不回流調參，揭露2025曾用於其他研究。</td></tr>
        <tr><th scope="row">18 · 2026歷史回放</th><td>逐場按當時資訊執行，會出現多少提醒、灰燈及漏掉的機會？</td><td>時序紀錄、覆蓋與提醒負擔、預測及事件對應。這是回溯部署檢查，並非真正前瞻實測。</td></tr>
        <tr><th scope="row">19–20 · Personal／In game</th><td>能否在同場WPA走勢上看見狀態、研究提示與實際換投？</td><td>個人頁、單場時間軸、投球鍵同步與雙層燈號；只呈現有支持的提示，畫面與操作由你驗收。</td></tr>
        <tr><th scope="row">21 · 新資料影子監測</th><td>模型凍結後，面對之後的新比賽是否仍可靠？</td><td>2027+新資料只追加紀錄，檢查漂移、提醒與有效覆蓋；達到預先約定的支持及成效才評估產品晉升。</td></tr>
      </tbody></table></div>
      <p><strong>驗證時間點：</strong>現在可驗收展示與案例；15檢查比較資格；16開始驗證離線策略效益；17檢查保留年度；18看完整回放的提醒負擔；19–20驗收整合畫面；21才有真正的新資料前瞻監測。任何一步沒有足夠支持，都可能需要回到模型研究，不能只因Slice往前就開啟推薦。</p>
      <p class="footnote">Slice 22代打／跑壘／防守仍暫緩；目前51／58，停在16.3，17–21未開始、2025封存。</p>
    </section>

    <section class="panel safeguards" aria-labelledby="scope-heading"><h2 id="scope-heading">研究範圍與進入下一階段的條件</h2><ul><li v-for="rule in plan.guardrails" :key="rule">{{ rule }}</li></ul><p class="footnote">本頁為規劃快照，不會觸發補抓、模型訓練或換投預警。單場儀表板、電池條、In game 同步與燈號列在後續 Slices；代打、跑壘與防守另行擴充。</p></section>
  </main>
</template>

<style scoped>
#overlap-revision,#rp-target-research,#entry-review,#pe-revision,#exploratory-replay{scroll-margin-top:90px}
.reading-nav{display:flex;flex-wrap:wrap;gap:10px}.reading-nav a{padding:9px 13px;border:1px solid var(--color-border);border-radius:8px;color:var(--color-primary);font-size:13px}.research-history,.research-group[open]{display:grid;gap:14px}.research-group{min-width:0;scroll-margin-top:90px;border:1px solid var(--color-border);border-radius:var(--radius-md);padding:16px}.research-group>summary{cursor:pointer;font-weight:700;line-height:1.7}.research-group>summary::marker{color:var(--color-primary)}.sub-slice{margin-left:14px}.next-slices{white-space:normal;min-width:620px}.next-slices th:first-child{min-width:140px}.next-slices td{min-width:220px;line-height:1.7}#signal-lights,#next-validation,#research-history{scroll-margin-top:90px}
.decision-plan{display:grid;gap:22px;min-width:0}.panel{min-width:0;border:1px solid var(--color-border);border-radius:var(--radius-md);background:var(--color-surface);padding:20px}.eyebrow{color:var(--color-primary);font-size:12px;font-weight:800;letter-spacing:.06em}.decision-plan h2{font-size:23px;margin:8px 0 12px}.decision-plan h3{margin:6px 0 10px;font-size:19px}.decision-plan p,.decision-plan li,.decision-plan dd{line-height:1.7;color:var(--color-muted-text)}.decision-plan p{margin:8px 0}.overview{display:grid;grid-template-columns:minmax(0,1fr) 210px;gap:16px;border-top:3px solid var(--color-primary)}.progress{display:grid;gap:9px;align-content:center}.progress strong{font-size:32px;color:var(--color-primary)}.progress span{font-size:12px;color:var(--color-muted-text)}progress{width:100%;height:7px;accent-color:var(--color-primary)}.next-step{grid-column:1/-1;border-top:1px solid var(--color-border);padding-top:14px}.next-step strong{color:var(--color-primary)}.audit-stats,.metric-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.audit-stats article{display:grid;gap:14px}.audit-stats span{color:var(--color-muted-text);font-size:13px}.audit-stats strong{font-size:clamp(24px,3vw,34px);font-variant-numeric:tabular-nums}.section-heading{display:flex;justify-content:space-between;align-items:center;gap:14px;flex-wrap:wrap}.tag{display:inline-block;width:max-content;max-width:100%;font-size:12px;line-height:1.5;padding:5px 10px;border:1px solid var(--color-border);border-radius:20px;color:var(--color-muted-text)}.tag.done{color:#8ee0b0;border-color:#316047}.tag.in_progress{color:var(--color-primary);border-color:var(--color-primary)}.table-scroll{overflow-x:auto;max-width:100%;margin:16px 0}.table-scroll:focus-visible{outline:2px solid var(--color-primary);outline-offset:3px}table{width:100%;border-collapse:collapse;white-space:nowrap;text-align:left;font-size:13px}caption{text-align:left;color:var(--color-muted-text);padding-bottom:12px}th,td{padding:12px;border-bottom:1px solid var(--color-border);font-variant-numeric:tabular-nums}thead th{color:var(--color-primary)}.footnote{font-size:12px}.timeline{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px}.timeline strong{color:var(--color-primary);font-size:19px}.timeline p{font-size:13px}.roadmap,.stage{display:grid;gap:12px}.phase-nav{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px}.phase-nav button{padding:10px 14px;border:1px solid var(--color-border);border-radius:8px;background:var(--color-surface);color:var(--color-foreground);font:inherit;cursor:pointer}.phase-nav button[aria-pressed=true]{color:var(--color-on-primary);background:var(--color-primary);border-color:var(--color-primary)}button:focus-visible,summary:focus-visible,a:focus-visible{outline:2px solid var(--color-primary);outline-offset:4px}.stage{margin-bottom:18px}.stage>header{border-left:3px solid var(--color-primary);padding-left:16px}.stage>header h3{margin-top:0}.slice{padding:0;scroll-margin-top:90px}.slice summary{padding:17px 20px;cursor:pointer;line-height:1.7}.slice summary>span:first-child{font-weight:700;margin-right:12px}.slice summary::marker{color:var(--color-primary)}.slice-body{padding:0 20px 18px;border-top:1px solid var(--color-border)}dl{display:grid;grid-template-columns:85px minmax(0,1fr);gap:12px;font-size:14px}dt{font-weight:700;padding-top:3px}dd{margin:0;overflow-wrap:anywhere}dd a{display:inline-block;margin-right:12px;color:var(--color-primary)}.metric-grid h3{color:var(--color-primary)}.safeguards ul{padding-left:22px;display:grid;gap:8px}
.footnote{overflow-wrap:anywhere}
.revision-figures{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.revision-figures figure{margin:0;min-width:0}.revision-figures img{width:100%;height:auto;background:white;border-radius:6px}.revision-figures figcaption{font-size:12px;color:var(--color-muted-text);line-height:1.6;margin:8px 0}@media(max-width:900px){.revision-figures{grid-template-columns:1fr}}
@media(max-width:1100px){.timeline{grid-template-columns:repeat(3,minmax(0,1fr))}}@media(max-width:700px){.overview{grid-template-columns:1fr}.audit-stats,.metric-grid,.timeline{grid-template-columns:1fr}.progress{max-width:260px}.panel{padding:16px}.slice{padding:0}.slice summary{padding:16px}.slice summary .tag{margin-top:6px}.slice-body{padding:0 16px 16px}dl{grid-template-columns:1fr;gap:5px}dd{margin-bottom:9px}}
</style>
