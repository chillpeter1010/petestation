<template>
  <section class="station-hero">
    <div class="station-hero__copy">
      <span class="eyebrow"><ChartNoAxesCombined :size="16" aria-hidden="true" /> Batter command center</span>
      <h1>See the hitter<br><em>behind the line.</em></h1>
      <p>League-wide production, expected results, and contact quality in one current-season workspace.</p>
      <div class="station-hero__status">
        <span><Database :size="15" aria-hidden="true" /> 2026 pitch data</span>
        <strong>{{ hitters.toLocaleString() }} hitters tracked</strong>
      </div>
    </div>

    <div class="leaders" aria-label="Current batting leaders">
      <NuxtLink
        v-for="leader in leaders"
        :key="leader.label"
        class="leader-card"
        :to="leader.to"
      >
        <span>{{ leader.label }}</span>
        <div>
          <MlbPlayerHeadshot
            :player-id="leader.playerId"
            :name="leader.name"
            :size="58"
            :source-width="160"
            decorative
            shape="circle"
          />
          <p><strong>{{ leader.name }}</strong><small>{{ leader.team }}</small></p>
          <b>{{ leader.value }}</b>
        </div>
      </NuxtLink>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ChartNoAxesCombined, Database } from '@lucide/vue'

defineProps<{
  hitters: number
  leaders: Array<{
    label: string
    name: string
    team: string
    value: string
    playerId: number
    to: Record<string, unknown>
  }>
}>()
</script>

<style scoped>
.station-hero {
  position: relative;
  overflow: hidden;
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(420px, 0.85fr);
  gap: 32px;
  min-height: 370px;
  border: 1px solid color-mix(in srgb, var(--color-primary) 28%, var(--color-border));
  border-radius: 24px;
  padding: clamp(28px, 5vw, 64px);
  background:
    radial-gradient(circle at 12% 12%, rgba(255, 153, 0, 0.2), transparent 28rem),
    linear-gradient(128deg, #090a0d 5%, #101722 58%, #21170c 125%);
  box-shadow: 0 28px 70px rgba(0, 0, 0, 0.28);
}

.station-hero::after {
  position: absolute;
  right: -90px;
  bottom: -170px;
  width: 430px;
  height: 430px;
  border: 72px solid rgba(255, 153, 0, 0.045);
  border-radius: 50%;
  content: '';
  pointer-events: none;
}

.station-hero__copy,
.leaders { position: relative; z-index: 1; }

.eyebrow,
.station-hero__status span {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: #ffad33;
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.09em;
  text-transform: uppercase;
}

h1 {
  margin: 18px 0 16px;
  color: #f8fafc;
  font-size: clamp(44px, 6vw, 78px);
  line-height: 0.94;
  letter-spacing: -0.055em;
}

h1 em { color: #ff9900; font-style: normal; }

.station-hero__copy > p {
  max-width: 640px;
  margin: 0;
  color: #aebbd0;
  font-size: clamp(16px, 1.5vw, 19px);
  line-height: 1.6;
}

.station-hero__status {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 22px;
  margin-top: 32px;
}

.station-hero__status strong { color: #e5edf8; font-size: 13px; }

.leaders { display: grid; align-content: center; gap: 10px; }

.leader-card {
  display: grid;
  gap: 10px;
  min-height: 92px;
  border: 1px solid rgba(255, 255, 255, 0.11);
  border-radius: 15px;
  padding: 14px 16px;
  color: #f8fafc;
  background: rgba(15, 21, 31, 0.8);
  text-decoration: none;
  transition: border-color 180ms ease, background 180ms ease;
}

.leader-card:hover,
.leader-card:focus-visible {
  border-color: rgba(255, 153, 0, 0.6);
  background: rgba(26, 31, 41, 0.95);
  outline: none;
}

.leader-card > span { color: #8fa0b8; font-size: 10px; font-weight: 900; letter-spacing: 0.1em; text-transform: uppercase; }
.leader-card > div { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 12px; }
.leader-card p { display: grid; gap: 3px; min-width: 0; margin: 0; }
.leader-card p strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.leader-card p small { color: #91a1b7; }
.leader-card b { color: #ffad33; font: 700 22px "Fira Code", monospace; }

@media (max-width: 980px) {
  .station-hero { grid-template-columns: 1fr; }
  .leaders { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .leader-card > div { grid-template-columns: auto 1fr; }
  .leader-card b { grid-column: 1 / -1; }
}

@media (max-width: 680px) {
  .station-hero { min-height: auto; border-radius: 16px; padding: 26px 20px; }
  .leaders { grid-template-columns: 1fr; }
  .leader-card > div { grid-template-columns: auto minmax(0, 1fr) auto; }
  .leader-card b { grid-column: auto; }
}

@media (prefers-reduced-motion: reduce) {
  .leader-card { transition: none; }
}
</style>
