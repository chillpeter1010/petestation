<template>
  <main class="register-page">
    <NuxtLink class="brand" :class="{ 'brand--petehub': isPetehub }" to="/login"><template v-if="isPetehub"><span>Pete</span><strong>hub</strong></template><span v-else>Peteclub</span></NuxtLink>
    <section class="register-card" aria-labelledby="register-title">
      <template v-if="completed">
        <div class="status-mark" aria-hidden="true">✓</div>
        <p class="eyebrow">REQUEST RECEIVED</p>
        <h1 id="register-title">Waiting for approval</h1>
        <p>Your account has been created. An administrator must approve it before you can sign in.</p>
        <NuxtLink class="primary-link" to="/login">Return to sign in</NuxtLink>
      </template>
      <form v-else @submit.prevent="submit">
        <header><p class="eyebrow">PRIVATE ACCESS</p><h1 id="register-title">Request an account</h1><p>Choose a username and password. Registration does not grant immediate access.</p></header>
        <label for="username">Username</label>
        <input id="username" v-model.trim="username" autocomplete="username" minlength="3" maxlength="32" pattern="[A-Za-z0-9_.-]+" required aria-describedby="username-help" />
        <small id="username-help">3–32 characters: letters, numbers, dots, dashes, or underscores.</small>
        <label for="password">Password</label>
        <input id="password" v-model="password" type="password" autocomplete="new-password" minlength="10" maxlength="128" required />
        <label for="confirmation">Confirm password</label>
        <input id="confirmation" v-model="confirmation" type="password" autocomplete="new-password" minlength="10" maxlength="128" required :aria-invalid="Boolean(errorMessage)" />
        <p v-if="errorMessage" class="form-error" role="alert">{{ errorMessage }}</p>
        <button type="submit" :disabled="submitting">{{ submitting ? 'Submitting…' : 'Request access' }}</button>
        <p class="switch-copy">Already approved? <NuxtLink to="/login">Sign in</NuxtLink></p>
      </form>
    </section>
  </main>
</template>

<script setup lang="ts">
const auth = useAuth()
const { isPetehub, brandName } = useSiteBrand()
const username = ref('')
const password = ref('')
const confirmation = ref('')
const submitting = ref(false)
const completed = ref(false)
const errorMessage = ref('')

useHead(() => ({ title: `Request access · ${brandName.value}` }))

async function submit() {
  errorMessage.value = ''
  if (password.value !== confirmation.value) {
    errorMessage.value = 'Passwords do not match.'
    return
  }
  submitting.value = true
  try {
    await auth.register(username.value, password.value)
    completed.value = true
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to register.'
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.register-page{min-height:100vh;display:grid;place-items:center;padding:86px 22px 42px;background:radial-gradient(circle at 50% 0,rgb(255 153 0 / 16%),transparent 34rem),var(--color-background)}.brand{position:absolute;top:26px;left:30px;color:#e8ddce;font-family:"Aptos Display","Segoe UI Variable Display","Segoe UI",sans-serif;font-size:25px;font-weight:680;letter-spacing:-.025em;text-decoration:none}.brand--petehub{color:var(--color-text);font-family:inherit;font-weight:950;letter-spacing:normal}.brand--petehub strong{margin-left:4px;border-radius:5px;padding:2px 8px 4px;color:#111;background:#ff9900}.register-card{width:min(100%,570px);border:1px solid var(--color-border);border-radius:18px;padding:clamp(26px,5vw,48px);background:var(--color-surface);box-shadow:0 28px 80px rgb(0 0 0 / 22%)}form{display:grid;gap:9px}.eyebrow{margin:0 0 10px;color:var(--color-primary);font-size:10px;font-weight:900;letter-spacing:.15em}h1{margin:0;color:var(--color-text);font-size:36px;letter-spacing:-.035em}.register-card header>p:last-child,.register-card>p{color:var(--color-muted-text);line-height:1.6}label{margin-top:9px;color:var(--color-text);font-size:12px;font-weight:850}input{height:50px;border:1px solid var(--color-border-strong);border-radius:9px;padding:0 14px;color:var(--color-text);background:var(--color-background)}input[aria-invalid=true]{border-color:var(--color-destructive)}small{color:var(--color-muted-text);font-size:10px}button,.primary-link{min-height:50px;display:grid;place-items:center;margin-top:14px;border:0;border-radius:9px;color:#111;background:var(--color-primary);font-weight:900;text-decoration:none;cursor:pointer}button:disabled{opacity:.6}.form-error{margin:5px 0 0;color:var(--color-destructive);font-size:12px}.switch-copy{margin:13px 0 0;color:var(--color-muted-text);font-size:13px;text-align:center}.switch-copy a{color:var(--color-primary);font-weight:850}.status-mark{width:58px;height:58px;display:grid;place-items:center;margin-bottom:25px;border-radius:50%;color:#111;background:var(--color-primary);font-size:29px;font-weight:950}
</style>
