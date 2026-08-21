<template>
  <header class="player-hero">
    <div class="player-hero__identity">
      <MlbPlayerHeadshot
        v-if="playerId"
        :player-id="playerId"
        :name="name"
        :size="138"
        :source-width="320"
        priority
        shape="circle"
      />
      <div>
        <span class="eyebrow"><Activity :size="16" aria-hidden="true" /> Batter analysis</span>
        <h1>{{ name || 'Select a hitter' }}</h1>
        <p>Season production, contact quality, and swing decisions.</p>
        <dl>
          <div><dt>Season</dt><dd>{{ year }}</dd></div>
          <div><dt>Team</dt><dd>{{ team || '-' }}</dd></div>
          <div><dt>Data through</dt><dd>{{ dataThrough }}</dd></div>
        </dl>
      </div>
    </div>
    <div class="player-hero__actions">
      <span class="status" :class="{ ready: !loading }">{{ loading ? 'Loading data' : 'Live season view' }}</span>
      <NuxtLink to="/batters"><ArrowLeft :size="15" aria-hidden="true" /> Batter Station</NuxtLink>
    </div>
  </header>
</template>

<script setup lang="ts">
import { Activity, ArrowLeft } from '@lucide/vue'

defineProps<{
  playerId: number | null
  name: string
  team: string
  year: number
  dataThrough: string
  loading: boolean
}>()
</script>

<style scoped>
.player-hero {
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 28px;
  min-height: 250px;
  border: 1px solid color-mix(in srgb, var(--color-primary) 30%, var(--color-border));
  border-radius: 22px;
  padding: clamp(24px, 4vw, 46px);
  color: #f8fafc;
  background:
    radial-gradient(circle at 86% 30%, rgba(255, 153, 0, .17), transparent 22rem),
    linear-gradient(125deg, #090b0f, #101827 62%, #24180b);
  box-shadow: 0 24px 60px rgba(0, 0, 0, .25);
}
.player-hero::after { position: absolute; right: -120px; bottom: -250px; width: 500px; height: 500px; border: 78px solid rgba(255, 153, 0, .04); border-radius: 50%; content: ''; }
.player-hero__identity, .player-hero__actions { position: relative; z-index: 1; }
.player-hero__identity { display: flex; align-items: center; gap: 28px; min-width: 0; }
.eyebrow { display: inline-flex; align-items: center; gap: 7px; color: #ffad33; font-size: 11px; font-weight: 900; letter-spacing: .1em; text-transform: uppercase; }
h1 { margin: 8px 0 5px; font-size: clamp(38px, 5.5vw, 68px); line-height: 1; letter-spacing: -.045em; }
.player-hero__identity p { margin: 0; color: #a7b6cb; }
dl { display: flex; flex-wrap: wrap; gap: 9px; margin: 22px 0 0; }
dl div { min-width: 105px; border: 1px solid rgba(255,255,255,.1); border-radius: 9px; padding: 9px 12px; background: rgba(7,10,15,.36); }
dt { color: #8495ad; font-size: 9px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }
dd { margin: 4px 0 0; color: #f4f7fb; font: 700 12px "Fira Code", monospace; }
.player-hero__actions { align-self: stretch; display: flex; flex-direction: column; align-items: flex-end; justify-content: space-between; }
.status, .player-hero__actions a { display: inline-flex; align-items: center; min-height: 38px; border: 1px solid rgba(255,255,255,.13); border-radius: 999px; padding: 8px 13px; color: #b8c5d8; background: rgba(8,12,18,.55); font-size: 11px; font-weight: 800; }
.status.ready::before { width: 7px; height: 7px; margin-right: 7px; border-radius: 50%; background: #4ade80; content: ''; }
.player-hero__actions a { gap: 7px; color: #f3f5f8; text-decoration: none; }
.player-hero__actions a:hover { border-color: #ff9900; }
@media (max-width: 760px) { .player-hero { align-items: flex-start; border-radius: 16px; } .player-hero__identity { align-items: flex-start; } .player-hero__identity :deep(.mlb-headshot) { width: 90px !important; height: 90px !important; } .player-hero__actions { align-self: auto; } .status { display: none; } }
@media (max-width: 560px) { .player-hero { display: grid; } .player-hero__identity { display: grid; } .player-hero__actions { align-items: flex-start; } }
</style>
