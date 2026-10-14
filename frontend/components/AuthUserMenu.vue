<template>
  <div class="auth-user-menu" :class="{ 'auth-user-menu--petehub': isPetehub }">
    <details>
      <summary aria-label="Open account menu">
        <span>{{ initial }}</span>
        <strong>{{ auth.user.value?.username }}</strong>
      </summary>
      <nav aria-label="Account menu">
        <p><small>Signed in as</small>{{ auth.user.value?.username }}</p>
        <NuxtLink v-if="auth.user.value?.role === 'admin'" to="/admin/accounts">Manage accounts</NuxtLink>
        <NuxtLink v-if="auth.user.value?.role === 'admin'" to="/admin/updates">Data operations</NuxtLink>
        <button type="button" @click="signOut">Sign out</button>
      </nav>
    </details>
  </div>
</template>

<script setup lang="ts">
const auth = useAuth()
const { isPetehub } = useSiteBrand()
const initial = computed(() => auth.user.value?.username.slice(0, 1).toUpperCase() || 'U')

async function signOut() {
  await auth.logout()
  await navigateTo('/login')
}
</script>

<style scoped>
.auth-user-menu{position:fixed;z-index:70;top:12px;right:14px}.auth-user-menu details{position:relative}.auth-user-menu summary{min-height:38px;display:flex;align-items:center;gap:8px;border:1px solid var(--color-border-strong);border-radius:10px;padding:4px 10px 4px 5px;color:var(--color-text);background:color-mix(in srgb,var(--color-surface) 94%,transparent);box-shadow:var(--shadow-sm);backdrop-filter:blur(14px);cursor:pointer;list-style:none}.auth-user-menu summary::-webkit-details-marker{display:none}.auth-user-menu summary span{width:28px;height:28px;display:grid;place-items:center;border-radius:9px;color:#111;background:var(--color-primary);font-weight:950}.auth-user-menu summary strong{max-width:130px;overflow:hidden;text-overflow:ellipsis;font-size:12px;white-space:nowrap}.auth-user-menu nav{position:absolute;top:calc(100% + 8px);right:0;width:210px;display:grid;overflow:hidden;border:1px solid var(--color-border);border-radius:12px;background:var(--color-surface);box-shadow:0 18px 48px rgb(0 0 0 / 32%)}.auth-user-menu p{display:grid;gap:3px;margin:0;border-bottom:1px solid var(--color-border);padding:13px;color:var(--color-text);font-size:13px;font-weight:850}.auth-user-menu small{color:var(--color-muted-text);font-size:9px;text-transform:uppercase}.auth-user-menu a,.auth-user-menu button{min-height:42px;display:flex;align-items:center;border:0;border-bottom:1px solid var(--color-border);padding:9px 13px;color:var(--color-text);background:transparent;font-size:12px;font-weight:750;text-align:left;text-decoration:none;cursor:pointer}.auth-user-menu a:hover,.auth-user-menu button:hover{color:#111;background:var(--color-primary)}.auth-user-menu--petehub summary{border-radius:999px}.auth-user-menu--petehub summary span{border-radius:50%}@media(max-width:760px){.auth-user-menu{top:9px;right:10px}.auth-user-menu summary strong{display:none}}
</style>
