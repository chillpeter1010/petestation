<template>
  <main class="lab-hub">
    <section class="hub-hero"><span>Batter Lab</span><h1>Study the hitter’s response.</h1><p>Research workbenches separate swing decisions, bat-to-ball execution, and damage instead of compressing them into one grade.</p></section>
    <section class="study-grid">
      <NuxtLink class="study-card" to="/batters/lab/stuff-attack"><span>Pitch quality</span><h2>Stuff Attack</h2><strong>Open research</strong></NuxtLink>
      <NuxtLink class="study-card timing" to="/batters/lab/swing-timing"><span>Bat-to-ball alignment</span><h2>Swing Timing</h2><strong>Open research</strong></NuxtLink>
      <NuxtLink class="study-card vision" to="/batters/lab/vision"><span>Swing visual</span><h2>Vision</h2><strong>Open research</strong></NuxtLink>
    </section>
  </main>
</template>

<style scoped>
.lab-hub { max-width: 1160px; min-height: 100vh; margin: 0 auto; padding: 104px 20px 56px; }
.hub-hero, .study-card { border: 1px solid var(--color-border); border-radius: var(--radius-md); background: var(--color-surface); box-shadow: var(--shadow-sm); }
.hub-hero { padding: 30px; background: radial-gradient(circle at top right, color-mix(in srgb, var(--color-primary) 20%, transparent), transparent 35%), var(--color-surface); }
.hub-hero span, .study-card > span { color: var(--color-primary); font-size: 11px; font-weight: 900; letter-spacing: .1em; text-transform: uppercase; }
h1 { margin: 10px 0 0; color: var(--color-foreground); font-size: clamp(36px, 5vw, 56px); font-weight: 750; line-height: 1.08; letter-spacing: -.012em; }
h2 { color: var(--color-foreground); }
p, li { color: var(--color-muted-text); line-height: 1.6; }
.study-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; margin-top: 18px; }
.study-card { min-height: 210px; padding: 24px; color: inherit; text-decoration: none; transition: transform 150ms ease, border-color 150ms ease; }
.study-card:hover { border-color: var(--color-primary); transform: translateY(-2px); }
.study-card h2 { margin: 10px 0 0; font-size: 28px; }
.study-card strong { display: inline-flex; margin-top: 10px; border-radius: 999px; padding: 8px 14px; color: var(--color-on-primary); background: var(--color-primary); }
.study-card.timing { background: radial-gradient(circle at top right, color-mix(in srgb, #8fd3f4 18%, transparent), transparent 38%), var(--color-surface); }
.study-card.vision { background: radial-gradient(circle at top right, color-mix(in srgb, #69d3c3 20%, transparent), transparent 40%), var(--color-surface); }
@media (max-width: 760px) { .lab-hub { padding-top: 32px; } .study-grid { grid-template-columns: 1fr; } }
@media (prefers-reduced-motion: reduce) { .study-card { transition: none; } }
</style>
