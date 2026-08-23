<template>
  <section class="intel-card timing-map">
    <header>
      <div><span class="eyebrow">TEAM TIMING MAP</span><h3>Who gets the barrel there on time?</h3></div>
      <NuxtLink :to="labLink">Open Batter Lab <ArrowUpRight :size="15" /></NuxtLink>
    </header>
    <p class="deck">橫軸是 On Time%，縱軸是 Perfect Contact%；虛線為聯盟平均，頭像外圈越實代表揮棒樣本越多。</p>
    <div class="plot" role="img" :aria-label="`${teamId} hitter timing and perfect contact scatter plot`">
      <span class="quadrant top-left">準時較少 · 完美接觸較多</span>
      <span class="quadrant top-right">準時且精準</span>
      <span class="quadrant bottom-left">兩者都低</span>
      <span class="quadrant bottom-right">準時較多 · 接觸未完全對齊</span>
      <span class="league-line league-line--x" :style="{ left: `${xPosition(league.on_time_pct)}%` }" />
      <span class="league-line league-line--y" :style="{ bottom: `${yPosition(league.perfect_pct)}%` }" />
      <NuxtLink
        v-for="row in points"
        :key="row.batter_id"
        class="player-point"
        :class="{ developing: row.sample_status !== 'Stable' }"
        :style="pointStyle(row)"
        :to="playerLink(row)"
        :title="`${row.name}: On Time ${formatPct(row.on_time_pct)}, Perfect ${formatPct(row.perfect_pct)}, ${row.swings} swings`"
      >
        <MlbPlayerHeadshot :player-id="row.batter_id" :name="row.name" :size="38" :source-width="160" decorative shape="circle" />
      </NuxtLink>
      <span class="axis axis--x">On Time% →</span><span class="axis axis--y">Perfect Contact% →</span>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ArrowUpRight } from '@lucide/vue'
import type { TeamHitterIntelligenceRow, TeamHittingProfile } from '~/types/api'

const props = defineProps<{ rows: TeamHitterIntelligenceRow[]; league: TeamHittingProfile; teamId: string; year: number }>()
const points = computed(() => props.rows.filter(row => row.on_time_pct != null && row.perfect_pct != null).slice(0, 18))
const xValues = computed(() => [...points.value.map(row => Number(row.on_time_pct)), Number(props.league.on_time_pct ?? 65)])
const yValues = computed(() => [...points.value.map(row => Number(row.perfect_pct)), Number(props.league.perfect_pct ?? 25)])
const extent = (values: number[], padding: number) => ({ min: Math.min(...values) - padding, max: Math.max(...values) + padding })
const xExtent = computed(() => extent(xValues.value, 2.5))
const yExtent = computed(() => extent(yValues.value, 2.5))
const scale = (value: number | null, range: { min: number; max: number }) => value == null ? 50 : Math.max(4, Math.min(96, ((value - range.min) / Math.max(1, range.max - range.min)) * 100))
const xPosition = (value: number | null) => scale(value, xExtent.value)
const yPosition = (value: number | null) => scale(value, yExtent.value)
const pointStyle = (row: TeamHitterIntelligenceRow) => ({ left: `${xPosition(row.on_time_pct)}%`, bottom: `${yPosition(row.perfect_pct)}%`, '--sample-opacity': String(Math.max(.55, Math.min(1, row.swings / 350))) })
const playerLink = (row: TeamHitterIntelligenceRow) => ({ path: '/batter-personal', query: { year: props.year, team: props.teamId, batter_id: row.batter_id } })
const labLink = computed(() => ({ path: '/batters/lab/swing-timing', query: { year: props.year, batter_team: props.teamId } }))
const formatPct = (value: number | null) => value == null ? '—' : `${value.toFixed(1)}%`
</script>

<style scoped>
.intel-card { min-width: 0; border: 1px solid var(--team-panel-border); border-radius: 16px; padding: 22px; background: var(--team-panel-bg); }
header { display: flex; justify-content: space-between; gap: 18px; align-items: flex-start; }
h3 { margin: 5px 0 0; color: var(--color-text); font-size: clamp(21px, 2vw, 30px); }
.eyebrow { color: var(--team-accent); font-size: 11px; font-weight: 900; letter-spacing: .12em; }
header a { display: inline-flex; align-items: center; gap: 5px; color: var(--team-accent); font-size: 12px; font-weight: 850; text-decoration: none; white-space: nowrap; }
.deck { margin: 8px 0 18px; color: var(--color-muted-text); font-size: 13px; line-height: 1.6; }
.plot { position: relative; min-height: 420px; overflow: hidden; border: 1px solid color-mix(in srgb, var(--team-panel-border) 80%, white 20%); border-radius: 14px; background: linear-gradient(90deg, transparent 49.8%, color-mix(in srgb, var(--color-border) 48%, transparent) 50%, transparent 50.2%), linear-gradient(0deg, transparent 49.8%, color-mix(in srgb, var(--color-border) 48%, transparent) 50%, transparent 50.2%), color-mix(in srgb, var(--color-background) 72%, transparent); }
.quadrant { position: absolute; z-index: 1; color: color-mix(in srgb, var(--color-muted-text) 84%, transparent); font-size: 10px; font-weight: 750; }
.top-left { top: 12px; left: 14px; }.top-right { top: 12px; right: 14px; }.bottom-left { bottom: 31px; left: 14px; }.bottom-right { right: 14px; bottom: 31px; }
.league-line { position: absolute; z-index: 1; pointer-events: none; opacity: .68; }
.league-line--x { top: 0; bottom: 0; border-left: 1px dashed var(--team-accent); }
.league-line--y { right: 0; left: 0; border-top: 1px dashed var(--team-accent); }
.player-point { position: absolute; z-index: 2; display: block; border: 3px solid color-mix(in srgb, var(--team-primary) calc(var(--sample-opacity) * 100%), #73819a); border-radius: 50%; transform: translate(-50%, 50%); transition: transform .18s ease, z-index .18s ease; box-shadow: 0 3px 12px rgb(0 0 0 / 28%); }
.player-point:hover,.player-point:focus-visible { z-index: 5; outline: 2px solid #fff; outline-offset: 2px; transform: translate(-50%, 50%) scale(1.22); }
.player-point.developing { border-style: dashed; }
.axis { position: absolute; z-index: 1; color: var(--color-muted-text); font-size: 11px; font-weight: 800; }
.axis--x { bottom: 9px; left: 50%; transform: translateX(-50%); }.axis--y { top: 50%; left: 7px; writing-mode: vertical-rl; transform: translateY(-50%) rotate(180deg); }
@media (max-width: 680px) { header { flex-direction: column; }.plot { min-height: 360px; }.quadrant { display: none; } }
</style>
