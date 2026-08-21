<template>
  <main class="station-page">
    <section class="station-hero">
      <div>
        <span class="eyebrow">Fielder Station</span>
        <h1>Defense tools staged by role.</h1>
        <p>Start with catcher workflows, then expand into infield and outfield defensive modules.</p>
      </div>
      <NuxtLink class="hub-link" to="/">Home</NuxtLink>
    </section>

    <section class="station-card-grid">
      <NuxtLink class="station-card station-card--active" to="/fielders/catchers">
        <span>Catchers</span>
        <h2>Catcher Station</h2>
        <p>Framing, blocking, throwing, ABS context, and catcher-pitcher sequencing.</p>
      </NuxtLink>
      <article class="station-card">
        <span>Infielders</span>
        <h2>Coming Soon</h2>
        <p>Positioning, range, arm, and batted-ball routing will live here.</p>
      </article>
      <article class="station-card">
        <span>Outfielders</span>
        <h2>Coming Soon</h2>
        <p>Routes, jumps, arm strength, and catch probability will live here.</p>
      </article>
    </section>
  </main>
</template>

<style scoped>
.station-page {
  display: grid;
  gap: 24px;
  padding: 24px;
}

.station-hero,
.station-card {
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background: radial-gradient(circle at top right, rgba(247, 166, 52, 0.16), transparent 38%),
    var(--color-surface);
  box-shadow: var(--shadow-card);
}

.station-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 28px;
  padding: 28px;
}

.eyebrow,
.station-card span {
  color: var(--color-primary);
  font-weight: 900;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

h1,
h2,
p {
  margin: 0;
}

h1 {
  margin-top: 8px;
  font-size: clamp(36px, 6vw, 80px);
  line-height: 0.95;
}

p {
  margin-top: 12px;
  color: var(--color-text-muted);
  font-size: 18px;
}

.hub-link,
.station-card--active {
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

.station-card-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
}

.station-card {
  min-height: 220px;
  padding: 24px;
}

.station-card--active:hover {
  border-color: var(--color-primary);
}

@media (max-width: 900px) {
  .station-hero,
  .station-card-grid {
    grid-template-columns: 1fr;
  }

  .station-hero {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
