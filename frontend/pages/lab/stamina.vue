<template>
  <main class="stamina-lab">
    <ComparisonPageHeader
      eyebrow="Stamina research · Observed game state"
      title="Stamina Lab"
      description="Validated v1 retention plus context-adjusted family curves, cross-season model validation, and transparent Stamina v2 release gates."
      back-to="/lab"
      back-label="Pitcher Lab"
    />

    <section class="control-bar" aria-label="Stamina Lab controls">
      <div>
        <span>Research stage</span>
        <strong>Validated v1 benchmark and Stamina v2 cross-season release audit</strong>
      </div>
      <label>Season<select v-model.number="year"><option :value="2026">2026</option></select></label>
    </section>

    <p v-if="pending" class="state-panel">Loading the cleaned Stamina research dataset…</p>
    <p v-else-if="errorMessage" class="state-panel state-panel--error">{{ errorMessage }}</p>

    <template v-if="response">
      <section class="research-status" :class="`is-${response.dataset_status}`">
        <div><span>{{ response.dataset_status }}</span><h2>Single-game and season Stamina state is available</h2></div>
        <p>Data through {{ response.data_as_of || 'unknown' }} · built {{ formatDateTime(response.generated_at) }} · {{ response.model_version }}</p>
      </section>

      <section class="metric-strip" aria-label="Dataset summary">
        <article><span>Clean pitches</span><strong>{{ integer(response.dataset_rows) }}</strong><small>one row per unique pitch key</small></article>
        <article><span>Appearances</span><strong>{{ integer(response.appearances) }}</strong><small>role assigned per appearance</small></article>
        <article><span>Pitchers</span><strong>{{ integer(response.pitchers) }}</strong><small>regular-season pitchers</small></article>
        <article><span>Dual role</span><strong>{{ integer(response.dual_role_pitchers) }}</strong><small>separate SP and RP samples</small></article>
      </section>

      <section class="panel slice-one-panel">
        <header>
          <div><span>Slice 1 · League decline</span><h2>Adjusted quality retention</h2></div>
          <div class="outcome-switch" aria-label="Select outcome">
            <button type="button" :class="{ active: selectedOutcome === 'pitch_stuff_plus' }" @click="selectedOutcome = 'pitch_stuff_plus'">Stuff+</button>
            <button type="button" :class="{ active: selectedOutcome === 'location_plus_pitch' }" @click="selectedOutcome = 'location_plus_pitch'">Location+</button>
          </div>
        </header>
        <div class="method-note"><strong>{{ response.slice1.method }}</strong><p>{{ response.slice1.interpretation }}</p></div>
        <div class="summary-grid">
          <article v-for="summary in selectedSummaries" :key="`${summary.role}-${summary.dimension}`" :class="`is-${summary.direction}`">
            <span>{{ summary.role }} · {{ dimensionLabel(summary.dimension) }}</span>
            <strong>{{ signed(summary.adjusted_delta) }}</strong>
            <p>{{ summary.reference_bucket }} → {{ summary.terminal_bucket }}</p>
            <small>95% CI {{ signed(summary.ci_low) }} to {{ signed(summary.ci_high) }} · {{ summary.direction }}</small>
          </article>
        </div>
        <div class="curve-grid">
          <article v-for="chart in curveCharts" :key="`${chart.role}-${chart.dimension}`" class="curve-card">
            <header><div><span>{{ chart.role }}</span><h3>{{ dimensionLabel(chart.dimension) }}</h3></div><small>Adjusted Plus-point delta · 95% CI</small></header>
            <svg viewBox="0 0 720 280" role="img" :aria-label="`${chart.role} ${dimensionLabel(chart.dimension)} ${outcomeLabel} curve`">
              <line x1="58" x2="690" :y1="chartY(0, chart.range)" :y2="chartY(0, chart.range)" class="zero-line" />
              <text x="12" :y="chartY(0, chart.range) + 5" class="axis-label">0</text>
              <polyline :points="polyline(chart.points, chart.range)" class="curve-line" />
              <g v-for="(point, index) in chart.points" :key="point.bucket">
                <line :x1="chartX(index, chart.points.length)" :x2="chartX(index, chart.points.length)" :y1="chartY(point.ci_low, chart.range)" :y2="chartY(point.ci_high, chart.range)" class="ci-line" />
                <line :x1="chartX(index, chart.points.length) - 6" :x2="chartX(index, chart.points.length) + 6" :y1="chartY(point.ci_low, chart.range)" :y2="chartY(point.ci_low, chart.range)" class="ci-line" />
                <line :x1="chartX(index, chart.points.length) - 6" :x2="chartX(index, chart.points.length) + 6" :y1="chartY(point.ci_high, chart.range)" :y2="chartY(point.ci_high, chart.range)" class="ci-line" />
                <circle :cx="chartX(index, chart.points.length)" :cy="chartY(point.adjusted_delta, chart.range)" r="6" class="curve-dot" />
                <text :x="chartX(index, chart.points.length)" :y="chartY(point.adjusted_delta, chart.range) - 13" class="value-label">{{ signed(point.adjusted_delta) }}</text>
                <text :x="chartX(index, chart.points.length)" y="260" class="bucket-label">{{ point.bucket }}</text>
              </g>
            </svg>
            <div class="curve-table table-scroll"><table><thead><tr><th>Window</th><th>Adjusted Δ</th><th>95% CI</th><th>Pitches</th><th>Games</th><th>Pitchers</th></tr></thead><tbody>
              <tr v-for="point in chart.points" :key="point.bucket"><td><strong>{{ point.bucket }}</strong></td><td>{{ point.reference ? 'Reference' : signed(point.adjusted_delta) }}</td><td>{{ point.reference ? '—' : `${signed(point.ci_low)} to ${signed(point.ci_high)}` }}</td><td>{{ integer(point.pitches) }}</td><td>{{ integer(point.appearances) }}</td><td>{{ integer(point.pitchers) }}</td></tr>
            </tbody></table></div>
          </article>
        </div>
        <div class="analysis-warnings"><p v-for="warning in response.slice1.warnings" :key="warning">{{ warning }}</p></div>
      </section>

      <section class="panel slice-two-panel">
        <header>
          <div><span>Slice 2 · Selection correction</span><h2>Does the late-window rebound survive correction?</h2></div>
          <span class="status-chip is-ready">research result</span>
        </header>
        <div class="method-note"><strong>{{ response.slice2.method }}</strong><p>Every later window is compared with the same appearance's first window. Stabilized observation weights re-balance pitchers who were more or less likely to remain in the game.</p></div>
        <div class="correction-grid">
          <article v-for="row in selectedExtremeComparison" :key="`${row.role}-${row.outcome}`">
            <div><span>{{ row.role }} · {{ row.target_bucket }}</span><b :class="interpretCorrection(row.slice1_adjusted_delta, row.weighted_paired_delta).className">{{ interpretCorrection(row.slice1_adjusted_delta, row.weighted_paired_delta).label }}</b></div>
            <h3>{{ row.outcome_label }}</h3>
            <dl><div><dt>Slice 1 adjusted</dt><dd>{{ signed(row.slice1_adjusted_delta) }}</dd></div><div><dt>Same-game paired</dt><dd>{{ signed(row.survivor_paired_delta) }}</dd></div><div><dt>Selection weighted</dt><dd>{{ signed(row.weighted_paired_delta) }}</dd></div></dl>
          </article>
        </div>
        <div class="bias-layout">
          <article>
            <header><div><span>Appearance correction</span><h3>Naïve survivor vs weighted paired Δ</h3></div></header>
            <div class="table-scroll"><table><thead><tr><th>Role / window</th><th>Games</th><th>Pitchers</th><th>Survivor Δ</th><th>Weighted Δ</th><th>Weighted 95% CI</th></tr></thead><tbody>
              <tr v-for="row in selectedAppearanceCorrections" :key="`${row.role}-${row.target_bucket}`"><td><strong>{{ row.role }} · {{ row.reference_bucket }} → {{ row.target_bucket }}</strong></td><td>{{ integer(row.appearances) }}</td><td>{{ integer(row.pitchers) }}</td><td>{{ signed(row.unweighted_delta) }}</td><td>{{ signed(row.weighted_delta) }}</td><td>{{ signed(row.weighted_ci_low) }} to {{ signed(row.weighted_ci_high) }}</td></tr>
            </tbody></table></div>
          </article>
          <article>
            <header><div><span>Weight diagnostics</span><h3>Can the observed selection be modeled?</h3></div></header>
            <div class="table-scroll"><table><thead><tr><th>Role / window</th><th>Reach</th><th>AUC</th><th>Effective N</th><th>Max weight</th></tr></thead><tbody>
              <tr v-for="row in response.slice2.selection_models" :key="`${row.role}-${row.bucket}`"><td><strong>{{ row.role }} · {{ row.bucket }}</strong></td><td>{{ pct(row.marginal_reach_pct) }}</td><td>{{ row.auc.toFixed(3) }}</td><td>{{ integer(Math.round(row.effective_sample_size)) }}</td><td>{{ row.max_weight.toFixed(2) }}</td></tr>
            </tbody></table></div>
          </article>
        </div>
        <details class="sensitivity-details"><summary>Show season fixed-cohort and times-through-order sensitivity tables</summary>
          <div class="bias-layout">
            <article><header><div><span>Season survivor cohort</span><h3>Same pitchers across workload windows</h3></div></header><div class="table-scroll"><table><thead><tr><th>Role / window</th><th>Pitchers</th><th>Paired Δ</th><th>95% CI</th></tr></thead><tbody>
              <tr v-for="row in selectedSeasonCorrections" :key="`${row.role}-${row.target_bucket}`"><td><strong>{{ row.role }} · {{ row.reference_bucket }} → {{ row.target_bucket }}</strong></td><td>{{ integer(row.pitchers) }}</td><td>{{ signed(row.paired_delta) }}</td><td>{{ signed(row.ci_low) }} to {{ signed(row.ci_high) }}</td></tr>
            </tbody></table></div></article>
            <article><header><div><span>TTO sensitivity</span><h3>Weighted result by target-window TTO</h3></div></header><div class="table-scroll"><table><thead><tr><th>Role / window</th><th>TTO</th><th>Games</th><th>Weighted Δ</th><th>95% CI</th></tr></thead><tbody>
              <tr v-for="row in selectedTtoCorrections" :key="`${row.role}-${row.target_bucket}-${row.tto}`"><td><strong>{{ row.role }} · {{ row.target_bucket }}</strong></td><td>{{ row.tto }}</td><td>{{ integer(row.appearances) }}</td><td>{{ signed(row.weighted_delta) }}</td><td>{{ signed(row.ci_low) }} to {{ signed(row.ci_high) }}</td></tr>
            </tbody></table></div></article>
          </div>
        </details>
        <div class="analysis-warnings"><p v-for="warning in response.slice2.warnings" :key="warning">{{ warning }}</p></div>
      </section>

      <section class="panel slice-three-panel">
        <header>
          <div><span>Slice 3 · Pitcher heterogeneity</span><h2>Partially pooled personal retention slopes</h2></div>
          <div class="slice-three-controls" aria-label="Pitcher slope filters">
            <div class="outcome-switch"><button v-for="role in pitcherRoles" :key="role" type="button" :class="{ active: selectedRole === role }" @click="selectedRole = role">{{ role }}</button></div>
            <input v-model.trim="pitcherSearch" type="search" placeholder="Search pitcher or team" aria-label="Search pitcher or team">
          </div>
        </header>
        <div class="method-note"><strong>{{ response.slice3.method }}</strong><p>Higher slope means better quality retention. The estimate is shrunk toward the role average when a pitcher has fewer or noisier matched appearances.</p><p><b>SP and RP are separate models.</b> Reliability measures sampling precision within that role, not pitcher quality; starters usually have more matched pitches and longer within-game spans, so their reliability is expected to be higher.</p></div>
        <div class="personal-summary-grid">
          <article v-if="selectedPrior"><span>Eligible pitchers</span><strong>{{ integer(selectedPrior.eligible_pitchers) }}</strong><p>of {{ integer(selectedPrior.candidate_pitchers) }} candidates · minimum {{ selectedPrior.minimum_appearances }} appearances</p></article>
          <article v-if="selectedPrior"><span>League slope</span><strong>{{ signed(selectedPrior.league_slope) }}</strong><p>Plus points per {{ selectedPrior.unit_pitches }} pitches</p></article>
          <article v-if="selectedPrior"><span>Between-pitcher SD</span><strong>{{ selectedPrior.between_pitcher_sd.toFixed(2) }}</strong><p>Empirical heterogeneity after sampling error</p></article>
          <article v-if="selectedValidation"><span>Split-half repeatability</span><strong>{{ selectedValidation.spearman_correlation === null ? '—' : selectedValidation.spearman_correlation.toFixed(2) }}</strong><p>{{ selectedValidation.status }} · {{ integer(selectedValidation.pitchers) }} pitchers · Spearman ρ</p></article>
        </div>
        <div class="personal-table table-scroll">
          <table><thead><tr><th>#</th><th>Pitcher</th><th>Team</th><th>Posterior slope</th><th>95% CI</th><th>Raw slope</th><th>Reliability</th><th>Games</th><th>Matched pitches</th><th>Assessment</th></tr></thead><tbody>
            <tr v-for="row in selectedPitcherRows" :key="`${row.role}-${row.outcome}-${row.pitcher_id}`">
              <td>{{ row.rank }}</td>
              <td><NuxtLink class="pitcher-cell" :to="pitcherLink(row)"><MlbPlayerHeadshot :player-id="row.pitcher_id" :name="row.pitcher_name" :size="38" :source-width="160" decorative shape="circle" /><span><strong>{{ row.pitcher_name }}</strong><small>{{ row.role }} · {{ row.outcome_label }}</small></span></NuxtLink></td>
              <td>{{ row.team || '—' }}</td><td><strong>{{ signed(row.posterior_slope) }}</strong><small> / {{ row.unit_pitches }} pitches</small></td><td>{{ signed(row.ci_low) }} to {{ signed(row.ci_high) }}</td><td>{{ signed(row.raw_slope) }}</td><td><span class="reliability-chip" :class="`is-${row.reliability_label}`">{{ reliabilityPct(row.reliability) }} · {{ row.reliability_label }}</span></td><td>{{ integer(row.appearances) }}</td><td>{{ integer(row.matched_pitches) }}</td><td>{{ retentionLabel(row.retention_band) }}</td>
            </tr>
          </tbody></table>
        </div>
        <p v-if="!selectedPitcherRows.length" class="empty-row">No eligible pitchers match this search.</p>
        <div class="analysis-warnings"><p v-for="warning in response.slice3.warnings" :key="warning">{{ warning }}</p></div>
      </section>

      <section class="panel slice-four-panel">
        <header><div><span>Slice 4A–E · Recovery & season load</span><h2>Does prior workload predict the next appearance?</h2></div><div class="slice-four-controls"><div class="outcome-switch"><button v-for="role in pitcherRoles" :key="`workload-${role}`" type="button" :class="{ active: selectedRole === role }" @click="selectedRole = role">{{ role }}</button></div><div class="outcome-switch"><button type="button" :class="{ active: selectedOutcome === 'pitch_stuff_plus' }" @click="selectedOutcome = 'pitch_stuff_plus'">Stuff+</button><button type="button" :class="{ active: selectedOutcome === 'location_plus_pitch' }" @click="selectedOutcome = 'location_plus_pitch'">Location+</button></div></div></header>
        <div class="method-note"><strong>{{ response.slice4.method }}</strong><p>All predictors stop before the current appearance. Positive estimates mean better next-appearance quality or retention; negative estimates mean decline.</p></div>

        <article class="slice-stage">
          <header><div><span>4A · Lagged workload</span><h3>Cross-role physiological history</h3></div><p>SP/RP models remain separate, but workload never resets when a pitcher changes role.</p></header>
          <div class="audit-strip"><div v-for="item in response.slice4.workload_audit" :key="item.field"><span>{{ item.feature }}</span><strong>{{ pct(item.coverage_pct) }}</strong><small>{{ item.lagged_only ? 'prior appearances only' : 'review required' }}</small></div></div>
        </article>

        <div class="slice-four-grid">
          <article v-for="stage in workloadEffectStages" :key="stage.key" class="slice-stage"><header><div><span>{{ stage.eyebrow }}</span><h3>{{ stage.title }}</h3></div></header><div class="table-scroll"><table><thead><tr><th>Feature</th><th>Estimate</th><th>95% CI</th><th>Unit</th><th>Signal</th></tr></thead><tbody>
            <tr v-for="row in stage.rows" :key="row.feature"><td><strong>{{ row.feature_label }}</strong></td><td>{{ signed3(row.estimate) }}</td><td>{{ signed3(row.ci_low) }} to {{ signed3(row.ci_high) }}</td><td>{{ row.unit }}</td><td><span class="status-chip" :class="row.significant ? 'is-partial' : ''">{{ row.significant ? 'detected' : 'uncertain' }}</span></td></tr>
          </tbody></table></div></article>
        </div>

        <article class="slice-stage feature-influence-stage">
          <header><div><span>4B–C · Standardized influence</span><h3>Which observed workload features move the model most?</h3></div><p>Absolute strength is normalized within the selected role, outcome, and endpoint model.</p></header>
          <div class="method-note"><strong>This is not the Stamina+ formula.</strong><p>Standardized Δ is the modeled Plus-point change for a one-within-pitcher-SD feature change. Correlated workload fields can share signal, and these associations are not causal.</p></div>
          <div class="table-scroll"><table><thead><tr><th>Endpoint</th><th>Feature</th><th>Standardized Δ</th><th>Relative strength</th><th>Raw unit estimate</th><th>Signal</th></tr></thead><tbody>
            <tr v-for="row in selectedFeatureInfluence" :key="`${row.endpoint}-${row.feature}`"><td><strong>{{ endpointLabel(row.endpoint) }}</strong></td><td>{{ row.feature_label }}</td><td :class="Number(row.standardized_effect || 0) >= 0 ? 'positive-value' : 'negative-value'">{{ signed3(Number(row.standardized_effect || 0)) }}</td><td><div class="strength-cell"><span><i :style="{ width: `${row.relative_strength_pct || 0}%` }" /></span><b>{{ nullableFixed(row.relative_strength_pct, 1) }}%</b></div></td><td>{{ signed3(row.estimate) }} · {{ row.unit }}</td><td><span class="status-chip" :class="row.significant ? 'is-partial' : ''">{{ row.significant ? 'detected' : 'uncertain' }}</span></td></tr>
          </tbody></table></div>
        </article>

        <article class="slice-stage">
          <header><div><span>4D · Chronic season load</span><h3>Cumulative pitches separated from calendar progression</h3></div><p>Pitcher fixed effects plus linear and curved calendar terms.</p></header>
          <div class="table-scroll"><table><thead><tr><th>Endpoint</th><th>Feature</th><th>Estimate</th><th>95% CI</th><th>Unit</th><th>Signal</th></tr></thead><tbody>
            <tr v-for="row in selectedSeasonEffects" :key="`${row.endpoint}-${row.feature}`"><td><strong>{{ endpointLabel(row.endpoint) }}</strong></td><td>{{ row.feature_label }}</td><td>{{ signed3(row.estimate) }}</td><td>{{ signed3(row.ci_low) }} to {{ signed3(row.ci_high) }}</td><td>{{ row.unit }}</td><td><span class="status-chip" :class="row.significant ? 'is-partial' : ''">{{ row.significant ? 'detected' : 'uncertain' }}</span></td></tr>
          </tbody></table></div>
        </article>

        <article class="slice-stage validation-stage">
          <header><div><span>4E · Out-of-time validation</span><h3>Can workload predict unseen appearances?</h3></div><p>RMSE improvement is measured against a train-period mean baseline.</p></header>
          <div class="validation-grid">
            <div v-for="row in selectedTimeValidation" :key="`${row.validation}-${row.endpoint}`"><span>2026 {{ endpointLabel(row.endpoint || '') }}</span><strong>{{ validationGain(row) }}</strong><p>{{ row.status }} · corr {{ nullableFixed(row.correlation, 3) }}</p><small>{{ integer(row.train_appearances || 0) }} train · {{ integer(row.test_appearances || 0) }} test</small></div>
            <div v-for="row in selectedCrossSeasonValidation" :key="`${row.validation}-${row.endpoint || 'status'}`"><span>2025 → 2026 {{ endpointLabel(row.endpoint || '') }}</span><strong>{{ validationGain(row) }}</strong><p>{{ row.status }}<template v-if="row.correlation !== null && row.correlation !== undefined"> · corr {{ nullableFixed(row.correlation, 3) }}</template></p><small v-if="row.source_coverage_pct !== null && row.source_coverage_pct !== undefined">Historical coverage {{ pct(row.source_coverage_pct) }} · {{ row.reason }}</small><small v-else>{{ row.reason || `${integer(row.train_appearances || 0)} train · ${integer(row.test_appearances || 0)} test` }}</small></div>
          </div>
        </article>
        <div class="analysis-warnings"><p v-for="warning in response.slice4.warnings" :key="warning">{{ warning }}</p></div>
      </section>

      <section v-if="response.slice5" class="panel slice-five-panel">
        <header>
          <div><span>Slice 5 · Retention trait</span><h2>{{ staminaScopeLabel }}</h2></div>
          <span class="status-chip" :class="staminaScope === 'trait' && response.slice5.publication_status === 'validated' ? 'is-ready' : 'is-partial'">{{ staminaScope === 'trait' ? response.slice5.publication_status : 'season estimate' }}</span>
        </header>
        <div class="method-note">
          <strong>{{ staminaScope === 'trait' ? response.slice5.method : 'Single-season view rescales that season’s Slice 3 posterior Stuff+ retention slope within role; it does not borrow the second season.' }}</strong>
          <p>100 is the role average. Higher scores mean better within-appearance Stuff+ retention, not more innings, lower injury risk, or a next-game readiness forecast.</p>
        </div>
        <div v-if="staminaScope === 'trait'" class="slice-five-summary">
          <article v-if="selectedSlice5Prior"><span>{{ selectedRole }} pool</span><strong>{{ integer(selectedSlice5Prior.pitchers) }}</strong><p>{{ integer(selectedSlice5Prior.two_season_pitchers) }} pitchers have both seasons · {{ selectedSlice5Prior.unit_pitches }}-pitch unit</p></article>
          <article v-if="selectedSlice5Validation"><span>2025 → 2026 rank</span><strong>{{ nullableFixed(selectedSlice5Validation.spearman_correlation, 3) }}</strong><p>{{ selectedSlice5Validation.common_pitchers }} common · {{ selectedSlice5Validation.reliable_pitchers }} reliable</p></article>
          <article v-if="selectedSlice5Validation"><span>RMSE improvement</span><strong>{{ validationGain(selectedSlice5Validation) }}</strong><p>against the role-average slope baseline</p></article>
          <article v-if="selectedSlice5Validation"><span>Release gate</span><strong>{{ selectedSlice5Validation.status }}</strong><p>{{ passedGateCount(selectedSlice5Validation.gates) }} / {{ Object.keys(selectedSlice5Validation.gates).length }} gates passed</p></article>
        </div>
        <div v-else-if="selectedSeasonPrior" class="slice-five-summary">
          <article><span>{{ selectedSeasonPrior.season }} {{ selectedRole }} pool</span><strong>{{ integer(selectedSeasonPrior.eligible_pitchers) }}</strong><p>eligible single-season pitchers</p></article>
          <article><span>League slope</span><strong>{{ signed(selectedSeasonPrior.league_slope) }}</strong><p>Plus points per {{ selectedSeasonPrior.unit_pitches }} pitches</p></article>
          <article><span>Between-pitcher SD</span><strong>{{ selectedSeasonPrior.between_pitcher_sd.toFixed(2) }}</strong><p>used to scale 100 ± 10</p></article>
          <article><span>Split-half repeatability</span><strong>{{ nullableFixed(selectedSeasonPrior.split_half_spearman, 3) }}</strong><p>{{ selectedSeasonPrior.split_half_status }} · single-season stability</p></article>
        </div>
        <div v-if="staminaScope === 'trait' && selectedSlice5Validation" class="gate-grid">
          <div v-for="(passed, gate) in selectedSlice5Validation.gates" :key="gate"><span>{{ gate }}</span><b :class="passed ? 'is-pass' : 'is-hold'">{{ passed ? 'pass' : 'hold' }}</b></div>
        </div>
        <div class="slice-three-controls slice-five-controls" aria-label="Stamina Plus filters">
          <label>Score view<select v-model="staminaScope"><option value="trait">2025–2026 Trait</option><option value="2026">2026 Season</option><option value="2025">2025 Season</option></select></label>
          <div class="outcome-switch"><button v-for="role in pitcherRoles" :key="`stamina-${role}`" type="button" :class="{ active: selectedRole === role }" @click="selectedRole = role">{{ role }}</button></div>
          <input v-model.trim="staminaSearch" type="search" placeholder="Search pitcher or team" aria-label="Search Stamina Plus pitcher or team">
          <label><input v-model="qualifiedOnly" type="checkbox"> Qualified only</label>
        </div>
        <div class="personal-table table-scroll">
          <table><thead><tr><th>#</th><th>Pitcher</th><th>Team</th><th>Stamina+</th><th>95% CI</th><th>Retention edge</th><th>Reliability</th><th>Seasons</th><th>Games</th><th>Matched pitches</th><th>Sample</th></tr></thead><tbody>
            <tr v-for="row in selectedStaminaRows" :key="`${row.role}-${row.pitcher_id}`">
              <td>{{ row.rank }}</td>
              <td><NuxtLink class="pitcher-cell" :to="pitcherLink(row)"><MlbPlayerHeadshot :player-id="row.pitcher_id" :name="row.pitcher_name" :size="38" :source-width="160" decorative shape="circle" /><span><strong>{{ row.pitcher_name }}</strong><small>{{ row.role }} · {{ row.publication_status }}</small></span></NuxtLink></td>
              <td>{{ row.team || '—' }}</td><td><strong class="stamina-score">{{ row.stamina_plus.toFixed(1) }}</strong></td><td>{{ row.ci_low.toFixed(1) }} to {{ row.ci_high.toFixed(1) }}</td><td>{{ signed(row.retention_advantage) }}<small> / {{ row.unit_pitches }} pitches</small></td><td><span class="reliability-chip" :class="`is-${row.reliability_label}`">{{ reliabilityPct(row.reliability) }} · {{ row.reliability_label }}</span></td><td>{{ row.seasons }}</td><td>{{ integer(row.appearances) }}</td><td>{{ integer(row.matched_pitches) }}</td><td><span class="status-chip" :class="row.sample_label === 'qualified' ? 'is-ready' : 'is-partial'">{{ row.sample_label }}</span></td>
            </tr>
          </tbody></table>
        </div>
        <p v-if="!selectedStaminaRows.length" class="empty-row">No Stamina+ rows match these filters.</p>
        <div class="analysis-warnings"><p v-for="warning in response.slice5.warnings" :key="warning">{{ warning }}</p></div>
      </section>

      <section v-if="response.slice6" class="panel slice-six-panel">
        <header><div><span>Slice 6 · Per-pitch state</span><h2>Cached hover context</h2></div><span class="status-chip" :class="`is-${response.slice6.status}`">{{ response.slice6.status }}</span></header>
        <div class="method-note"><strong>{{ response.slice6.method }}</strong><p>The fixed trait, expected retention path and observed pitch scores are kept separate on Pitcher Personal movement and location hovers.</p></div>
        <div class="personal-summary-grid">
          <article><span>Pitch rows</span><strong>{{ integer(response.slice6.pitch_rows) }}</strong><p>Current Stamina pitch cache</p></article>
          <article><span>Trait coverage</span><strong>{{ pct(response.slice6.trait_coverage_pct) }}</strong><p>{{ integer(response.slice6.trait_rows) }} pitches linked to a pitcher-role trait</p></article>
          <article><span>Expected Stuff+ coverage</span><strong>{{ pct(response.slice6.expected_coverage_pct) }}</strong><p>{{ integer(response.slice6.expected_rows) }} pitches have a same-game, same-pitch-type early baseline</p></article>
          <article><span>Interpretation</span><strong>3 layers</strong><p>Trait · expected path · observed pitch</p></article>
        </div>
        <div class="analysis-warnings"><p v-for="warning in response.slice6.warnings" :key="warning">{{ warning }}</p></div>
      </section>

      <section v-if="response.slice7" class="panel slice-seven-panel">
        <header><div><span>Slice 7 · Family & target audit</span><h2>Ceiling-neutral v2 preregistration</h2></div><span class="status-chip" :class="`is-${response.slice7.status}`">{{ response.slice7.status }}</span></header>
        <div class="method-note"><strong>{{ response.slice7.method }}</strong><p>{{ response.slice7.scope }} · {{ response.slice7.contract_version }}</p></div>
        <div class="personal-summary-grid">
          <article><span>Classified pitches</span><strong>{{ integer(response.slice7.classified_pitches) }}</strong><p>{{ pct(response.slice7.classified_coverage_pct) }} of SP pitches</p></article>
          <article><span>Classified Stuff+</span><strong>{{ pct(response.slice7.classified_stuff_coverage_pct) }}</strong><p>Missing values remain null</p></article>
          <article><span>v1 audit pitchers</span><strong>{{ integer(response.slice7.pitchers_with_v1_audit) }}</strong><p>SP with early, late and v1 trait data</p></article>
          <article><span>FO taxonomy</span><strong>Offspeed</strong><p>Locked before v2 modeling</p></article>
        </div>
        <article class="slice-stage">
          <header><div><span>Family coverage & usage</span><h3>Early versus late repertoire selection</h3></div><p>Usage shifts are diagnostics only; late usage will never set the overall score weight.</p></header>
          <div class="table-scroll"><table><thead><tr><th>Family</th><th>Pitch types</th><th>Pitches</th><th>Games</th><th>Pitchers</th><th>Stuff+</th><th>Velocity</th><th>Early usage</th><th>Late usage</th><th>Late Δ</th></tr></thead><tbody>
            <tr v-for="row in response.slice7.family_coverage" :key="row.family"><td><strong>{{ row.family }}</strong></td><td>{{ row.pitch_types.join(' / ') }}</td><td>{{ integer(row.pitches) }}</td><td>{{ integer(row.appearances) }}</td><td>{{ integer(row.pitchers) }}</td><td>{{ pct(row.stuff_coverage_pct) }}</td><td>{{ pct(row.velocity_coverage_pct) }}</td><td>{{ pct(row.early_usage_pct) }}</td><td>{{ pct(row.late_usage_pct) }}</td><td>{{ signed(row.late_usage_delta_pp) }} pp</td></tr>
          </tbody></table></div>
        </article>
        <div class="slice-four-grid">
          <article class="slice-stage"><header><div><span>Bias audit</span><h3>Rank associations</h3></div></header><div class="table-scroll"><table><thead><tr><th>Diagnostic</th><th>SP</th><th>Spearman</th></tr></thead><tbody>
            <tr v-for="row in response.slice7.bias_correlations" :key="row.key"><td><strong>{{ row.label }}</strong></td><td>{{ integer(row.pitchers) }}</td><td>{{ nullableFixed(row.spearman, 3) }}</td></tr>
          </tbody></table></div></article>
          <article class="slice-stage"><header><div><span>Ceiling quartiles</span><h3>Descriptive early / late quality</h3></div></header><div class="table-scroll"><table><thead><tr><th>Early band</th><th>SP</th><th>Early</th><th>Late</th><th>Naïve Δ</th><th>v1</th></tr></thead><tbody>
            <tr v-for="row in response.slice7.ceiling_bands" :key="row.band"><td><strong>{{ row.band }}</strong></td><td>{{ integer(row.pitchers) }}</td><td>{{ row.early_stuff.toFixed(2) }}</td><td>{{ row.late_stuff.toFixed(2) }}</td><td>{{ signed(row.naive_delta) }}</td><td>{{ row.mean_stamina_plus.toFixed(1) }}</td></tr>
          </tbody></table></div></article>
        </div>
        <div class="slice-four-grid">
          <article class="slice-stage"><header><div><span>v2 targets</span><h3>Locked before modeling</h3></div></header><div class="contract-list"><div v-for="row in response.slice7.targets" :key="row.key"><strong>{{ row.label }}</strong><p>{{ row.definition }}</p><small>{{ row.purpose }}</small></div></div></article>
          <article class="slice-stage"><header><div><span>Release gates</span><h3>2025 → 2026 holdout</h3></div></header><div class="contract-list"><div v-for="row in response.slice7.release_gates" :key="row.key"><strong>{{ row.scope }} · {{ row.key }}</strong><p>{{ row.threshold }}</p></div></div></article>
        </div>
        <details class="sensitivity-details"><summary>Show missing and unclassified pitch audit</summary><div class="bias-layout"><article><div class="table-scroll"><table><thead><tr><th>Check</th><th>Pitches</th><th>Share</th></tr></thead><tbody><tr v-for="row in response.slice7.missing_audit" :key="row.key"><td><strong>{{ row.label }}</strong></td><td>{{ integer(row.pitches) }}</td><td>{{ pct(row.pct) }}</td></tr></tbody></table></div></article><article><div class="table-scroll"><table><thead><tr><th>Unclassified type</th><th>Pitches</th></tr></thead><tbody><tr v-for="row in response.slice7.unclassified_pitch_types" :key="row.pitch_type"><td><strong>{{ row.pitch_type }}</strong></td><td>{{ integer(row.pitches) }}</td></tr><tr v-if="!response.slice7.unclassified_pitch_types.length"><td colspan="2">None</td></tr></tbody></table></div></article></div></details>
        <div class="analysis-warnings"><p v-for="warning in response.slice7.warnings" :key="warning">{{ warning }}</p></div>
      </section>

      <section v-if="response.slice8" class="panel slice-eight-panel">
        <header><div><span>Slice 8 · Appearance fatigue curves</span><h2>Context-adjusted family trajectories</h2></div><span class="status-chip" :class="`is-${response.slice8.status}`">{{ response.slice8.status }}</span></header>
        <div class="method-note"><strong>{{ response.slice8.method }}</strong><p>{{ response.slice8.context_controls.join(' · ') }} · within-context R² {{ response.slice8.context_r_squared.toFixed(4) }}</p></div>
        <div class="personal-summary-grid">
          <article><span>Pitch curve cache</span><strong>{{ integer(response.slice8.pitch_curve_rows) }}</strong><p>Raw pitch points; MA5 starts on the fifth same-family pitch</p></article>
          <article><span>Appearance curves</span><strong>{{ integer(response.slice8.appearance_curve_rows) }}</strong><p>Family and fixed-weight Overall windows</p></article>
          <article><span>Prior weights</span><strong>{{ integer(response.slice8.prior_weight_pitchers) }}</strong><p>Pitchers using previous-season repertoire</p></article>
          <article><span>Early weights</span><strong>{{ integer(response.slice8.early_weight_appearances) }}</strong><p>Appearance fallbacks using pitches 1–20</p></article>
        </div>
        <article class="slice-stage"><header><div><span>Curve view</span><h3>League research trajectory</h3></div><div class="outcome-switch"><button v-for="family in v2Families" :key="family" type="button" :class="{ active: selectedV2Family === family }" @click="selectedV2Family = family">{{ family }}</button></div></header>
          <div class="table-scroll"><table><thead><tr><th>Pitch window</th><th>Adjusted Stuff+</th><th>Raw Stuff+</th><th>Trailing MA5</th><th>Pitches</th><th>Games</th><th>Pitchers</th><th v-if="selectedV2Family === 'Overall'">Overall coverage</th></tr></thead><tbody>
            <tr v-for="row in selectedV2Curves" :key="`${row.family}-${row.bucket}`"><td><strong>{{ row.bucket }}</strong></td><td>{{ nullableFixed(row.adjusted_stuff, 3) }}</td><td>{{ nullableFixed(row.raw_stuff, 3) }}</td><td>{{ nullableFixed(row.trailing_ma5, 3) }}</td><td>{{ integer(row.pitches) }}</td><td>{{ integer(row.appearances) }}</td><td>{{ integer(row.pitchers) }}</td><td v-if="selectedV2Family === 'Overall'">{{ row.fixed_weight_coverage_pct === null || row.fixed_weight_coverage_pct === undefined ? '—' : pct(row.fixed_weight_coverage_pct) }}</td></tr>
          </tbody></table></div>
        </article>
        <article class="slice-stage"><header><div><span>MA5 support</span><h3>Family smoothing coverage</h3></div><p>Coverage counts only points with five prior same-family observations in the same appearance.</p></header><div class="table-scroll"><table><thead><tr><th>Family</th><th>Pitches</th><th>Games</th><th>Pitchers</th><th>MA5 rows</th><th>MA5 coverage</th></tr></thead><tbody>
          <tr v-for="row in response.slice8.family_audit" :key="row.family"><td><strong>{{ row.family }}</strong></td><td>{{ integer(row.pitches) }}</td><td>{{ integer(row.appearances) }}</td><td>{{ integer(row.pitchers) }}</td><td>{{ integer(row.ma5_rows) }}</td><td>{{ pct(row.ma5_coverage_pct) }}</td></tr>
        </tbody></table></div></article>
        <div class="analysis-warnings"><p v-for="warning in response.slice8.warnings" :key="warning">{{ warning }}</p></div>
      </section>

      <section v-if="response.slice9" class="panel slice-nine-panel">
        <header><div><span>Slice 9 · Model challengers</span><h2>Which ceiling-neutral model earns a holdout?</h2></div><span class="status-chip" :class="`is-${response.slice9.status}`">{{ response.slice9.status }}</span></header>
        <div class="method-note"><strong>{{ response.slice9.method }}</strong><p>Development split {{ response.slice9.development_split_date || 'unavailable' }} · {{ response.slice9.selection_weighting }}</p></div>
        <article class="slice-stage"><header><div><span>Chronological development test</span><h3>Raw-pitch prediction comparison</h3></div><p>Improvement is relative to carrying the exact pitch type’s early-game quality forward.</p></header><div class="table-scroll"><table><thead><tr><th>Model</th><th>Role</th><th>Train pitches</th><th>Test pitches</th><th>RMSE</th><th>MAE</th><th>Correlation</th><th>RMSE gain</th><th>Status</th></tr></thead><tbody>
          <tr v-for="row in response.slice9.comparisons" :key="row.model"><td><strong>{{ row.model }}</strong></td><td>{{ row.kind }}</td><td>{{ integer(row.train_pitches) }}</td><td>{{ integer(row.test_pitches) }}</td><td>{{ row.rmse.toFixed(3) }}</td><td>{{ row.mae.toFixed(3) }}</td><td>{{ nullableFixed(row.correlation, 3) }}</td><td>{{ row.rmse_improvement_pct > 0 ? '+' : '' }}{{ row.rmse_improvement_pct.toFixed(2) }}%</td><td><span class="status-chip" :class="row.status === 'improves' ? 'is-ready' : 'is-partial'">{{ row.status }}</span></td></tr>
        </tbody></table></div></article>
        <div class="slice-four-grid">
          <article class="slice-stage"><header><div><span>Hierarchical slopes</span><h3>{{ integer(response.slice9.hierarchical_estimate_rows) }} pitcher-family estimates</h3></div></header><div class="table-scroll"><table><thead><tr><th>Family</th><th>Eligible / candidate</th><th>League slope</th><th>Between SD</th><th>Median reliability</th></tr></thead><tbody>
            <tr v-for="row in response.slice9.family_priors" :key="row.family"><td><strong>{{ row.family }}</strong></td><td>{{ integer(row.eligible_pitchers) }} / {{ integer(row.candidate_pitchers) }}</td><td>{{ signed3(row.league_slope) }}</td><td>{{ row.between_pitcher_sd.toFixed(3) }}</td><td>{{ reliabilityPct(row.median_reliability) }}</td></tr>
          </tbody></table></div></article>
          <article class="slice-stage"><header><div><span>ML challenger</span><h3>Permutation influence</h3></div><p>Predictive importance only; not a causal contribution.</p></header><div class="table-scroll"><table><thead><tr><th>Feature</th><th>Importance</th><th>Relative strength</th></tr></thead><tbody>
            <tr v-for="row in response.slice9.challenger_influence" :key="row.feature"><td><strong>{{ row.feature }}</strong></td><td>{{ row.importance.toFixed(4) }}</td><td><div class="strength-cell"><span><i :style="{ width: `${row.relative_strength_pct}%` }" /></span><b>{{ row.relative_strength_pct.toFixed(1) }}%</b></div></td></tr>
          </tbody></table></div></article>
        </div>
        <div class="analysis-warnings"><p v-for="warning in response.slice9.warnings" :key="warning">{{ warning }}</p></div>
      </section>

      <section v-if="response.slice10" class="panel slice-ten-panel">
        <header><div><span>Slice 10 · Strict cross-season holdout</span><h2>Can Stamina v2 be published?</h2></div><span class="status-chip" :class="response.slice10.publication_status === 'candidate_ready' ? 'is-ready' : 'is-partial'">{{ response.slice10.publication_status }}</span></header>
        <div class="method-note"><strong>{{ response.slice10.method }}</strong><p>{{ response.slice10.train_year }} train → {{ response.slice10.test_year }} untouched holdout · {{ response.slice10.contract_version }}</p></div>
        <div class="personal-summary-grid">
          <article><span>Selected model</span><strong>{{ response.slice10.selected_model || 'None' }}</strong><p>Uses the preregistered 0.25pp parsimony rule</p></article>
          <article><span>Validated scopes</span><strong>{{ response.slice10.validated_scopes.length }}</strong><p>{{ response.slice10.validated_scopes.join(' · ') || 'No scope passed every gate' }}</p></article>
          <article><span>Candidate rows</span><strong>{{ integer(response.slice10.candidate_rows) }}</strong><p>Failed scopes emit no score</p></article>
          <article><span>Decision</span><strong>{{ response.slice10.publication_status === 'candidate_ready' ? 'Advance' : 'Hold' }}</strong><p>Research curves remain available without a v2 leaderboard</p></article>
        </div>
        <article class="slice-stage"><header><div><span>Pitch-level model holdout</span><h3>2025 fit, 2026 test only</h3></div><p>A model may predict pitches well without supporting stable pitcher rankings.</p></header><div class="table-scroll"><table><thead><tr><th>Model</th><th>RMSE</th><th>Gain</th><th>Calibration</th><th>Residual vs early Stuff+</th><th>Residual vs early velo</th><th>Gates</th><th>Status</th></tr></thead><tbody>
          <tr v-for="row in response.slice10.model_validations" :key="row.model"><td><strong>{{ row.model }}</strong></td><td>{{ row.rmse.toFixed(3) }}</td><td>{{ row.rmse_improvement_pct > 0 ? '+' : '' }}{{ row.rmse_improvement_pct.toFixed(2) }}%</td><td>{{ nullableFixed(row.calibration_slope, 3) }}</td><td>{{ nullableFixed(row.residual_early_stuff_spearman, 3) }}</td><td>{{ nullableFixed(row.residual_early_velocity_spearman, 3) }}</td><td>{{ passedGateCount(row.gates) }} / {{ Object.keys(row.gates).length }}</td><td><span class="status-chip" :class="row.status === 'validated' ? 'is-ready' : 'is-partial'">{{ row.status }}</span></td></tr>
        </tbody></table></div></article>
        <article class="slice-stage"><header><div><span>Pitcher-score release gates</span><h3>Overall and family decisions</h3></div><p>Every gate must pass. Strong rank correlation alone is not enough.</p></header><div class="table-scroll"><table><thead><tr><th>Scope</th><th>Common SP</th><th>Coverage</th><th>Rank ρ</th><th>RMSE gain</th><th>Calibration</th><th>Residual early Stuff+</th><th>Residual early velo</th><th>Gates</th><th>Decision</th></tr></thead><tbody>
          <tr v-for="row in response.slice10.scope_validations" :key="row.scope"><td><strong>{{ row.scope }}</strong></td><td>{{ integer(row.common_pitchers) }}</td><td>{{ pct(row.source_coverage_pct) }}</td><td>{{ nullableFixed(row.spearman_correlation, 3) }}</td><td>{{ row.rmse_improvement_pct === null || row.rmse_improvement_pct === undefined ? '—' : `${row.rmse_improvement_pct > 0 ? '+' : ''}${row.rmse_improvement_pct.toFixed(2)}%` }}</td><td>{{ nullableFixed(row.calibration_slope, 3) }}</td><td>{{ nullableFixed(row.residual_early_stuff_spearman, 3) }}</td><td>{{ nullableFixed(row.residual_early_velocity_spearman, 3) }}</td><td>{{ passedGateCount(row.gates) }} / {{ Object.keys(row.gates).length }}</td><td><span class="status-chip" :class="row.status === 'validated' ? 'is-ready' : 'is-partial'">{{ row.status }}</span></td></tr>
        </tbody></table></div></article>
        <div class="analysis-warnings"><p v-for="warning in response.slice10.warnings" :key="warning">{{ warning }}</p></div>
      </section>

      <section v-if="response.slice11" class="panel slice-eleven-panel">
        <header><div><span>Slice 11 · Multi-signal diagnostics</span><h2>How does each pitch family change within a start?</h2></div><span class="status-chip is-partial">{{ response.slice11.publication_status }}</span></header>
        <div class="method-note"><strong>{{ response.slice11.method }}</strong><p>Every physical signal is kept separate. This panel describes within-game change; it does not issue a pitcher score or leaderboard.</p></div>
        <div class="personal-summary-grid">
          <article><span>Artifact rows</span><strong>{{ integer(response.slice11.artifact_rows) }}</strong><p>appearance × family × reached window</p></article>
          <article><span>Starting pitchers</span><strong>{{ integer(response.slice11.pitchers) }}</strong><p>{{ integer(response.slice11.appearances) }} starts</p></article>
          <article><span>Early support</span><strong>≥ {{ response.slice11.minimum_early_pitches }}</strong><p>same exact pitch type in pitches 1–20</p></article>
          <article><span>Publication</span><strong>Diagnostic</strong><p>No Stamina+ v2 score or downstream activation</p></article>
        </div>
        <article class="slice-stage">
          <header><div><span>League signal path</span><h3>Within-appearance change from the early exact-type baseline</h3></div><div class="outcome-switch"><button v-for="family in slice11Families" :key="`slice11-${family}`" type="button" :class="{ active: selectedSlice11Family === family }" @click="selectedSlice11Family = family">{{ family }}</button></div></header>
          <div class="table-scroll"><table class="multisignal-table"><thead><tr><th>Window</th><th>Pitches</th><th>Stuff+ Δ</th><th>Velo Δ</th><th>Spin Δ</th><th>Movement drift</th><th>Release drift</th><th>Extension Δ</th><th>Location+ Δ</th><th>Usage</th><th>Usage Δ</th></tr></thead><tbody>
            <tr v-for="row in selectedSlice11League" :key="`${row.family}-${row.bucket}`"><td><strong>{{ row.bucket }}</strong></td><td>{{ integer(row.pitches) }}</td><td>{{ nullableSigned(row.stuff_delta, 2) }}</td><td>{{ nullableSigned(row.velocity_delta, 2) }} mph</td><td>{{ nullableSigned(row.spin_delta, 1) }} rpm</td><td>{{ nullableFixed(row.movement_drift_inches, 2) }} in</td><td>{{ nullableFixed(row.release_point_drift_inches, 2) }} in</td><td>{{ nullableSigned(row.extension_delta, 2) }} ft</td><td>{{ nullableSigned(row.location_delta, 2) }}</td><td>{{ nullableFixed(row.usage_pct, 1) }}%</td><td>{{ nullableSigned(row.usage_delta_pp, 1) }} pp</td></tr>
          </tbody></table></div>
          <div class="coverage-strip"><div v-for="row in selectedSlice11Coverage" :key="`${row.family}-${row.signal}`"><span>{{ signalLabel(row.signal) }}</span><strong>{{ pct(row.coverage_pct) }}</strong><small>{{ integer(row.available_rows) }} / {{ integer(row.total_rows) }} observed rows</small></div></div>
        </article>
        <div class="slice-four-grid">
          <article class="slice-stage"><header><div><span>Cross-family conversion</span><h3>Fastball − Offspeed velocity separation</h3></div><p>Only games containing both families in the early and target windows.</p></header><div class="table-scroll"><table><thead><tr><th>Window</th><th>Games</th><th>Speed gap</th><th>Change from early</th></tr></thead><tbody>
            <tr v-for="row in response.slice11.transitions" :key="row.bucket"><td><strong>{{ row.bucket }}</strong></td><td>{{ integer(row.appearances) }}</td><td>{{ nullableFixed(row.speed_gap_mph, 2) }} mph</td><td>{{ nullableSigned(row.speed_gap_delta_mph, 2) }} mph</td></tr>
          </tbody></table></div></article>
          <article class="slice-stage"><header><div><span>Interpretation guardrail</span><h3>What these signals can and cannot say</h3></div></header><div class="contract-list"><div><strong>Stuff+ and velocity can move differently</strong><p>A family may lose speed while pitch shape, sequencing or selection keeps Stuff+ stable.</p></div><div><strong>Drift is displacement, not automatic decline</strong><p>Movement and release-point distance show change from the early centroid; direction and intent still matter.</p></div><div><strong>Usage is part of the response</strong><p>A pitcher can compensate for a fading fastball by changing the mix, so family results must be read together.</p></div></div></article>
        </div>
        <article class="slice-stage">
          <header><div><span>Player / game explorer</span><h3>Inspect one start without turning it into a ranking</h3></div><div class="slice-eleven-controls"><label>Pitcher<select v-model.number="slice11PitcherId"><option v-for="player in response.slice11.players" :key="player.pitcher_id" :value="player.pitcher_id">{{ player.name }} · {{ player.team }}</option></select></label><label>Game<select v-model.number="slice11GamePk"><option v-for="game in slice11Curves?.games || []" :key="game.game_pk" :value="game.game_pk">{{ game.game_date }} · {{ game.total_pitches }} pitches</option></select></label></div></header>
          <p v-if="slice11CurvesPending" class="empty-row">Loading player research curves…</p>
          <div v-else-if="selectedSlice11GameRows.length" class="table-scroll"><table class="multisignal-table"><thead><tr><th>Family / window</th><th>Pitches</th><th>Early support</th><th>Stuff+ Δ</th><th>Velo Δ</th><th>Movement drift</th><th>Release drift</th><th>Location+ Δ</th><th>Usage</th><th>Usage Δ</th></tr></thead><tbody>
            <tr v-for="row in selectedSlice11GameRows" :key="`${row.pitch_family}-${row.analysis_bucket}`"><td><strong>{{ row.pitch_family }} · {{ row.analysis_bucket }}</strong></td><td>{{ integer(row.pitches) }}</td><td>{{ integer(row.reference_pitches) }}</td><td>{{ nullableSigned(row.stuff_delta, 2) }}</td><td>{{ nullableSigned(row.velocity_delta, 2) }} mph</td><td>{{ nullableFixed(row.movement_drift_inches, 2) }} in</td><td>{{ nullableFixed(row.release_point_drift_inches, 2) }} in</td><td>{{ nullableSigned(row.location_delta, 2) }}</td><td>{{ row.usage_pct.toFixed(1) }}%</td><td>{{ nullableSigned(row.usage_delta_pp, 1) }} pp</td></tr>
          </tbody></table></div>
          <p v-else class="empty-row">No research curve is available for this selection.</p>
        </article>
        <div class="analysis-warnings"><p v-for="warning in response.slice11.warnings" :key="warning">{{ warning }}</p></div>
      </section>

      <section v-if="response.slice15 && response.slice16" class="panel slice-physical-panel">
        <header><div><span>Slice 15–16 · Physical Stability+</span><h2>How stable are the tracked physical signals within a start?</h2></div><span class="status-chip is-partial">{{ response.slice16.publication_status }}</span></header>
        <div class="method-note"><strong>{{ response.slice16.method }}</strong><p>This challenger never uses Stuff+ as its training target. Higher means less measured physical drift, not lower injury risk.</p></div>
        <div class="personal-summary-grid">
          <article><span>Covered seasons</span><strong>{{ response.slice15.covered_years.join('–') }}</strong><p>2023 is the frozen development reference</p></article>
          <article><span>Early exact-type support</span><strong>≥ {{ response.slice15.minimum_early_exact_pitches }}</strong><p>same pitch type among pitches 1–20</p></article>
          <article><span>Game support</span><strong>≥ {{ response.slice15.minimum_late_pitches }}</strong><p>supported pitches after pitch 20</p></article>
          <article><span>Component coverage</span><strong>≥ {{ response.slice15.minimum_component_coverage_pct.toFixed(0) }}%</strong><p>missing fixed weight stays league-neutral</p></article>
        </div>
        <article class="slice-stage"><header><div><span>Frozen signal contract</span><h3>Six transparent components</h3></div><p>Absolute or vector drift from the same-game early baseline.</p></header><div class="coverage-strip physical-contract-strip"><div v-for="signal in response.slice15.signals" :key="signal.key"><span>{{ signal.label }}</span><strong>{{ (signal.weight * 100).toFixed(0) }}%</strong><small>{{ signal.definition }}</small></div></div></article>
        <article class="slice-stage"><header><div><span>Four-season audit</span><h3>Coverage, reliability and score behavior</h3></div></header><div class="table-scroll"><table><thead><tr><th>Year</th><th>Supported late</th><th>Arm angle</th><th>Eligible games</th><th>Pitchers</th><th>Median rel</th><th>80% width</th><th>21–40 vs 61–80 ρ</th><th>Velo vs Physical ρ</th><th>P05 / P50 / P95</th></tr></thead><tbody>
          <tr v-for="audit in response.slice16.year_audits" :key="audit.year"><td><strong>{{ audit.year }}</strong></td><td>{{ pct(physicalCoverage(audit.year)?.supported_late_pct || 0) }}</td><td>{{ pct(physicalCoverage(audit.year)?.signal_coverage_pct.arm_angle || 0) }}</td><td>{{ integer(audit.eligible_games) }}</td><td>{{ integer(audit.pitchers) }}</td><td>{{ reliabilityPct(audit.median_reliability) }}</td><td>{{ audit.median_interval_width.toFixed(1) }}</td><td>{{ nullableFixed(audit.split_window_spearman, 3) }}</td><td>{{ nullableFixed(audit.velocity_vs_physical_spearman, 3) }}</td><td>{{ nullableFixed(audit.score_p05, 1) }} / {{ nullableFixed(audit.score_p50, 1) }} / {{ nullableFixed(audit.score_p95, 1) }}</td></tr>
        </tbody></table></div></article>
        <article class="slice-stage"><header><div><span>Player / game explorer</span><h3>{{ physicalDetail?.pitcher_name || 'Pitcher' }} · Physical Stability+</h3></div><div class="slice-eleven-controls"><label>Pitcher<select v-model.number="slice11PitcherId"><option v-for="player in response.slice16.players" :key="`physical-${player.pitcher_id}`" :value="player.pitcher_id">{{ player.name }} · {{ player.team }}</option></select></label><label>Game<select v-model.number="physicalGamePk"><option v-for="game in eligiblePhysicalGames" :key="game.game_pk" :value="game.game_pk">{{ game.game_date }} · {{ game.physical_stability_plus.toFixed(1) }}</option></select></label></div></header>
          <p v-if="physicalPending" class="empty-row">Loading physical stability states…</p>
          <template v-else-if="selectedPhysicalGame">
            <div class="personal-summary-grid"><article><span>Physical Stability+</span><strong>{{ selectedPhysicalGame.physical_stability_plus.toFixed(1) }}</strong><p>80% interval {{ selectedPhysicalGame.ci_low.toFixed(1) }}–{{ selectedPhysicalGame.ci_high.toFixed(1) }}</p></article><article><span>Reliability</span><strong>{{ reliabilityPct(selectedPhysicalGame.reliability) }}</strong><p>{{ selectedPhysicalGame.confidence }} confidence</p></article><article><span>Supported pitches</span><strong>{{ integer(selectedPhysicalGame.supported_pitches) }}</strong><p>{{ reliabilityPct(selectedPhysicalGame.component_coverage) }} component coverage</p></article><article><span>Velocity / release</span><strong>{{ nullableFixed(selectedPhysicalGame.velocity_plus, 1) }} / {{ nullableFixed(selectedPhysicalGame.release_point_plus, 1) }}</strong><p>component Plus scores</p></article></div>
            <div class="table-scroll"><table><thead><tr><th>Window</th><th>Physical+</th><th>80% interval</th><th>Rel</th><th>Velo</th><th>Spin</th><th>Movement</th><th>Release</th><th>Extension</th><th>Arm angle</th><th>Pitches</th></tr></thead><tbody><tr v-for="row in selectedPhysicalWindows" :key="`${row.game_pk}-${row.analysis_bucket}`"><td><strong>{{ row.analysis_bucket }}</strong></td><td>{{ row.eligible ? row.physical_stability_plus.toFixed(1) : '—' }}</td><td>{{ row.eligible ? `${row.ci_low.toFixed(1)}–${row.ci_high.toFixed(1)}` : '—' }}</td><td>{{ reliabilityPct(row.reliability) }}</td><td>{{ nullableFixed(row.velocity_plus, 1) }}</td><td>{{ nullableFixed(row.spin_plus, 1) }}</td><td>{{ nullableFixed(row.movement_plus, 1) }}</td><td>{{ nullableFixed(row.release_point_plus, 1) }}</td><td>{{ nullableFixed(row.extension_plus, 1) }}</td><td>{{ nullableFixed(row.arm_angle_plus, 1) }}</td><td>{{ integer(row.supported_pitches) }}</td></tr></tbody></table></div>
          </template>
          <p v-else class="empty-row">No eligible Physical Stability+ game is available for this pitcher.</p>
        </article>
        <div class="analysis-warnings"><p v-for="warning in [...response.slice15.warnings, ...response.slice16.warnings]" :key="warning">{{ warning }}</p></div>
      </section>

      <section v-if="response.slice17 && response.slice18" class="panel slice-command-panel">
        <header><div><span>Slice 17–18 · Command Retention+ & incremental validation</span><h2>Does command hold up, and does it add information beyond the current signals?</h2></div><span class="status-chip" :class="response.slice18.composite_release_eligible ? 'is-ready' : 'is-partial'">{{ response.slice18.composite_release_eligible ? 'composite review ready' : 'keep separate' }}</span></header>
        <div class="method-note"><strong>{{ response.slice17.method }}</strong><p>Higher Command Retention+ means Location+ held up better than the frozen 2023 workload and pitch-type expectation. It is not Stuff+, Physical Stability+, or injury risk.</p></div>
        <div class="personal-summary-grid">
          <article><span>Covered seasons</span><strong>{{ response.slice17.covered_years.join('–') }}</strong><p>2023 development; later years use the frozen rule</p></article>
          <article><span>Game support</span><strong>≥ {{ response.slice17.minimum_game_pitches }}</strong><p>later supported pitches and ≥{{ response.slice17.minimum_fixed_mix_coverage_pct.toFixed(0) }}% early mix</p></article>
          <article><span>2026 matched starts</span><strong>{{ integer(response.slice18.test_rows) }}</strong><p>{{ pct(response.slice18.test_pair_coverage_pct) }} of eligible 21–40 / 61–80 pairs</p></article>
          <article><span>RMSE change</span><strong>{{ signed3(response.slice18.rmse_improvement_pct) }}%</strong><p>challenger versus early-Quality baseline</p></article>
        </div>
        <article class="slice-stage"><header><div><span>Four-season audit</span><h3>Command signal behavior</h3></div></header><div class="table-scroll"><table><thead><tr><th>Year</th><th>Eligible games</th><th>Pitchers</th><th>Model / naive RMSE</th><th>Gain</th><th>Opening Location ρ</th><th>21–40 vs 61–80 ρ</th><th>Median rel</th><th>80% width</th><th>P05 / P50 / P95</th></tr></thead><tbody>
          <tr v-for="audit in response.slice17.year_audits" :key="`command-${audit.year}`"><td><strong>{{ audit.year }}</strong></td><td>{{ integer(audit.eligible_overall_games) }}</td><td>{{ integer(audit.pitchers) }}</td><td>{{ audit.pitch_model_rmse.toFixed(3) }} / {{ audit.pitch_baseline_rmse.toFixed(3) }}</td><td>{{ signed3(audit.pitch_rmse_improvement_pct) }}%</td><td>{{ nullableFixed(audit.early_location_spearman, 3) }}</td><td>{{ nullableFixed(audit.split_window_spearman, 3) }}</td><td>{{ reliabilityPct(audit.median_reliability) }}</td><td>{{ audit.median_interval_width.toFixed(1) }}</td><td>{{ nullableFixed(audit.score_p05, 1) }} / {{ nullableFixed(audit.score_p50, 1) }} / {{ nullableFixed(audit.score_p95, 1) }}</td></tr>
        </tbody></table></div></article>
        <article class="slice-stage"><header><div><span>Frozen 2025 → 2026 test</span><h3>{{ response.slice18.decision }}</h3></div><p>21–40 predictors; 61–80 Quality retention target.</p></header>
          <div class="coverage-strip"><div v-for="gate in response.slice18.gates" :key="gate.key"><span>{{ gate.label }}</span><strong>{{ gate.passed ? 'PASS' : 'FAIL' }}</strong><small>{{ gate.value }} · requires {{ gate.threshold }}</small></div></div>
          <div class="table-scroll"><table><thead><tr><th>Model</th><th>2026 RMSE</th><th>Spearman</th><th>Calibration slope</th></tr></thead><tbody><tr v-for="(model, key) in response.slice18.models" :key="key"><td><strong>{{ key }}</strong></td><td>{{ nullableFixed(model.rmse, 4) }}</td><td>{{ nullableFixed(model.spearman, 4) }}</td><td>{{ nullableFixed(model.calibration_slope, 4) }}</td></tr></tbody></table></div>
        </article>
        <article class="slice-stage"><header><div><span>Player / game explorer</span><h3>{{ commandDetail?.pitcher_name || 'Pitcher' }} · Command Retention+</h3></div><div class="slice-eleven-controls"><label>Pitcher<select v-model.number="slice11PitcherId"><option v-for="player in response.slice17.players" :key="`command-${player.pitcher_id}`" :value="player.pitcher_id">{{ player.name }} · {{ player.team }}</option></select></label><label>Game<select v-model.number="commandGamePk"><option v-for="game in eligibleCommandGames" :key="game.game_pk" :value="game.game_pk">{{ game.game_date }} · {{ game.command_retention_plus.toFixed(1) }}</option></select></label></div></header>
          <p v-if="commandPending" class="empty-row">Loading command retention states…</p>
          <template v-else-if="selectedCommandGame">
            <div class="personal-summary-grid"><article><span>Command Retention+</span><strong>{{ selectedCommandGame.command_retention_plus.toFixed(1) }}</strong><p>80% interval {{ selectedCommandGame.ci_low.toFixed(1) }}–{{ selectedCommandGame.ci_high.toFixed(1) }}</p></article><article><span>Reliability</span><strong>{{ reliabilityPct(selectedCommandGame.reliability) }}</strong><p>{{ selectedCommandGame.confidence }} confidence</p></article><article><span>Supported pitches</span><strong>{{ integer(selectedCommandGame.late_pitches) }}</strong><p>{{ reliabilityPct(selectedCommandGame.fixed_mix_coverage) }} fixed early mix</p></article><article><span>Early Location+</span><strong>{{ selectedCommandGame.early_location.toFixed(1) }}</strong><p>used to estimate, not reward, the expected ceiling</p></article></div>
            <div class="table-scroll"><table><thead><tr><th>Scope</th><th>Window</th><th>Command+</th><th>80% interval</th><th>Rel</th><th>Residual</th><th>Pitches</th></tr></thead><tbody><tr v-for="row in selectedCommandWindows" :key="`${row.scope}-${row.analysis_bucket}`"><td><strong>{{ row.scope }}</strong></td><td>{{ row.analysis_bucket }}</td><td>{{ row.eligible ? row.command_retention_plus.toFixed(1) : '—' }}</td><td>{{ row.eligible ? `${row.ci_low.toFixed(1)}–${row.ci_high.toFixed(1)}` : '—' }}</td><td>{{ reliabilityPct(row.reliability) }}</td><td>{{ nullableSigned(row.retention, 2) }}</td><td>{{ integer(row.pitches) }}</td></tr></tbody></table></div>
          </template>
          <p v-else class="empty-row">No eligible Command Retention+ game is available for this pitcher.</p>
        </article>
        <article v-if="response.slice19" class="slice-stage"><header><div><span>Slice 19 · Product decision</span><h3>Keep the three signals separate</h3></div><p>{{ integer(response.slice19.qualified_three_signal_pitchers) }} pitchers have at least 10 games in all three panels.</p></header>
          <div class="method-note"><strong>{{ response.slice19.method }}</strong><p>These are game-level means for case review, not the adjusted season leaderboard score.</p></div>
          <div class="table-scroll"><table><thead><tr><th>Case</th><th>Pitcher</th><th>Quality</th><th>Physical</th><th>Command</th><th>Games Q / P / C</th><th>Rel Q / P / C</th></tr></thead><tbody><tr v-for="player in response.slice19.representative_pitchers" :key="`${player.case}-${player.pitcher_id}`"><td><strong>{{ productCaseLabel(player.case) }}</strong></td><td>{{ player.name }} · {{ player.team }}</td><td>{{ player.quality_stamina_plus.toFixed(1) }}</td><td>{{ player.physical_stability_plus.toFixed(1) }}</td><td>{{ player.command_retention_plus.toFixed(1) }}</td><td>{{ player.quality_games }} / {{ player.physical_games }} / {{ player.command_games }}</td><td>{{ player.quality_reliability.toFixed(3) }} / {{ player.physical_reliability.toFixed(3) }} / {{ player.command_reliability.toFixed(3) }}</td></tr></tbody></table></div>
          <div class="analysis-warnings"><p v-for="rule in response.slice19.product_rules" :key="rule">{{ rule }}</p></div>
        </article>
        <div class="analysis-warnings"><p v-for="warning in [...response.slice17.warnings, ...response.slice18.warnings]" :key="warning">{{ warning }}</p></div>
      </section>

      <section v-if="response.slice11_game_state" class="panel slice-eleven-game-state-panel">
        <header><div><span>Observed Game Stamina+</span><h2>One-game decline and full-season state</h2></div><span class="status-chip is-ready">observed state</span></header>
        <div class="method-note"><strong>{{ response.slice11_game_state.method }}</strong><p>100 is the league-average observed retention state. This describes the current game only and does not forecast the next start.</p></div>
        <div class="personal-summary-grid">
          <article><span>Eligible starts</span><strong>{{ integer(response.slice11_game_state.eligible_overall_games) }}</strong><p>{{ integer(response.slice11_game_state.pitchers) }} starting pitchers</p></article>
          <article><span>Expected-curve gain</span><strong>+{{ response.slice11_game_state.pitch_rmse_improvement_pct.toFixed(2) }}%</strong><p>{{ response.slice11_game_state.pitch_model_rmse.toFixed(3) }} vs {{ response.slice11_game_state.pitch_baseline_rmse.toFixed(3) }} RMSE</p></article>
          <article><span>Opening neutrality</span><strong>{{ nullableFixed(response.slice11_game_state.early_stuff_spearman, 3) }}</strong><p>retention vs early Stuff+ rank correlation</p></article>
          <article><span>Within-game consistency</span><strong>{{ nullableFixed(response.slice11_game_state.within_game_split_spearman, 3) }}</strong><p>21–40 vs 61–80 retention</p></article>
          <article><span>Start coverage</span><strong>{{ pct(response.slice11_game_state.overall_start_coverage_pct) }}</strong><p>requires ≥{{ response.slice11_game_state.minimum_fixed_mix_coverage_pct.toFixed(0) }}% fixed early-mix support</p></article>
          <article><span>Median 80% interval</span><strong>{{ response.slice11_game_state.median_interval_width.toFixed(1) }}</strong><p>inning-cluster bootstrap Stamina+ points</p></article>
        </div>
        <article class="slice-stage"><header><div><span>Season timeline</span><h3>{{ gameStateDetail?.pitcher_name || 'Pitcher' }} · {{ gameStateScope }}</h3></div><div class="slice-eleven-controls"><label>Pitcher<select v-model.number="slice11PitcherId"><option v-for="player in response.slice11?.players || []" :key="`state-${player.pitcher_id}`" :value="player.pitcher_id">{{ player.name }} · {{ player.team }}</option></select></label><label>Scope<select v-model="gameStateScope"><option v-for="scope in gameStateScopes" :key="scope" :value="scope">{{ scope }}</option></select></label></div></header>
          <p v-if="gameStatePending" class="empty-row">Loading observed game states…</p>
          <div v-else-if="selectedGameStates.length" class="season-state-chart"><svg viewBox="0 0 760 260" role="img" :aria-label="`${gameStateScope} season Game Stamina+ timeline`"><line x1="50" x2="735" :y1="gameStateY(100)" :y2="gameStateY(100)" class="zero-line"/><polyline :points="gameStatePolyline(selectedGameStates, 'stamina_plus')" class="curve-line"/><polyline :points="gameStatePolyline(selectedGameStates, 'rolling_5')" class="season-trend-line"/><g v-for="(row, index) in selectedGameStates" :key="`state-point-${row.game_pk}`"><circle :cx="gameStateX(index, selectedGameStates.length)" :cy="gameStateY(row.stamina_plus || 100)" r="5" class="curve-dot"/><title>{{ row.game_date }} · {{ nullableFixed(row.stamina_plus, 1) }}</title></g></svg><div class="state-chart-key"><span>Game Stamina+</span><span>5-start trend</span></div></div>
        </article>
        <article class="slice-stage"><header><div><span>Every eligible start</span><h3>Observed state, uncertainty and rolling trend</h3></div></header><div class="table-scroll"><table><thead><tr><th>Date</th><th>Start</th><th>Game Stamina+</th><th>80% interval</th><th>Confidence</th><th>3-game</th><th>5-game</th><th>Retention</th><th>Velo Δ</th><th>Fixed mix</th><th>Observed pitches</th><th>Total pitches</th></tr></thead><tbody>
          <tr v-for="row in [...selectedGameStates].reverse()" :key="`state-${row.scope}-${row.game_pk}`" @click="slice11GamePk = row.game_pk"><td><strong>{{ row.game_date }}</strong></td><td>{{ row.season_start_number }}</td><td>{{ nullableFixed(row.stamina_plus, 1) }}</td><td>{{ nullableFixed(row.ci_low, 1) }}–{{ nullableFixed(row.ci_high, 1) }}</td><td><span class="reliability-chip" :class="`is-${row.confidence}`">{{ row.confidence }} · {{ row.reliability === null || row.reliability === undefined ? '—' : reliabilityPct(row.reliability) }}</span></td><td>{{ nullableFixed(row.rolling_3, 1) }}</td><td>{{ nullableFixed(row.rolling_5, 1) }}</td><td>{{ nullableSigned(row.posterior_retention, 2) }}</td><td>{{ nullableSigned(row.velocity_delta, 2) }} mph</td><td>{{ row.fixed_mix_coverage === null || row.fixed_mix_coverage === undefined ? '—' : reliabilityPct(row.fixed_mix_coverage) }}</td><td>{{ integer(row.pitches) }}</td><td>{{ integer(row.total_pitches) }}</td></tr>
        </tbody></table></div></article>
        <article class="slice-stage"><header><div><span>Selected-game decline</span><h3>{{ selectedGameState?.game_date || 'Choose a game' }} · pitch-count windows</h3></div></header><div class="table-scroll"><table><thead><tr><th>Scope</th><th>Window</th><th>Retention vs expected</th><th>Velo Δ</th><th>Pitches</th></tr></thead><tbody>
          <tr v-for="row in selectedGameWindows" :key="`${row.scope}-${row.analysis_bucket}`"><td><strong>{{ row.scope }}</strong></td><td>{{ row.analysis_bucket }}</td><td>{{ nullableSigned(row.retention, 2) }}</td><td>{{ nullableSigned(row.velocity_delta, 2) }} mph</td><td>{{ integer(row.pitches) }}</td></tr>
        </tbody></table></div></article>
        <div class="analysis-warnings"><p v-for="warning in response.slice11_game_state.warnings" :key="warning">{{ warning }}</p></div>
      </section>

      <section class="panel arm-audit-panel slice-zero-panel">
        <header><div><span>Source diagnosis</span><h2>Why arm angle coverage is only {{ pct(response.arm_angle_audit.coverage_pct) }}</h2></div><span class="status-chip is-partial">date-batch missingness</span></header>
        <div class="arm-audit-grid">
          <article><span>Missing pitches</span><strong>{{ integer(response.arm_angle_audit.missing_pitches) }}</strong><p>{{ integer(response.arm_angle_audit.otherwise_trackable_missing) }} still have the other physical tracking fields.</p></article>
          <article><span>Zero-coverage dates</span><strong>{{ integer(response.arm_angle_audit.zero_coverage_date_count) }} / {{ integer(response.arm_angle_audit.dates) }}</strong><p>Entire dates are absent, so this is not a pitcher-level trait.</p></article>
          <article><span>Slice 1 treatment</span><strong>Excluded</strong><p>Arm angle is not used as a primary-model control until the affected date batches are repaired.</p></article>
        </div>
        <details><summary>Show zero-coverage dates</summary><p>{{ response.arm_angle_audit.zero_coverage_dates.join(' · ') }}</p></details>
      </section>

      <section class="panel slice-zero-panel">
        <header><div><span>Data cleaning</span><h2>Every exclusion remains visible</h2></div><p>No missing score is filled with zero.</p></header>
        <div class="table-scroll"><table><thead><tr><th>Step</th><th>Input</th><th>Output</th><th>Removed</th><th>Status</th><th>Rule</th></tr></thead><tbody>
          <tr v-for="step in response.cleaning" :key="step.key"><td><strong>{{ step.label }}</strong></td><td>{{ integer(step.input_rows) }}</td><td>{{ integer(step.output_rows) }}</td><td>{{ integer(step.removed_rows) }}</td><td><span class="status-chip" :class="`is-${step.status}`">{{ step.status }}</span></td><td class="note-cell">{{ step.note }}</td></tr>
        </tbody></table></div>
      </section>

      <section class="two-column slice-zero-panel">
        <article class="panel">
          <header><div><span>Role integrity</span><h2>Starter and reliever samples</h2></div></header>
          <div class="role-grid">
            <div v-for="role in response.roles" :key="role.role"><b>{{ role.role }}</b><strong>{{ integer(role.pitches) }}</strong><span>pitches</span><p>{{ integer(role.appearances) }} appearances · {{ integer(role.pitchers) }} pitchers</p><small>{{ integer(role.dual_role_pitchers) }} dual-role pitchers retained here</small></div>
          </div>
        </article>

        <article class="panel">
          <header><div><span>Primary outcomes</span><h2>Plus-score coverage</h2></div></header>
          <div class="table-scroll"><table><thead><tr><th>Role</th><th>Pitches</th><th>Stuff+</th><th>Location+</th><th>Both</th></tr></thead><tbody>
            <tr v-for="row in response.coverage" :key="row.role"><td><strong>{{ row.role }}</strong></td><td>{{ integer(row.pitches) }}</td><td>{{ pct(row.stuff_coverage_pct) }}</td><td>{{ pct(row.location_coverage_pct) }}</td><td>{{ pct(row.both_coverage_pct) }}</td></tr>
          </tbody></table></div>
        </article>
      </section>

      <section class="panel slice-zero-panel">
        <header><div><span>Sample support</span><h2>Pitch-count research windows</h2></div><p>SP and RP use different workload windows.</p></header>
        <div class="bucket-layout">
          <div v-for="role in ['SP', 'RP']" :key="role">
            <h3>{{ role === 'SP' ? 'Starter windows' : 'Reliever windows' }}</h3>
            <div class="table-scroll"><table><thead><tr><th>Pitch #</th><th>Pitches</th><th>Games</th><th>Pitchers</th><th>Stuff+</th><th>Location+</th></tr></thead><tbody>
              <tr v-for="row in bucketsFor(role)" :key="`${role}-${row.bucket}`"><td><strong>{{ row.bucket }}</strong></td><td>{{ integer(row.pitches) }}</td><td>{{ integer(row.appearances) }}</td><td>{{ integer(row.pitchers) }}</td><td>{{ pct(row.stuff_coverage_pct) }}</td><td>{{ pct(row.location_coverage_pct) }}</td></tr>
            </tbody></table></div>
          </div>
        </div>
      </section>

      <section class="panel slice-zero-panel">
        <header><div><span>Feature readiness</span><h2>Signals prepared for later modeling</h2></div><p>Coverage is measured after cleaning.</p></header>
        <div class="feature-grid">
          <article v-for="feature in response.feature_audit" :key="`${feature.group}-${feature.feature}`">
            <div><span>{{ feature.group }}</span><span class="status-chip" :class="`is-${feature.status}`">{{ feature.status }}</span></div>
            <h3>{{ feature.feature }}</h3><strong>{{ pct(feature.coverage_pct) }}</strong><p>{{ feature.note }}</p>
          </article>
        </div>
      </section>

      <section class="panel slice-zero-panel">
        <header><div><span>Pre-analysis contract</span><h2>Hypotheses locked before scoring</h2></div><p>These are research questions, not confirmed findings.</p></header>
        <div class="hypothesis-list">
          <article v-for="hypothesis in response.hypotheses" :key="hypothesis.key">
            <b>{{ hypothesis.key }}</b><div><h3>{{ hypothesis.title }}</h3><p>{{ hypothesis.question }}</p><small><strong>Outcomes:</strong> {{ hypothesis.primary_outcomes.join(', ') }}</small><small><strong>Controls:</strong> {{ hypothesis.required_controls.join(', ') }}</small></div><span class="status-chip">{{ hypothesis.status }}</span>
          </article>
        </div>
      </section>

      <section class="warning-panel slice-zero-panel"><strong>Research limitations</strong><p v-for="warning in response.warnings" :key="warning">{{ warning }}</p></section>
    </template>
  </main>
</template>

<script setup lang="ts">
import type { StaminaGameState, StaminaPitchBucket, StaminaSlice1Point } from '~/types/api'

const api = useApi()
const year = ref(2026)
const selectedOutcome = ref<'pitch_stuff_plus' | 'location_plus_pitch'>('pitch_stuff_plus')
const pitcherRoles = ['SP', 'RP'] as const
const selectedRole = ref<'SP' | 'RP'>('SP')
const pitcherSearch = ref('')
const staminaSearch = ref('')
const qualifiedOnly = ref(false)
const staminaScope = ref<'trait' | '2026' | '2025'>('trait')
const v2Families = ['Overall', 'Fastball', 'Breaking', 'Offspeed'] as const
const selectedV2Family = ref<(typeof v2Families)[number]>('Overall')
const slice11Families = ['Fastball', 'Breaking', 'Offspeed'] as const
const selectedSlice11Family = ref<(typeof slice11Families)[number]>('Fastball')
const gameStateScopes = ['Overall', 'Fastball', 'Breaking', 'Offspeed'] as const
const gameStateScope = ref<(typeof gameStateScopes)[number]>('Overall')
const slice11PitcherId = ref(0)
const slice11GamePk = ref(0)
const physicalGamePk = ref(0)
const commandGamePk = ref(0)
const { data: response, pending, error } = await useAsyncData(
  'stamina-slice0',
  () => api.staminaOverview(year.value),
  { watch: [year] }
)
const activeSlice11PitcherId = computed(() => slice11PitcherId.value || response.value?.slice11?.players[0]?.pitcher_id || 0)
const { data: slice11Curves, pending: slice11CurvesPending } = await useAsyncData(
  'stamina-slice11-curves',
  () => activeSlice11PitcherId.value ? api.staminaResearchCurves(year.value, activeSlice11PitcherId.value) : Promise.resolve(null),
  { watch: [year, activeSlice11PitcherId] }
)
const { data: gameStateDetail, pending: gameStatePending } = await useAsyncData(
  'stamina-game-states',
  () => activeSlice11PitcherId.value ? api.staminaGameStates(year.value, activeSlice11PitcherId.value) : Promise.resolve(null),
  { watch: [year, activeSlice11PitcherId] }
)
const { data: physicalDetail, pending: physicalPending } = await useAsyncData(
  'stamina-physical-stability',
  () => activeSlice11PitcherId.value && response.value?.slice16 ? api.staminaPhysicalStability(year.value, activeSlice11PitcherId.value) : Promise.resolve(null),
  { watch: [year, activeSlice11PitcherId] }
)
const { data: commandDetail, pending: commandPending } = await useAsyncData(
  'stamina-command-retention',
  () => activeSlice11PitcherId.value && response.value?.slice17 ? api.staminaCommandRetention(year.value, activeSlice11PitcherId.value) : Promise.resolve(null),
  { watch: [year, activeSlice11PitcherId] }
)
watch(response, value => {
  if (!slice11PitcherId.value && value?.slice11?.players.length) slice11PitcherId.value = value.slice11.players[0].pitcher_id
}, { immediate: true })
watch(slice11Curves, value => {
  if (value?.games.length && !value.games.some(game => game.game_pk === slice11GamePk.value)) slice11GamePk.value = value.games[0].game_pk
}, { immediate: true })
watch(physicalDetail, value => {
  const games = (value?.games || []).filter(game => game.eligible)
  if (games.length && !games.some(game => game.game_pk === physicalGamePk.value)) physicalGamePk.value = games.at(-1)?.game_pk || 0
}, { immediate: true })
watch(commandDetail, value => {
  const games = (value?.games || []).filter(game => game.scope === 'Overall' && game.eligible)
  if (games.length && !games.some(game => game.game_pk === commandGamePk.value)) commandGamePk.value = games.at(-1)?.game_pk || 0
}, { immediate: true })
const errorMessage = computed(() => error.value ? String((error.value as { data?: { detail?: string } }).data?.detail || error.value.message || error.value) : '')
const numberFormat = new Intl.NumberFormat('en-US')
function integer(value: number) { return numberFormat.format(value) }
function pct(value: number) { return `${value.toFixed(1)}%` }
function signed(value: number) { return `${value > 0 ? '+' : ''}${value.toFixed(2)}` }
function signed3(value: number) { return `${value > 0 ? '+' : ''}${value.toFixed(3)}` }
function bucketsFor(role: string): StaminaPitchBucket[] { return response.value?.pitch_buckets.filter(row => row.role === role) || [] }
function formatDateTime(value: string) { return new Date(value).toLocaleString('en-CA', { hour12: false }) }
function dimensionLabel(value: string) { return value === 'appearance_pitch_count' ? 'Within appearance' : 'Season workload' }
const outcomeLabel = computed(() => selectedOutcome.value === 'pitch_stuff_plus' ? 'Stuff+' : 'Location+')
const selectedSummaries = computed(() => response.value?.slice1.summaries.filter(row => row.outcome === selectedOutcome.value) || [])
const selectedExtremeComparison = computed(() => response.value?.slice2.extreme_comparison.filter(row => row.outcome === selectedOutcome.value) || [])
const selectedAppearanceCorrections = computed(() => response.value?.slice2.appearance_results.filter(row => row.outcome === selectedOutcome.value) || [])
const selectedSeasonCorrections = computed(() => response.value?.slice2.season_fixed_cohort.filter(row => row.outcome === selectedOutcome.value) || [])
const selectedTtoCorrections = computed(() => response.value?.slice2.tto_sensitivity.filter(row => row.outcome === selectedOutcome.value) || [])
const selectedPrior = computed(() => response.value?.slice3.priors.find(row => row.role === selectedRole.value && row.outcome === selectedOutcome.value))
const selectedValidation = computed(() => response.value?.slice3.split_half_validation.find(row => row.role === selectedRole.value && row.outcome === selectedOutcome.value))
const selectedPitcherRows = computed(() => {
  const query = pitcherSearch.value.toLocaleLowerCase()
  return (response.value?.slice3.leaderboard || []).filter(row => {
    if (row.role !== selectedRole.value || row.outcome !== selectedOutcome.value) return false
    return !query || row.pitcher_name.toLocaleLowerCase().includes(query) || row.team.toLocaleLowerCase().includes(query)
  })
})
const selectedReadinessEffects = computed(() => response.value?.slice4.readiness_effects.filter(row => row.role === selectedRole.value && row.outcome === selectedOutcome.value) || [])
const selectedRetentionEffects = computed(() => response.value?.slice4.retention_effects.filter(row => row.role === selectedRole.value && row.outcome === selectedOutcome.value) || [])
const selectedSeasonEffects = computed(() => response.value?.slice4.season_effects.filter(row => row.role === selectedRole.value && row.outcome === selectedOutcome.value) || [])
const selectedTimeValidation = computed(() => response.value?.slice4.time_validation.filter(row => row.role === selectedRole.value && row.outcome === selectedOutcome.value) || [])
const selectedCrossSeasonValidation = computed(() => response.value?.slice4.cross_season_validation.filter(row => !row.role || (row.role === selectedRole.value && row.outcome === selectedOutcome.value)) || [])
const selectedFeatureInfluence = computed(() => [...selectedReadinessEffects.value, ...selectedRetentionEffects.value]
  .filter(row => row.standardized_effect !== null && row.standardized_effect !== undefined)
  .sort((a, b) => Math.abs(Number(b.standardized_effect)) - Math.abs(Number(a.standardized_effect))))
const selectedSlice5Prior = computed(() => response.value?.slice5?.priors.find(row => row.role === selectedRole.value))
const selectedSlice5Validation = computed(() => response.value?.slice5?.validations.find(row => row.role === selectedRole.value))
const selectedSeasonPrior = computed(() => response.value?.slice5?.season_priors.find(row => row.role === selectedRole.value && row.season === Number(staminaScope.value)))
const selectedV2Curves = computed(() => (response.value?.slice8?.league_curves || []).filter(row => row.family === selectedV2Family.value).sort((a, b) => a.order - b.order))
const selectedSlice11League = computed(() => (response.value?.slice11?.league_curves || []).filter(row => row.family === selectedSlice11Family.value).sort((a, b) => a.order - b.order))
const selectedSlice11Coverage = computed(() => (response.value?.slice11?.signal_coverage || []).filter(row => row.family === selectedSlice11Family.value))
const selectedSlice11GameRows = computed(() => (slice11Curves.value?.curves || []).filter(row => row.game_pk === slice11GamePk.value).sort((a, b) => a.order - b.order || slice11Families.indexOf(a.pitch_family) - slice11Families.indexOf(b.pitch_family)))
const selectedGameStates = computed(() => (gameStateDetail.value?.states || []).filter(row => row.scope === gameStateScope.value && row.eligible && row.stamina_plus !== null && row.stamina_plus !== undefined).sort((a, b) => a.game_date.localeCompare(b.game_date)))
const selectedGameState = computed(() => selectedGameStates.value.find(row => row.game_pk === slice11GamePk.value) || selectedGameStates.value.at(-1))
const selectedGameWindows = computed(() => (gameStateDetail.value?.windows || []).filter(row => row.game_pk === selectedGameState.value?.game_pk).sort((a, b) => gameStateScopes.indexOf(a.scope) - gameStateScopes.indexOf(b.scope) || a.order - b.order))
const eligiblePhysicalGames = computed(() => (physicalDetail.value?.games || []).filter(row => row.eligible).sort((a, b) => b.game_date.localeCompare(a.game_date)))
const selectedPhysicalGame = computed(() => eligiblePhysicalGames.value.find(row => row.game_pk === physicalGamePk.value))
const selectedPhysicalWindows = computed(() => (physicalDetail.value?.windows || []).filter(row => row.game_pk === physicalGamePk.value).sort((a, b) => a.order - b.order))
function physicalCoverage(coverageYear: number) { return response.value?.slice15?.coverage.find(row => row.year === coverageYear) }
function productCaseLabel(value: string) { return value.split('_').map(part => part.charAt(0).toUpperCase() + part.slice(1)).join(' ') }
const eligibleCommandGames = computed(() => (commandDetail.value?.games || []).filter(row => row.scope === 'Overall' && row.eligible).sort((a, b) => b.game_date.localeCompare(a.game_date)))
const selectedCommandGame = computed(() => eligibleCommandGames.value.find(row => row.game_pk === commandGamePk.value))
const selectedCommandWindows = computed(() => (commandDetail.value?.windows || []).filter(row => row.game_pk === commandGamePk.value).sort((a, b) => gameStateScopes.indexOf(a.scope as typeof gameStateScopes[number]) - gameStateScopes.indexOf(b.scope as typeof gameStateScopes[number]) || a.order - b.order))
const staminaScopeLabel = computed(() => staminaScope.value === 'trait' ? 'Validated two-season Stamina+' : `${staminaScope.value} Season Stamina+`)
const selectedStaminaRows = computed(() => {
  const query = staminaSearch.value.toLocaleLowerCase()
  const source = staminaScope.value === 'trait'
    ? (response.value?.slice5?.leaderboard || [])
    : (response.value?.slice5?.season_leaderboard || []).filter(row => row.season === Number(staminaScope.value))
  return source.filter(row => {
    if (row.role !== selectedRole.value || (qualifiedOnly.value && row.sample_label !== 'qualified')) return false
    return !query || row.pitcher_name.toLocaleLowerCase().includes(query) || row.team.toLocaleLowerCase().includes(query)
  })
})
const workloadEffectStages = computed(() => [
  { key: 'readiness', eyebrow: '4B · Readiness', title: 'Next appearance early-window quality', rows: selectedReadinessEffects.value },
  { key: 'retention', eyebrow: '4C · Retention', title: 'Workload effect on same-game slope', rows: selectedRetentionEffects.value }
])
function interpretCorrection(before: number, after: number) {
  if (Math.sign(before) !== Math.sign(after) && Math.abs(before) >= 0.05 && Math.abs(after) >= 0.05) return { label: 'direction reversed', className: 'is-reversed' }
  if (Math.abs(after) < Math.abs(before) * 0.6) return { label: 'attenuated', className: 'is-attenuated' }
  return { label: 'persists', className: 'is-persists' }
}
const curveCharts = computed(() => (['SP', 'RP'] as const).flatMap(role => (['appearance_pitch_count', 'season_workload'] as const).map(dimension => {
  const points = (response.value?.slice1.points || []).filter(row => row.role === role && row.dimension === dimension && row.outcome === selectedOutcome.value).sort((a, b) => a.order - b.order)
  return { role, dimension, points, range: chartRange(points) }
})))
function chartRange(points: StaminaSlice1Point[]) { return Math.max(0.5, Math.ceil(Math.max(...points.flatMap(point => [Math.abs(point.ci_low), Math.abs(point.ci_high)]), 0.5) * 10) / 10) }
function chartX(index: number, count: number) { return count <= 1 ? 374 : 72 + index * (600 / (count - 1)) }
function chartY(value: number, range: number) { return 130 - value / range * 92 }
function polyline(points: StaminaSlice1Point[], range: number) { return points.map((point, index) => `${chartX(index, points.length)},${chartY(point.adjusted_delta, range)}`).join(' ') }
function reliabilityPct(value: number) { return `${Math.round(value * 100)}%` }
function retentionLabel(value: string) { return ({ above_average: 'Above league estimate', below_average: 'Below league estimate', indistinguishable: 'Within uncertainty' } as Record<string, string>)[value] || value }
function pitcherLink(row: { pitcher_id: number; role: string; team: string; season?: number | null }) { return { path: '/pitcher-personal', query: { year: row.season || year.value, role: row.role, team: row.team, pitcher_id: row.pitcher_id } } }
function endpointLabel(value: string) { return value === 'readiness' ? 'Readiness' : value === 'retention' ? 'Retention slope' : '' }
function nullableFixed(value: number | null | undefined, digits: number) { return value === null || value === undefined ? '—' : value.toFixed(digits) }
function nullableSigned(value: number | null | undefined, digits: number) { return value === null || value === undefined ? '—' : `${value > 0 ? '+' : ''}${value.toFixed(digits)}` }
function signalLabel(value: string) { return ({ stuff_delta: 'Stuff+', velocity_delta: 'Velocity', spin_delta: 'Spin', movement_drift_inches: 'Movement', release_point_drift_inches: 'Release point', extension_delta: 'Extension', location_delta: 'Location+' } as Record<string, string>)[value] || value }
function validationGain(row: { rmse_improvement_pct?: number | null }) { return row.rmse_improvement_pct === null || row.rmse_improvement_pct === undefined ? '—' : `${row.rmse_improvement_pct > 0 ? '+' : ''}${row.rmse_improvement_pct.toFixed(2)}%` }
function passedGateCount(gates: Record<string, boolean>) { return Object.values(gates).filter(Boolean).length }
function gameStateX(index: number, count: number) { return count <= 1 ? 390 : 55 + index * (670 / (count - 1)) }
function gameStateY(value: number) { return 130 - Math.max(-30, Math.min(30, value - 100)) * 3.2 }
function gameStatePolyline(rows: StaminaGameState[], key: 'stamina_plus' | 'rolling_5') { return rows.map((row, index) => `${gameStateX(index, rows.length)},${gameStateY(row[key] ?? 100)}`).join(' ') }
</script>

<style scoped>
.stamina-lab { display: grid; gap: 18px; font-size: 16px; }
.slice-zero-panel { order: 1; }
.slice-one-panel { order: 10; }
.slice-two-panel { order: 20; }
.slice-three-panel { order: 30; }
.slice-four-panel { order: 40; }
.slice-five-panel { order: 50; }
.slice-six-panel { order: 60; }
.slice-seven-panel { order: 70; }
.slice-eight-panel { order: 80; }
.slice-nine-panel { order: 90; }
.slice-ten-panel { order: 100; }
.slice-eleven-panel { order: 110; }
.slice-eleven-game-state-panel { order: 111; }
.control-bar, .panel, .research-status, .metric-strip article, .warning-panel { border: 1px solid var(--color-border); border-radius: 0; background: var(--color-surface); }
.control-bar { display: flex; align-items: end; justify-content: space-between; gap: 22px; padding: 18px 20px; }
.control-bar > div { display: grid; gap: 6px; }
.control-bar span, .panel header span, .metric-strip span, .feature-grid article > div > span:first-child { color: var(--color-accent); font-size: 13px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }
.control-bar strong { color: var(--color-text); font-size: 20px; }
.control-bar label { display: grid; gap: 7px; color: var(--color-muted-text); font-size: 13px; font-weight: 850; text-transform: uppercase; }
.control-bar select { min-width: 150px; height: 46px; border: 1px solid var(--color-border-strong); border-radius: 0; padding: 0 13px; color: var(--color-text); background: var(--color-background); font: 800 15px inherit; }
.state-panel { margin: 0; border: 1px solid var(--color-border); border-radius: 0; padding: 20px; color: var(--color-muted-text); background: var(--color-surface); font-size: 16px; }
.state-panel--error { color: #ff8a8a; }
.research-status { display: flex; align-items: center; justify-content: space-between; gap: 20px; border-left: 5px solid var(--color-accent); padding: 18px 20px; }
.research-status div { display: grid; gap: 4px; }
.research-status span { color: var(--color-accent); font-size: 13px; font-weight: 900; text-transform: uppercase; }
.research-status h2 { margin: 0; color: var(--color-text); font-size: 24px; }
.research-status p { margin: 0; color: var(--color-muted-text); font-size: 14px; }
.metric-strip { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.metric-strip article { display: grid; gap: 7px; min-height: 128px; padding: 20px; }
.metric-strip strong { color: var(--color-text); font: 900 32px "Fira Code", monospace; }
.metric-strip small { color: var(--color-muted-text); font-size: 14px; }
.panel { overflow: hidden; }
.panel > header { display: flex; align-items: end; justify-content: space-between; gap: 20px; border-bottom: 1px solid var(--color-border); padding: 19px 21px; }
.panel > header > div { display: grid; gap: 5px; }
.panel h2 { margin: 0; color: var(--color-text); font-size: 24px; }
.panel > header p { margin: 0; color: var(--color-muted-text); font-size: 14px; }
.table-scroll { width: 100%; overflow: auto; }
table { width: 100%; min-width: 760px; border-collapse: collapse; }
th, td { border-bottom: 1px solid var(--color-border); padding: 14px 16px; text-align: right; white-space: nowrap; }
th { color: var(--color-muted-text); font-size: 12px; text-transform: uppercase; }
td { color: var(--color-muted-text); font-size: 14px; }
th:first-child, td:first-child, .note-cell { text-align: left; }
td strong { color: var(--color-text); font-size: 15px; }
.note-cell { min-width: 360px; white-space: normal; line-height: 1.55; }
.status-chip { display: inline-flex; border: 1px solid var(--color-border-strong); padding: 4px 8px; color: var(--color-muted-text); font-size: 12px; font-weight: 900; text-transform: uppercase; }
.status-chip.is-ready, .status-chip.is-current { color: #8ee8b1; border-color: #357a50; background: #183526; }
.status-chip.is-partial, .status-chip.is-scoped { color: var(--color-accent); border-color: color-mix(in srgb, var(--color-accent) 55%, var(--color-border)); }
.two-column { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.role-grid { display: grid; grid-template-columns: repeat(2, 1fr); }
.role-grid > div { display: grid; gap: 7px; min-height: 210px; border-right: 1px solid var(--color-border); padding: 22px; }
.role-grid > div:last-child { border-right: 0; }
.role-grid b { color: var(--color-accent); font-size: 15px; }
.role-grid strong { color: var(--color-text); font: 900 34px "Fira Code", monospace; }
.role-grid span, .role-grid p, .role-grid small { margin: 0; color: var(--color-muted-text); font-size: 14px; }
.bucket-layout { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); }
.bucket-layout > div:first-child { border-right: 1px solid var(--color-border); }
.bucket-layout h3 { margin: 0; border-bottom: 1px solid var(--color-border); padding: 15px 18px; color: var(--color-text); font-size: 18px; }
.feature-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); }
.feature-grid article { min-height: 210px; border-right: 1px solid var(--color-border); border-bottom: 1px solid var(--color-border); padding: 19px; }
.feature-grid article > div { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.feature-grid h3 { margin: 18px 0 7px; color: var(--color-text); font-size: 20px; }
.feature-grid article > strong { color: var(--color-accent); font: 900 27px "Fira Code", monospace; }
.feature-grid p { margin: 13px 0 0; color: var(--color-muted-text); font-size: 14px; line-height: 1.55; }
.hypothesis-list article { display: grid; grid-template-columns: 55px minmax(0, 1fr) auto; gap: 18px; border-bottom: 1px solid var(--color-border); padding: 20px 21px; }
.hypothesis-list article > b { color: var(--color-accent); font-size: 20px; }
.hypothesis-list h3 { margin: 0; color: var(--color-text); font-size: 19px; }
.hypothesis-list p { margin: 6px 0 12px; color: var(--color-muted-text); line-height: 1.55; }
.hypothesis-list small { display: block; margin-top: 5px; color: var(--color-muted-text); font-size: 13px; line-height: 1.5; }
.hypothesis-list small strong { color: var(--color-text); }
.warning-panel { padding: 19px 21px; }
.warning-panel > strong { color: var(--color-accent); font-size: 17px; }
.warning-panel p { margin: 9px 0 0; color: var(--color-muted-text); font-size: 14px; line-height: 1.55; }
.outcome-switch { display: flex; border: 1px solid var(--color-border-strong); }
.outcome-switch button { min-width: 118px; border: 0; border-right: 1px solid var(--color-border-strong); padding: 11px 16px; color: var(--color-muted-text); background: var(--color-background); font: 900 14px inherit; cursor: pointer; }
.outcome-switch button:last-child { border-right: 0; }
.outcome-switch button.active { color: #111827; background: var(--color-accent); }
.method-note { border-bottom: 1px solid var(--color-border); padding: 18px 21px; }
.method-note strong { color: var(--color-text); font-size: 15px; line-height: 1.55; }
.method-note p { margin: 7px 0 0; color: var(--color-muted-text); font-size: 14px; line-height: 1.55; }
.summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); border-bottom: 1px solid var(--color-border); }
.summary-grid article { min-height: 164px; border-right: 1px solid var(--color-border); padding: 18px; }
.summary-grid article:last-child { border-right: 0; }
.summary-grid article > span, .arm-audit-grid article > span { color: var(--color-accent); font-size: 12px; font-weight: 900; letter-spacing: .06em; text-transform: uppercase; }
.summary-grid article > strong { display: block; margin-top: 13px; color: var(--color-text); font: 900 28px "Fira Code", monospace; }
.summary-grid article.is-decline > strong { color: #ef9a9a; }
.summary-grid article.is-increase > strong { color: #90caf9; }
.summary-grid p, .summary-grid small { display: block; margin: 8px 0 0; color: var(--color-muted-text); font-size: 13px; line-height: 1.45; }
.curve-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); }
.curve-card { min-width: 0; border-right: 1px solid var(--color-border); border-bottom: 1px solid var(--color-border); }
.curve-card:nth-child(2n) { border-right: 0; }
.curve-card > header { display: flex; align-items: end; justify-content: space-between; gap: 14px; padding: 18px 20px 4px; }
.curve-card > header span { color: var(--color-accent); font-size: 13px; font-weight: 900; }
.curve-card h3 { margin: 3px 0 0; color: var(--color-text); font-size: 21px; }
.curve-card > header small { color: var(--color-muted-text); font-size: 12px; }
.curve-card svg { display: block; width: 100%; min-height: 280px; }
.zero-line { stroke: var(--color-border-strong); stroke-width: 1.5; stroke-dasharray: 6 5; }
.curve-line { fill: none; stroke: var(--color-accent); stroke-width: 3; }
.ci-line { stroke: #9fb1c9; stroke-width: 2; }
.curve-dot { fill: var(--color-accent); stroke: var(--color-background); stroke-width: 3; }
.axis-label, .bucket-label, .value-label { fill: var(--color-muted-text); font-size: 13px; font-weight: 800; }
.bucket-label, .value-label { text-anchor: middle; }
.value-label { fill: var(--color-text); }
.curve-table table { min-width: 650px; }
.curve-table th, .curve-table td { padding: 11px 13px; font-size: 12px; }
.analysis-warnings { padding: 16px 21px; }
.analysis-warnings p { margin: 6px 0; color: var(--color-muted-text); font-size: 14px; line-height: 1.5; }
.analysis-warnings p::before { content: "⚠ "; color: var(--color-accent); }
.correction-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); border-bottom: 1px solid var(--color-border); }
.correction-grid article { padding: 21px; border-right: 1px solid var(--color-border); }
.correction-grid article:last-child { border-right: 0; }
.correction-grid article > div { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.correction-grid span { color: var(--color-accent); font-size: 13px; font-weight: 900; letter-spacing: .05em; text-transform: uppercase; }
.correction-grid b { padding: 5px 8px; border: 1px solid var(--color-border-strong); font-size: 12px; text-transform: uppercase; }
.correction-grid b.is-reversed { color: #ffb4a8; border-color: #9a4f43; }
.correction-grid b.is-attenuated { color: #ffe29a; border-color: #8b7437; }
.correction-grid b.is-persists { color: #9bd8ff; border-color: #39769a; }
.correction-grid h3 { margin: 14px 0; color: var(--color-text); font-size: 22px; }
.correction-grid dl { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); margin: 0; }
.correction-grid dl div { display: grid; gap: 7px; border-left: 1px solid var(--color-border); padding: 8px 12px; }
.correction-grid dl div:first-child { border-left: 0; padding-left: 0; }
.correction-grid dt { color: var(--color-muted-text); font-size: 13px; }
.correction-grid dd { margin: 0; color: var(--color-text); font: 900 23px "Fira Code", monospace; }
.bias-layout { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); border-bottom: 1px solid var(--color-border); }
.bias-layout > article { min-width: 0; border-right: 1px solid var(--color-border); }
.bias-layout > article:last-child { border-right: 0; }
.bias-layout article > header { padding: 17px 20px; border-bottom: 1px solid var(--color-border); }
.bias-layout article > header span { color: var(--color-accent); font-size: 12px; font-weight: 900; text-transform: uppercase; }
.bias-layout h3 { margin: 5px 0 0; color: var(--color-text); font-size: 18px; }
.bias-layout table { min-width: 660px; }
.sensitivity-details { border-bottom: 1px solid var(--color-border); }
.sensitivity-details > summary { padding: 16px 21px; color: var(--color-text); font-size: 15px; font-weight: 850; cursor: pointer; }
.slice-three-controls { display: flex; align-items: center; gap: 10px; }
.slice-three-controls input { width: 240px; height: 42px; border: 1px solid var(--color-border-strong); border-radius: 0; padding: 0 13px; color: var(--color-text); background: var(--color-background); font: 750 14px inherit; }
.personal-summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); border-bottom: 1px solid var(--color-border); }
.personal-summary-grid article { min-height: 150px; border-right: 1px solid var(--color-border); padding: 20px; }
.personal-summary-grid article:last-child { border-right: 0; }
.personal-summary-grid span { color: var(--color-accent); font-size: 12px; font-weight: 900; letter-spacing: .06em; text-transform: uppercase; }
.personal-summary-grid strong { display: block; margin-top: 13px; color: var(--color-text); font: 900 28px "Fira Code", monospace; }
.personal-summary-grid p { margin: 9px 0 0; color: var(--color-muted-text); font-size: 14px; line-height: 1.5; }
.slice-five-summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); border-bottom: 1px solid var(--color-border); }
.slice-five-summary article { min-height: 150px; border-right: 1px solid var(--color-border); padding: 20px; }
.slice-five-summary article:last-child { border-right: 0; }
.slice-five-summary span, .gate-grid span { color: var(--color-accent); font-size: 12px; font-weight: 900; letter-spacing: .06em; text-transform: uppercase; }
.slice-five-summary strong { display: block; margin-top: 13px; color: var(--color-text); font: 900 28px "Fira Code", monospace; text-transform: capitalize; }
.slice-five-summary p { margin: 9px 0 0; color: var(--color-muted-text); font-size: 14px; line-height: 1.5; }
.gate-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); border-bottom: 1px solid var(--color-border); }
.gate-grid div { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 13px 20px; border-right: 1px solid var(--color-border); }
.gate-grid div:last-child { border-right: 0; }
.gate-grid b { font-size: 13px; text-transform: uppercase; }
.gate-grid b.is-pass { color: #8ee8b1; }
.gate-grid b.is-hold { color: #ffb4a8; }
.slice-five-controls { justify-content: flex-end; border-bottom: 1px solid var(--color-border); padding: 14px 20px; }
.slice-five-controls label { display: flex; align-items: center; gap: 8px; color: var(--color-muted-text); font-size: 13px; font-weight: 850; }
.slice-five-controls select { height: 42px; border: 1px solid var(--color-border-strong); border-radius: 0; padding: 0 11px; color: var(--color-text); background: var(--color-background); font: 800 13px inherit; }
.slice-five-controls input[type="checkbox"] { width: 18px; height: 18px; padding: 0; accent-color: var(--color-accent); }
.stamina-score { color: var(--color-accent); font-size: 18px; }
.slice-four-controls { display: flex; align-items: center; gap: 9px; }
.feature-influence-stage .method-note { border-top: 0; }
.positive-value { color: #8ee8b1; font-weight: 850; }
.negative-value { color: #ffb4a8; font-weight: 850; }
.strength-cell { display: flex; align-items: center; justify-content: flex-end; gap: 9px; min-width: 170px; }
.strength-cell > span { width: 105px; height: 9px; border: 1px solid var(--color-border-strong); background: var(--color-background); }
.strength-cell i { display: block; height: 100%; background: var(--color-accent); }
.strength-cell b { min-width: 45px; color: var(--color-text); font-size: 12px; }
.personal-table { max-height: 720px; border-bottom: 1px solid var(--color-border); }
.personal-table table { min-width: 1250px; }
.personal-table thead { position: sticky; top: 0; z-index: 2; background: var(--color-surface); }
.personal-table th:first-child, .personal-table td:first-child { width: 48px; text-align: center; }
.personal-table th:nth-child(2), .personal-table td:nth-child(2) { text-align: left; }
.personal-table td > small { color: var(--color-muted-text); font-size: 12px; }
.pitcher-cell { display: inline-flex; align-items: center; gap: 10px; color: var(--color-text); text-decoration: none; }
.pitcher-cell > span { display: grid; gap: 3px; }
.pitcher-cell strong { font-size: 15px; }
.pitcher-cell small { color: var(--color-muted-text); font-size: 12px; }
.pitcher-cell:hover strong { color: var(--color-accent); }
.reliability-chip { display: inline-flex; padding: 5px 8px; border: 1px solid var(--color-border-strong); font-size: 12px; font-weight: 850; text-transform: uppercase; }
.reliability-chip.is-strong { color: #8ee8b1; border-color: #357a50; }
.reliability-chip.is-moderate { color: #ffe29a; border-color: #8b7437; }
.reliability-chip.is-limited { color: #ffb4a8; border-color: #9a4f43; }
.empty-row { margin: 0; padding: 20px; color: var(--color-muted-text); font-size: 15px; }
.slice-stage { min-width: 0; border-bottom: 1px solid var(--color-border); }
.contract-list { display: grid; }
.contract-list > div { padding: 17px 20px; border-bottom: 1px solid var(--color-border); }
.contract-list > div:last-child { border-bottom: 0; }
.contract-list strong { color: var(--color-text); font-size: 14px; }
.contract-list p { margin: 7px 0 0; color: var(--color-muted-text); font-size: 14px; line-height: 1.55; }
.contract-list small { display: block; margin-top: 6px; color: var(--color-muted-text); font-size: 12px; line-height: 1.5; }
.slice-stage > header { display: flex; align-items: end; justify-content: space-between; gap: 18px; padding: 18px 21px; border-bottom: 1px solid var(--color-border); }
.slice-stage > header > div { display: grid; gap: 5px; }
.slice-stage > header span { color: var(--color-accent); font-size: 12px; font-weight: 900; letter-spacing: .06em; text-transform: uppercase; }
.slice-stage h3 { margin: 0; color: var(--color-text); font-size: 20px; }
.slice-stage > header p { max-width: 560px; margin: 0; color: var(--color-muted-text); font-size: 14px; line-height: 1.5; }
.audit-strip { display: grid; grid-template-columns: repeat(7, minmax(150px, 1fr)); overflow-x: auto; }
.audit-strip > div { display: grid; gap: 7px; min-height: 138px; border-right: 1px solid var(--color-border); padding: 18px; }
.audit-strip span { color: var(--color-muted-text); font-size: 13px; font-weight: 800; }
.audit-strip strong { color: var(--color-text); font: 900 25px "Fira Code", monospace; }
.audit-strip small { color: var(--color-accent); font-size: 12px; }
.slice-four-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); }
.slice-four-grid > article:first-child { border-right: 1px solid var(--color-border); }
.slice-four-grid table { min-width: 760px; }
.validation-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); }
.validation-grid > div { min-height: 150px; border-right: 1px solid var(--color-border); border-bottom: 1px solid var(--color-border); padding: 19px; }
.validation-grid span { color: var(--color-accent); font-size: 12px; font-weight: 900; text-transform: uppercase; }
.validation-grid strong { display: block; margin-top: 12px; color: var(--color-text); font: 900 26px "Fira Code", monospace; }
.validation-grid p, .validation-grid small { display: block; margin: 8px 0 0; color: var(--color-muted-text); font-size: 13px; line-height: 1.45; }
.arm-audit-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); }
.arm-audit-grid article { min-height: 160px; border-right: 1px solid var(--color-border); padding: 20px; }
.arm-audit-grid article:last-child { border-right: 0; }
.arm-audit-grid strong { display: block; margin-top: 13px; color: var(--color-text); font: 900 27px "Fira Code", monospace; }
.arm-audit-grid p { margin: 10px 0 0; color: var(--color-muted-text); font-size: 14px; line-height: 1.55; }
.arm-audit-panel details { border-top: 1px solid var(--color-border); padding: 15px 20px; }
.arm-audit-panel summary { color: var(--color-text); font-size: 14px; font-weight: 850; cursor: pointer; }
.arm-audit-panel details p { color: var(--color-muted-text); font-size: 13px; line-height: 1.7; }
.multisignal-table { min-width: 1320px; }
.coverage-strip { display: grid; grid-template-columns: repeat(7, minmax(150px, 1fr)); overflow-x: auto; border-top: 1px solid var(--color-border); }
.coverage-strip > div { display: grid; gap: 6px; min-height: 120px; border-right: 1px solid var(--color-border); padding: 17px; }
.coverage-strip span { color: var(--color-muted-text); font-size: 12px; font-weight: 850; text-transform: uppercase; }
.coverage-strip strong { color: var(--color-text); font: 900 23px "Fira Code", monospace; }
.coverage-strip small { color: var(--color-accent); font-size: 12px; }
.slice-eleven-controls { display: flex; align-items: end; gap: 10px; }
.slice-eleven-controls label { display: grid; gap: 6px; color: var(--color-muted-text); font-size: 12px; font-weight: 850; text-transform: uppercase; }
.slice-eleven-controls select { min-width: 210px; height: 42px; border: 1px solid var(--color-border-strong); border-radius: 0; padding: 0 10px; color: var(--color-text); background: var(--color-background); font: 750 13px inherit; }
.season-state-chart { padding: 16px 20px 10px; }
.season-state-chart svg { width: 100%; min-width: 620px; }
.season-trend-line { fill: none; stroke: var(--color-warning, #d99a32); stroke-width: 4; stroke-linejoin: round; stroke-linecap: round; }
.state-chart-key { display: flex; gap: 22px; color: var(--color-muted-text); font-size: 12px; font-weight: 800; }
.state-chart-key span::before { content: ''; display: inline-block; width: 22px; height: 3px; margin-right: 7px; vertical-align: middle; background: var(--color-accent); }
.state-chart-key span:last-child::before { background: var(--color-warning, #d99a32); }
.inline-select { display: grid; gap: 6px; color: var(--color-muted-text); font-size: 12px; font-weight: 850; text-transform: uppercase; }
.inline-select select { min-width: 250px; height: 42px; border: 1px solid var(--color-border-strong); border-radius: 0; padding: 0 10px; color: var(--color-text); background: var(--color-background); font: 750 13px inherit; }
@media (max-width: 1050px) { .metric-strip, .feature-grid, .personal-summary-grid, .validation-grid, .slice-five-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); } .two-column, .bucket-layout, .bias-layout, .slice-four-grid { grid-template-columns: 1fr; } .bucket-layout > div:first-child, .bias-layout > article:first-child, .slice-four-grid > article:first-child { border-right: 0; border-bottom: 1px solid var(--color-border); } }
@media (max-width: 1050px) { .summary-grid, .curve-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .arm-audit-grid { grid-template-columns: 1fr; } .arm-audit-grid article { border-right: 0; border-bottom: 1px solid var(--color-border); } }
@media (max-width: 680px) { .control-bar, .research-status, .panel > header, .curve-card > header, .slice-three-controls, .slice-stage > header, .slice-four-controls, .slice-eleven-controls { align-items: stretch; flex-direction: column; } .metric-strip, .feature-grid, .summary-grid, .curve-grid, .correction-grid, .personal-summary-grid, .validation-grid, .slice-five-summary, .gate-grid { grid-template-columns: 1fr; } .summary-grid article, .curve-card, .correction-grid article, .personal-summary-grid article, .slice-five-summary article { border-right: 0; border-bottom: 1px solid var(--color-border); } .correction-grid dl { grid-template-columns: 1fr; } .correction-grid dl div { border-left: 0; border-top: 1px solid var(--color-border); padding-left: 0; } .outcome-switch { width: 100%; } .outcome-switch button { flex: 1; } .slice-three-controls input[type="search"], .slice-five-controls select, .slice-eleven-controls select { width: 100%; } .role-grid { grid-template-columns: 1fr; } .role-grid > div { border-right: 0; border-bottom: 1px solid var(--color-border); } .hypothesis-list article { grid-template-columns: 44px minmax(0, 1fr); } .hypothesis-list article > .status-chip { grid-column: 2; width: fit-content; } }
</style>
