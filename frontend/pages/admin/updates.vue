<template>
  <main class="operations-page">
    <header class="operations-topbar">
      <NuxtLink class="home-link" to="/"><ArrowLeft :size="17" /> Back home</NuxtLink>
    </header>

    <section class="operations-hero">
      <div>
        <span class="eyebrow"><Settings2 :size="16" /> Maintenance console</span>
        <h1>Data operations</h1>
        <p>Pitch data, videos, official game lines, transactions, injuries, and contract snapshots live here. The scheduler checks in daily at 03:00 Asia/Taipei.</p>
      </div>
      <div class="operations-controls">
        <button class="brand-switch" type="button" role="switch" :aria-checked="isPetehub" @click="toggleBrand">
          <span class="brand-switch__track" aria-hidden="true"><span /></span>
          <span><small>Site identity</small><strong>{{ brandName }}</strong></span>
        </button>
        <button class="daily-switch" type="button" role="switch" :aria-checked="dailyGameUpdatesEnabled" :disabled="settingsSaving" @click="toggleDailyGameUpdates">
          <span class="daily-switch__track" aria-hidden="true"><span /></span>
          <span><small>Daily game refresh</small><strong>{{ dailyGameUpdatesEnabled ? 'Enabled' : 'Off-season pause' }}</strong><em>Transactions stay daily</em></span>
        </button>
        <label>
          Season
          <select v-model.number="year" :disabled="running">
            <option v-for="option in yearOptions" :key="option" :value="option">{{ option }}</option>
          </select>
        </label>
      </div>
    </section>

    <AdminProjectTracker />

    <AdminResearchDisplayStandards />

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

    <AdminVideoBackfill :year="year" :disabled="running" />

    <section class="historical-panel" aria-labelledby="historical-plus-title">
      <div class="historical-copy">
        <span class="eyebrow">Historical model coverage</span>
        <h2 id="historical-plus-title">Backfill Plus data by season</h2>
        <p>Select one season below. Only that season runs Location+, per-pitch Stuff+, Plus leaderboards, Pitching+, and Stamina datasets; completed pitchers are skipped automatically.</p>
        <p class="historical-note">This uses local compute, not chat tokens. You may close this page, but the backend must remain running.</p>
      </div>
      <div class="historical-action">
        <span :class="['historical-state', historicalStateClass]">{{ historicalStateLabel }}</span>
      </div>
      <div class="historical-years" aria-label="Historical backfill season status">
        <button
          v-for="item in historicalYears"
          :key="item.year"
          type="button"
          :disabled="historicalRunning"
          :aria-label="`Update ${item.year} Plus data`"
          @click="runHistoricalPlus(item.year)"
        >
          <span>{{ item.year }}</span>
          <strong :class="`is-${item.status}`">{{ item.status }}</strong>
          <small>{{ item.detail }}</small>
          <em>{{ historicalRunning && Number(historicalStatus?.current_year) === item.year ? 'Running…' : `Update ${item.year}` }}</em>
        </button>
      </div>
      <p class="historical-progress" role="status">{{ historicalMessage }}</p>
    </section>

    <section class="historical-panel catcher-ledger-panel" aria-labelledby="catcher-ledger-title">
      <div class="historical-copy">
        <span class="eyebrow">Catcher descriptive metrics · Slice 1</span>
        <h2 id="catcher-ledger-title">Build catcher ledger by season</h2>
        <p>Select a season to download or resume immutable MLB game feeds, rebuild PA and runner responsibility accounting, and reconcile the pitcher-catcher ledger to official pitcher game lines.</p>
        <p class="historical-note">Existing snapshots are reused. This runs on the backend without chat tokens; keep the backend running, but this page may be closed or refreshed.</p>
      </div>
      <div class="historical-action">
        <span :class="['historical-state', catcherStateClass]">{{ catcherStateLabel }}</span>
      </div>
      <div class="historical-years catcher-years" aria-label="Catcher ledger season status">
        <button
          v-for="item in catcherYears"
          :key="item.year"
          type="button"
          :class="{ 'is-complete': item.status === 'completed' }"
          :disabled="catcherRunning || item.status === 'completed'"
          :aria-label="item.status === 'completed' ? `${item.year} catcher ledger completed` : `Build ${item.year} catcher ledger`"
          @click="runCatcherLedger(item.year)"
        >
          <span>{{ item.year }}</span>
          <strong :class="`is-${item.status}`">{{ item.status }}</strong>
          <small>{{ item.detail }}</small>
          <div
            class="catcher-progress-track"
            role="progressbar"
            :aria-label="`${item.year} catcher ledger progress`"
            :aria-valuenow="item.progress"
            aria-valuemin="0"
            aria-valuemax="100"
          ><i :style="{ width: `${item.progress}%` }" /></div>
          <em>{{ catcherRunning && Number(catcherStatus?.active_job?.year) === item.year ? 'Running…' : item.status === 'completed' ? 'Completed' : item.status === 'failed' ? 'Retry after review' : 'Start / resume' }}</em>
        </button>
      </div>
      <p class="historical-progress" role="status">{{ catcherMessage }}</p>
    </section>

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
        <div><span>Daily game refresh</span><strong>{{ dailyGameUpdatesEnabled ? 'enabled' : 'paused' }}</strong></div>
        <div><span>Daily transactions</span><strong>enabled</strong></div>
        <div><span>Daily update</span><strong>{{ statusValue('daily_update.status') || '—' }}</strong></div>
        <div><span>Last heartbeat</span><strong class="status-time">{{ statusValue('daily_update.heartbeat_at') || '—' }}</strong></div>
      </div>
    </section>

    <AdminDataFreshness ref="freshnessPanel" :year="year" />

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

    <footer>Backstage operations are restricted by server-side authorization.</footer>
  </main>
</template>

<script setup lang="ts">
import { ArrowLeft, CheckCircle2, CircleX, Clock3, Database, DatabaseZap, Eraser, Film, FileChartColumn, RefreshCw, Settings2, ShieldPlus, WalletCards } from '@lucide/vue'
import SiteArchitectureMap from '~/components/admin/SiteArchitectureMap.vue'
import AdminDataFreshness from '~/components/admin/AdminDataFreshness.vue'
import AdminProjectTracker from '~/components/admin/AdminProjectTracker.vue'
import AdminResearchDisplayStandards from '~/components/admin/AdminResearchDisplayStandards.vue'
import AdminVideoBackfill from '~/components/admin/AdminVideoBackfill.vue'

const api = useApi()
const { isPetehub, brandName, toggleBrand } = useSiteBrand()
const year = ref(2026)
const yearOptions = [2026, 2025, 2024, 2023, 2022, 2021]
const running = ref(false)
const failed = ref(false)
const message = ref('')
const jobs = ref<Record<string, any>[]>([])
const status = ref<Record<string, unknown> | null>(null)
const statusLoading = ref(false)
const dailyGameUpdatesEnabled = ref(true)
const settingsSaving = ref(false)
const historicalStatus = ref<Record<string, any> | null>(null)
const catcherStatus = ref<Record<string, any> | null>(null)
const freshnessPanel = ref<InstanceType<typeof AdminDataFreshness> | null>(null)
const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))
let historicalPollTimer: ReturnType<typeof setInterval> | undefined
let catcherPollTimer: ReturnType<typeof setInterval> | undefined

const pipelineItems = [
  { key: 'pitches', group: 'Game pipeline', title: 'Pitch data', description: 'Refresh the season pitch database and derived source files.', scope: 'Season', icon: Database },
  { key: 'videos', group: 'Game pipeline', title: 'Video lookup', description: 'Attach playable video sources to newly available pitches.', scope: 'New games', icon: Film },
  { key: 'lines', group: 'Game pipeline', title: 'Pitcher game lines', description: 'Build official outing lines used by reports and rotations.', scope: 'New games', icon: FileChartColumn },
  { key: 'transactions', group: 'Roster pipeline', title: 'Transactions & injuries', description: 'Refresh the league-wide MLB roster movement cache.', scope: '30 clubs', icon: ShieldPlus },
  { key: 'payroll', group: 'Roster pipeline', title: 'Contract snapshots', description: 'Refresh FanGraphs payroll and contract tables with bounded concurrency.', scope: '30 clubs', icon: WalletCards }
]

const historicalRunning = computed(() => running.value || Boolean(historicalStatus.value?.active_job))
const historicalStateLabel = computed(() => {
  if (historicalStatus.value?.active_job) return 'RUNNING'
  return String(historicalStatus.value?.status || 'not_started').replace('_', ' ').toUpperCase()
})
const historicalStateClass = computed(() => String(historicalStatus.value?.active_job ? 'running' : historicalStatus.value?.status || 'not_started'))
const historicalMessage = computed(() => String(historicalStatus.value?.message || 'No historical backfill has been started.'))
const historicalYears = computed(() => [2021, 2022, 2023, 2024, 2025].map(targetYear => {
  const entry = historicalStatus.value?.years?.[String(targetYear)] || {}
  const stage = String(entry.current_stage || '')
  const stages = Object.values(entry.stages || {}) as Record<string, any>[]
  const completedStages = stages.filter(item => ['completed', 'current'].includes(String(item.status))).length
  const stuffProgress = entry.stages?.pitch_stuff_plus?.progress
  const detail = stage === 'pitch_stuff_plus' && stuffProgress
    ? `${Number(stuffProgress.coverage_pct || 0).toFixed(1)}% · ${Number(stuffProgress.processed_pitchers || 0).toLocaleString()} pitchers`
    : stage ? `${stage.replaceAll('_', ' ')} · ${completedStages}/5` : `${completedStages}/5 stages`
  return {
    year: targetYear,
    status: String(entry.status || 'pending'),
    detail
  }
}))

const catcherRunning = computed(() => running.value || Boolean(catcherStatus.value?.active_job))
const catcherStateLabel = computed(() => {
  if (catcherStatus.value?.active_job) return 'RUNNING'
  return String(catcherStatus.value?.status || 'not_started').replace('_', ' ').toUpperCase()
})
const catcherStateClass = computed(() => String(catcherStatus.value?.active_job ? 'running' : catcherStatus.value?.status || 'not_started'))
const catcherMessage = computed(() => String(catcherStatus.value?.message || 'No catcher ledger season has been completed.'))
const catcherYears = computed(() => [2021, 2022, 2023, 2024, 2025, 2026].map(targetYear => {
  const entry = catcherStatus.value?.years?.[String(targetYear)] || {}
  const available = Number(entry.available_snapshots || 0)
  const expected = Number(entry.expected_games || 0)
  const status = String(entry.status || (available ? 'partial' : 'not_started'))
  const processed = Number(entry.processed_games || 0)
  const progress = status === 'completed'
    ? 100
    : expected
      ? Math.max(0, Math.min(100, Math.round(((status === 'building' ? processed : available) / expected) * 100)))
      : 0
  const detail = status === 'completed'
    ? `${Number(entry.summary?.pitcher_catcher_rows || 0).toLocaleString()} pairs · reconciled`
    : status === 'building' && expected
      ? `${processed.toLocaleString()} / ${expected.toLocaleString()} games · building ledger`
    : expected
      ? `${available.toLocaleString()} / ${expected.toLocaleString()} feeds · ${String(entry.stage || 'pending').replaceAll('_', ' ')}`
      : available
        ? `${available.toLocaleString()} feeds saved · resumable`
        : 'No snapshots yet'
  return { year: targetYear, status, detail, progress }
}))

onMounted(async () => {
  await Promise.all([refreshStatus(), refreshHistoricalPlusStatus(), refreshCatcherStatus()])
  if (historicalStatus.value?.active_job) beginHistoricalStatusPolling()
  if (catcherStatus.value?.active_job) beginCatcherStatusPolling()
})
onBeforeUnmount(() => {
  if (historicalPollTimer) clearInterval(historicalPollTimer)
  if (catcherPollTimer) clearInterval(catcherPollTimer)
})

async function runEverything() { await execute(async () => { await runGameSteps(); await runRosterStep() }, 'All data pipelines completed.') }
async function runGamePipeline() { await execute(runGameSteps, 'Game data pipeline completed.') }
async function runRosterPipeline() { await execute(runRosterStep, 'Contracts, transactions, and injuries updated.') }

async function runHistoricalPlus(targetYear: number) {
  if (historicalRunning.value) return
  running.value = true
  failed.value = false
  message.value = `Starting the resumable ${targetYear} Plus backfill…`
  try {
    const started = await api.backfillHistoricalPlusJob(targetYear)
    beginHistoricalStatusPolling()
    await trackJob(started)
    await refreshHistoricalPlusStatus()
    const completed = historicalStatus.value?.years?.[String(targetYear)]?.status === 'completed'
    failed.value = !completed
    message.value = completed
      ? `Historical Plus backfill completed for ${targetYear}.`
      : `${targetYear} Plus backfill stopped before all stages completed. Select the same year to resume.`
  } catch (error) {
    failed.value = true
    message.value = error instanceof Error ? error.message : `${targetYear} Plus backfill failed.`
  } finally {
    running.value = false
    await Promise.all([refreshStatus(), refreshHistoricalPlusStatus()])
    await freshnessPanel.value?.refresh(false)
  }
}

async function runCatcherLedger(targetYear: number) {
  if (catcherRunning.value) return
  running.value = true
  failed.value = false
  message.value = `Starting or resuming the ${targetYear} catcher ledger…`
  try {
    const started = await api.buildCatcherDescriptiveLedgerJob(targetYear)
    beginCatcherStatusPolling()
    await trackJob(started)
    await refreshCatcherStatus()
    const completed = catcherStatus.value?.years?.[String(targetYear)]?.status === 'completed'
    failed.value = !completed
    message.value = completed
      ? `${targetYear} catcher ledger completed and reconciled.`
      : `${targetYear} catcher ledger stopped before completion. Select the same season to resume.`
  } catch (error) {
    failed.value = true
    message.value = error instanceof Error ? error.message : `${targetYear} catcher ledger failed.`
  } finally {
    running.value = false
    await refreshCatcherStatus()
  }
}

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
    await freshnessPanel.value?.refresh(false)
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
    if (String(current.name).includes('historical_plus')) await refreshHistoricalPlusStatus()
    if (String(current.name).includes('catcher_descriptive')) await refreshCatcherStatus()
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
  try {
    status.value = await api.adminStatus(year.value)
    dailyGameUpdatesEnabled.value = statusValue('daily_settings.game_updates_enabled') !== 'false'
  }
  catch { status.value = null }
  finally { statusLoading.value = false }
}

async function toggleDailyGameUpdates() {
  if (settingsSaving.value) return
  settingsSaving.value = true
  const nextValue = !dailyGameUpdatesEnabled.value
  try {
    const result = await api.updateDailySettings(nextValue)
    dailyGameUpdatesEnabled.value = Boolean(result.game_updates_enabled)
    message.value = dailyGameUpdatesEnabled.value
      ? 'Daily game refresh enabled for the next 03:00 run. Transactions remain daily.'
      : 'Daily game refresh paused for the off-season. Transactions remain enabled every day.'
    failed.value = false
    await refreshStatus()
  } catch (error) {
    failed.value = true
    message.value = error instanceof Error ? error.message : 'Could not update the daily schedule.'
  } finally {
    settingsSaving.value = false
  }
}

async function refreshHistoricalPlusStatus() {
  try { historicalStatus.value = await api.historicalPlusStatus() }
  catch { historicalStatus.value = null }
}

async function refreshCatcherStatus() {
  try { catcherStatus.value = await api.catcherDescriptiveLedgerStatus() }
  catch { catcherStatus.value = null }
}

function beginHistoricalStatusPolling() {
  if (historicalPollTimer) return
  historicalPollTimer = setInterval(async () => {
    await refreshHistoricalPlusStatus()
    if (!historicalStatus.value?.active_job && historicalPollTimer) {
      clearInterval(historicalPollTimer)
      historicalPollTimer = undefined
    }
  }, 3000)
}

function beginCatcherStatusPolling() {
  if (catcherPollTimer) return
  catcherPollTimer = setInterval(async () => {
    await refreshCatcherStatus()
    if (!catcherStatus.value?.active_job && catcherPollTimer) {
      clearInterval(catcherPollTimer)
      catcherPollTimer = undefined
    }
  }, 3000)
}

function statusValue(path: string) {
  const value = path.split('.').reduce<unknown>((current, key) => current && typeof current === 'object' ? (current as Record<string, unknown>)[key] : undefined, status.value)
  return value === undefined || value === null || value === '' ? '' : String(value)
}

function jobLabel(job: Record<string, any>) {
  const name = String(job.name || '')
  if (name.includes('historical_plus')) return `${Number(job.year || 0) || 'Historical'} Plus backfill`
  if (name.includes('catcher_descriptive')) return `${Number(job.year || 0) || 'Catcher'} catcher ledger`
  if (name.includes('roster')) return 'Contracts & transactions'
  if (name.includes('video')) return 'Video lookup'
  if (name.includes('game') || name.includes('line')) return 'Pitcher game lines'
  if (name.includes('pitcher')) return 'Pitch data'
  return 'Update job'
}

function jobDetail(job: Record<string, any>) {
  if (job.error) return String(job.error)
  if (job.status !== 'completed') return job.status === 'running' ? 'Update is running on the backend.' : 'Waiting to start.'
  if (String(job.name).includes('historical_plus')) return String(job.result?.message || 'Historical Plus datasets processed.')
  if (String(job.name).includes('catcher_descriptive')) {
    const summary = job.result?.yearly_summary
    return `${Number(summary?.games || 0).toLocaleString()} games · ${Number(summary?.official_play_rows || summary?.official_pa_rows || 0).toLocaleString()} official plays · ${Number(summary?.pitcher_catcher_rows || 0).toLocaleString()} pitcher-catcher rows.`
  }
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
.operations-topbar,.operations-hero,.command-bar,.historical-panel,.pipeline-grid,.status-panel,.jobs-panel,.operations-page>footer { max-width: 1280px; margin-inline: auto; }
.operations-topbar { display:flex; align-items:center; justify-content:flex-end; margin-bottom:24px; }
.home-link,.eyebrow { display:inline-flex; align-items:center; gap:7px; }.home-link{color:#bbb;font-weight:800;text-decoration:none}.home-link:hover{color:var(--orange)}
.operations-hero { display:flex; align-items:end; justify-content:space-between; gap:30px; border:1px solid var(--line); border-radius:18px; padding:clamp(25px,4vw,46px); background:linear-gradient(110deg,rgba(255,255,255,.035),rgba(245,163,50,.08)); }
.eyebrow { color:var(--orange); font-size:11px; font-weight:950; letter-spacing:.09em; text-transform:uppercase; }.operations-hero h1{margin:10px 0 8px;font-size:clamp(38px,5vw,62px);font-weight:750;line-height:1.06;letter-spacing:-.012em}.operations-hero p{max-width:690px;margin:0;color:#aaa;font-size:16px;line-height:1.55}
.operations-hero label{display:grid;gap:8px;min-width:150px;color:#aaa;font-size:11px;font-weight:900;text-transform:uppercase}.operations-hero select{min-height:44px;border:1px solid #444;border-radius:10px;padding:0 12px;color:#fff;background:#111;font-weight:850}
.operations-controls{display:flex;align-items:end;gap:12px}.brand-switch,.daily-switch{min-height:58px;display:flex;align-items:center;gap:11px;border:1px solid #444;border-radius:10px;padding:8px 12px;color:#fff;background:#080808;cursor:pointer}.brand-switch:hover,.brand-switch:focus-visible,.daily-switch:hover,.daily-switch:focus-visible{border-color:var(--orange)}.brand-switch>span:last-child,.daily-switch>span:last-child{display:grid;gap:2px;text-align:left}.brand-switch small,.daily-switch small{color:#888;font-size:9px;font-weight:900;letter-spacing:.08em;text-transform:uppercase}.brand-switch strong,.daily-switch strong{font-size:13px}.daily-switch em{color:#aaa;font-size:9px;font-style:normal}.brand-switch__track,.daily-switch__track{width:36px;height:20px;display:flex;align-items:center;flex:0 0 auto;border-radius:999px;padding:2px;background:#444;transition:background 140ms ease}.brand-switch__track>span,.daily-switch__track>span{width:16px;height:16px;border-radius:50%;background:#fff;transition:transform 140ms ease}.brand-switch[aria-checked="true"] .brand-switch__track,.daily-switch[aria-checked="true"] .daily-switch__track{background:var(--orange)}.brand-switch[aria-checked="true"] .brand-switch__track>span,.daily-switch[aria-checked="true"] .daily-switch__track>span{transform:translateX(16px)}.daily-switch:disabled{cursor:wait;opacity:.6}
.command-bar { display:flex; flex-wrap:wrap; gap:10px; margin-top:16px; border:1px solid #292929;border-radius:14px;padding:12px;background:rgba(17,17,17,.92)}.command-bar button{min-height:44px;display:inline-flex;align-items:center;gap:8px;border:1px solid #393939;border-radius:10px;padding:0 15px;color:#eee;background:#181818;font-weight:900;cursor:pointer}.command-bar button:hover{border-color:var(--orange)}.command-bar .primary-action{color:#111;border-color:var(--orange);background:var(--orange)}.command-bar .cache-action{margin-left:auto;color:#aaa}.command-bar button:disabled{cursor:wait;opacity:.55}
.operations-message{max-width:1280px;margin:14px auto 0;border-left:3px solid #64c77a;padding:9px 13px;color:#d8f5df;background:rgba(70,150,88,.1)}.operations-message.error{border-color:#e3544d;color:#ffd8d4;background:rgba(190,58,50,.1)}
.historical-panel{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:22px;margin-top:16px;border:1px solid var(--line);border-radius:14px;padding:22px;background:linear-gradient(115deg,rgba(245,163,50,.09),#121212 48%)}.historical-copy h2{margin:7px 0 8px;font-size:24px}.historical-copy p{max-width:780px;margin:0;color:#aaa;font-size:14px;line-height:1.55}.historical-copy .historical-note{margin-top:8px;color:#d9bd91}.historical-action{display:flex;align-items:flex-end;flex-direction:column;gap:10px}.historical-state{border:1px solid #444;border-radius:999px;padding:5px 9px;color:#aaa;font-size:10px;font-weight:950;letter-spacing:.07em}.historical-state.running{color:#111;border-color:var(--orange);background:var(--orange)}.historical-state.completed{color:#9ae8ac;border-color:#397648}.historical-state.partial,.historical-state.invalid{color:#ffc0b8;border-color:#98483f}.historical-years{grid-column:1/-1;display:grid;grid-template-columns:repeat(5,minmax(0,1fr));border:1px solid #292929;border-radius:10px;overflow:hidden}.historical-years>button{display:grid;gap:4px;border:0;border-right:1px solid #292929;padding:13px 15px;color:inherit;background:rgba(0,0,0,.2);font:inherit;text-align:left;cursor:pointer}.historical-years>button:last-child{border-right:0}.historical-years>button:hover,.historical-years>button:focus-visible{background:rgba(245,163,50,.12);outline:0}.historical-years>button:disabled{cursor:wait;opacity:.58}.historical-years span{color:#eee;font-size:16px;font-weight:900}.historical-years strong{color:#888;font-size:10px;text-transform:uppercase}.historical-years strong.is-completed{color:#79db91}.historical-years strong.is-running{color:var(--orange)}.historical-years strong.is-failed{color:#ff8c80}.historical-years small{color:#777;font-size:10px}.historical-years em{margin-top:5px;color:var(--orange);font-size:10px;font-style:normal;font-weight:900;text-transform:uppercase}.historical-progress{grid-column:1/-1;margin:0;color:#bbb;font-size:12px}
.catcher-ledger-panel{background:linear-gradient(115deg,rgba(76,145,255,.11),#121212 48%)}
.historical-years.catcher-years{grid-template-columns:repeat(6,minmax(0,1fr))}
.historical-years>button.is-complete:disabled{cursor:default;opacity:.78}
.historical-state.downloading,.historical-state.building{color:#111;border-color:var(--orange);background:var(--orange)}
.historical-state.snapshot_failures,.historical-years strong.is-snapshot_failures{color:#ff8c80;border-color:#98483f}
.historical-years strong.is-downloading,.historical-years strong.is-building{color:var(--orange)}
.catcher-progress-track{height:6px;overflow:hidden;border-radius:999px;background:#292929}.catcher-progress-track i{display:block;height:100%;border-radius:inherit;background:linear-gradient(90deg,#4c91ff,var(--orange));transition:width 180ms ease}
.pipeline-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin-top:16px}.pipeline-card{min-height:185px;display:flex;flex-direction:column;gap:15px;border:1px solid #292929;border-radius:14px;padding:18px;background:#141414}.pipeline-card>svg{color:var(--orange)}.pipeline-card span{color:#777;font-size:9px;font-weight:900;letter-spacing:.08em;text-transform:uppercase}.pipeline-card h2{margin:4px 0 0;font-size:17px}.pipeline-card p{margin:7px 0 0;color:#999;font-size:12px;line-height:1.5}.pipeline-card>strong{margin-top:auto;color:var(--orange);font-size:11px;text-transform:uppercase}
.status-panel,.jobs-panel{margin-top:16px;border:1px solid #292929;border-radius:14px;background:#121212}.status-panel>header,.jobs-panel>header{display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #292929;padding:17px 20px}.status-panel h2,.jobs-panel h2{margin:5px 0 0;font-size:20px}.status-panel header button{width:36px;height:36px;display:grid;place-items:center;border:1px solid #333;border-radius:9px;color:var(--orange);background:#181818;cursor:pointer}.status-grid{display:grid;grid-template-columns:repeat(3,1fr)}.status-grid>div{display:grid;gap:7px;border-right:1px solid #292929;border-bottom:1px solid #292929;padding:20px}.status-grid>div:nth-child(3n){border-right:0}.status-grid>div:nth-last-child(-n+3){border-bottom:0}.status-grid span{color:#888;font-size:10px;font-weight:850;text-transform:uppercase}.status-grid strong{font:800 22px "Fira Code",monospace}.status-grid .status-time{font-size:13px;line-height:1.45}
.jobs-panel>header>span{color:#777;font-size:11px;font-weight:850}.job-list{display:grid}.job-list article{display:grid;grid-template-columns:38px minmax(0,1fr) auto;align-items:center;gap:11px;border-bottom:1px solid #242424;padding:14px 20px}.job-list article:last-child{border:0}.job-icon{width:34px;height:34px;display:grid;place-items:center;border-radius:50%;color:var(--orange);background:rgba(245,163,50,.1)}.job-list h3{margin:0;font-size:14px}.job-list p{margin:4px 0 0;color:#888;font-size:11px}.job-pill{min-width:88px;border-radius:999px;padding:6px 9px;color:#111;background:#999;font-size:9px;font-weight:950;text-align:center;text-transform:uppercase}.job-pill.queued,.job-pill.running{background:var(--orange)}.job-pill.completed{background:#64c77a}.job-pill.failed{color:#fff;background:#c43d34}.empty-jobs{margin:0;padding:30px 20px;color:#777;text-align:center}.operations-page>footer{margin-top:26px;border-top:1px solid var(--line);padding-top:18px;color:#666;font-size:10px;text-align:right}.spinning{animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}
@media(max-width:1050px){.pipeline-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:680px){.operations-hero{align-items:stretch;flex-direction:column}.operations-controls{align-items:stretch;flex-direction:column}.command-bar{display:grid}.command-bar .cache-action{margin-left:0}.historical-panel{grid-template-columns:1fr}.historical-action{align-items:stretch}.historical-years{grid-template-columns:1fr}.historical-years>button{border-right:0;border-bottom:1px solid #292929}.pipeline-grid,.status-grid{grid-template-columns:1fr}.status-grid>div,.status-grid>div:nth-child(3n){border-right:0;border-bottom:1px solid #292929}.status-grid>div:last-child{border-bottom:0}.job-list article{grid-template-columns:34px minmax(0,1fr)}.job-pill{grid-column:2;width:max-content}.operations-page>footer{text-align:left}}
@media(max-width:680px){.historical-years.catcher-years{grid-template-columns:1fr}}
@media(prefers-reduced-motion:reduce){.spinning{animation:none}}
</style>
