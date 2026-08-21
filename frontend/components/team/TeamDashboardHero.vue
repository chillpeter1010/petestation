<template>
  <header class="team-hero" :class="{ 'team-hero--az': team.team_id === 'AZ' }">
    <img
      v-if="team.logo_url && !logoFailed"
      class="team-hero__watermark"
      :src="team.logo_url"
      alt=""
      aria-hidden="true"
    >
    <div class="team-hero__identity">
      <div class="team-hero__back"><TeamHeroSwitcher :current-team="team.team_id" :primary-color="team.primary_color" /></div>
      <div class="team-hero__title-row">
        <span class="team-hero__monogram">
          <img
            v-if="team.logo_url && !logoFailed"
            :src="team.logo_url"
            :alt="`${team.name} logo`"
            fetchpriority="high"
            @error="logoFailed = true"
          >
          <span v-else aria-hidden="true">{{ team.team_id }}</span>
        </span>
        <div>
          <span class="team-hero__eyebrow">{{ team.year }} Team Command Center</span>
          <h1>{{ team.name }}</h1>
          <p>
            <Database :size="15" aria-hidden="true" />
            Data through {{ formatDate(team.data_as_of) }}
          </p>
        </div>
      </div>
    </div>

  </header>
</template>

<script setup lang="ts">
import { Database } from '@lucide/vue'
import type { TeamIdentity } from '~/types/api'

defineProps<{
  team: TeamIdentity
}>()

const logoFailed = ref(false)

function formatDate(value: string | null) {
  if (!value) {
    return 'not available'
  }
  return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric' }).format(new Date(`${value}T00:00:00`))
}
</script>

<style scoped>
.team-hero {
  position: relative;
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--team-primary) 56%, var(--color-border));
  border-radius: 20px;
  padding: clamp(24px, 4vw, 44px);
  background:
    radial-gradient(circle at 10% 12%, color-mix(in srgb, var(--team-primary) 24%, transparent), transparent 36%),
    radial-gradient(circle at 88% 4%, color-mix(in srgb, var(--team-secondary) 12%, transparent), transparent 40%),
    linear-gradient(125deg, #11151d, #07090d 68%);
  box-shadow: 0 28px 80px rgba(3, 7, 18, 0.28);
  color: #f8fafc;
}

.team-hero__watermark {
  position: absolute;
  right: clamp(22px, 8vw, 120px);
  bottom: -68px;
  width: clamp(210px, 24vw, 360px);
  height: clamp(210px, 24vw, 360px);
  object-fit: contain;
  z-index: 1;
  opacity: 0.18;
  filter: brightness(0) invert(1);
  pointer-events: none;
}

.team-hero--az .team-hero__watermark {
  right: clamp(30px, 6vw, 88px);
  bottom: 50%;
  width: clamp(220px, 20vw, 300px);
  height: clamp(220px, 20vw, 300px);
  transform: translateY(50%);
  opacity: 0.28;
  filter:
    saturate(0.9)
    brightness(1.15)
    drop-shadow(0 12px 28px rgba(0, 0, 0, 0.42));
}

.team-hero__identity {
  position: relative;
  z-index: 2;
}

.team-hero__back {
  width: fit-content;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 28px;
}

.team-hero__title-row {
  display: flex;
  align-items: center;
  gap: 22px;
}

.team-hero__monogram {
  width: 90px;
  height: 90px;
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 22px;
  color: #ffffff;
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.12), rgba(255, 255, 255, 0.025)),
    #0c1118;
  box-shadow:
    inset 0 0 0 1px rgba(255, 255, 255, 0.04),
    0 16px 40px color-mix(in srgb, var(--team-primary) 20%, transparent);
  font-family: "Fira Code", monospace;
  font-size: 28px;
  font-weight: 900;
}

.team-hero__monogram img {
  width: 68px;
  height: 68px;
  object-fit: contain;
  filter:
    drop-shadow(0 2px 5px rgba(0, 0, 0, 0.56))
    drop-shadow(0 0 2px rgba(255, 255, 255, 0.2));
}

.team-hero__eyebrow {
  color: color-mix(in srgb, var(--team-primary) 55%, #ffffff);
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.team-hero h1 {
  margin: 6px 0;
  color: #ffffff;
  font-size: clamp(34px, 5vw, 62px);
  line-height: 1;
  letter-spacing: -0.045em;
}

.team-hero p {
  display: flex;
  align-items: center;
  gap: 7px;
  margin: 0;
  color: #b9c0cb;
  font-size: 13px;
}

@media (max-width: 900px) {
  .team-hero__watermark {
    right: -24px;
  }
}

@media (max-width: 560px) {
  .team-hero--az .team-hero__watermark {
    right: -22px;
    width: 210px;
    height: 210px;
    opacity: 0.13;
  }

  .team-hero__title-row {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
