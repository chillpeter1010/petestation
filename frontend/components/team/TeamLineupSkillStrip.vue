<template>
  <section class="intel-card lineup-strip">
    <header><div><span class="eyebrow">LINEUP SKILL STRIP</span><h3>PA-based nine</h3></div><span class="basis">不是官方或預測先發打序</span></header>
    <p class="deck">依本季 PA 排出九名打者，快速比較棒速、揮棒接觸、準時率與 platoon 接觸優勢。</p>
    <div class="players">
      <NuxtLink v-for="(row, index) in rows" :key="row.batter_id" :to="playerLink(row)" class="player-card">
        <span class="order">{{ index + 1 }}</span><MlbPlayerHeadshot :player-id="row.batter_id" :name="row.name" :size="44" shape="circle" decorative />
        <strong>{{ row.name }}</strong><small>{{ row.hand }} · {{ row.plate_appearances ?? '—' }} PA</small>
        <dl><div><dt>Bat</dt><dd>{{ number(row.avg_bat_speed, 1) }}</dd></div><div><dt>Contact</dt><dd>{{ percent(row.contact_pct) }}</dd></div><div><dt>On Time</dt><dd>{{ percent(row.on_time_pct) }}</dd></div><div><dt>Platoon</dt><dd>{{ signed(row.platoon_edge) }}</dd></div></dl>
      </NuxtLink>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { TeamHitterIntelligenceRow } from '~/types/api'
const props = defineProps<{ rows: TeamHitterIntelligenceRow[]; teamId: string; year: number }>()
const playerLink = (row: TeamHitterIntelligenceRow) => ({ path: '/batter-personal', query: { year: props.year, team: props.teamId, batter_id: row.batter_id } })
const number = (value: number | null, digits = 1) => value == null ? '—' : value.toFixed(digits)
const percent = (value: number | null) => value == null ? '—' : `${value.toFixed(1)}%`
const signed = (value: number | null) => value == null ? '—' : `${value >= 0 ? '+' : ''}${value.toFixed(1)}`
</script>

<style scoped>
.intel-card { min-width: 0; border: 1px solid var(--team-panel-border); border-radius: 16px; padding: 22px; background: var(--team-panel-bg); } header { display:flex;justify-content:space-between;gap:16px;align-items:flex-start } h3{margin:5px 0 0;color:var(--color-text);font-size:clamp(21px,2vw,30px)}.eyebrow{color:var(--team-accent);font-size:11px;font-weight:900;letter-spacing:.12em}.basis{border:1px solid var(--team-panel-border);border-radius:999px;padding:6px 9px;color:var(--color-muted-text);font-size:10px;font-weight:750}.deck{margin:8px 0 18px;color:var(--color-muted-text);font-size:13px;line-height:1.6}.players{display:grid;grid-template-columns:repeat(9,minmax(126px,1fr));gap:8px;overflow-x:auto;padding-bottom:4px}.player-card{position:relative;min-height:190px;display:flex;flex-direction:column;align-items:center;border:1px solid var(--team-panel-border);border-radius:12px;padding:13px 8px 10px;color:var(--color-text);background:color-mix(in srgb,var(--color-background) 76%,transparent);text-align:center;text-decoration:none;transition:transform .16s ease,border-color .16s ease}.player-card:hover,.player-card:focus-visible{border-color:var(--team-primary);outline:none;transform:translateY(-3px)}.order{position:absolute;top:8px;left:9px;color:var(--team-accent);font-size:10px;font-weight:900}.player-card strong{width:100%;overflow:hidden;margin-top:7px;font-size:11px;text-overflow:ellipsis;white-space:nowrap}.player-card>small{margin-top:2px;color:var(--color-muted-text);font-size:9px}.player-card dl{width:100%;display:grid;grid-template-columns:1fr 1fr;gap:5px;margin:10px 0 0}.player-card dl div{border-radius:7px;padding:5px 3px;background:color-mix(in srgb,var(--color-muted) 55%,transparent)}dt{color:var(--color-muted-text);font-size:8px;font-weight:750}dd{margin:2px 0 0;font-size:10px;font-weight:850}.players::-webkit-scrollbar{height:7px}.players::-webkit-scrollbar-thumb{border-radius:99px;background:var(--team-primary)}
</style>
