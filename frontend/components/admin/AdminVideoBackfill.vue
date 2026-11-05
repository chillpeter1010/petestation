<template>
  <section class="video-backfill" aria-labelledby="video-backfill-title">
    <header>
      <div>
        <h2 id="video-backfill-title">逐球影片補抓 · {{ year }}</h2>
        <p>只補所選年度尚未建立完整場次映射的資料，供 Stuff 與 In game 共用；不重算模型。</p>
      </div>
      <button type="button" :disabled="disabled || starting || !snapshot || !!activeJob || !!error || !!snapshot.coverage_error || !snapshot.exists || snapshot.missing_games === 0" @click="start">
        {{ starting ? '正在提交…' : activeJob ? `${activeJob.year} 補抓中` : '補齊缺漏影片' }}
      </button>
    </header>
    <p class="coverage">已保存映射：{{ snapshot?.complete_games ?? '—' }} / {{ snapshot?.season_games ?? '—' }} 場；待補：{{ snapshot?.missing_games ?? '—' }} 場</p>
    <p role="status" aria-live="polite">{{ stateMessage }}</p>
    <p v-if="error || snapshot?.coverage_error" class="warning" role="alert">{{ error || '覆蓋率暫時無法讀取，稍後自動重試；不代表覆蓋率歸零。' }}</p>
    <button class="refresh" type="button" :disabled="loading || starting" @click="refresh">重新讀取狀態</button>
    <p class="note">每 50 場保存一次，狀態每 5 秒更新。可關閉此頁，不消耗聊天 token，但後端須保持運行；後端重啟後再按一次可接續已保存進度。</p>
    <p class="note">這是官方 playId／影片連結映射，不保證每一球都有可播放的官方影片。首次補全可能需要較長時間。</p>
  </section>
</template>

<script setup lang="ts">
type VideoJob = {
  job_id: string
  year: number
  status: string
  error?: string
  result?: { failed_games?: number[] }
}
type VideoStatus = {
  exists?: boolean
  complete_games?: number
  season_games?: number
  missing_games?: number
  coverage_error?: string
  active_job?: VideoJob | null
  latest_job?: VideoJob | null
}
const props = defineProps<{ year: number; disabled?: boolean }>()
const api = useApi()
const snapshot = ref<VideoStatus | null>(null)
const error = ref('')
const loading = ref(false)
const starting = ref(false)
const activeJob = computed(() => snapshot.value?.active_job)
const stateMessage = computed(() => {
  if (starting.value) return '正在提交後端工作，請勿重複點擊。'
  if (activeJob.value) return `${activeJob.value.year} 年工作${activeJob.value.status === 'queued' ? '已排隊（可能等待其他資料更新）' : '執行中'}；離開此頁不會取消。`
  if (!snapshot.value) return '正在讀取補抓狀態…'
  const job = snapshot.value.latest_job
  if (job?.status === 'failed') return `上次補抓失敗：${job.error || '請稍後重試'}。已保存資料會保留，可再按補抓。`
  const failures = job?.result?.failed_games?.length || 0
  if (failures) return `上次工作已結束，${failures} 場讀取失敗；可再按補抓重試，非全季完成。`
  if (!snapshot.value.exists && !snapshot.value.coverage_error) return '本年度尚無本機賽事資料，請先更新賽事資料。'
  if (snapshot.value.missing_games === 0) return '目前本機賽事皆有場次映射；不代表逐球播放驗收通過。'
  return '可開始／接續缺漏場次補抓；已保存場次自動跳過。'
})
let timer: ReturnType<typeof setTimeout> | undefined
let requestVersion = 0
let disposed = false

async function refresh() {
  clearTimeout(timer)
  const version = ++requestVersion
  const year = props.year
  loading.value = true
  try {
    const result = await api.videoLookupStatus(year) as VideoStatus
    if (disposed || version !== requestVersion) return
    // Retain the last saved counts during the short database write window.
    snapshot.value = result.coverage_error ? { ...snapshot.value, ...result } : result
    error.value = ''
  } catch {
    if (!disposed && version === requestVersion) error.value = '狀態讀取失敗，稍後自動重試；請確認後端與登入權限。'
  } finally {
    if (!disposed && version === requestVersion) {
      loading.value = false
      timer = setTimeout(refresh, 5000)
    }
  }
}

async function start() {
  if (starting.value || activeJob.value || props.disabled) return
  starting.value = true
  clearTimeout(timer)
  ++requestVersion
  try {
    const job = await api.backfillVideoLookupJob({ year: props.year, batchSize: 50 }) as VideoJob
    if (!disposed) snapshot.value = { ...snapshot.value, active_job: job }
  } catch {
    if (!disposed) error.value = '提交未確認，請先重新讀取狀態；工作可能已啟動，不需連按。'
  } finally {
    starting.value = false
    if (!disposed) await refresh()
  }
}
onMounted(() => refresh())
watch(() => props.year, () => { snapshot.value = null; error.value = ''; void refresh() })
onBeforeUnmount(() => { disposed = true; ++requestVersion; clearTimeout(timer) })
</script>

<style scoped>
.video-backfill { margin-top: 16px; padding: 1.5rem; border: 1px solid var(--color-border, #343a46); border-radius: 20px; background: var(--color-surface, #151a23); color: var(--color-text, #eeeade); }
header { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 1rem; }
h2 { margin: 0 0 .5rem; font-size: 1.25rem; }
p { line-height: 1.6; overflow-wrap: anywhere; }
button { padding: .75rem 1.1rem; border: 1px solid #d89c3d; border-radius: 12px; background: #dfa640; color: #171b16; font: inherit; font-weight: 700; cursor: pointer; }
button:disabled { opacity: .5; cursor: not-allowed; }
button:focus-visible { outline: 3px solid #f4d495; outline-offset: 3px; }
.refresh { padding: .5rem .8rem; background: transparent; color: inherit; border-color: #626976; }
.coverage { font-weight: 700; }
.warning { color: #ffbb9b; }
.note { color: #adb5c1; font-size: .88rem; margin-bottom: 0; }
</style>
