<template>
  <main class="lab-hub">
    <section class="hub-hero"><span>Batter Lab</span><h1>Study the hitter’s response.</h1><p>Research workbenches separate swing decisions, bat-to-ball execution, and damage instead of compressing them into one grade.</p></section>
    <section class="study-grid">
      <NuxtLink class="study-card" to="/batters/lab/stuff-attack"><span>Pitch quality</span><h2>Stuff Attack</h2><p>Identify hitters who attack premium fastballs and continue to create contact quality or positive run value.</p><ul><li>Stuff+ response bins</li><li>Raw and context-adjusted views</li><li>Decision × result quadrant</li></ul><strong>Open research</strong></NuxtLink>
      <article class="principles"><span>Research contract</span><h2>Three questions, kept separate.</h2><div><p><b>Decision</b> Did the hitter offer?</p><p><b>Execution</b> Did the swing make contact?</p><p><b>Damage</b> What happened after contact?</p></div></article>
    </section>
  </main>
</template>

<style scoped>
.lab-hub { max-width: 1160px; min-height: 100vh; margin: 0 auto; padding: 104px 20px 56px; }
.hub-hero, .study-card, .principles { border: 1px solid var(--color-border); border-radius: var(--radius-md); background: var(--color-surface); box-shadow: var(--shadow-sm); }
.hub-hero { padding: 30px; background: radial-gradient(circle at top right, color-mix(in srgb, var(--color-primary) 20%, transparent), transparent 35%), var(--color-surface); }
.hub-hero span, .study-card > span, .principles > span { color: var(--color-primary); font-size: 11px; font-weight: 900; letter-spacing: .1em; text-transform: uppercase; }
h1 { margin: 9px 0 0; color: var(--color-foreground); font-size: clamp(36px, 6vw, 62px); letter-spacing: -.05em; }
h2 { color: var(--color-foreground); }
p, li { color: var(--color-muted-text); line-height: 1.6; }
.study-grid { display: grid; grid-template-columns: 1.35fr .65fr; gap: 18px; margin-top: 18px; }
.study-card, .principles { padding: 24px; }
.study-card { color: inherit; text-decoration: none; transition: transform 150ms ease, border-color 150ms ease; }
.study-card:hover { border-color: var(--color-primary); transform: translateY(-2px); }
.study-card h2, .principles h2 { margin: 10px 0 0; font-size: 28px; }
.study-card ul { padding-left: 19px; }
.study-card strong { display: inline-flex; margin-top: 10px; border-radius: 999px; padding: 8px 14px; color: var(--color-on-primary); background: var(--color-primary); }
.principles div { display: grid; gap: 1px; margin-top: 18px; }
.principles p { margin: 0; border-top: 1px solid var(--color-border); padding: 13px 0; }
.principles b { display: block; color: var(--color-foreground); }
@media (max-width: 760px) { .lab-hub { padding-top: 32px; } .study-grid { grid-template-columns: 1fr; } }
@media (prefers-reduced-motion: reduce) { .study-card { transition: none; } }
</style>
