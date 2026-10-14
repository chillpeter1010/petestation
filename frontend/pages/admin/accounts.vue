<template>
  <main class="accounts-page">
    <header>
      <div><p>ACCESS CONTROL</p><h1>Account approvals</h1><span>Approve new registrations or disable existing access.</span></div>
      <NuxtLink to="/">Back to dashboard</NuxtLink>
    </header>

    <p v-if="errorMessage" class="message message--error" role="alert">{{ errorMessage }}</p>
    <p v-if="successMessage" class="message" role="status">{{ successMessage }}</p>
    <section class="account-list" aria-live="polite">
      <p v-if="loading" class="state">Loading accounts…</p>
      <article v-for="account in accounts" v-else :key="account.id">
        <div class="avatar">{{ account.username.slice(0, 1).toUpperCase() }}</div>
        <div class="identity"><strong>{{ account.username }}</strong><span>Registered {{ formatDate(account.created_at) }}</span></div>
        <span :class="['status', `status--${account.status}`]">{{ account.status }}</span>
        <span class="role">{{ account.role }}</span>
        <div class="actions">
          <button v-if="account.status !== 'active'" type="button" :disabled="busyId === account.id" @click="changeStatus(account, 'active')">Approve</button>
          <button v-if="account.status === 'active' && account.id !== auth.user.value?.id" class="danger" type="button" :disabled="busyId === account.id" @click="changeStatus(account, 'disabled')">Disable</button>
        </div>
      </article>
    </section>
  </main>
</template>

<script setup lang="ts">
import type { AuthUser } from '~/composables/useAuth'

const auth = useAuth()
const { brandName } = useSiteBrand()
const accounts = ref<AuthUser[]>([])
const loading = ref(true)
const busyId = ref<number | null>(null)
const errorMessage = ref('')
const successMessage = ref('')

useHead(() => ({ title: `Account approvals · ${brandName.value}` }))

onMounted(loadAccounts)

async function loadAccounts() {
  loading.value = true
  errorMessage.value = ''
  try { accounts.value = await auth.listUsers() }
  catch { errorMessage.value = 'Unable to load accounts.' }
  finally { loading.value = false }
}

async function changeStatus(account: AuthUser, status: 'active' | 'disabled') {
  busyId.value = account.id
  errorMessage.value = ''
  successMessage.value = ''
  try {
    const updated = await auth.setUserStatus(account.id, status)
    accounts.value = accounts.value.map(item => item.id === updated.id ? updated : item)
    successMessage.value = `${updated.username} is now ${updated.status}.`
  } catch { errorMessage.value = 'Unable to update this account.' }
  finally { busyId.value = null }
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat('zh-TW', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}
</script>

<style scoped>
.accounts-page{width:min(1120px,calc(100% - 40px));min-height:100vh;margin:0 auto;padding:84px 0 60px}.accounts-page>header{display:flex;align-items:end;justify-content:space-between;gap:20px;margin-bottom:24px}.accounts-page header p{margin:0 0 8px;color:var(--color-primary);font-size:11px;font-weight:900;letter-spacing:.15em}.accounts-page h1{margin:0;color:var(--color-text);font-size:42px}.accounts-page header span{display:block;margin-top:8px;color:var(--color-muted-text)}.accounts-page header a{border:1px solid var(--color-border);border-radius:9px;padding:10px 13px;color:var(--color-text);text-decoration:none}.account-list{overflow:hidden;border:1px solid var(--color-border);border-radius:15px;background:var(--color-surface)}article{min-height:76px;display:grid;grid-template-columns:44px minmax(180px,1fr) 100px 80px 180px;align-items:center;gap:14px;border-bottom:1px solid var(--color-border);padding:12px 18px}article:last-child{border-bottom:0}.avatar{width:38px;height:38px;display:grid;place-items:center;border-radius:50%;color:#111;background:var(--color-primary);font-weight:950}.identity{display:grid;gap:4px}.identity span,.role{color:var(--color-muted-text);font-size:11px}.status{width:max-content;border-radius:999px;padding:5px 8px;font-size:9px;font-weight:900;text-transform:uppercase}.status--pending{color:#111;background:#fbbf24}.status--active{color:#d1fae5;background:#065f46}.status--disabled{color:#fee2e2;background:#991b1b}.actions{display:flex;justify-content:flex-end;gap:7px}.actions button{min-height:35px;border:1px solid var(--color-primary);border-radius:7px;padding:6px 10px;color:#111;background:var(--color-primary);font-size:11px;font-weight:850;cursor:pointer}.actions button.danger{color:var(--color-destructive);border-color:var(--color-destructive);background:transparent}.actions button:disabled{opacity:.5}.state,.message{margin:0;padding:18px;color:var(--color-muted-text)}.message{margin-bottom:14px;border:1px solid var(--color-border);border-radius:9px;background:var(--color-surface)}.message--error{color:var(--color-destructive)}@media(max-width:720px){.accounts-page{width:min(100% - 24px,1120px);padding-top:72px}.accounts-page>header{align-items:flex-start;flex-direction:column}.accounts-page h1{font-size:34px}article{grid-template-columns:44px 1fr auto}.status{grid-column:3}.role{grid-column:2}.actions{grid-column:2/-1;justify-content:flex-start}}
</style>
