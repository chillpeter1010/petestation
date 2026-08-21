<template>
  <main class="rotation-hub">
    <section class="hub-hero">
      <span>Rotation</span>
      <h1>Choose a pitching role view.</h1>
      <p>Starter rotation and reliever role will share workload, leverage, and player-link modules.</p>
    </section>

    <section class="mode-grid" aria-label="Rotation modes">
      <NuxtLink class="mode-card primary" to="/rotation/starter">
        <span>Starter</span>
        <h2>Starter Rotation</h2>
        <p>Rotation table, workload, rest patterns, pitch-count buckets, and per-game WPA trends.</p>
        <strong>Open</strong>
      </NuxtLink>

      <NuxtLink class="mode-card primary" to="/rotation/reliever">
        <span>Reliever</span>
        <h2>Bullpen Role</h2>
        <p>Relief role, save/hold context, inherited runners, leverage usage, and freshness views.</p>
        <strong>Open</strong>
      </NuxtLink>

      <NuxtLink class="mode-card shortcut" to="/rotation/fatigue-lab">
        <span>Starter Lab</span>
        <h2>Starter Fatigue Lab</h2>
        <p>Prototype readiness by rest, age, previous start workload, and season-start context.</p>
        <strong>Open Lab</strong>
      </NuxtLink>

      <NuxtLink class="mode-card shortcut" to="/rotation/reliever-fatigue-lab">
        <span>Reliever Lab</span>
        <h2>Bullpen Fatigue Lab</h2>
        <p>Prototype bullpen readiness by yesterday workload, recent load, leverage, and rest days.</p>
        <strong>Open Lab</strong>
      </NuxtLink>
    </section>
  </main>
</template>

<style scoped>
.rotation-hub {
  max-width: 1160px;
  margin: 0 auto;
  padding: 104px 20px 56px;
}

.hub-hero {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 28px;
  background:
    radial-gradient(circle at top right, color-mix(in srgb, var(--color-primary) 18%, transparent), transparent 34%),
    var(--color-surface);
  box-shadow: var(--shadow-md);
}

.hub-hero span,
.mode-card span {
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 900;
  text-transform: uppercase;
}

.hub-hero h1 {
  margin: 8px 0 0;
  color: var(--color-foreground);
  font-size: clamp(32px, 5vw, 56px);
  line-height: 1;
}

.hub-hero p,
.mode-card p {
  color: var(--color-muted-text);
}

.mode-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 18px;
  margin-top: 18px;
}

.mode-card {
  min-height: 220px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 22px;
  color: inherit;
  background: var(--color-surface);
  text-decoration: none;
  box-shadow: var(--shadow-sm);
}

.mode-card h2 {
  margin: 10px 0 0;
  color: var(--color-foreground);
}

.mode-card strong {
  display: inline-flex;
  margin-top: 24px;
  border-radius: 999px;
  padding: 8px 14px;
  color: var(--color-on-primary);
  background: var(--color-primary);
}

.mode-card.primary {
  transition: transform 140ms ease, border-color 140ms ease;
}

.mode-card.primary:hover {
  border-color: var(--color-primary);
  transform: translateY(-2px);
}

.mode-card.shortcut {
  min-height: 190px;
  background:
    linear-gradient(135deg, color-mix(in srgb, var(--color-primary) 13%, transparent), transparent 52%),
    var(--color-surface);
  transition: transform 140ms ease, border-color 140ms ease;
}

.mode-card.shortcut:hover {
  border-color: var(--color-primary);
  transform: translateY(-2px);
}

@media (max-width: 780px) {
  .mode-grid {
    grid-template-columns: 1fr;
  }
}

@media (min-width: 781px) and (max-width: 1160px) {
  .mode-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
