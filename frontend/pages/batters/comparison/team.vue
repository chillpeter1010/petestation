<template>
  <main class="research-page">
    <ComparisonPageHeader eyebrow="Batter comparison · Slice 7" title="Team Batting Research" description="Observed batting-order, platoon and defensive-position context. These are descriptive associations, not causal effects." back-to="/batters/comparison" back-label="Batter comparison" />
    <section class="controls">
      <label>Year<select v-model.number="year"><option v-for="value in years" :key="value" :value="value">{{ value }}</option></select></label>
      <label>Team<select v-model="team"><option v-for="value in teams" :key="value" :value="value">{{ value }}</option></select></label>
      <label>Opponent hand<select v-model="opponentHand"><option value="All">All</option><option value="L">L</option><option value="R">R</option></select></label>
      <button type="button" :disabled="pending" @click="load">{{ pending ? 'Loading…' : 'Apply' }}</button>
    </section>
    <ComparisonStatus :pending="pending" :error="errorMessage" />
    <template v-if="payload">
      <section class="coverage"><article v-for="(value, key) in payload.coverage" :key="key"><span>{{ label(key) }}</span><strong>{{ value }}</strong></article></section>
      <ResearchTable title="Observed platoon hitter results" :columns="['name','pa','avg','obp','slg','woba','k_pct','bb_pct','reliability']" :rows="payload.hitters" />
      <section class="positions"><header><span>Observed defense</span><h2>Position coverage</h2></header><div><article v-for="row in payload.position_coverage" :key="Number(row.player_id)"><strong>{{ row.name }}</strong><span>{{ row.primary_position }}</span><small>{{ row.fielding_games }} fielding-game records</small></article></div></section>
      <ComparisonNotes :notes="payload.limitations" />
    </template>
  </main>
</template>

<script setup lang="ts">
import type { BatterTeamResearchResponse } from '~/types/api'
const api = useApi()
const years = [2026, 2025, 2024, 2023]
const year = ref(2026)
const team = ref('AZ')
const opponentHand = ref('All')
const payload = ref<BatterTeamResearchResponse | null>(null)
const pending = ref(false)
const errorMessage = ref('')
const { data: batterOptions } = await useAsyncData('batter-team-research-options', () => api.batters({ year: 2026 }), { default: () => [] })
const teams = computed(() => [...new Set(batterOptions.value.map(row => row.team).filter(value => value && value !== '-'))].sort())
async function load() { pending.value = true; errorMessage.value = ''; try { payload.value = await api.batterTeamResearch({ year: year.value, team: team.value, opponentHand: opponentHand.value }) } catch (error) { errorMessage.value = error instanceof Error ? error.message : 'Team batting research failed.' } finally { pending.value = false } }
function label(value: string | number) { return String(value).replaceAll('_', ' ') }
onMounted(() => { void load() })
</script>

<style scoped>
.research-page { max-width: 1280px; margin: 0 auto; padding: 104px 20px 56px; }
.controls, .coverage, .positions { margin-top: 16px; border: 1px solid var(--color-border); border-radius: 0; background: var(--color-surface); }
.controls { display: grid; grid-template-columns: 120px 180px 180px auto; gap: 12px; align-items: end; padding: 16px; }
label { display: grid; gap: 6px; color: var(--color-muted-text); font-size: 11px; font-weight: 850; text-transform: uppercase; }
select, button { min-height: 42px; border: 1px solid var(--color-border-strong); border-radius: 0; padding: 0 11px; color: var(--color-text); background: var(--color-surface); }
button { color: var(--color-on-primary); background: var(--color-primary); font-weight: 850; cursor: pointer; }
.coverage { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); }
.coverage article { display: grid; gap: 4px; padding: 14px; border-right: 1px solid var(--color-border); border-bottom: 1px solid var(--color-border); }
.coverage span, .positions header span { color: var(--color-primary); font-size: 10px; font-weight: 850; text-transform: uppercase; }
.coverage strong { overflow-wrap: anywhere; color: var(--color-foreground); font-size: 14px; }
.positions header { padding: 14px 16px; border-bottom: 1px solid var(--color-border); }
.positions h2 { margin: 3px 0 0; color: var(--color-foreground); }
.positions > div { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); }
.positions article { display: grid; grid-template-columns: 1fr auto; gap: 4px 10px; padding: 11px 14px; border-right: 1px solid var(--color-border); border-bottom: 1px solid var(--color-border); }
.positions small { grid-column: 1 / -1; color: var(--color-muted-text); }
@media (max-width: 820px) { .controls, .coverage, .positions > div { grid-template-columns: 1fr 1fr; } }
@media (max-width: 560px) { .controls, .coverage, .positions > div { grid-template-columns: 1fr; } }
</style>
