<template>
  <main class="site-home" :class="isPetehub ? 'site-home--petehub' : 'site-home--peteclub'">
    <header class="site-home__top">
      <NuxtLink class="site-home__brand" :class="{ 'site-home__brand--petehub': isPetehub }" to="/" :aria-label="`${brandName} home`">
        <template v-if="isPetehub"><span>Pete</span><strong>hub</strong></template>
        <span v-else>Peteclub</span>
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
      <div class="site-home__footer-notes">
        <NuxtLink class="site-home__maintenance-entry" to="/admin/updates">Per aspera ad astra</NuxtLink>
        <StatcastFieldNote />
      </div>
      <span>{{ brandName }} · Baseball Analysis Platform</span>
    </footer>
  </main>
</template>

<script setup lang="ts">
import type { RouteLocationRaw } from 'vue-router'
import type { HomeRecommendationsResponse } from '~/types/api'
import StatcastFieldNote from '~/components/home/StatcastFieldNote.vue'

interface SearchDestination {
  id: string
  label: string
  meta: string
  kind: 'team' | 'player'
  to: RouteLocationRaw
}

const api = useApi()
const { isPetehub, brandName } = useSiteBrand()
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
  --home-orange: #c88a2f;
  --home-orange-soft: rgba(200, 138, 47, 0.12);
  --home-line: rgba(200, 138, 47, 0.18);
  --home-text: #f3f4f6;
  --home-muted: #a7abb2;
  min-height: 100vh;
  padding: 16px clamp(18px, 4vw, 58px) 32px;
  color: var(--home-text);
  background:
    radial-gradient(circle at 86% 82%, rgba(200, 138, 47, 0.065), transparent 22rem),
    linear-gradient(145deg, #0b0d10 0%, #111318 58%, #0b0d10 100%);
}

.site-home__top,
.site-home__hero,
.site-home__footer {
  max-width: 1380px;
  margin-inline: auto;
}

.site-home__footer-notes {
  display: flex;
  align-items: baseline;
  gap: clamp(18px, 3vw, 34px);
}

.site-home__top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 30px;
  margin-bottom: 12px;
  padding: 4px clamp(70px, 6vw, 110px) 16px 0;
}

.site-home__actions {
  width: min(100%, 620px);
  display: grid;
  justify-items: end;
  gap: 12px;
}

.site-home__actions > .home-player-search { width: min(100%, 560px); }

.site-home__brand {
  position: relative;
  display: inline-flex;
  align-items: center;
  padding-bottom: 10px;
  color: #e8ddce;
  background: linear-gradient(108deg, #f0e8dc 8%, #d8c5aa 56%, #b9823c 100%);
  background-clip: text;
  font-family: "Aptos Display", "Segoe UI Variable Display", "Segoe UI", sans-serif;
  font-size: clamp(36px, 4vw, 52px);
  font-weight: 680;
  letter-spacing: -0.035em;
  line-height: 1;
  text-decoration: none;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.site-home__brand::after {
  position: absolute;
  bottom: 0;
  left: 2px;
  width: 42px;
  height: 2px;
  border-radius: 2px;
  background: linear-gradient(90deg, #c88a2f, rgba(200, 138, 47, 0));
  content: "";
}

.site-home__brand--petehub {
  color: var(--home-text);
  background: none;
  letter-spacing: -1.4px;
  -webkit-text-fill-color: currentColor;
}

.site-home__brand--petehub::after {
  display: none;
}

.site-home__brand--petehub strong {
  margin-left: 5px;
  border-radius: 7px;
  padding: 1px 9px 5px;
  color: #111;
  background: var(--home-orange);
  -webkit-text-fill-color: #111;
}

.site-home__nav {
  display: flex;
  min-height: 41px;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 26px;
}

.site-home__nav > a {
  height: 41px;
  display: inline-flex;
  align-items: center;
  border: 0;
  border-bottom: 1px solid transparent;
  padding: 0;
  color: #d7d7d7;
  background: transparent;
  font-family: "Aptos", "Segoe UI", sans-serif;
  font-size: 14px;
  font-weight: 700;
  line-height: 1;
  text-decoration: none;
  transition: border-color .15s ease, color .15s ease;
}

.site-home__nav > a:hover,
.site-home__nav > a.router-link-active {
  color: var(--home-orange);
  border-color: var(--home-orange);
  background: transparent;
}

.site-home__hero {
  position: relative;
  isolation: isolate;
  min-height: clamp(250px, 34vh, 350px);
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: clamp(28px, 6vw, 90px);
  overflow: hidden;
  margin-bottom: 22px;
  border: 0;
  border-bottom: 1px solid rgba(200, 138, 47, 0.16);
  border-radius: 12px;
  padding: clamp(38px, 5vw, 68px) clamp(24px, 4vw, 54px);
  background:
    radial-gradient(circle at 69% 56%, rgba(200, 138, 47, 0.08), transparent 17rem),
    linear-gradient(100deg, #101217 0%, #111318 64%, #0e1014 100%);
}

.site-home__hero::before {
  position: absolute;
  z-index: -1;
  top: 14%;
  right: 8%;
  width: min(31%, 390px);
  aspect-ratio: 1.24;
  border: 1px solid currentColor;
  content: "";
  color: rgba(230, 233, 238, 0.055);
  background-image:
    linear-gradient(currentColor 1px, transparent 1px),
    linear-gradient(90deg, currentColor 1px, transparent 1px),
    radial-gradient(circle at 21% 72%, currentColor 0 2px, transparent 2.5px),
    radial-gradient(circle at 57% 36%, currentColor 0 2px, transparent 2.5px),
    radial-gradient(circle at 76% 61%, currentColor 0 2px, transparent 2.5px);
  background-size: 25% 25%, 25% 25%, 100% 100%, 100% 100%, 100% 100%;
  transform: perspective(520px) rotateY(-7deg);
}

.site-home__hero::after {
  position: absolute;
  z-index: -1;
  right: 3%;
  bottom: 4%;
  width: min(39%, 510px);
  height: 58%;
  border-top: 1px solid rgba(230, 233, 238, 0.045);
  border-radius: 50%;
  content: "";
  transform: rotate(-11deg);
}

.site-home__hero-copy { position: relative; z-index: 1; max-width: 920px; }

.site-home__hero h1 {
  max-width: 830px;
  margin: 0;
  color: var(--home-text);
  font-family: Baskerville, "Iowan Old Style", "Palatino Linotype", Georgia, serif;
  font-size: clamp(42px, 5.2vw, 70px);
  font-weight: 560;
  line-height: 1.01;
  letter-spacing: -.012em;
  text-wrap: balance;
}

.site-home__hero h1 span {
  color: var(--home-orange);
  font-family: inherit;
  font-size: inherit;
  font-weight: 500;
  line-height: inherit;
  text-shadow: none;
}

.site-home__hero-copy p {
  max-width: 620px;
  margin: 24px 0 0;
  color: var(--home-muted);
  font-size: clamp(15px, 1.4vw, 18px);
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

/* Petehub keeps the original homepage art direction. */
.site-home--petehub {
  --home-orange: #ff9900;
  --home-orange-soft: rgba(255, 153, 0, 0.18);
  --home-line: rgba(255, 153, 0, 0.3);
  --home-text: #f7f7f7;
  --home-muted: #b7b7b7;
  padding: 26px clamp(18px, 4vw, 58px) 32px;
  background:
    radial-gradient(circle at 78% 8%, rgba(255, 153, 0, 0.24), transparent 28rem),
    radial-gradient(circle at 12% 76%, rgba(255, 153, 0, 0.1), transparent 24rem),
    linear-gradient(135deg, #070707 0%, #141414 52%, #060606 100%);
}

.site-home--petehub .site-home__top {
  align-items: center;
  gap: 18px;
  margin-bottom: 14px;
  padding: 0;
}

.site-home--petehub .site-home__actions { gap: 16px; }

.site-home--petehub .site-home__brand {
  padding-bottom: 0;
  font-family: inherit;
  font-size: clamp(34px, 5vw, 62px);
  font-weight: 950;
  line-height: normal;
}

.site-home--petehub .site-home__nav { gap: 10px; }

.site-home--petehub .site-home__nav > a {
  height: auto;
  min-height: 41px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 999px;
  padding: 9px 15px;
  color: var(--home-muted);
  background: rgba(255, 255, 255, 0.045);
  font-family: inherit;
  font-size: inherit;
  font-weight: 900;
  line-height: normal;
}

.site-home--petehub .site-home__nav > a:hover,
.site-home--petehub .site-home__nav > a.router-link-active {
  color: #111;
  border-color: var(--home-orange);
  background: var(--home-orange);
}

.site-home--petehub .site-home__hero {
  min-height: clamp(190px, 26vh, 290px);
  margin-bottom: 18px;
  overflow: visible;
  border: 1px solid rgba(255, 153, 0, 0.22);
  border-radius: 10px;
  padding: clamp(24px, 4vw, 48px);
  background:
    linear-gradient(90deg, rgba(0, 0, 0, 0.86), rgba(0, 0, 0, 0.44) 56%, rgba(255, 153, 0, 0.11)),
    radial-gradient(circle at 82% 32%, rgba(255, 153, 0, 0.16), transparent 28rem),
    rgba(18, 18, 18, 0.84);
  box-shadow: 0 28px 90px rgba(0, 0, 0, 0.44);
}

.site-home--petehub .site-home__hero::before,
.site-home--petehub .site-home__hero::after { display: none; }

.site-home--petehub .site-home__hero h1 {
  font-size: clamp(36px, 4.8vw, 64px);
  font-weight: 600;
  line-height: 1.04;
}

.site-home--petehub .site-home__hero h1 span {
  font: inherit;
  text-shadow: 0 10px 34px rgba(255, 153, 0, .18);
}

.site-home--petehub .site-home__hero-copy p {
  margin-top: 18px;
  font-size: clamp(15px, 1.6vw, 20px);
}

@media (max-width: 980px) {
  .site-home__top { padding-right: 90px; }
  .site-home--petehub .site-home__top { padding-right: 0; }
  .site-home__hero { align-items: stretch; flex-direction: column; }
}

@media (max-width: 720px) {
  .site-home__top { align-items: flex-start; flex-direction: column; padding-right: 0; }
  .site-home__actions { width: 100%; justify-items: start; }
  .site-home__nav { justify-content: flex-start; }
  .site-home__search-destination { align-items: flex-start; flex-direction: column; gap: 4px; }
  .site-home__search-destination em { margin-left: 0; }
  .site-home__footer { align-items: start; flex-direction: column; }
}
</style>
