<template>
  <main class="operations-page">
    <header class="operations-topbar">
      <NuxtLink class="home-link" to="/"><ArrowLeft :size="17" /> Back home</NuxtLink>
    </header>

    <section class="operations-hero">
      <div>
        <span class="eyebrow"><Settings2 :size="16" /> Maintenance console</span>
        <h1>Data operations</h1>
        <p>Pitch data, videos, official game lines, transactions, injuries, and contract snapshots live here. Automatic update: daily at 03:00 Asia/Taipei.</p>
      </div>
      <label>
        Season
        <select v-model.number="year" :disabled="running">
          <option v-for="option in yearOptions" :key="option" :value="option">{{ option }}</option>
        </select>
      </label>
    </section>

    <SiteArchitectureMap />

    <section class="command-bar" aria-label="Update commands">
      <button class="primary-action" type="button" :disabled="running" @click="runEverything">
        <RefreshCw :size="19" :class="{ spinning: running }" />
        {{ running ? 'Update in progress' : 'Update everything' }}
      </button>
      <button type="button" :disabled="running" @click="runGamePipeline"><DatabaseZap :size="18" /> Update game data</button>
      <button type="button" :disabled="running" @click="runRosterPipeline"><WalletCards :size="18" /> Update contracts & transactions</button>
      <button class="cache-action" type="button" :disabled="running" @click="clearClientCache"><Eraser :size="18" /> Clear browser cache</button>
    </section>

    <p v-if="message" :class="['operations-message', { error: failed }]" role="status">{{ message }}</p>

    <section class="pipeline-grid">
      <article v-for="item in pipelineItems" :key="item.key" class="pipeline-card">
        <component :is="item.icon" :size="23" />
        <div><span>{{ item.group }}</span><h2>{{ item.title }}</h2><p>{{ item.description }}</p></div>
        <strong>{{ item.scope }}</strong>
      </article>
    </section>

    <section class="status-panel">
      <header>
        <div><span class="eyebrow">Current data</span><h2>Pipeline status</h2></div>
        <button type="button" :disabled="statusLoading" aria-label="Refresh status" @click="refreshStatus">
          <RefreshCw :size="17" :class="{ spinning: statusLoading }" />
        </button>
      </header>
      <div class="status-grid">
        <div><span>Pitch data</span><strong>{{ statusValue('pitcher_data.latest_pitch_date') || statusValue('pitcher_data.data_through') || '—' }}</strong></div>
        <div><span>Location+</span><strong>{{ statusValue('pitcher_data.latest_location_plus_date') || '—' }}</strong></div>
        <div><span>Video lookup</span><strong>{{ statusValue('video_lookup.latest_source_game_date') || statusValue('video_lookup.latest_game_date') || '—' }}</strong></div>
        <div><span>Pitcher lines</span><strong>{{ statusValue('pitcher_game_lines.latest_source_game_date') || statusValue('pitcher_game_lines.latest_game_date') || '—' }}</strong></div>
      </div>
    </section>

    <section class="jobs-panel">
      <header><div><span class="eyebrow">This session</span><h2>Update jobs</h2></div><span>{{ jobs.length }} jobs</span></header>
      <div v-if="jobs.length" class="job-list">
        <article v-for="job in jobs" :key="String(job.job_id)">
          <div class="job-icon">
            <CheckCircle2 v-if="job.status === 'completed'" :size="20" />
            <CircleX v-else-if="job.status === 'failed'" :size="20" />
            <Clock3 v-else :size="20" />
          </div>
          <div><h3>{{ jobLabel(job) }}</h3><p>{{ jobDetail(job) }}</p></div>
          <span :class="['job-pill', String(job.status || 'queued')]">{{ job.status || 'queued' }}</span>
        </article>
      </div>
      <p v-else class="empty-jobs">No update jobs have been started in this session.</p>
    </section>

    <footer>Hidden entry, visible operations. This page is not an authentication boundary.</footer>
  </main>
</template>

<script setup lang="ts">
import { ArrowLeft, CheckCircle2, CircleX, Clock3, Database, DatabaseZap, Eraser, Film, FileChartColumn, RefreshCw, Settings2, ShieldPlus, WalletCards } from '@lucide/vue'
import SiteArchitectureMap from '~/components/admin/SiteArchitectureMap.vue'

const api = useApi()
const year = ref(2026)
const yearOptions = [2026, 2025, 2024, 2023, 2022, 2021]
const running = ref(false)
const failed = ref(false)
const message = ref('')
const jobs = ref<Record<string, any>[]>([])
const status = ref<Record<string, unknown> | null>(null)
const statusLoading = ref(false)
const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))

const pipelineItems = [
  { key: 'pitches', group: 'Game pipeline', title: 'Pitch data', description: 'Refresh the season pitch database and derived source files.', scope: 'Season', icon: Database },
  { key: 'videos', group: 'Game pipeline', title: 'Video lookup', description: 'Attach playable video sources to newly available pitches.', scope: 'New games', icon: Film },
  { key: 'lines', group: 'Game pipeline', title: 'Pitcher game lines', description: 'Build official outing lines used by reports and rotations.', scope: 'New games', icon: FileChartColumn },
  { key: 'transactions', group: 'Roster pipeline', title: 'Transactions & injuries', description: 'Refresh the league-wide MLB roster movement cache.', scope: '30 clubs', icon: ShieldPlus },
  { key: 'payroll', group: 'Roster pipeline', title: 'Contract snapshots', description: 'Refresh FanGraphs payroll and contract tables with bounded concurrency.', scope: '30 clubs', icon: WalletCards }
]

onMounted(refreshStatus)

async function runEverything() { await execute(async () => { await runGameSteps(); await runRosterStep() }, 'All data pipelines completed.') }
async function runGamePipeline() { await execute(runGameSteps, 'Game data pipeline completed.') }
async function runRosterPipeline() { await execute(runRosterStep, 'Contracts, transactions, and injuries updated.') }

async function execute(task: () => Promise<void>, successMessage: string) {
  if (running.value) return
  running.value = true
  failed.value = false
  message.value = 'Starting update pipeline…'
  jobs.value = []
  try {
    await task()
    message.value = successMessage
  } catch (error) {
    failed.value = true
    message.value = error instanceof Error ? error.message : 'The update pipeline failed.'
  } finally {
    running.value = false
    await refreshStatus()
  }
}

async function runGameSteps() {
  message.value = 'Refreshing pitch data…'
  await trackJob(await api.refreshPitcherDataJob(year.value))
  message.value = 'Backfilling video lookup…'
  await trackJob(await api.backfillVideoLookupJob({ year: year.value }))
  message.value = 'Building official pitcher game lines…'
  await trackJob(await api.backfillPitcherGameLinesJob({ year: year.value }))
}

async function runRosterStep() {
  message.value = 'Refreshing transactions, injuries, and all team contracts…'
  await trackJob(await api.refreshRosterDataJob(year.value))
}

async function trackJob(started: Record<string, any>) {
  let current = started
  const jobId = String(started.job_id || '')
  upsertJob(current)
  while (jobId && !['completed', 'failed'].includes(String(current.status))) {
    await sleep(2200)
    current = await api.adminJob(jobId)
    upsertJob(current)
  }
  if (String(current.status) === 'failed') throw new Error(`${jobLabel(current)} failed: ${String(current.error || 'Unknown error')}`)
  return current
}

function upsertJob(job: Record<string, any>) {
  const index = jobs.value.findIndex(item => String(item.job_id) === String(job.job_id))
  if (index >= 0) jobs.value.splice(index, 1, job)
  else jobs.value.push(job)
}

async function refreshStatus() {
  statusLoading.value = true
  try { status.value = await api.adminStatus(year.value) }
  catch { status.value = null }
  finally { statusLoading.value = false }
}

function statusValue(path: string) {
  const value = path.split('.').reduce<unknown>((current, key) => current && typeof current === 'object' ? (current as Record<string, unknown>)[key] : undefined, status.value)
  return value === undefined || value === null || value === '' ? '' : String(value)
}

function jobLabel(job: Record<string, any>) {
  const name = String(job.name || '')
  if (name.includes('roster')) return 'Contracts & transactions'
  if (name.includes('video')) return 'Video lookup'
  if (name.includes('game') || name.includes('line')) return 'Pitcher game lines'
  if (name.includes('pitcher')) return 'Pitch data'
  return 'Update job'
}

function jobDetail(job: Record<string, any>) {
  if (job.error) return String(job.error)
  if (job.status !== 'completed') return job.status === 'running' ? 'Update is running on the backend.' : 'Waiting to start.'
  const coverage = job.result?.coverage
  if (coverage?.status === 'source_pending') {
    const pendingDates = coverage.source_pending?.pending_dates?.join(', ') || coverage.missing_dates?.join(', ') || 'latest games'
    return `Statcast has not published ${pendingDates} yet. Kept data through ${coverage.latest_local_date || 'the latest available date'}; the next update will retry automatically.`
  }
  const payroll = job.result?.payroll
  if (payroll?.source_status === 'temporarily_blocked') return `FanGraphs temporarily blocked automated access. Kept ${payroll.preserved_count} team snapshots; transactions refreshed.`
  if (payroll) return `${payroll.updated_count}/${payroll.requested_count} team payrolls updated${payroll.failed_count ? ` · ${payroll.failed_count} failed` : ''}. Transactions refreshed.`
  return 'Completed successfully.'
}

async function clearClientCache() {
  if (!import.meta.client) return
  const savedTheme = localStorage.getItem('theme-mode')
  clearNuxtData()
  localStorage.clear()
  sessionStorage.clear()
  if (savedTheme) localStorage.setItem('theme-mode', savedTheme)
  if ('caches' in window) await Promise.all((await caches.keys()).map(name => caches.delete(name)))
  message.value = 'Browser cache cleared.'
}
</script>

<style scoped>
.operations-page { --orange: #f5a332; --line: rgba(245,163,50,.24); min-height: 100vh; padding: 28px clamp(18px,4vw,58px) 36px; color: #f7f7f7; background: radial-gradient(circle at 84% 4%,rgba(245,163,50,.18),transparent 30rem),linear-gradient(145deg,#070707,#111 55%,#070707); }
.operations-topbar,.operations-hero,.command-bar,.pipeline-grid,.status-panel,.jobs-panel,.operations-page>footer { max-width: 1280px; margin-inline: auto; }
.operations-topbar { display:flex; align-items:center; justify-content:flex-end; margin-bottom:24px; }
.home-link,.eyebrow { display:inline-flex; align-items:center; gap:7px; }.home-link{color:#bbb;font-weight:800;text-decoration:none}.home-link:hover{color:var(--orange)}
.operations-hero { display:flex; align-items:end; justify-content:space-between; gap:30px; border:1px solid var(--line); border-radius:18px; padding:clamp(25px,4vw,46px); background:linear-gradient(110deg,rgba(255,255,255,.035),rgba(245,163,50,.08)); }
.eyebrow { color:var(--orange); font-size:11px; font-weight:950; letter-spacing:.09em; text-transform:uppercase; }.operations-hero h1{margin:10px 0 8px;font-size:clamp(38px,5vw,62px);font-weight:750;line-height:1.06;letter-spacing:-.012em}.operations-hero p{max-width:690px;margin:0;color:#aaa;font-size:16px;line-height:1.55}
.operations-hero label{display:grid;gap:8px;min-width:150px;color:#aaa;font-size:11px;font-weight:900;text-transform:uppercase}.operations-hero select{min-height:44px;border:1px solid #444;border-radius:10px;padding:0 12px;color:#fff;background:#111;font-weight:850}
.command-bar { display:flex; flex-wrap:wrap; gap:10px; margin-top:16px; border:1px solid #292929;border-radius:14px;padding:12px;background:rgba(17,17,17,.92)}.command-bar button{min-height:44px;display:inline-flex;align-items:center;gap:8px;border:1px solid #393939;border-radius:10px;padding:0 15px;color:#eee;background:#181818;font-weight:900;cursor:pointer}.command-bar button:hover{border-color:var(--orange)}.command-bar .primary-action{color:#111;border-color:var(--orange);background:var(--orange)}.command-bar .cache-action{margin-left:auto;color:#aaa}.command-bar button:disabled{cursor:wait;opacity:.55}
.operations-message{max-width:1280px;margin:14px auto 0;border-left:3px solid #64c77a;padding:9px 13px;color:#d8f5df;background:rgba(70,150,88,.1)}.operations-message.error{border-color:#e3544d;color:#ffd8d4;background:rgba(190,58,50,.1)}
.pipeline-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin-top:16px}.pipeline-card{min-height:185px;display:flex;flex-direction:column;gap:15px;border:1px solid #292929;border-radius:14px;padding:18px;background:#141414}.pipeline-card>svg{color:var(--orange)}.pipeline-card span{color:#777;font-size:9px;font-weight:900;letter-spacing:.08em;text-transform:uppercase}.pipeline-card h2{margin:4px 0 0;font-size:17px}.pipeline-card p{margin:7px 0 0;color:#999;font-size:12px;line-height:1.5}.pipeline-card>strong{margin-top:auto;color:var(--orange);font-size:11px;text-transform:uppercase}
.status-panel,.jobs-panel{margin-top:16px;border:1px solid #292929;border-radius:14px;background:#121212}.status-panel>header,.jobs-panel>header{display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #292929;padding:17px 20px}.status-panel h2,.jobs-panel h2{margin:5px 0 0;font-size:20px}.status-panel header button{width:36px;height:36px;display:grid;place-items:center;border:1px solid #333;border-radius:9px;color:var(--orange);background:#181818;cursor:pointer}.status-grid{display:grid;grid-template-columns:repeat(4,1fr)}.status-grid>div{display:grid;gap:7px;padding:20px;border-right:1px solid #292929}.status-grid>div:last-child{border:0}.status-grid span{color:#888;font-size:10px;font-weight:850;text-transform:uppercase}.status-grid strong{font:800 22px "Fira Code",monospace}
.jobs-panel>header>span{color:#777;font-size:11px;font-weight:850}.job-list{display:grid}.job-list article{display:grid;grid-template-columns:38px minmax(0,1fr) auto;align-items:center;gap:11px;border-bottom:1px solid #242424;padding:14px 20px}.job-list article:last-child{border:0}.job-icon{width:34px;height:34px;display:grid;place-items:center;border-radius:50%;color:var(--orange);background:rgba(245,163,50,.1)}.job-list h3{margin:0;font-size:14px}.job-list p{margin:4px 0 0;color:#888;font-size:11px}.job-pill{min-width:88px;border-radius:999px;padding:6px 9px;color:#111;background:#999;font-size:9px;font-weight:950;text-align:center;text-transform:uppercase}.job-pill.queued,.job-pill.running{background:var(--orange)}.job-pill.completed{background:#64c77a}.job-pill.failed{color:#fff;background:#c43d34}.empty-jobs{margin:0;padding:30px 20px;color:#777;text-align:center}.operations-page>footer{margin-top:26px;border-top:1px solid var(--line);padding-top:18px;color:#666;font-size:10px;text-align:right}.spinning{animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}
@media(max-width:1050px){.pipeline-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:680px){.operations-hero{align-items:stretch;flex-direction:column}.command-bar{display:grid}.command-bar .cache-action{margin-left:0}.pipeline-grid,.status-grid{grid-template-columns:1fr}.status-grid>div{border-right:0;border-bottom:1px solid #292929}.job-list article{grid-template-columns:34px minmax(0,1fr)}.job-pill{grid-column:2;width:max-content}.operations-page>footer{text-align:left}}
@media(prefers-reduced-motion:reduce){.spinning{animation:none}}
</style>
