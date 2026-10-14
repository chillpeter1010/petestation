<template>
  <main class="lab-page">
    <ComparisonPageHeader
      eyebrow="Pitcher Lab"
      title="Pitcher Lab"
      description="Research workbenches for pitch quality, command, and workload models."
      back-to="/"
      back-label="Home"
    />

    <section class="lab-grid" aria-label="Lab modules">
      <NuxtLink class="lab-card ready explorer-card" to="/lab/pitcher-metrics">
        <span>Cross-metric research</span>
        <h2>Pitcher Metric Explorer</h2>
        <p>Choose any two compatible pitcher-season metrics, inspect coverage, and run descriptive correlation and regression.</p>
        <strong>Open</strong>
      </NuxtLink>

      <NuxtLink class="lab-card ready" to="/rotation/fatigue-lab">
        <span>Starter</span>
        <h2>Starter Fatigue Lab</h2>
        <p>Pregame readiness, inning fatigue bars, PA fatigue trend, and starter game trials.</p>
        <strong>Open</strong>
      </NuxtLink>

      <NuxtLink class="lab-card ready" to="/rotation/reliever-fatigue-lab">
        <span>Reliever</span>
        <h2>Bullpen Fatigue Lab</h2>
        <p>Recent workload, rest-day context, leverage, and bullpen readiness experiments.</p>
        <strong>Open</strong>
      </NuxtLink>

      <NuxtLink class="lab-card ready" to="/lab/stuff">
        <span>Stuff</span>
        <h2>Stuff Lab</h2>
        <p>Global pitch-type Stuff+, movement profiles, release traits, and model diagnostics.</p>
        <strong>Open</strong>
      </NuxtLink>

      <NuxtLink class="lab-card ready" to="/lab/stuff-calculator">
        <span>Simulator</span>
        <h2>Stuff Calculator</h2>
        <p>Adjust a hypothetical pitch shape and score it with the active Peter Stuff+ model.</p>
        <strong>Open</strong>
      </NuxtLink>

      <NuxtLink class="lab-card ready" to="/lab/location">
        <span>Location</span>
        <h2>Location Lab</h2>
        <p>Zone quality, heart-shadow-chase features, and Location+ model diagnostics.</p>
        <strong>Open</strong>
      </NuxtLink>

      <NuxtLink class="lab-card ready" to="/lab/pitching">
        <span>Pitching</span>
        <h2>Pitching+ Lab</h2>
        <p>Complete-pitch value, pitcher rankings, pitch-type splits, trends, and model validation.</p>
        <strong>Open</strong>
      </NuxtLink>

      <NuxtLink class="lab-card ready leverage-card" to="/lab/leverage">
        <span>Bullpen value</span>
        <h2>RE24 &amp; Leverage Lab</h2>
        <p>Test game states, inspect RE24 and LI, validate the estimates, and rank MLB relievers.</p>
        <strong>Open</strong>
      </NuxtLink>

      <NuxtLink class="lab-card ready stamina-card" to="/lab/stamina">
        <span>Workload quality</span>
        <h2>Stamina Lab</h2>
        <p>Audit cleaned pitch data, SP/RP role splits, Plus coverage, workload samples, and the Stamina+ research contract.</p>
        <strong>Open</strong>
      </NuxtLink>

      <NuxtLink class="lab-card ready state-card" to="/lab/performance-state">
        <span>Performance state</span>
        <h2>Performance State Lab</h2>
        <p>Inspect collapse and rebound forecasts, release gates, feature layers, and completed-appearance player timelines.</p>
        <strong>Open</strong>
      </NuxtLink>
    </section>
  </main>
</template>

<style scoped>
.lab-page {
  display: grid;
  gap: 18px;
}

.lab-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.lab-card {
  min-height: 220px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 16px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 18px;
  color: var(--color-foreground);
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
  text-decoration: none;
  transition: transform 140ms ease, border-color 140ms ease, background-color 140ms ease;
}

.lab-card:hover {
  transform: translateY(-2px);
  border-color: var(--color-primary);
}

.lab-card span {
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 900;
  text-transform: uppercase;
}

.lab-card h2 {
  margin: 0;
  font-size: 22px;
}

.lab-card p {
  margin: 0;
  color: var(--color-muted-text);
  line-height: 1.45;
}

.lab-card strong {
  width: fit-content;
  border: 1px solid var(--color-primary);
  border-radius: 999px;
  padding: 6px 12px;
  color: var(--color-on-primary);
  background: var(--color-primary);
  font-size: 13px;
}

.lab-card.planned strong {
  color: var(--color-primary);
  background: transparent;
}

.leverage-card { border-radius: 0; }
.stamina-card { border-radius: 0; }
.state-card { border-radius: 0; border-color: color-mix(in srgb, var(--color-primary) 52%, var(--color-border)); }
.explorer-card { border-color: color-mix(in srgb, var(--color-primary) 52%, var(--color-border)); }

@media (max-width: 1120px) {
  .lab-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 680px) {
  .lab-grid {
    grid-template-columns: 1fr;
  }
}
</style>
