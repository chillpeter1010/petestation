<template>
  <main class="catcher-hub">
    <section class="catcher-hero">
      <div>
        <span>Catcher Station</span>
        <h1>Receiving workflows start here.</h1>
        <p>Framing, blocking, throwing, ABS review, and pitcher-pair sequence analysis.</p>
      </div>
      <NuxtLink class="hub-link" to="/fielders">Fielders</NuxtLink>
    </section>

    <section class="module-grid">
      <NuxtLink v-for="module in modules" :key="module.to" class="module-card" :to="module.to">
        <span>{{ module.kicker }}</span>
        <h2>{{ module.title }}</h2>
        <p>{{ module.copy }}</p>
      </NuxtLink>
    </section>
  </main>
</template>

<script setup lang="ts">
const modules = [
  { title: 'Framing', kicker: 'Receiving', copy: 'Called-strike lift and zone value staging page.', to: '/fielders/catchers/framing' },
  { title: 'Blocking', kicker: 'Control', copy: 'Blocked balls, passed-ball risk, and dirt management staging page.', to: '/fielders/catchers/blocking' },
  { title: 'Throwing', kicker: 'Run Game', copy: 'Pop time, exchange, arm, and caught-stealing staging page.', to: '/fielders/catchers/throwing' },
  { title: 'ABS', kicker: 'Challenge', copy: 'Automated-zone review and challenge context staging page.', to: '/fielders/catchers/abs' },
  { title: 'Sequence', kicker: 'Pairing', copy: 'Pitch mix by count for each catcher and paired pitcher.', to: '/fielders/catchers/sequence' }
]
</script>

<style scoped>
.catcher-hub {
  display: grid;
  gap: 24px;
  padding: 24px;
}

.catcher-hero,
.module-card {
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background: radial-gradient(circle at top right, rgba(247, 166, 52, 0.16), transparent 38%),
    var(--color-surface);
  box-shadow: var(--shadow-card);
}

.catcher-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 28px;
  padding: 28px;
}

span {
  color: var(--color-primary);
  font-weight: 900;
  text-transform: uppercase;
}

h1,
h2,
p {
  margin: 0;
}

h1 {
  margin-top: 8px;
  font-size: clamp(36px, 6vw, 76px);
  line-height: 0.95;
}

p {
  margin-top: 12px;
  color: var(--color-text-muted);
  font-size: 18px;
}

.hub-link,
.module-card {
  color: var(--color-text);
  text-decoration: none;
}

.hub-link {
  border: 1px solid var(--color-border-strong);
  border-radius: 999px;
  padding: 12px 22px;
  color: var(--color-primary);
  font-weight: 900;
}

.module-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 16px;
}

.module-card {
  min-height: 220px;
  padding: 22px;
}

.module-card:hover {
  border-color: var(--color-primary);
}

@media (max-width: 1100px) {
  .module-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .catcher-hero {
    align-items: flex-start;
    flex-direction: column;
  }

  .module-grid {
    grid-template-columns: 1fr;
  }
}
</style>
