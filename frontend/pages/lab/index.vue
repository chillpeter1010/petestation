<template>
  <main class="lab-hub-page">
    <ComparisonPageHeader eyebrow="Petehub Research" title="Lab" description="One entrance for pitcher, batter, fielder, and pitcher-catcher research workbenches." back-to="/" back-label="Home" />

    <nav class="lab-stations" aria-label="Lab stations" role="tablist">
      <NuxtLink v-for="station in stations" :key="station.value" :to="{ path: '/lab', query: { area: station.value } }" role="tab" :aria-selected="activeArea === station.value" :class="{ active: activeArea === station.value }">
        <span>{{ station.kicker }}</span><strong>{{ station.label }}</strong>
      </NuxtLink>
    </nav>

    <section class="station-intro">
      <span>{{ activeStation.kicker }}</span>
      <h2>{{ activeStation.title }}</h2>
      <p>{{ activeStation.description }}</p>
    </section>

    <section class="lab-grid" :aria-label="`${activeStation.label} modules`">
      <NuxtLink v-for="module in activeStation.modules" :key="module.title" class="lab-card" :class="module.accent" :to="module.to">
        <span>{{ module.kicker }}</span><h3>{{ module.title }}</h3><p>{{ module.description }}</p><strong>Open</strong>
      </NuxtLink>
    </section>
  </main>
</template>

<script setup lang="ts">
type LabArea = 'pitcher' | 'batter' | 'fielder' | 'pair'
type LabModule = { kicker: string; title: string; description: string; to: string | { path: string; query: Record<string, string> }; accent?: string }
type LabStation = { value: LabArea; label: string; kicker: string; title: string; description: string; modules: LabModule[] }

const route = useRoute()
const stations: LabStation[] = [
  { value:'pitcher',label:'Pitcher',kicker:'Pitch design & state',title:'Pitcher Lab',description:'Pitch quality, command, workload, leverage, archetypes, and performance-state research.',modules:[
    {kicker:'Player archetypes',title:'Pitcher Tag Lab',description:'Arsenal depth, primary pairs, arm slots, command profiles, and sample support.',to:'/lab/tags',accent:'tags'},
    {kicker:'Cross-metric research',title:'Pitcher Metric Explorer',description:'Compare compatible pitcher-season metrics with coverage-aware descriptive analysis.',to:'/lab/pitcher-metrics'},
    {kicker:'Starter',title:'Starter Fatigue Lab',description:'Pregame readiness, inning fatigue, PA trends, and starter game trials.',to:'/rotation/fatigue-lab'},
    {kicker:'Reliever',title:'Bullpen Fatigue Lab',description:'Recent workload, rest context, leverage, and bullpen readiness.',to:'/rotation/reliever-fatigue-lab'},
    {kicker:'Stuff',title:'Stuff Lab',description:'Pitch-type Stuff+, movement profiles, release traits, and diagnostics.',to:'/lab/stuff'},
    {kicker:'Simulator',title:'Stuff Calculator',description:'Score a hypothetical pitch shape with the active Stuff+ model.',to:'/lab/stuff-calculator'},
    {kicker:'Location',title:'Location+ Field',description:'Zone quality, heart-shadow-chase features, and Location+ diagnostics.',to:'/lab/location'},
    {kicker:'Pitching',title:'Pitching+ Lab',description:'Complete-pitch value, rankings, pitch splits, trends, and validation.',to:'/lab/pitching'},
    {kicker:'Bullpen value',title:'RE24 & Leverage Lab',description:'Game states, RE24, LI, reference checks, and reliever rankings.',to:'/lab/leverage'},
    {kicker:'Workload quality',title:'Stamina Lab',description:'Observed game stamina, coverage, reliability, and frozen research contracts.',to:'/lab/stamina'},
    {kicker:'Performance state',title:'Performance State Lab',description:'Collapse and rebound forecasts, shadow layers, and player timelines.',to:'/lab/performance-state'}]},
  { value:'batter',label:'Batter',kicker:'Decisions & contact',title:'Batter Lab',description:'Swing decisions, bat-to-ball execution, pitch-quality response, and hitter archetypes.',modules:[
    {kicker:'Player archetypes',title:'Batter Tag Lab',description:'Review descriptive hitter tags and sample support.',to:'/batters/lab/tags',accent:'tags'},
    {kicker:'Pitch quality',title:'Stuff Attack',description:'Who attacks premium pitches and who still creates value against them.',to:'/batters/lab/stuff-attack'},
    {kicker:'Bat-to-ball alignment',title:'Swing Timing',description:'Timing, attack-angle, contact, and outcome relationships.',to:'/batters/lab/swing-timing'},
    {kicker:'Swing visual',title:'Vision',description:'Interactive swing-path and pitch-contact visual research.',to:'/batters/lab/vision'}]},
  { value:'fielder',label:'Fielder',kicker:'Defense research',title:'Fielder Lab',description:'Role-specific defensive workbenches, currently centered on catcher receiving and run prevention.',modules:[
    {kicker:'Catcher research',title:'Catcher Metrics Lab',description:'Raw accounting, pitcher-mix baselines, xERA, FRV, and reliability diagnostics.',to:'/fielders/catchers/lab'},
    {kicker:'Receiving',title:'Framing',description:'Called-strike lift and zone-value staging page.',to:'/fielders/catchers/framing'},
    {kicker:'Control',title:'Blocking',description:'Blocked balls, passed-ball risk, and dirt management.',to:'/fielders/catchers/blocking'},
    {kicker:'Run game',title:'Throwing',description:'Pop time, exchange, arm, and caught-stealing context.',to:'/fielders/catchers/throwing'},
    {kicker:'Challenge',title:'ABS',description:'Automated-zone review and challenge context.',to:'/fielders/catchers/abs'}]},
  { value:'pair',label:'Pitcher × Catcher',kicker:'Battery research',title:'Pitcher × Catcher Lab',description:'The shared pitcher-catcher ledger, paired results, sequence context, and sensitivity diagnostics in one station.',modules:[
    {kicker:'Paired efficiency',title:'Paired Duo',description:'Compare pitcher-catcher combinations with the default 40-inning shared-work threshold.',to:{path:'/fielders/catchers/leaderboard',query:{view:'pairs'}},accent:'pair'},
    {kicker:'Catcher-led view',title:'Catcher Metrics Lab',description:'Select a catcher and audit every paired pitcher, full-season mix, xERA, and LCO diagnostics.',to:'/fielders/catchers/lab'},
    {kicker:'Pitch mix by count',title:'Battery Sequence',description:'Inspect count-level pitch usage for a selected catcher and pitcher.',to:'/fielders/catchers/sequence'},
    {kicker:'Reference table',title:'Catcher Leaderboard',description:'Return to the catcher-level descriptive leaderboard and expand individual pairing rows.',to:'/fielders/catchers/leaderboard'}]}
]
const requestedArea = computed(() => String(route.query.area || 'pitcher'))
const activeArea = computed<LabArea>(() => stations.some(station => station.value === requestedArea.value) ? requestedArea.value as LabArea : 'pitcher')
const activeStation = computed(() => stations.find(station => station.value === activeArea.value) || stations[0])
</script>

<style scoped>
.lab-hub-page{display:grid;gap:18px}.lab-stations{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;border:1px solid var(--color-border);border-radius:14px;padding:9px;background:var(--color-surface);box-shadow:var(--shadow-sm)}.lab-stations a{min-height:66px;display:grid;align-content:center;gap:3px;border:1px solid transparent;border-radius:10px;padding:10px 14px;color:var(--color-muted-text);text-decoration:none}.lab-stations a:hover,.lab-stations a:focus-visible{border-color:var(--color-border-strong);outline:none}.lab-stations a.active{color:var(--color-on-primary);background:var(--color-primary)}.lab-stations span{font-size:9px;font-weight:900;letter-spacing:.08em;text-transform:uppercase}.lab-stations strong{font-size:15px}.station-intro{border-left:4px solid var(--color-primary);padding:13px 18px}.station-intro span,.lab-card>span{color:var(--color-primary);font-size:11px;font-weight:900;letter-spacing:.06em;text-transform:uppercase}.station-intro h2{margin:4px 0;font-size:28px}.station-intro p,.lab-card p{margin:0;color:var(--color-muted-text);line-height:1.5}.lab-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}.lab-card{min-height:210px;display:flex;flex-direction:column;justify-content:space-between;gap:14px;border:1px solid var(--color-border);border-radius:var(--radius-md);padding:18px;color:var(--color-foreground);background:var(--color-surface);box-shadow:var(--shadow-sm);text-decoration:none;transition:transform 140ms ease,border-color 140ms ease}.lab-card:hover{transform:translateY(-2px);border-color:var(--color-primary)}.lab-card h3{margin:0;font-size:22px}.lab-card>strong{width:max-content;border-radius:999px;padding:6px 12px;color:var(--color-on-primary);background:var(--color-primary);font-size:12px}.lab-card.tags{background:radial-gradient(circle at top right,color-mix(in srgb,#69d3c3 12%,transparent),transparent 40%),var(--color-surface)}.lab-card.pair{background:radial-gradient(circle at top right,color-mix(in srgb,var(--color-primary) 18%,transparent),transparent 42%),var(--color-surface)}
@media(max-width:1120px){.lab-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:760px){.lab-stations{grid-template-columns:repeat(2,minmax(0,1fr))}.lab-grid{grid-template-columns:1fr}}@media(prefers-reduced-motion:reduce){.lab-card{transition:none}}
</style>
