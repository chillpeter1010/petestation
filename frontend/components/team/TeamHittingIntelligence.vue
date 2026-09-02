<template>
  <section class="hitting-intelligence" aria-labelledby="team-hitting-title">
    <header class="section-hero">
      <div><span>V3 · TEAM HITTING INTELLIGENCE</span><h2 id="team-hitting-title">How does this lineup create contact?</h2><p>把球隊打擊拆成時間點、三維對齊、球種壓力與九人能力輪廓。</p></div>
      <NuxtLink :to="labLink">Explore all hitters <ArrowUpRight :size="16" /></NuxtLink>
    </header>
    <div v-if="pending" class="state-card" aria-live="polite">Loading team hitting intelligence…</div>
    <div v-else-if="error || !payload" class="state-card state-card--error">Team hitting intelligence is temporarily unavailable.</div>
    <template v-else>
      <TeamLineupSkillStrip :rows="payload.lineup" :team-id="teamId" :year="year" />
      <div class="two-column"><TeamTimingMap :rows="payload.hitters" :league="payload.league_profile" :team-id="teamId" :year="year" /><TeamMissProfile :team="payload.team_profile" :league="payload.league_profile" /></div>
      <TeamPitchFamilyMatrix :families="payload.pitch_families" :lineup="payload.lineup" :team-id="teamId" :year="year" />
      <p class="method-note">Tracking begins at the 2023 All-Star break. Contact% = 100 − Whiff%. Platoon edge compares swing-contact rate in the hitter’s favorable pitcher-hand matchup with the opposite split; switch hitters show the absolute LHP/RHP gap.</p>
    </template>
  </section>
</template>

<script setup lang="ts">
import { ArrowUpRight } from '@lucide/vue'
import type { TeamHittingIntelligenceResponse } from '~/types/api'
const props = defineProps<{ payload: TeamHittingIntelligenceResponse | null; pending: boolean; error: boolean; teamId: string; year: number }>()
const labLink = computed(() => ({ path: '/batters/lab/swing-timing', query: { year: props.year, batter_team: props.teamId } }))
</script>

<style scoped>
.hitting-intelligence{display:grid;gap:18px}.section-hero{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;border:1px solid var(--team-panel-border);border-radius:16px;padding:24px;background:linear-gradient(125deg,color-mix(in srgb,var(--team-primary) 14%,var(--team-panel-bg)),var(--team-panel-bg) 60%)}.section-hero span{color:var(--team-accent);font-size:11px;font-weight:900;letter-spacing:.12em}.section-hero h2{margin:7px 0 5px;color:var(--color-text);font-size:clamp(28px,3vw,42px);font-weight:750;line-height:1.1;letter-spacing:-.01em}.section-hero p{margin:0;color:var(--color-muted-text);font-size:14px}.section-hero a{min-height:40px;display:inline-flex;align-items:center;gap:6px;border-radius:9px;padding:8px 13px;color:#fff;background:var(--team-primary);font-size:12px;font-weight:850;text-decoration:none;white-space:nowrap}.two-column{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(360px,.85fr);gap:18px}.state-card{border:1px solid var(--team-panel-border);border-radius:15px;padding:38px;color:var(--color-muted-text);background:var(--team-panel-bg);text-align:center}.state-card--error{color:var(--color-destructive)}.method-note{margin:0;border-left:3px solid var(--team-primary);padding:6px 12px;color:var(--color-muted-text);font-size:11px;line-height:1.55}@media(max-width:1050px){.two-column{grid-template-columns:1fr}}@media(max-width:680px){.section-hero{align-items:flex-start;flex-direction:column}}
</style>
