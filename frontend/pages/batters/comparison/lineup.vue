<template>
  <main class="lineup-page">
    <ComparisonPageHeader eyebrow="Batter comparison · Slice 8" title="Lineup Scenarios" description="Recent observed starter probabilities and empirical run-expectancy scenarios. Outputs are research estimates, never an official lineup." back-to="/batters/comparison" back-label="Batter comparison" />
    <section class="controls">
      <label>Year<select v-model.number="year"><option v-for="value in years" :key="value" :value="value">{{ value }}</option></select></label>
      <label>Team<select v-model="team"><option v-for="value in teams" :key="value" :value="value">{{ value }}</option></select></label>
      <label>Opposing starter hand<select v-model="opponentHand"><option value="All">Unknown / All</option><option value="L">LHP</option><option value="R">RHP</option></select></label>
      <button type="button" :disabled="pending" @click="load">{{ pending ? 'Simulating…' : 'Build scenarios' }}</button>
    </section>
    <ComparisonStatus :pending="pending" :error="errorMessage" />
    <template v-if="payload">
      <section class="mode-note"><strong>{{ payload.data_mode }}</strong><p>{{ payload.lineup_prediction.basis }}</p></section>
      <ResearchTable title="Recent starter & batting-order probabilities" :columns="['name','starts','start_probability','primary_position']" :rows="predictionRows" />
      <section class="scenario-grid">
        <article v-for="scenario in payload.scenarios" :key="scenarioLabel(scenario)">
          <header><span>{{ scenarioLabel(scenario) }}</span><strong>{{ scenarioRuns(scenario) }}</strong><small>projected R/G</small></header>
          <ol><li v-for="player in scenarioLineup(scenario)" :key="player.player_id"><b>{{ player.slot }}</b><span>{{ player.name }}</span><small>{{ player.position }}</small></li></ol>
          <p>{{ scenarioConstraint(scenario) }}</p>
        </article>
      </section>
      <ComparisonNotes :notes="payload.limitations" />
    </template>
  </main>
</template>

<script setup lang="ts">
import type { BatterTeamResearchResponse } from '~/types/api'
interface LineupPlayer { slot: number; player_id: number; name: string; position: string }
const api = useApi()
const years = [2026, 2025, 2024, 2023]
const year = ref(2026)
const team = ref('AZ')
const opponentHand = ref('All')
const payload = ref<BatterTeamResearchResponse | null>(null)
const pending = ref(false)
const errorMessage = ref('')
const { data: batterOptions } = await useAsyncData('batter-lineup-options', () => api.batters({ year: 2026 }), { default: () => [] })
const teams = computed(() => [...new Set(batterOptions.value.map(row => row.team).filter(value => value && value !== '-'))].sort())
const predictionRows = computed(() => payload.value?.lineup_prediction.players || [])
async function load() { pending.value = true; errorMessage.value = ''; try { payload.value = await api.batterTeamResearch({ year: year.value, team: team.value, opponentHand: opponentHand.value }) } catch (error) { errorMessage.value = error instanceof Error ? error.message : 'Lineup research failed.' } finally { pending.value = false } }
function scenarioLabel(row: Record<string, unknown>) { return String(row.label || 'Scenario') }
function scenarioRuns(row: Record<string, unknown>) { const value = Number(row.projected_runs_per_game); return Number.isFinite(value) ? value.toFixed(2) : '—' }
function scenarioLineup(row: Record<string, unknown>) { return (row.lineup || []) as LineupPlayer[] }
function scenarioConstraint(row: Record<string, unknown>) { return String(row.constraint_status || '') }
onMounted(() => { void load() })
</script>

<style scoped>
.lineup-page { max-width: 1220px; margin: 0 auto; padding: 104px 20px 56px; }
.controls, .mode-note { margin-top: 16px; border: 1px solid var(--color-border); border-radius: 0; background: var(--color-surface); }
.controls { display: grid; grid-template-columns: 120px 180px 220px auto; gap: 12px; align-items: end; padding: 16px; }
label { display: grid; gap: 6px; color: var(--color-muted-text); font-size: 11px; font-weight: 850; text-transform: uppercase; }
select, button { min-height: 42px; border: 1px solid var(--color-border-strong); border-radius: 0; padding: 0 11px; color: var(--color-text); background: var(--color-surface); }
button { color: var(--color-on-primary); background: var(--color-primary); font-weight: 850; cursor: pointer; }
.mode-note { padding: 13px 16px; } .mode-note strong { color: var(--color-primary); text-transform: uppercase; } .mode-note p { margin: 4px 0 0; color: var(--color-muted-text); }
.scenario-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; margin-top: 16px; }
.scenario-grid article { border: 1px solid var(--color-border); background: var(--color-surface); }
.scenario-grid header { display: grid; grid-template-columns: 1fr auto; gap: 3px 12px; padding: 14px; border-bottom: 1px solid var(--color-border); }
.scenario-grid header span { color: var(--color-primary); font-weight: 850; } .scenario-grid header strong { color: var(--color-foreground); font-size: 24px; } .scenario-grid header small { grid-column: 2; color: var(--color-muted-text); }
ol { margin: 0; padding: 0; list-style: none; } li { display: grid; grid-template-columns: 26px 1fr auto; gap: 9px; align-items: center; min-height: 42px; padding: 7px 12px; border-bottom: 1px solid var(--color-border); } li b { display: grid; place-items: center; width: 24px; height: 24px; color: var(--color-on-primary); background: var(--color-primary); } li span { color: var(--color-foreground); font-weight: 750; } li small { color: var(--color-muted-text); }
.scenario-grid article > p { margin: 0; padding: 12px; color: var(--color-muted-text); font-size: 11px; line-height: 1.5; }
@media (max-width: 900px) { .controls, .scenario-grid { grid-template-columns: 1fr 1fr; } }
@media (max-width: 620px) { .controls, .scenario-grid { grid-template-columns: 1fr; } }
</style>
