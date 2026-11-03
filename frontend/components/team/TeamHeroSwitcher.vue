<template>
  <PopoverRoot v-model:open="isOpen">
    <PopoverTrigger class="team-switcher__trigger" aria-label="Switch MLB team">
      <LayoutGrid :size="15" />
      Teams
      <ChevronDown :size="14" />
    </PopoverTrigger>
    <PopoverPortal>
      <PopoverContent
        class="team-switcher__panel"
        :style="{ '--switch-team-primary': primaryColor }"
        :side-offset="9"
        align="start"
      >
        <header>
          <div><strong>Switch team</strong><span>2026 command centers</span></div>
          <NuxtLink :to="favoriteTeam ? `/teams/${favoriteTeam}` : '/teams'" @click="isOpen = false">My team</NuxtLink>
        </header>
        <div class="team-switcher__grid">
          <NuxtLink
            v-for="team in teams"
            :key="team.code"
            :to="`/teams/${team.code}`"
            :aria-current="team.code === currentTeam ? 'page' : undefined"
            @click="isOpen = false"
          >
            <strong>{{ team.code }}</strong>
            <span>{{ team.name }}</span>
          </NuxtLink>
        </div>
        <PopoverArrow class="team-switcher__arrow" />
      </PopoverContent>
    </PopoverPortal>
  </PopoverRoot>
</template>

<script setup lang="ts">
import { ChevronDown, LayoutGrid } from '@lucide/vue'
import { PopoverArrow, PopoverContent, PopoverPortal, PopoverRoot, PopoverTrigger } from 'reka-ui'
import { MLB_TEAMS, normalizeMlbTeamCode } from '~/config/mlbTeams'

defineProps<{ currentTeam: string; primaryColor: string }>()
const isOpen = ref(false)
const auth = useAuth()
const favoriteTeam = computed(() => normalizeMlbTeamCode(auth.user.value?.favorite_team_code))
const teams = MLB_TEAMS
</script>

<style scoped>
.team-switcher__trigger { min-height: 38px; display: inline-flex; align-items: center; gap: 7px; border: 1px solid rgba(255,255,255,.18); border-radius: 999px; padding: 7px 13px; color: #e2e8f0; background: rgba(5,8,13,.34); font-size: 12px; font-weight: 900; cursor: pointer; backdrop-filter: blur(10px); }
.team-switcher__trigger:hover, .team-switcher__trigger:focus-visible, .team-switcher__trigger[data-state="open"] { border-color: var(--team-primary); color: #fff; background: color-mix(in srgb, var(--team-primary) 78%, #090b10); outline: none; }
:global(.team-switcher__panel) { z-index: 80; width: min(720px, calc(100vw - 28px)); border: 1px solid color-mix(in srgb, var(--switch-team-primary) 44%, #3b4250); border-radius: 14px; padding: 12px; color: #f8fafc; background: rgba(10,13,19,.98); box-shadow: 0 22px 75px rgba(0,0,0,.58); backdrop-filter: blur(18px); }
:global(.team-switcher__panel > header) { display: flex; align-items: center; justify-content: space-between; gap: 14px; padding: 3px 4px 11px; }
:global(.team-switcher__panel > header div) { display: grid; gap: 2px; }
:global(.team-switcher__panel > header strong) { font-size: 13px; }
:global(.team-switcher__panel > header span) { color: #929baa; font-size: 10px; }
:global(.team-switcher__panel > header a) { color: #cbd5e1; font-size: 11px; font-weight: 800; text-decoration: none; }
:global(.team-switcher__grid) { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 5px; }
:global(.team-switcher__grid a) { min-width: 0; display: grid; gap: 2px; border: 1px solid transparent; border-radius: 8px; padding: 8px 9px; color: #f8fafc; text-decoration: none; }
:global(.team-switcher__grid a:hover), :global(.team-switcher__grid a:focus-visible), :global(.team-switcher__grid a[aria-current="page"]) { border-color: color-mix(in srgb, var(--switch-team-primary) 70%, #fff); background: color-mix(in srgb, var(--switch-team-primary) 72%, #0a0d13); outline: none; }
:global(.team-switcher__grid strong) { font-size: 12px; }
:global(.team-switcher__grid span) { overflow: hidden; color: #929baa; font-size: 9px; text-overflow: ellipsis; white-space: nowrap; }
:global(.team-switcher__grid a:hover span), :global(.team-switcher__grid a:focus-visible span), :global(.team-switcher__grid a[aria-current="page"] span) { color: #e2e8f0; }
:global(.team-switcher__arrow) { fill: color-mix(in srgb, var(--switch-team-primary) 44%, #3b4250); }
@media (max-width: 680px) { :global(.team-switcher__panel) { max-height: min(640px, calc(100vh - 28px)); overflow-y: auto; } :global(.team-switcher__grid) { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
