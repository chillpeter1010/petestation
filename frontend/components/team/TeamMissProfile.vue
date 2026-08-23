<template>
  <section class="intel-card miss-profile">
    <header><div><span class="eyebrow">TEAM MISS PROFILE</span><h3>How does this lineup miss?</h3></div><span class="sample">{{ team.swings.toLocaleString() }} swings</span></header>
    <p class="deck">三個方向分開看；彩色區塊為球隊，細線標記聯盟比例。中間區代表 Centered／On Time／Lined Up。</p>
    <div class="dimensions">
      <div v-for="dimension in dimensions" :key="dimension.label" class="dimension">
        <div class="dimension-title"><strong>{{ dimension.label }}</strong><span>{{ dimension.caption }}</span></div>
        <div class="segments">
          <span v-for="segment in dimension.segments" :key="segment.label" :class="segment.tone" :style="{ width: `${segment.team}%` }"><b>{{ segment.label }}</b><small>{{ formatPct(segment.team) }}</small></span>
          <i v-for="(segment, index) in dimension.segments.slice(0, 2)" :key="`${dimension.label}-${index}`" class="league-marker" :style="{ left: `${markerPosition(dimension.segments, index)}%` }" />
        </div>
        <div class="league-copy">MLB {{ dimension.segments.map(segment => `${segment.label} ${formatPct(segment.league)}`).join(' · ') }}</div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { TeamHittingProfile } from '~/types/api'
const props = defineProps<{ team: TeamHittingProfile; league: TeamHittingProfile }>()
type Segment = { label: string; team: number; league: number; tone: string }
const value = (number: number | null) => Math.max(0, Number(number ?? 0))
const dimensions = computed(() => [
  { label: 'Horizontal', caption: '橫向包住或伸手去搆', segments: [segment('Tied Up', props.team.tied_up_pct, props.league.tied_up_pct, 'bad'), segment('Centered', props.team.centered_pct, props.league.centered_pct, 'good'), segment('Flail', props.team.flail_pct, props.league.flail_pct, 'bad')] },
  { label: 'Timing', caption: '時間點早或晚', segments: [segment('Late', props.team.late_pct, props.league.late_pct, 'bad'), segment('On Time', props.team.on_time_pct, props.league.on_time_pct, 'good'), segment('Early', props.team.early_pct, props.league.early_pct, 'bad')] },
  { label: 'Vertical', caption: '球棒位於球的上方或下方', segments: [segment('Over', props.team.over_pct, props.league.over_pct, 'bad'), segment('Lined Up', props.team.lined_up_pct, props.league.lined_up_pct, 'good'), segment('Under', props.team.under_pct, props.league.under_pct, 'bad')] }
])
function segment(label: string, teamValue: number | null, leagueValue: number | null, tone: string): Segment { return { label, team: value(teamValue), league: value(leagueValue), tone } }
function markerPosition(segments: Segment[], index: number) { return segments.slice(0, index + 1).reduce((sum, item) => sum + item.league, 0) }
const formatPct = (number: number) => `${number.toFixed(1)}%`
</script>

<style scoped>
.intel-card { min-width: 0; border: 1px solid var(--team-panel-border); border-radius: 16px; padding: 22px; background: var(--team-panel-bg); }
header { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; } h3 { margin: 5px 0 0; color: var(--color-text); font-size: clamp(21px,2vw,30px); }.eyebrow { color: var(--team-accent); font-size: 11px; font-weight: 900; letter-spacing: .12em; }.sample { border: 1px solid var(--team-panel-border); border-radius: 999px; padding: 6px 9px; color: var(--color-muted-text); font-size: 10px; font-weight: 800; white-space: nowrap; }.deck { margin: 8px 0 18px; color: var(--color-muted-text); font-size: 13px; line-height: 1.6; }.dimensions { display: grid; gap: 18px; }.dimension-title { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 7px; color: var(--color-text); }.dimension-title span,.league-copy { color: var(--color-muted-text); font-size: 10px; }.segments { position: relative; display: flex; min-height: 62px; overflow: hidden; border-radius: 10px; background: var(--color-muted); }.segments > span { min-width: 0; display: grid; place-content: center; padding: 5px; text-align: center; }.segments b { font-size: 10px; }.segments small { margin-top: 3px; font-size: 11px; }.segments .good { color: #fff; background: color-mix(in srgb, var(--team-primary) 74%, #1b5e50); }.segments .bad { color: var(--color-text); background: color-mix(in srgb, var(--color-muted) 72%, #7183aa); }.league-marker { position: absolute; top: 0; bottom: 0; z-index: 2; border-left: 2px solid #fff; filter: drop-shadow(0 0 2px #000); }.league-copy { margin-top: 6px; line-height: 1.45; }
</style>
