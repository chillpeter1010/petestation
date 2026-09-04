<template>
  <main class="batter-comparison-hub">
    <ComparisonPageHeader
      eyebrow="Batter station · Comparison"
      title="Choose a batter comparison workflow."
      description="Move from one hitter across two periods into team batting context and lineup research."
      back-to="/batters"
      back-label="Batter station"
    />
    <section class="mode-grid" aria-label="Batter comparison modes">
      <NuxtLink class="mode-card" to="/batters/comparison/period"><span>Period</span><h2>Batter Period Compare</h2><p>A/B production, bat tracking, timing coverage and shared location maps.</p><strong>Open</strong></NuxtLink>
      <NuxtLink class="mode-card" to="/batters/comparison/team"><span>Team research</span><h2>Team Batting</h2><p>Observed batting order, position coverage, role splits and platoon context.</p><strong>Open</strong></NuxtLink>
      <NuxtLink class="mode-card" to="/batters/comparison/lineup"><span>Research mode</span><h2>Lineup Scenarios</h2><p>Recent-lineup probabilities and constrained run-expectancy scenarios with explicit uncertainty.</p><strong>Open</strong></NuxtLink>
    </section>
  </main>
</template>

<style scoped>
.batter-comparison-hub { max-width: 1160px; margin: 0 auto; padding: 104px 20px 56px; }
.mode-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; margin-top: 18px; }
.mode-card { min-height: 220px; border: 1px solid var(--color-border); border-radius: 0; padding: 22px; color: inherit; background: var(--color-surface); text-decoration: none; box-shadow: var(--shadow-sm); transition: transform 140ms ease, border-color 140ms ease; }
.mode-card:hover { border-color: var(--color-primary); transform: translateY(-2px); }
.mode-card > span { color: var(--color-primary); font-size: 11px; font-weight: 900; text-transform: uppercase; }
.mode-card h2 { margin: 10px 0 0; color: var(--color-foreground); }
.mode-card p { color: var(--color-muted-text); line-height: 1.55; }
.mode-card strong { display: inline-flex; margin-top: 20px; border: 1px solid var(--color-primary); border-radius: 0; padding: 8px 13px; color: var(--color-on-primary); background: var(--color-primary); }
@media (max-width: 840px) { .mode-grid { grid-template-columns: 1fr; } }
</style>
