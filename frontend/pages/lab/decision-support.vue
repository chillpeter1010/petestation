<script setup lang="ts">
import snapshot from '~/data/pitcherDecisionPlan.json'

const plan = snapshot.project
const phase = ref('all')
const visiblePhases = computed(() => plan.phases.filter(item => phase.value === 'all' || item.id === phase.value))
const completed = plan.slices.filter(item => item.status === 'done').length
const total = (key: 'pitches' | 'pa' | 'changes') => snapshot.coverage.reduce((sum, row) => sum + row[key], 0).toLocaleString('en-US')
const format = (value: number | null) => value === null ? '尚無成績檔' : value.toLocaleString('en-US')
const percent = (value: number) => `${value.toFixed(2)}%`
const statusLabels: Record<string, string> = { done: '已完成', in_progress: '進行中', planned: '待開始', deferred: '後續擴充' }
const status = (value: string) => statusLabels[value] || value
const slicesFor = (id: string) => plan.slices.filter(item => item.phase === id)
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
      <p class="footnote">候選附近期用球、前次用球、連續登板、同日登板、距離先發／長局數的歷史。曾先發不自動加體力。此處尚未訓練 xWPA／xRE24，沒有換投燈號或最佳人選建議。</p>
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

    <section class="timeline" aria-label="模型時間切分">
      <article v-for="window in plan.experiment" :key="window.years" class="panel"><strong>{{ window.years }}</strong><h3>{{ window.role }}</h3><p>{{ window.detail }}</p></article>
    </section>

    <section aria-labelledby="roadmap-heading" class="roadmap">
      <div class="section-heading"><div><span class="eyebrow">Slice roadmap</span><h2 id="roadmap-heading">五階段研究流程</h2></div><span class="tag">決策模型與預警尚未開工</span></div>
      <nav class="phase-nav" aria-label="篩選研究階段">
        <button type="button" :aria-pressed="phase === 'all'" @click="phase = 'all'">全部階段</button>
        <button v-for="item in plan.phases" :key="item.id" type="button" :aria-pressed="phase === item.id" @click="phase = item.id">{{ item.title }}</button>
      </nav>
      <section v-for="stage in visiblePhases" :key="stage.id" :aria-labelledby="`phase-${stage.id}`" class="stage">
        <header><h3 :id="`phase-${stage.id}`">{{ stage.title }}</h3><p>{{ stage.description }}</p></header>
        <details v-for="item in slicesFor(stage.id)" :id="`slice-${item.id}`" :key="item.id" class="slice panel" :open="item.id === '1'">
          <summary><span>{{ item.label }}</span><span class="tag" :class="item.status">{{ status(item.status) }}</span></summary>
          <div class="slice-body"><p>{{ item.deliverable }}</p><dl><dt>依賴</dt><dd v-if="item.depends_on.length"><NuxtLink v-for="dependency in item.depends_on" :key="dependency" :to="{ path: '/lab/decision-support', hash: `#slice-${dependency}` }" @click="phase = 'all'">{{ dependency === 'P0' ? dependency : `Slice ${dependency}` }}</NuxtLink></dd><dd v-else>無</dd><dt>完成條件</dt><dd>{{ item.acceptance }}</dd><dt>目前證據</dt><dd>{{ item.verification === 'Pending' ? '待開始；尚無驗證結果。' : item.verification === 'Deferred' ? '暫緩；待投手主線完成後另行展開。' : item.verification }}</dd></dl></div>
        </details>
      </section>
    </section>

    <section class="metric-grid" aria-label="預期價值定義"><article v-for="metric in metrics" :key="metric.name" class="panel"><h3>{{ metric.name }}</h3><p>{{ metric.text }}</p></article></section>
    <section class="panel safeguards" aria-labelledby="scope-heading"><h2 id="scope-heading">研究範圍與進入下一階段的條件</h2><ul><li v-for="rule in plan.guardrails" :key="rule">{{ rule }}</li></ul><p class="footnote">本頁為規劃快照，不會觸發補抓、模型訓練或換投預警。單場儀表板、電池條、In game 同步與燈號列在後續 Slices；代打、跑壘與防守另行擴充。</p></section>
  </main>
</template>

<style scoped>
.decision-plan{display:grid;gap:22px;min-width:0}.panel{min-width:0;border:1px solid var(--color-border);border-radius:var(--radius-md);background:var(--color-surface);padding:20px}.eyebrow{color:var(--color-primary);font-size:12px;font-weight:800;letter-spacing:.06em}.decision-plan h2{font-size:23px;margin:8px 0 12px}.decision-plan h3{margin:6px 0 10px;font-size:19px}.decision-plan p,.decision-plan li,.decision-plan dd{line-height:1.7;color:var(--color-muted-text)}.decision-plan p{margin:8px 0}.overview{display:grid;grid-template-columns:minmax(0,1fr) 210px;gap:16px;border-top:3px solid var(--color-primary)}.progress{display:grid;gap:9px;align-content:center}.progress strong{font-size:32px;color:var(--color-primary)}.progress span{font-size:12px;color:var(--color-muted-text)}progress{width:100%;height:7px;accent-color:var(--color-primary)}.next-step{grid-column:1/-1;border-top:1px solid var(--color-border);padding-top:14px}.next-step strong{color:var(--color-primary)}.audit-stats,.metric-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.audit-stats article{display:grid;gap:14px}.audit-stats span{color:var(--color-muted-text);font-size:13px}.audit-stats strong{font-size:clamp(24px,3vw,34px);font-variant-numeric:tabular-nums}.section-heading{display:flex;justify-content:space-between;align-items:center;gap:14px;flex-wrap:wrap}.tag{display:inline-block;width:max-content;max-width:100%;font-size:12px;line-height:1.5;padding:5px 10px;border:1px solid var(--color-border);border-radius:20px;color:var(--color-muted-text)}.tag.done{color:#8ee0b0;border-color:#316047}.tag.in_progress{color:var(--color-primary);border-color:var(--color-primary)}.table-scroll{overflow-x:auto;max-width:100%;margin:16px 0}.table-scroll:focus-visible{outline:2px solid var(--color-primary);outline-offset:3px}table{width:100%;border-collapse:collapse;white-space:nowrap;text-align:left;font-size:13px}caption{text-align:left;color:var(--color-muted-text);padding-bottom:12px}th,td{padding:12px;border-bottom:1px solid var(--color-border);font-variant-numeric:tabular-nums}thead th{color:var(--color-primary)}.footnote{font-size:12px}.timeline{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px}.timeline strong{color:var(--color-primary);font-size:19px}.timeline p{font-size:13px}.roadmap,.stage{display:grid;gap:12px}.phase-nav{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px}.phase-nav button{padding:10px 14px;border:1px solid var(--color-border);border-radius:8px;background:var(--color-surface);color:var(--color-foreground);font:inherit;cursor:pointer}.phase-nav button[aria-pressed=true]{color:var(--color-on-primary);background:var(--color-primary);border-color:var(--color-primary)}button:focus-visible,summary:focus-visible,a:focus-visible{outline:2px solid var(--color-primary);outline-offset:4px}.stage{margin-bottom:18px}.stage>header{border-left:3px solid var(--color-primary);padding-left:16px}.stage>header h3{margin-top:0}.slice{padding:0;scroll-margin-top:90px}.slice summary{padding:17px 20px;cursor:pointer;line-height:1.7}.slice summary>span:first-child{font-weight:700;margin-right:12px}.slice summary::marker{color:var(--color-primary)}.slice-body{padding:0 20px 18px;border-top:1px solid var(--color-border)}dl{display:grid;grid-template-columns:85px minmax(0,1fr);gap:12px;font-size:14px}dt{font-weight:700;padding-top:3px}dd{margin:0;overflow-wrap:anywhere}dd a{display:inline-block;margin-right:12px;color:var(--color-primary)}.metric-grid h3{color:var(--color-primary)}.safeguards ul{padding-left:22px;display:grid;gap:8px}
@media(max-width:1100px){.timeline{grid-template-columns:repeat(3,minmax(0,1fr))}}@media(max-width:700px){.overview{grid-template-columns:1fr}.audit-stats,.metric-grid,.timeline{grid-template-columns:1fr}.progress{max-width:260px}.panel{padding:16px}.slice{padding:0}.slice summary{padding:16px}.slice summary .tag{margin-top:6px}.slice-body{padding:0 16px 16px}dl{grid-template-columns:1fr;gap:5px}dd{margin-bottom:9px}}
</style>
