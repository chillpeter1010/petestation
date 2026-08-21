<template>
  <NuxtLayout>
    <NuxtLink v-if="showGlobalHomeLink" class="global-home-link" to="/" aria-label="Petehub home">
      <span>Pete</span><strong>hub</strong>
    </NuxtLink>
    <button v-if="isHomePage" class="theme-toggle" type="button" :aria-label="themeLabel" @click="toggleTheme">
      <span class="theme-toggle-track" aria-hidden="true">
        <span class="theme-toggle-thumb" />
      </span>
      <span>{{ themeLabel }}</span>
    </button>
    <div class="app-page-shell" :class="{ 'global-home-offset': showGlobalHomeLink }">
      <NuxtPage />
    </div>
  </NuxtLayout>
</template>

<script setup lang="ts">
type ThemeMode = 'light' | 'dark'

const theme = useState<ThemeMode>('theme-mode', () => 'dark')
const route = useRoute()
const themeLabel = computed(() => (theme.value === 'dark' ? 'Light' : 'Dark'))
const isHomePage = computed(() => route.path === '/')
const showGlobalHomeLink = computed(() => route.path !== '/' && route.path !== '/pitchers')

useHead(() => ({
  htmlAttrs: {
    'data-theme': theme.value
  }
}))

function applyTheme(value: ThemeMode) {
  document.documentElement.dataset.theme = value
  localStorage.setItem('theme-mode', value)
}

function toggleTheme() {
  theme.value = theme.value === 'dark' ? 'light' : 'dark'
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
