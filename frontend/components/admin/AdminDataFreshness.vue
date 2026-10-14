<template>
  <section class="freshness-panel">
    <header>
      <div>
        <span class="eyebrow">Data observability</span>
        <h2>Freshness & page impact</h2>
        <p>One manifest tracks source cutoffs, derived snapshots, automation and every page that can be affected.</p>
      </div>
      <div class="freshness-actions">
        <span v-if="generatedAt">Generated {{ formatTimestamp(generatedAt) }}</span>
        <button type="button" :disabled="loading" @click="refresh(true)">
          <RefreshCw :size="16" :class="{ spinning: loading }" /> Rebuild report
        </button>
      </div>
    </header>

    <div v-if="error" class="freshness-error" role="alert">{{ error }}</div>
    <template v-else>
      <div class="freshness-summary">
        <div><span>Overall</span><strong :class="statusClass(overallStatus)">{{ labelStatus(overallStatus) }}</strong></div>
        <div><span>Datasets</span><strong>{{ datasets.length }}</strong></div>
        <div><span>Pages mapped</span><strong>{{ pages.length }}</strong></div>
        <div><span>Needs attention</span><strong>{{ attentionCount }}</strong></div>
      </div>

      <div class="freshness-tabs" role="tablist" aria-label="Freshness report view">
        <button type="button" role="tab" :aria-selected="view === 'datasets'" @click="view = 'datasets'">Datasets</button>
        <button type="button" role="tab" :aria-selected="view === 'pages'" @click="view = 'pages'">Page impact</button>
      </div>

      <div v-if="view === 'datasets'" class="freshness-table-wrap">
        <table>
          <thead><tr><th>Dataset</th><th>Status</th><th>Data as of</th><th>Source as of</th><th>Automation</th><th>Pages</th></tr></thead>
          <tbody>
            <tr v-for="item in datasets" :key="item.key">
              <td>
                <strong>{{ item.label }}</strong>
                <small v-if="item.warnings?.length">{{ item.warnings.join(' · ') }}</small>
              </td>
              <td><span :class="['status-pill', statusClass(item.status)]">{{ labelStatus(item.status) }}</span></td>
              <td>{{ item.data_as_of || '—' }}</td>
              <td>{{ item.source_as_of || '—' }}</td>
              <td>{{ item.automation }}</td>
              <td><code>{{ item.affected_pages.join(', ') || '—' }}</code></td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-else class="page-impact-grid">
        <article v-for="page in pages" :key="page.route">
          <div><code>{{ page.route }}</code><span :class="['status-pill', statusClass(page.status)]">{{ labelStatus(page.status) }}</span></div>
          <p>Oldest dated dependency <strong>{{ page.data_as_of || '—' }}</strong></p>
          <small>{{ page.datasets.join(' · ') }}</small>
        </article>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { RefreshCw } from '@lucide/vue'

type DatasetItem = {
  key: string
  label: string
  status: string
  data_as_of: string | null
  source_as_of: string | null
  automation: string
  affected_pages: string[]
  warnings: string[]
}
type PageItem = { route: string; status: string; data_as_of: string | null; datasets: string[] }

const props = defineProps<{ year: number }>()
const api = useApi()
const loading = ref(false)
const error = ref('')
const report = ref<Record<string, any> | null>(null)
const view = ref<'datasets' | 'pages'>('datasets')
const datasets = computed(() => (report.value?.datasets || []) as DatasetItem[])
const pages = computed(() => (report.value?.pages || []) as PageItem[])
const generatedAt = computed(() => String(report.value?.generated_at || ''))
const overallStatus = computed(() => String(report.value?.overall_status || 'unavailable'))
const attentionCount = computed(() => datasets.value.filter(item => !['current', 'live', 'expected_lag'].includes(item.status)).length)

onMounted(() => refresh(false))
watch(() => props.year, () => refresh(false))
defineExpose({ refresh })

async function refresh(rebuild = false) {
  loading.value = true
  error.value = ''
  try {
    report.value = await (rebuild ? api.refreshDataFreshness(props.year) : api.dataFreshness(props.year))
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : 'Unable to load the freshness report.'
  } finally {
    loading.value = false
  }
}

function statusClass(status: string) { return `status-${String(status || 'unavailable').replaceAll('_', '-')}` }
function labelStatus(status: string) { return String(status || 'unavailable').replaceAll('_', ' ') }
function formatTimestamp(value: string) {
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString('zh-TW', { hour12: false })
}
</script>

<style scoped>
.freshness-panel{max-width:1280px;margin:16px auto 0;border:1px solid #2d2d2d;background:#111}.freshness-panel>header{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;border-bottom:1px solid #2d2d2d;padding:24px}.eyebrow{color:var(--orange,#f5a332);font-size:10px;font-weight:950;letter-spacing:.09em;text-transform:uppercase}.freshness-panel h2{margin:6px 0 0;font-size:26px}.freshness-panel header p{max-width:720px;margin:8px 0 0;color:#929292;font-size:13px;line-height:1.5}.freshness-actions{display:flex;align-items:center;gap:12px}.freshness-actions>span{color:#777;font-size:10px}.freshness-actions button{min-height:38px;display:inline-flex;align-items:center;gap:7px;border:1px solid #3b3b3b;padding:0 12px;color:#eee;background:#181818;font-weight:850;cursor:pointer}.freshness-actions button:hover{border-color:var(--orange,#f5a332)}.freshness-actions button:disabled{opacity:.55;cursor:wait}.freshness-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border-bottom:1px solid #2d2d2d}.freshness-summary>div{display:grid;gap:7px;border-right:1px solid #2d2d2d;padding:18px 22px}.freshness-summary>div:last-child{border:0}.freshness-summary span{color:#777;font-size:9px;font-weight:900;text-transform:uppercase}.freshness-summary strong{font:800 20px "Fira Code",monospace;text-transform:uppercase}.freshness-tabs{display:flex;border-bottom:1px solid #2d2d2d}.freshness-tabs button{border:0;border-right:1px solid #2d2d2d;padding:12px 18px;color:#888;background:#151515;font-weight:900;cursor:pointer}.freshness-tabs button[aria-selected="true"]{color:#111;background:var(--orange,#f5a332)}.freshness-table-wrap{overflow-x:auto}table{width:100%;min-width:1100px;border-collapse:collapse}th,td{border-bottom:1px solid #252525;padding:13px 14px;text-align:left;font-size:11px;vertical-align:top}th{color:#aaa;background:#151515;font-size:9px;text-transform:uppercase}td{color:#aaa}td strong{display:block;color:#eee;font-size:12px}td small{display:block;max-width:360px;margin-top:5px;color:#d39b48;line-height:1.4}td code,.page-impact-grid code{color:#b8c9e8;font-size:10px;white-space:normal}.status-pill{display:inline-flex;border:1px solid currentColor;padding:4px 7px;font-size:8px;font-weight:950;letter-spacing:.04em;text-transform:uppercase}.status-current,.status-live{color:#72cd8b}.status-expected-lag,.status-source-pending{color:#f5b84b}.status-stale,.status-failed{color:#f06b62}.status-partial,.status-manual,.status-unverified{color:#c29af4}.status-unavailable{color:#888}.page-impact-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1px;background:#2d2d2d}.page-impact-grid article{min-width:0;padding:18px;background:#111}.page-impact-grid article>div{display:flex;align-items:center;justify-content:space-between;gap:12px}.page-impact-grid p{margin:13px 0 6px;color:#888;font-size:11px}.page-impact-grid p strong{color:#eee}.page-impact-grid small{color:#666;font-size:9px;line-height:1.4}.freshness-error{border-left:3px solid #e3544d;padding:16px 20px;color:#ffd8d4;background:rgba(190,58,50,.1)}.spinning{animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}
@media(max-width:900px){.freshness-panel>header{align-items:stretch;flex-direction:column}.freshness-actions{justify-content:space-between}.freshness-summary{grid-template-columns:repeat(2,1fr)}.page-impact-grid{grid-template-columns:1fr}}
@media(max-width:560px){.freshness-summary{grid-template-columns:1fr}.freshness-summary>div{border-right:0;border-bottom:1px solid #2d2d2d}.freshness-actions{align-items:stretch;flex-direction:column}}
@media(prefers-reduced-motion:reduce){.spinning{animation:none}}
</style>
