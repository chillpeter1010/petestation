<template>
  <section class="display-contract" aria-labelledby="display-contract-title">
    <header>
      <div>
        <span class="eyebrow">Shared research UI contract · v1</span>
        <h2 id="display-contract-title">Tables & plots</h2>
        <p>New research screens use one display contract. Existing screens migrate in small reviewed slices.</p>
      </div>
      <code>docs/RESEARCH_DISPLAY_CONTRACT.md</code>
    </header>

    <div class="standard-grid">
      <article>
        <span>Player tables</span>
        <strong>14 px body · 44 px headshot</strong>
        <p>Player name and photo link to the personal page. Meaningful columns sort from the header; missing values stay missing.</p>
      </article>
      <article>
        <span>Player plots</span>
        <strong>Named axes · units · sample</strong>
        <p>Player points open the personal page. Tooltips expose exact values, reliability and support; Plus charts show the 100 reference.</p>
      </article>
      <article>
        <span>Model evidence</span>
        <strong>Uncertainty before claims</strong>
        <p>Regression needs slope, R², interval and n. Color always has a text or shape fallback, and correlation is not causation.</p>
      </article>
    </div>

    <details>
      <summary>Slice 3 tag balance acceptance</summary>
      <div class="tag-contract">
        <p><b>Player roster:</b> 3–4 supported tags, membership, reliability, sample size and unassigned reason.</p>
        <p><b>Distribution:</b> sortable year × role counts, share, retention, co-occurrence and imbalance flags.</p>
        <p><b>Review flags:</b> fewer than 30 players or 2%, above 60%, or unassigned above 20%. Flags trigger review; natural imbalance is not automatically an error.</p>
      </div>
    </details>
  </section>
</template>

<style scoped>
.display-contract{max-width:1280px;margin:16px auto 0;border:1px solid #342c22;background:#10100f}.display-contract>header{display:flex;align-items:end;justify-content:space-between;gap:24px;border-bottom:1px solid #342c22;padding:22px 25px}.eyebrow{color:var(--orange,#f5a332);font-size:10px;font-weight:950;letter-spacing:.09em;text-transform:uppercase}.display-contract h2{margin:6px 0 0;font-size:27px}.display-contract header p{max-width:720px;margin:8px 0 0;color:#96928c;font-size:13px;line-height:1.5}.display-contract code{color:#9eabc1;font-size:11px}.standard-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1px;background:#2b2824}.standard-grid article{padding:18px 20px;background:#0d0d0c}.standard-grid span{display:block;color:var(--orange,#f5a332);font-size:10px;font-weight:950;letter-spacing:.06em;text-transform:uppercase}.standard-grid strong{display:block;margin-top:7px;color:#eee;font-size:16px}.standard-grid p,.tag-contract p{margin:7px 0 0;color:#918d87;font-size:13px;line-height:1.55}.display-contract details{border-top:1px solid #342c22}.display-contract summary{padding:15px 24px;color:#ddd;font-size:13px;font-weight:900;cursor:pointer}.display-contract summary:hover{background:#151411}.tag-contract{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px;border-top:1px solid #27241f;padding:17px 24px;background:#0d0d0c}.tag-contract b{color:#ddd}@media(max-width:760px){.display-contract>header{align-items:start;flex-direction:column}.standard-grid,.tag-contract{grid-template-columns:1fr}.display-contract code{overflow-wrap:anywhere}}
</style>
