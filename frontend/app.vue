<template>
  <NuxtLayout>
    <NuxtLink
      v-if="showGlobalHomeLink"
      class="global-home-link"
      :class="{ 'global-home-link--brand': showBrandHomeLink }"
      to="/"
      :aria-label="`${brandName} home`"
    >
      <template v-if="showBrandHomeLink"><span>Pete</span><strong>hub</strong></template>
      <template v-else>
        <svg aria-hidden="true" viewBox="0 0 24 24">
          <path d="m3 11 9-8 9 8" />
          <path d="M5 10v10h14V10" />
          <path d="M9 20v-6h6v6" />
        </svg>
        <span>Home</span>
      </template>
    </NuxtLink>
    <AuthUserMenu v-if="auth.user.value && !isAuthPage && !isBallparkPage" />
    <BallparkClassicReturn v-if="!isAuthPage && !isBallparkPage" />
    <div
      class="app-page-shell"
      :class="{
        'global-home-offset': reserveGlobalHomeSpace,
        'app-page-shell--ballpark': isBallparkPage
      }"
    >
      <NuxtPage />
    </div>
  </NuxtLayout>
</template>

<script setup lang="ts">
type ThemeMode = 'light' | 'dark'

const theme = useState<ThemeMode>('theme-mode', () => 'dark')
const route = useRoute()
const auth = useAuth()
// Capture explicit Ballpark origin before individual Classic pages normalize their own query.
useBallparkReturn()
const { isPetehub, brandName } = useSiteBrand()
const isAuthPage = computed(() => route.path === '/login' || route.path === '/register')
const isBallparkPage = computed(() => route.path.replace(/\/+$/, '') === '/ballpark' || route.path.startsWith('/ballpark/play'))
const showGlobalHomeLink = computed(() => !isAuthPage.value && !isBallparkPage.value && route.path !== '/' && route.path !== '/pitchers')
const showBrandHomeLink = computed(() => isPetehub.value)
const reserveGlobalHomeSpace = computed(() => showGlobalHomeLink.value)

useHead(() => ({
  htmlAttrs: {
    'data-theme': theme.value
  }
}))

function applyTheme(value: ThemeMode) {
  document.documentElement.dataset.theme = value
  localStorage.setItem('theme-mode', value)
}

watch(theme, (value) => {
  if (import.meta.client) {
    applyTheme(value)
  }
})

onMounted(() => {
  const savedTheme = localStorage.getItem('theme-mode')
  if (savedTheme === 'dark' || savedTheme === 'light') {
    theme.value = savedTheme
    applyTheme(savedTheme)
    return
  }
  applyTheme(theme.value)
})
</script>
