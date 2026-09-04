<template>
  <main class="auth-page">
    <section class="auth-brand" aria-labelledby="login-title">
      <NuxtLink class="brand" to="/login"><span>Pete</span><strong>hub</strong></NuxtLink>
      <div>
        <p class="eyebrow">PRIVATE BASEBALL INTELLIGENCE</p>
        <h1 id="login-title">Your ballpark,<br><em>behind the gate.</em></h1>
        <p class="deck">Pitch-level research, team planning, and player comparisons in one private workspace.</p>
      </div>
      <p class="security-note"><span aria-hidden="true">●</span> Access is limited to approved accounts.</p>
    </section>

    <section class="auth-panel" aria-label="Sign in">
      <form @submit.prevent="submit">
        <header><p class="eyebrow">WELCOME BACK</p><h2>Sign in to Petehub</h2><p>Use your approved username and password.</p></header>
        <label for="username">Username</label>
        <input id="username" v-model.trim="username" name="username" autocomplete="username" minlength="3" maxlength="32" required autofocus :aria-invalid="Boolean(errorMessage)" />
        <label for="password">Password</label>
        <input id="password" v-model="password" name="password" type="password" autocomplete="current-password" minlength="10" maxlength="128" required :aria-invalid="Boolean(errorMessage)" :aria-describedby="errorMessage ? 'login-error' : undefined" />
        <p v-if="errorMessage" id="login-error" class="form-error" role="alert">{{ errorMessage }}</p>
        <button type="submit" :disabled="submitting">{{ submitting ? 'Signing in…' : 'Sign in' }}</button>
        <p class="switch-copy">Need an account? <NuxtLink to="/register">Request access</NuxtLink></p>
      </form>
    </section>
  </main>
</template>

<script setup lang="ts">
const auth = useAuth()
const route = useRoute()
const username = ref('')
const password = ref('')
const submitting = ref(false)
const errorMessage = ref('')

useHead({ title: 'Sign in · Petehub' })

async function submit() {
  submitting.value = true
  errorMessage.value = ''
  try {
    await auth.login(username.value, password.value)
    const target = typeof route.query.redirect === 'string' && route.query.redirect.startsWith('/') && !route.query.redirect.startsWith('//')
      ? route.query.redirect
      : '/'
    await navigateTo(target)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Unable to sign in.'
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.auth-page{min-height:100vh;display:grid;grid-template-columns:minmax(0,1.15fr) minmax(420px,.85fr);background:#08111f}.auth-brand{position:relative;min-height:100vh;display:flex;flex-direction:column;justify-content:space-between;overflow:hidden;padding:clamp(28px,5vw,72px);color:#edf4ff;background:radial-gradient(circle at 78% 22%,rgb(255 153 0 / 22%),transparent 28rem),linear-gradient(145deg,#101b2d 0%,#08111f 62%,#050a12 100%)}.auth-brand::after{content:"";position:absolute;right:-12vw;bottom:-27vw;width:62vw;height:62vw;border:1px solid rgb(255 153 0 / 17%);border-radius:50%;box-shadow:0 0 0 7vw rgb(255 153 0 / 3%),0 0 0 14vw rgb(255 153 0 / 2%);pointer-events:none}.brand{position:relative;z-index:1;width:max-content;color:#f8fafc;font-size:28px;font-weight:950;text-decoration:none}.brand strong{margin-left:4px;border-radius:5px;padding:2px 8px 4px;color:#111;background:#ff9900}.auth-brand>div{position:relative;z-index:1;max-width:760px}.eyebrow{margin:0 0 18px;color:#ffae35;font-size:11px;font-weight:900;letter-spacing:.16em}.auth-brand h1{margin:0;font-size:clamp(48px,6vw,92px);line-height:.94;letter-spacing:-.055em}.auth-brand h1 em{color:#ff9900;font-style:normal}.deck{max-width:620px;margin:28px 0 0;color:#9fb0c8;font-size:clamp(16px,1.6vw,21px);line-height:1.6}.security-note{position:relative;z-index:1;margin:0;color:#9fb0c8;font-size:12px}.security-note span{margin-right:8px;color:#ff9900}.auth-panel{display:grid;place-items:center;padding:34px;background:var(--color-background)}form{width:min(100%,440px);display:grid;gap:10px}form header{margin-bottom:20px}form h2{margin:0;color:var(--color-text);font-size:34px;letter-spacing:-.03em}form header>p:last-child{margin:9px 0 0;color:var(--color-muted-text)}label{margin-top:8px;color:var(--color-text);font-size:12px;font-weight:850}input{width:100%;height:52px;border:1px solid var(--color-border-strong);border-radius:9px;padding:0 14px;color:var(--color-text);background:var(--color-surface)}input[aria-invalid=true]{border-color:var(--color-destructive)}button{height:52px;margin-top:12px;border:0;border-radius:9px;color:#111;background:#ff9900;font-weight:900;cursor:pointer}button:disabled{opacity:.6;cursor:wait}.form-error{margin:4px 0 0;color:var(--color-destructive);font-size:12px}.switch-copy{margin:14px 0 0;color:var(--color-muted-text);font-size:13px;text-align:center}.switch-copy a{color:var(--color-primary);font-weight:850}@media(max-width:900px){.auth-page{grid-template-columns:1fr}.auth-brand{min-height:310px;padding:28px}.auth-brand h1{font-size:48px}.auth-brand .deck{font-size:14px}.auth-panel{min-height:calc(100vh - 310px);padding:32px 22px}}@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto}}
</style>
