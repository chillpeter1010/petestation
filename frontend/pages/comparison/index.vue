<template>
  <main class="comparison-hub">
    <section class="hub-hero">
      <span>Comparison</span>
      <h1>Choose comparison mode.</h1>
      <p>Choose a pitcher comparison workflow. Batter comparisons now live inside Batter Station.</p>
    </section>

    <section class="mode-grid" aria-label="Comparison modes">
      <NuxtLink class="mode-card primary" to="/comparison/personal">
        <span>Personal</span>
        <h2>Pitcher vs Pitcher</h2>
        <p>Start with two-player percentile cards from the legacy 24 Pitcher Comparison page.</p>
        <strong>Open</strong>
      </NuxtLink>

      <NuxtLink class="mode-card primary" to="/comparison/period">
        <span>Period</span>
        <h2>Period Compare</h2>
        <p>Compare one pitcher across two custom date windows using the reusable percentile module.</p>
        <strong>Open</strong>
      </NuxtLink>

    </section>
  </main>
</template>

<style scoped>
.comparison-hub {
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
  grid-template-columns: repeat(2, minmax(0, 1fr));
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

.mode-card.disabled {
  opacity: 0.68;
}

@media (max-width: 780px) {
  .mode-grid {
    grid-template-columns: 1fr;
  }
}
</style>
