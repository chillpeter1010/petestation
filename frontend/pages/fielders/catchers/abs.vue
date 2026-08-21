<template>
  <main class="placeholder-page">
    <NuxtLink class="hub-link" to="/fielders/catchers">Catcher Station</NuxtLink>
    <section>
      <span>Challenge</span>
      <h1>ABS</h1>
      <p>Staging page for challenge decisions, border pitches, and automated-zone review context.</p>
    </section>
  </main>
</template>

<style scoped>
.placeholder-page {
  display: grid;
  gap: 24px;
  padding: 24px;
}

section {
  min-height: 420px;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background: var(--color-surface);
  padding: 28px;
}

span,
.hub-link {
  color: var(--color-primary);
  font-weight: 900;
}

h1,
p {
  margin: 0;
}

h1 {
  margin-top: 8px;
  font-size: clamp(44px, 8vw, 96px);
}

p {
  margin-top: 12px;
  color: var(--color-text-muted);
  font-size: 20px;
}

.hub-link {
  justify-self: start;
  text-decoration: none;
}
</style>
