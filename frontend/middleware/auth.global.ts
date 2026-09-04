export default defineNuxtRouteMiddleware(async (to) => {
  const auth = useAuth()
  const isAuthPage = to.path === '/login' || to.path === '/register'

  if (!auth.ready.value) await auth.fetchMe()

  if (isAuthPage) {
    if (auth.user.value) return navigateTo('/')
    return
  }
  if (!auth.user.value) {
    return navigateTo({ path: '/login', query: { redirect: to.fullPath } })
  }
  if (to.path.startsWith('/admin') && auth.user.value.role !== 'admin') {
    return navigateTo('/')
  }
})
