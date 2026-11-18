<template>
  <NuxtLayout>
    <NuxtLink
      v-if="showGlobalHomeLink"
      class="global-home-link global-home-link--brand"
      to="/"
      :aria-label="`${brandName} home`"
    >
      <SiteBrandMark />
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
const { brandName } = useSiteBrand()
const isAuthPage = computed(() => route.path === '/login' || route.path === '/register')
const isBallparkPage = computed(() => route.path.replace(/\/+$/, '') === '/ballpark' || route.path.startsWith('/ballpark/play'))
const showGlobalHomeLink = computed(() => !isAuthPage.value && !isBallparkPage.value && route.path !== '/' && route.path !== '/pitchers')
const reserveGlobalHomeSpace = computed(() => showGlobalHomeLink.value)

useHead(() => ({
  bodyAttrs: { 'data-ballpark': isBallparkPage.value ? 'true' : undefined },
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
