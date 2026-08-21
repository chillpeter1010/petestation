<template>
  <main class="site-home">
    <header class="site-home__top">
      <NuxtLink class="site-home__brand" to="/" aria-label="Petehub home">
        <span>Pete</span><strong>hub</strong>
      </NuxtLink>
      <div class="site-home__actions">
        <nav class="site-home__nav" aria-label="Site sections">
          <HomeTeamMenu />
          <NuxtLink to="/pitchers">Pitchers</NuxtLink>
          <NuxtLink to="/batters">Batters</NuxtLink>
          <NuxtLink to="/fielders">Fielders</NuxtLink>
        </nav>
        <HomePlayerSearch v-model="videoQuery" @entity-change="detectedEntity = $event" />
      </div>
    </header>

    <section class="site-home__hero">
      <div class="site-home__hero-copy">
        <h1>Take me out to <span>the ball game</span></h1>
        <p>Every pitch, player, and game in one analysis workspace.</p>
      </div>
    </section>

    <NuxtLink
      v-if="detectedEntity && videoQuery.trim().length >= 2"
      class="site-home__search-destination"
      :to="detectedEntity.to"
    >
      <span>{{ detectedEntity.kind === 'team' ? 'Team match' : 'Player match' }}</span>
      <strong>{{ detectedEntity.label }}</strong>
      <small>{{ detectedEntity.meta }}</small>
      <em>Open {{ detectedEntity.kind === 'team' ? 'team page' : 'player page' }} ↗</em>
    </NuxtLink>

    <HomeRecommendedVideos
      :videos="displayedVideos?.videos || []"
      :latest-data-date="displayedVideos?.latest_data_date || recommendations?.latest_data_date || null"
      :loading="recommendationsLoading || searchLoading"
      :search-query="activeSearchQuery"
      @refresh="refreshVideos"
    />

    <footer class="site-home__footer">
      <NuxtLink class="site-home__maintenance-entry" to="/admin/updates">Per aspera ad astra</NuxtLink>
      <span>Petehub · Baseball Analysis Platform</span>
    </footer>
  </main>
</template>

<script setup lang="ts">
import type { RouteLocationRaw } from 'vue-router'
import type { HomeRecommendationsResponse } from '~/types/api'

interface SearchDestination {
  id: string
  label: string
  meta: string
  kind: 'team' | 'player'
  to: RouteLocationRaw
}

const api = useApi()
const recommendations = ref<HomeRecommendationsResponse | null>(null)
const recommendationsLoading = ref(false)
const searchResults = ref<HomeRecommendationsResponse | null>(null)
const searchLoading = ref(false)
const videoQuery = ref('')
const activeSearchQuery = ref('')
const detectedEntity = ref<SearchDestination | null>(null)
let searchTimer: ReturnType<typeof setTimeout> | null = null
let searchRequest = 0

const displayedVideos = computed(() => activeSearchQuery.value ? searchResults.value : recommendations.value)

onMounted(loadRecommendations)

watch(videoQuery, (value) => {
  if (searchTimer) clearTimeout(searchTimer)
  const query = value.trim()
  if (query.length < 2) {
    activeSearchQuery.value = ''
    searchResults.value = null
    searchLoading.value = false
    searchRequest += 1
    return
  }
  searchTimer = setTimeout(() => { void searchVideos(query) }, 350)
})

onBeforeUnmount(() => {
  if (searchTimer) clearTimeout(searchTimer)
})

async function loadRecommendations() {
  recommendationsLoading.value = true
  try {
    recommendations.value = await api.homeRecommendations(2026)
  } catch (error) {
    console.warn('Unable to load homepage recommendations', error)
  } finally {
    recommendationsLoading.value = false
  }
}

async function searchVideos(query: string) {
  const request = ++searchRequest
  searchLoading.value = true
  try {
    const result = await api.homeVideoSearch({ year: 2026, query })
    if (request !== searchRequest) return
    activeSearchQuery.value = query
    searchResults.value = result
  } catch (error) {
    console.warn('Unable to search homepage videos', error)
  } finally {
    if (request === searchRequest) searchLoading.value = false
  }
}

function refreshVideos() {
  const query = videoQuery.value.trim()
  if (query.length >= 2) void searchVideos(query)
  else void loadRecommendations()
}
</script>

<style>
.site-home {
  --home-orange: #ff9900;
  --home-orange-soft: rgba(255, 153, 0, 0.18);
  --home-line: rgba(255, 153, 0, 0.3);
  --home-text: #f7f7f7;
  --home-muted: #b7b7b7;
  min-height: 100vh;
  padding: 26px clamp(18px, 4vw, 58px) 32px;
  color: var(--home-text);
  background:
    radial-gradient(circle at 78% 8%, rgba(255, 153, 0, 0.24), transparent 28rem),
    radial-gradient(circle at 12% 76%, rgba(255, 153, 0, 0.1), transparent 24rem),
    linear-gradient(135deg, #070707 0%, #141414 52%, #060606 100%);
}

.site-home__top,
.site-home__hero,
.site-home__footer {
  max-width: 1380px;
  margin-inline: auto;
}

.site-home__top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 14px;
}

.site-home__actions {
  width: min(100%, 620px);
  display: grid;
  justify-items: end;
  gap: 16px;
}

.site-home__actions > .home-player-search { width: min(100%, 560px); }

.site-home__brand {
  display: inline-flex;
  align-items: center;
  color: var(--home-text);
  font-size: clamp(34px, 5vw, 62px);
  font-weight: 950;
  letter-spacing: -1.4px;
  text-decoration: none;
}

.site-home__brand strong {
  margin-left: 5px;
  border-radius: 7px;
  padding: 1px 9px 5px;
  color: #111;
  background: var(--home-orange);
}

.site-home__nav {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
}

.site-home__nav > a {
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 999px;
  padding: 9px 15px;
  color: var(--home-muted);
  background: rgba(255, 255, 255, 0.045);
  font-weight: 900;
  text-decoration: none;
}

.site-home__nav > a:hover,
.site-home__nav > a.router-link-active {
  color: #111;
  border-color: var(--home-orange);
  background: var(--home-orange);
}

.site-home__hero {
  min-height: clamp(190px, 26vh, 290px);
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: clamp(28px, 6vw, 90px);
  margin-bottom: 18px;
  border: 1px solid rgba(255, 153, 0, 0.22);
  border-radius: 10px;
  padding: clamp(24px, 4vw, 48px);
  background:
    linear-gradient(90deg, rgba(0, 0, 0, 0.86), rgba(0, 0, 0, 0.44) 56%, rgba(255, 153, 0, 0.11)),
    radial-gradient(circle at 82% 32%, rgba(255, 153, 0, 0.16), transparent 28rem),
    rgba(18, 18, 18, 0.84);
  box-shadow: 0 28px 90px rgba(0, 0, 0, 0.44);
}

.site-home__hero-copy { max-width: 920px; }

.site-home__hero h1 {
  max-width: 830px;
  margin: 0;
  color: var(--home-text);
  font-family: Baskerville, "Iowan Old Style", "Palatino Linotype", Georgia, serif;
  font-size: clamp(36px, 4.8vw, 64px);
  font-weight: 600;
  line-height: .91;
  letter-spacing: -.052em;
  text-wrap: balance;
}

.site-home__hero h1 span {
  color: var(--home-orange);
  font: inherit;
  text-shadow: 0 10px 34px rgba(255, 153, 0, .18);
}

.site-home__hero-copy p {
  max-width: 620px;
  margin: 18px 0 0;
  color: var(--home-muted);
  font-size: clamp(15px, 1.6vw, 20px);
  line-height: 1.45;
}

.site-home__search-destination {
  max-width: 1380px;
  min-height: 58px;
  display: flex;
  align-items: center;
  gap: 13px;
  margin: 0 auto 12px;
  border: 1px solid rgba(255, 153, 0, .34);
  border-radius: 10px;
  padding: 10px 15px;
  color: var(--home-text);
  background: linear-gradient(90deg, rgba(255,153,0,.13), rgba(16,16,16,.9) 48%);
  text-decoration: none;
  transition: border-color .15s ease, transform .15s ease;
}

.site-home__search-destination:hover { border-color: var(--home-orange); transform: translateY(-1px); }
.site-home__search-destination > span { color: var(--home-orange); font-size: 10px; font-weight: 950; letter-spacing: .08em; text-transform: uppercase; }
.site-home__search-destination strong { font-size: 17px; }
.site-home__search-destination small { color: var(--home-muted); }
.site-home__search-destination em { margin-left: auto; color: var(--home-orange); font-size: 11px; font-style: normal; font-weight: 900; text-transform: uppercase; }

.site-home__footer {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 18px;
  margin-top: 36px;
  border-top: 1px solid var(--home-line);
  padding: 24px 4px 0;
}

.site-home__maintenance-entry {
  margin: 0;
  color: var(--home-text);
  font-family: "Brush Script MT", "Segoe Script", "Lucida Handwriting", cursive;
  font-size: clamp(26px, 3vw, 42px);
  text-decoration: none;
  transition: color .16s ease, opacity .16s ease;
}

.site-home__maintenance-entry:hover,
.site-home__maintenance-entry:focus-visible { color: var(--home-orange); }

.site-home__footer span { color: var(--home-muted); font-size: 11px; font-weight: 800; text-transform: uppercase; }

@media (max-width: 980px) {
  .site-home__hero { align-items: stretch; flex-direction: column; }
}

@media (max-width: 720px) {
  .site-home__top { align-items: flex-start; flex-direction: column; }
  .site-home__actions { width: 100%; justify-items: start; }
  .site-home__nav { justify-content: flex-start; }
  .site-home__search-destination { align-items: flex-start; flex-direction: column; gap: 4px; }
  .site-home__search-destination em { margin-left: 0; }
  .site-home__footer { align-items: start; flex-direction: column; }
}
</style>
