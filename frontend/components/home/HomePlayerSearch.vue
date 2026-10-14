<template>
  <div ref="searchRoot" class="home-player-search" :class="{ 'home-player-search--petehub': isPetehub }" @focusout="handleFocusOut">
    <label for="home-player-search">Search {{ brandName }}</label>
    <div class="home-player-search__control">
      <Search :size="21" aria-hidden="true" />
      <input
        id="home-player-search"
        v-model.trim="query"
        type="search"
        placeholder="Try a player, team, grand slam, or pitch type"
        autocomplete="off"
        role="combobox"
        aria-autocomplete="list"
        aria-controls="home-player-results"
        :aria-expanded="showPanel"
        @focus="openSearch"
        @keydown.down.prevent="moveSelection(1)"
        @keydown.up.prevent="moveSelection(-1)"
        @keydown.enter.prevent="openSelected"
        @keydown.esc="isOpen = false"
      >
      <LoaderCircle v-if="isLoading" :size="18" class="is-spinning" aria-label="Loading player directory" />
      <button v-else-if="query" type="button" aria-label="Clear search" @click="query = ''"><X :size="18" /></button>
    </div>

    <div v-if="showPanel" id="home-player-results" class="home-player-search__results" role="listbox">
      <p v-if="!entityResults.length" class="home-player-search__message">Video results will appear below.</p>
      <NuxtLink
        v-for="(entity, index) in entityResults"
        v-else
        :key="`${entity.kind}-${entity.id}`"
        :to="entity.to"
        role="option"
        :aria-selected="index === selectedIndex"
        :class="{ 'is-selected': index === selectedIndex }"
        @mouseenter="selectedIndex = index"
        @click="isOpen = false"
      >
        <span>
          <strong>{{ entity.label }}</strong>
          <small>{{ entity.meta }}</small>
        </span>
        <em>{{ entity.kind === 'team' ? 'Team page' : 'Player page' }} <ArrowUpRight :size="14" /></em>
      </NuxtLink>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ArrowUpRight, LoaderCircle, Search, X } from '@lucide/vue'

const { brandName, isPetehub } = useSiteBrand()
import type { RouteLocationRaw } from 'vue-router'
import type { BatterOption, PitcherOption } from '~/types/api'

interface SearchEntity {
  id: string
  label: string
  meta: string
  kind: 'team' | 'player'
  searchable: string
  to: RouteLocationRaw
}

const props = defineProps<{ modelValue: string }>()
const emit = defineEmits<{
  'update:modelValue': [value: string]
  'entity-change': [entity: SearchEntity | null]
}>()

const api = useApi()
const router = useRouter()
const searchRoot = ref<HTMLElement | null>(null)
const isOpen = ref(false)
const isLoading = ref(false)
const isLoaded = ref(false)
const selectedIndex = ref(-1)
const players = ref<SearchEntity[]>([])
const year = 2026

const query = computed({
  get: () => props.modelValue,
  set: value => emit('update:modelValue', value)
})

const teams: SearchEntity[] = [
  ['ATH', 'Athletics'], ['AZ', 'Arizona Diamondbacks D-backs'], ['ATL', 'Atlanta Braves'],
  ['BAL', 'Baltimore Orioles'], ['BOS', 'Boston Red Sox'], ['CHC', 'Chicago Cubs'],
  ['CIN', 'Cincinnati Reds'], ['CLE', 'Cleveland Guardians'], ['COL', 'Colorado Rockies'],
  ['CWS', 'Chicago White Sox'], ['DET', 'Detroit Tigers'], ['HOU', 'Houston Astros'],
  ['KC', 'Kansas City Royals'], ['LAA', 'Los Angeles Angels'], ['LAD', 'Los Angeles Dodgers'],
  ['MIA', 'Miami Marlins'], ['MIL', 'Milwaukee Brewers'], ['MIN', 'Minnesota Twins'],
  ['NYM', 'New York Mets'], ['NYY', 'New York Yankees'], ['PHI', 'Philadelphia Phillies'],
  ['PIT', 'Pittsburgh Pirates'], ['SD', 'San Diego Padres'], ['SEA', 'Seattle Mariners'],
  ['SF', 'San Francisco Giants'], ['STL', 'St. Louis Cardinals'], ['TB', 'Tampa Bay Rays'],
  ['TEX', 'Texas Rangers'], ['TOR', 'Toronto Blue Jays'], ['WSH', 'Washington Nationals']
].map(([id, label]) => ({
  id,
  label: label.split(' D-backs')[0],
  meta: id,
  kind: 'team',
  searchable: `${id} ${label}`.toLocaleLowerCase(),
  to: { path: `/teams/${id}`, query: { year } }
}))

const normalizedQuery = computed(() => query.value.trim().toLocaleLowerCase())
const entityResults = computed(() => {
  if (normalizedQuery.value.length < 2) return []
  const terms = normalizedQuery.value.split(/\s+/).filter(Boolean)
  return [...teams, ...players.value]
    .filter(entity => terms.every(term => entity.searchable.includes(term)))
    .sort((left, right) => matchScore(left) - matchScore(right))
    .slice(0, 6)
})
const showPanel = computed(() => isOpen.value && normalizedQuery.value.length >= 2)

watch(entityResults, (results) => {
  selectedIndex.value = results.length ? 0 : -1
  emit('entity-change', results[0] || null)
}, { immediate: true })

async function openSearch() {
  isOpen.value = true
  if (isLoaded.value || isLoading.value) return
  isLoading.value = true
  try {
    const [startersResult, relieversResult, battersResult] = await Promise.allSettled([
      api.pitchers({ year, role: 'SP' }),
      api.pitchers({ year, role: 'RP' }),
      api.batters({ year })
    ])
    const starters = startersResult.status === 'fulfilled' ? startersResult.value : []
    const relievers = relieversResult.status === 'fulfilled' ? relieversResult.value : []
    const batters = battersResult.status === 'fulfilled' ? battersResult.value : []
    players.value = [
      ...starters.map(toPitcherResult),
      ...relievers.map(toPitcherResult),
      ...batters.map(toBatterResult)
    ]
    isLoaded.value = true
  } finally {
    isLoading.value = false
  }
}

function toPitcherResult(player: PitcherOption): SearchEntity {
  return {
    id: `pitcher-${player.value}-${player.role}`,
    label: player.name,
    meta: `${player.team} · ${player.role}`,
    kind: 'player',
    searchable: `${player.name} ${player.team} pitcher ${player.role}`.toLocaleLowerCase(),
    to: { path: '/pitcher-personal', query: { year, role: player.role, team: player.team, pitcher_id: player.value } }
  }
}

function toBatterResult(player: BatterOption): SearchEntity {
  return {
    id: `batter-${player.value}`,
    label: player.name,
    meta: `${player.team} · Batter`,
    kind: 'player',
    searchable: `${player.name} ${player.team} batter`.toLocaleLowerCase(),
    to: { path: '/batter-personal', query: { year, team: player.team, batter_id: player.value } }
  }
}

function matchScore(entity: SearchEntity) {
  const label = entity.label.toLocaleLowerCase()
  if (label === normalizedQuery.value || entity.meta.toLocaleLowerCase() === normalizedQuery.value) return 0
  if (label.startsWith(normalizedQuery.value)) return 1
  return entity.kind === 'team' ? 2 : 3
}

function moveSelection(direction: number) {
  if (!entityResults.value.length) return
  selectedIndex.value = (selectedIndex.value + direction + entityResults.value.length) % entityResults.value.length
}

function openSelected() {
  const entity = entityResults.value[selectedIndex.value]
  if (entity) {
    isOpen.value = false
    router.push(entity.to)
  }
}

function handleFocusOut(event: FocusEvent) {
  if (!searchRoot.value?.contains(event.relatedTarget as Node | null)) isOpen.value = false
}
</script>

<style scoped>
.home-player-search { position: relative; width: min(100%, 560px); }
.home-player-search label { display: block; margin-bottom: 8px; color: #9b9fa6; font-size: 10px; font-weight: 900; letter-spacing: .16em; text-transform: uppercase; }
.home-player-search__control { min-height: 52px; display: flex; align-items: center; gap: 10px; border: 1px solid #30343a; border-radius: 10px; padding: 0 15px; color: var(--home-orange); background: #0d0f12; box-shadow: inset 0 1px 1px rgba(255,255,255,.025), inset 0 -1px 2px rgba(0,0,0,.24); transition: border-color .15s ease, box-shadow .15s ease; }
.home-player-search__control:focus-within { border-color: rgba(200,138,47,.72); box-shadow: inset 0 1px 1px rgba(255,255,255,.025), 0 0 0 2px rgba(200,138,47,.075); }
.home-player-search--petehub label { margin-bottom: 7px; color: var(--home-orange); font-size: 11px; letter-spacing: .07em; }
.home-player-search--petehub .home-player-search__control { min-height: 54px; border: 2px solid rgba(255, 153, 0, .68); border-radius: 8px; color: var(--home-orange); background: rgba(4, 4, 4, .78); box-shadow: 0 14px 40px rgba(0, 0, 0, .28); }
.home-player-search--petehub .home-player-search__control:focus-within { border-color: var(--home-orange); box-shadow: 0 0 0 4px rgba(255, 153, 0, .14), 0 14px 40px rgba(0, 0, 0, .36); }
.home-player-search input { min-width: 0; flex: 1; border: 0; outline: 0; color: var(--home-text); background: transparent; font-size: 15px; }
.home-player-search input::placeholder { color: #858585; }
.home-player-search__control button { width: 32px; height: 32px; display: grid; place-items: center; border: 0; border-radius: 50%; color: var(--home-muted); background: transparent; cursor: pointer; }
.home-player-search__control button:hover { color: #111; background: var(--home-orange); }
.home-player-search__results { position: absolute; z-index: 30; top: calc(100% + 8px); right: 0; left: 0; overflow: hidden; border: 1px solid rgba(255, 153, 0, .4); border-radius: 9px; background: rgba(12, 12, 12, .99); box-shadow: 0 24px 70px rgba(0, 0, 0, .65); }
.home-player-search__message { margin: 0; padding: 15px; color: var(--home-muted); font-size: 13px; }
.home-player-search__results a { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 11px 14px; color: var(--home-text); text-decoration: none; }
.home-player-search__results a + a { border-top: 1px solid rgba(255,255,255,.08); }
.home-player-search__results a:hover, .home-player-search__results a:focus-visible, .home-player-search__results a.is-selected { color: #111; background: var(--home-orange); outline: none; }
.home-player-search__results a > span { min-width: 0; display: flex; align-items: baseline; gap: 8px; }
.home-player-search__results strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.home-player-search__results small { color: #999; font-size: 11px; white-space: nowrap; }
.home-player-search__results em { display: flex; align-items: center; gap: 4px; color: #999; font-size: 10px; font-style: normal; font-weight: 800; white-space: nowrap; text-transform: uppercase; }
.home-player-search__results a:hover small, .home-player-search__results a:hover em, .home-player-search__results a.is-selected small, .home-player-search__results a.is-selected em { color: rgba(17,17,17,.7); }
.is-spinning { animation: spin .8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
