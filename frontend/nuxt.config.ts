export default defineNuxtConfig({
  buildDir: process.env.NUXT_BUILD_DIR || '.nuxt',
  modules: ['@pinia/nuxt'],
  css: ['~/assets/css/main.css'],
  components: [
    {
      path: '~/components',
      pathPrefix: false
    }
  ],
  typescript: {
    strict: true
  },
  experimental: {
    appManifest: false
  },
  vite: {
    server: {
      allowedHosts: ['.trycloudflare.com', '.localhost.run', '.lhr.life']
    }
  },
  runtimeConfig: {
    apiInternalBase: process.env.NUXT_API_INTERNAL_BASE || 'http://127.0.0.1:8000/api',
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE || '/api'
    }
  }
})
