<template>
  <main class="team-picker-page">
    <h1>Choose a team</h1>
    <p>Choose a team to view its page. This does not change your home team.</p>
    <nav aria-label="MLB teams">
      <NuxtLink v-for="team in MLB_TEAMS" :key="team.id" :to="`/teams/${team.code}`">
        <strong>{{ team.code }}</strong><span>{{ team.name }}</span>
      </NuxtLink>
    </nav>
  </main>
</template>

<script setup lang="ts">
import { MLB_TEAMS, normalizeMlbTeamCode } from '~/config/mlbTeams'

const favoriteTeam = normalizeMlbTeamCode(useAuth().user.value?.favorite_team_code)
if (favoriteTeam) await navigateTo(`/teams/${favoriteTeam}`, { replace: true })

useHead({ title: 'Choose a team · Petehub' })
</script>

<style scoped>
.team-picker-page { min-height: 100dvh; max-width: 1100px; margin: auto; padding: 88px 24px 48px; }
.team-picker-page h1 { margin: 0 0 10px; }
.team-picker-page p { color: var(--color-muted-text); }
.team-picker-page nav { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 10px; margin-top: 28px; }
.team-picker-page nav a { display: flex; flex-direction: column; gap: 4px; border: 1px solid var(--color-border); border-radius: 10px; padding: 14px; color: var(--color-text); background: var(--color-surface); text-decoration: none; }
.team-picker-page nav a:hover, .team-picker-page nav a:focus-visible { border-color: var(--color-primary); outline: 2px solid var(--color-primary); }
.team-picker-page nav span { color: var(--color-muted-text); font-size: 13px; }
</style>
