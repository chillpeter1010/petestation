<template>
  <main
    class="team-dashboard-page"
    :style="teamTheme"
  >
    <div v-if="pending" class="team-dashboard team-dashboard--loading" aria-live="polite" aria-busy="true">
      <div class="team-skeleton team-skeleton--hero" />
      <div class="team-dashboard__primary-grid">
        <div class="team-skeleton" />
        <div class="team-skeleton" />
      </div>
      <div class="team-skeleton team-skeleton--wide" />
    </div>

    <section v-else-if="error || !dashboard" class="team-dashboard-error">
      <TriangleAlert :size="30" aria-hidden="true" />
      <h1>Team dashboard unavailable</h1>
      <p>{{ error?.message || 'No team data was returned.' }}</p>
      <NuxtLink to="/">Return home</NuxtLink>
    </section>

    <div v-else class="team-dashboard">
      <TeamDashboardHero :team="dashboard.team" />

      <TeamSeasonContext :record="dashboard.season_record" :next-game="dashboard.next_game" />

      <nav class="team-dashboard__quick-nav" aria-label="Team dashboard sections">
        <a href="#rotation"><RotateCw :size="15" /> Rotation</a>
        <a href="#impact"><Clapperboard :size="15" /> Pitch arsenal</a>
        <a href="#bullpen"><Gauge :size="15" /> Bullpen</a>
        <a href="#lineups"><ListOrdered :size="15" /> Lineups</a>
        <a href="#outings"><CalendarDays :size="15" /> Outings</a>
        <a href="#hitting"><ChartNoAxesCombined :size="15" /> Hitting intelligence</a>
        <a href="#leaders"><Trophy :size="15" /> Leaders</a>
        <a href="#transactions"><Activity :size="15" /> Transactions</a>
        <a href="#payroll"><Banknote :size="15" /> Payroll</a>
        <a href="#roster"><Users :size="15" /> Roster</a>
      </nav>

      <div id="rotation">
        <TeamStarterMatchup
          :games="dashboard.starter_games"
          :team-id="teamId"
          :year="year"
          @video-selection="starterVideoSelection = $event"
        />
      </div>

      <div id="impact">
        <TeamPitchArsenalVideos :selection="starterVideoSelection" :year="year" />
      </div>

      <div id="bullpen">
        <TeamBullpenPanel :rows="dashboard.bullpen" :team-id="teamId" :year="year" />
      </div>

      <div id="lineups">
        <TeamLineupScenarios :team-id="teamId" :year="year" />
      </div>

      <div id="outings">
        <TeamLatestOutings :rows="dashboard.latest_outings" :team-id="teamId" :year="year" />
      </div>

      <div id="hitting">
        <TeamHittingIntelligence
          :payload="hittingIntelligence || null"
          :pending="hittingPending"
          :error="Boolean(hittingError)"
          :team-id="teamId"
          :year="year"
        />
      </div>

      <div id="leaders">
        <TeamLeaderboardPanel
          :pitching="dashboard.pitching_leaders"
          :batting="dashboard.batting_leaders"
          :team-id="teamId"
          :year="year"
        />
        <TeamPitchFamilyMatrix
          v-if="hittingIntelligence"
          :families="hittingIntelligence.pitch_families"
          :lineup="hittingIntelligence.lineup"
          :team-id="teamId"
          :year="year"
        />
      </div>

      <div id="transactions">
        <TeamTransactionsPanel :team-id="teamId" :year="year" :roster="dashboard.roster" />
      </div>

      <div id="payroll">
        <TeamPayrollPanel :team-id="teamId" :year="year" :roster="dashboard.roster" />
      </div>

      <div id="roster">
        <TeamRosterPanel :rows="dashboard.roster" :team-id="teamId" :year="year" />
      </div>
    </div>
  </main>
</template>

<script setup lang="ts">
import { Activity, Banknote, CalendarDays, ChartNoAxesCombined, Clapperboard, Gauge, ListOrdered, RotateCw, TriangleAlert, Trophy, Users } from '@lucide/vue'

definePageMeta({ key: route => route.fullPath })

const route = useRoute()
const api = useApi()
const year = 2026
const teamId = computed(() => String(route.params.teamId || '').toUpperCase())
const starterVideoSelection = ref<{ teamId: string; pitcherId: number; pitcherName: string; gamePk: number } | null>(null)

const { data: dashboard, pending, error, refresh: refreshDashboard } = await useLazyAsyncData(
  () => `team-dashboard-${teamId.value}-${year}`,
  () => api.teamDashboard({ year, teamId: teamId.value }),
  { watch: [teamId] }
)

const { data: hittingIntelligence, pending: hittingPending, error: hittingError, refresh: refreshHitting } = await useLazyAsyncData(
  () => `team-hitting-intelligence-${teamId.value}-${year}`,
  () => api.teamHittingIntelligence({ year, teamId: teamId.value }),
  { watch: [teamId] }
)

useAutoRefresh(async () => {
  await Promise.all([refreshDashboard(), refreshHitting()])
})

const teamTheme = computed(() => ({
  '--team-primary': dashboard.value?.team.primary_color || '#ff9900',
  '--team-secondary': dashboard.value?.team.secondary_color || '#111827'
}))
</script>

<style scoped>
.team-dashboard-page {
  --team-accent: color-mix(in srgb, var(--team-primary) 82%, var(--color-text));
  --team-panel-bg: color-mix(in srgb, var(--color-surface) 96%, var(--team-primary) 4%);
  --team-panel-border: color-mix(in srgb, var(--color-border) 82%, var(--team-primary) 18%);
  min-height: 100vh;
  padding: 78px clamp(16px, 3vw, 40px) 64px;
  background:
    radial-gradient(circle at 8% 8%, color-mix(in srgb, var(--team-primary) 13%, transparent), transparent 30rem),
    radial-gradient(circle at 92% 40%, color-mix(in srgb, var(--team-secondary) 9%, transparent), transparent 34rem),
    var(--color-background);
}

.team-dashboard {
  width: 100%;
  max-width: none;
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 18px;
  margin: 0 auto;
}

.team-dashboard__quick-nav {
  position: sticky;
  z-index: 10;
  top: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
  overflow-x: auto;
  border: 1px solid var(--team-panel-border);
  border-radius: 13px;
  padding: 7px;
  background: color-mix(in srgb, var(--color-surface) 90%, transparent);
  box-shadow: var(--shadow-sm);
  backdrop-filter: blur(14px);
}

.team-dashboard__quick-nav a {
  min-height: 38px;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  border-radius: 9px;
  padding: 7px 12px;
  color: var(--color-muted-text);
  font-size: 12px;
  font-weight: 800;
  text-decoration: none;
  white-space: nowrap;
}

.team-dashboard__quick-nav a:hover,
.team-dashboard__quick-nav a:focus-visible {
  color: #ffffff;
  background: var(--team-primary);
  outline: none;
}

.team-dashboard__primary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.team-dashboard__primary-grid > div,
#rotation,
#hitting,
#bullpen,
#lineups,
#outings,
#impact,
#leaders,
#roster,
#transactions,
#payroll {
  scroll-margin-top: 76px;
}

#hitting {
  min-width: 0;
}

#leaders {
  display: grid;
  gap: 18px;
}

.team-dashboard-error {
  max-width: 620px;
  margin: 12vh auto;
  border: 1px solid var(--color-border);
  border-radius: 16px;
  padding: 32px;
  color: var(--color-text);
  background: var(--color-surface);
  text-align: center;
}

.team-dashboard-error svg {
  color: var(--color-destructive);
}

.team-dashboard-error h1 {
  margin: 12px 0 6px;
}

.team-dashboard-error p {
  color: var(--color-muted-text);
}

.team-dashboard-error a {
  min-height: 42px;
  display: inline-flex;
  align-items: center;
  margin-top: 10px;
  border-radius: 9px;
  padding: 8px 14px;
  color: #ffffff;
  background: var(--team-primary);
  font-weight: 800;
  text-decoration: none;
}

.team-dashboard--loading {
  overflow: hidden;
}

.team-skeleton {
  min-height: 430px;
  border-radius: 16px;
  background: linear-gradient(90deg, var(--color-muted), color-mix(in srgb, var(--color-muted) 60%, white), var(--color-muted));
  background-size: 220% 100%;
  animation: team-skeleton-pulse 1.4s ease infinite;
}

.team-skeleton--hero {
  min-height: 320px;
  border-radius: 20px;
}

.team-skeleton--wide {
  min-height: 300px;
}

@keyframes team-skeleton-pulse {
  from { background-position: 100% 0; }
  to { background-position: -100% 0; }
}

@media (prefers-reduced-motion: reduce) {
  .team-skeleton {
    animation: none;
  }
}

@media (max-width: 980px) {
  .team-dashboard__primary-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .team-dashboard-page {
    padding-top: 24px;
  }

  .team-dashboard__quick-nav {
    top: 6px;
  }
}
</style>
