<template>
  <section class="lineup-panel" aria-labelledby="lineup-scenarios-title">
    <header class="panel-header">
      <div>
        <span>PRECOMPUTED LINEUP SCENARIOS</span>
        <h3 id="lineup-scenarios-title">How might this lineup be arranged?</h3>
        <p>以近期先發、最新實際打序與經驗 run expectancy，顯示三種預先計算的候選打線。</p>
      </div>
      <div class="hand-toggle" aria-label="Opposing starter hand">
        <button type="button" :class="{ active: opponentHand === 'R' }" @click="opponentHand = 'R'">vs RHP</button>
        <button type="button" :class="{ active: opponentHand === 'L' }" @click="opponentHand = 'L'">vs LHP</button>
      </div>
    </header>

    <div v-if="pending" class="state" aria-live="polite">Loading precomputed lineup scenarios…</div>
    <div v-else-if="errorMessage" class="state state--error">{{ errorMessage }}</div>
    <div v-else-if="!payload || payload.cache_status === 'unavailable'" class="state">
      打線情境快取尚未建立；下一次資料更新完成後會自動出現。
    </div>
    <template v-else>
      <div class="cache-row">
        <span :class="['cache-badge', `cache-badge--${payload.cache_status}`]">
          {{ payload.cache_status === 'current' ? 'Current' : 'Updating · showing previous result' }}
        </span>
        <span>Data through {{ dateLabel(payload.meta.data_updated_at) }}</span>
        <span>Calculated {{ dateTimeLabel(payload.generated_at) }}</span>
      </div>

      <div class="scenario-grid">
        <article v-for="scenario in payload.scenarios" :key="scenario.label">
          <header>
            <span>{{ scenario.label }}</span>
            <strong>{{ runsLabel(scenario.projected_runs_per_game) }}</strong>
            <small>projected R/G</small>
          </header>
          <ol>
            <li v-for="player in scenario.lineup" :key="`${scenario.label}-${player.slot}-${player.player_id}`">
              <b>{{ player.slot }}</b>
              <span>{{ player.name }}</span>
              <small>{{ player.position }}</small>
            </li>
          </ol>
          <p>{{ scenario.constraint_status }}</p>
        </article>
      </div>
      <p v-if="payload.meta.warnings.length" class="warning">{{ payload.meta.warnings.join(' ') }}</p>
    </template>
  </section>
</template>

<script setup lang="ts">
const props = defineProps<{ teamId: string; year: number }>()
const api = useApi()
const opponentHand = ref<'L' | 'R'>('R')
const { data: payload, pending, error } = await useAsyncData(
  `batter-lineup-scenarios-${props.year}-${props.teamId}`,
  () => api.batterLineupScenarios({
      year: props.year,
      team: props.teamId,
      opponentHand: opponentHand.value
  }),
  { watch: [() => props.teamId, () => props.year, opponentHand] }
)
const errorMessage = computed(() => error.value?.message || '')

function runsLabel(value: number | null) {
  return value == null || !Number.isFinite(value) ? '—' : value.toFixed(2)
}

function dateLabel(value: string | null) {
  if (!value) return '—'
  return new Intl.DateTimeFormat('en-CA', { year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(value))
}

function dateTimeLabel(value: string | null) {
  if (!value) return '—'
  return new Intl.DateTimeFormat('zh-TW', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
}

</script>

<style scoped>
.lineup-panel{border:1px solid var(--team-panel-border);border-radius:0;background:var(--team-panel-bg);overflow:hidden}.panel-header{display:flex;align-items:flex-start;justify-content:space-between;gap:24px;padding:22px;border-bottom:1px solid var(--team-panel-border)}.panel-header span{color:var(--team-accent);font-size:11px;font-weight:900;letter-spacing:.12em}.panel-header h3{margin:7px 0 5px;color:var(--color-text);font-size:clamp(22px,2.2vw,31px);line-height:1.15}.panel-header p{margin:0;color:var(--color-muted-text);font-size:13px}.hand-toggle{display:flex;flex:0 0 auto;border:1px solid var(--team-panel-border)}.hand-toggle button{min-height:38px;border:0;border-left:1px solid var(--team-panel-border);border-radius:0;padding:0 13px;color:var(--color-muted-text);background:transparent;font-size:12px;font-weight:850;cursor:pointer}.hand-toggle button:first-child{border-left:0}.hand-toggle button.active{color:#fff;background:var(--team-primary)}.state{padding:34px 22px;color:var(--color-muted-text);text-align:center}.state--error,.warning{color:var(--color-destructive)}.cache-row{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center;padding:10px 16px;border-bottom:1px solid var(--team-panel-border);color:var(--color-muted-text);font-size:11px}.cache-badge{padding:4px 7px;border:1px solid var(--team-panel-border);font-weight:850;text-transform:uppercase}.cache-badge--current{color:var(--color-success)}.cache-badge--stale{color:var(--team-accent)}.scenario-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr))}.scenario-grid article{border-left:1px solid var(--team-panel-border)}.scenario-grid article:first-child{border-left:0}.scenario-grid article>header{display:grid;grid-template-columns:1fr auto;gap:3px 12px;min-height:76px;padding:13px 14px;border-bottom:1px solid var(--team-panel-border)}.scenario-grid article>header span{color:var(--team-accent);font-size:13px;font-weight:900}.scenario-grid article>header strong{color:var(--color-text);font-size:25px}.scenario-grid article>header small{grid-column:2;color:var(--color-muted-text)}ol{margin:0;padding:0;list-style:none}li{display:grid;grid-template-columns:28px minmax(0,1fr) auto;gap:9px;align-items:center;min-height:45px;padding:6px 12px;border-bottom:1px solid var(--team-panel-border)}li b{display:grid;place-items:center;width:26px;height:26px;color:#fff;background:var(--team-primary)}li span{overflow:hidden;color:var(--color-text);font-size:13px;font-weight:800;text-overflow:ellipsis;white-space:nowrap}li small{color:var(--color-muted-text)}.scenario-grid article>p{min-height:60px;margin:0;padding:11px 12px;color:var(--color-muted-text);font-size:10px;line-height:1.45}.warning{margin:0;padding:10px 16px;border-top:1px solid var(--team-panel-border);font-size:11px}@media(max-width:980px){.scenario-grid{grid-template-columns:1fr}.scenario-grid article{border-top:1px solid var(--team-panel-border);border-left:0}.scenario-grid article:first-child{border-top:0}}@media(max-width:680px){.panel-header{flex-direction:column}.hand-toggle{width:100%}.hand-toggle button{flex:1}}
</style>
