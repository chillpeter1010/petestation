<template>
  <section class="tracker-panel">
    <header>
      <div>
        <span class="eyebrow">Project memory</span>
        <h2>Plans, slices & completion</h2>
        <p>Tracked progress for completed work, active plans and future ideas. This is also the concise handoff source for a new conversation.</p>
      </div>
      <button type="button" :disabled="!handoffMarkdown" @click="copyHandoff">
        <ClipboardCheck v-if="copied" :size="16" /><ClipboardCopy v-else :size="16" />
        {{ copied ? 'Copied' : 'Copy handoff summary' }}
      </button>
    </header>

    <div v-if="error" class="tracker-error" role="alert">{{ error }}</div>
    <template v-else>
      <div class="tracker-overall">
        <div class="tracker-overall__copy">
          <span>Portfolio completion</span>
          <strong>{{ summary.progress || 0 }}%</strong>
          <small>{{ summary.completed_slices || 0 }} of {{ summary.total_slices || 0 }} scoped slices complete · {{ summary.active_projects || 0 }} active projects</small>
        </div>
        <progress :value="summary.completed_slices || 0" :max="summary.total_slices || 1" aria-label="Overall project slice completion" />
      </div>

      <div class="tracker-projects">
        <details v-for="project in projects" :key="project.id" :open="project.status === 'in_progress'">
          <summary>
            <div class="project-identity">
              <span :class="['project-status', `project-status--${project.status}`]">{{ project.status.replaceAll('_', ' ') }}</span>
              <div><h3>{{ project.title }}</h3><small>{{ project.area }}</small></div>
            </div>
            <div class="project-progress">
              <strong>{{ project.total_slices ? `${project.progress}%` : 'IDEA' }}</strong>
              <progress v-if="project.total_slices" :value="project.completed_slices" :max="project.total_slices" :aria-label="`${project.title} completion`" />
              <ChevronDown :size="17" aria-hidden="true" />
            </div>
          </summary>
          <div class="project-body">
            <div class="project-context"><p>{{ project.summary }}</p><p><span>Next</span>{{ project.next_step }}</p></div>
            <div v-if="project.slices.length" class="slice-list">
              <article v-for="slice in project.slices" :key="slice.id">
                <span :class="['slice-mark', `slice-mark--${slice.status}`]" aria-hidden="true" />
                <div><h4>{{ slice.label }}</h4><p>{{ slice.deliverable }}</p></div>
                <div class="slice-result"><strong>{{ slice.status.replaceAll('_', ' ') }}</strong><small>{{ slice.verification }}</small></div>
              </article>
            </div>
            <p v-else class="unscoped">Idea captured. Slices have not been defined yet.</p>
          </div>
        </details>
      </div>
      <footer><code>{{ sourcePath }}</code><span>Updated {{ updatedAt }}</span></footer>
    </template>
  </section>
</template>

<script setup lang="ts">
import { ChevronDown, ClipboardCheck, ClipboardCopy } from '@lucide/vue'

type Slice = { id: string; label: string; status: string; deliverable: string; verification: string }
type Project = {
  id: string
  title: string
  area: string
  status: string
  summary: string
  next_step: string
  progress: number
  completed_slices: number
  total_slices: number
  slices: Slice[]
}

const api = useApi()
const payload = ref<Record<string, any> | null>(null)
const error = ref('')
const copied = ref(false)
const projects = computed(() => (payload.value?.projects || []) as Project[])
const summary = computed(() => payload.value?.summary || {})
const handoffMarkdown = computed(() => String(payload.value?.handoff_markdown || ''))
const sourcePath = computed(() => String(payload.value?.source_path || 'docs/PROJECT_TRACKER.json'))
const updatedAt = computed(() => String(payload.value?.updated_at || '—'))

onMounted(load)

async function load() {
  error.value = ''
  try { payload.value = await api.projectTracker() }
  catch (reason) { error.value = reason instanceof Error ? reason.message : 'Unable to load the project tracker.' }
}

async function copyHandoff() {
  if (!import.meta.client || !handoffMarkdown.value) return
  await navigator.clipboard.writeText(handoffMarkdown.value)
  copied.value = true
  window.setTimeout(() => { copied.value = false }, 1800)
}
</script>

<style scoped>
.tracker-panel{max-width:1280px;margin:16px auto 0;border:1px solid #342c22;background:#10100f}.tracker-panel>header{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;border-bottom:1px solid #342c22;padding:25px}.eyebrow{color:var(--orange,#f5a332);font-size:10px;font-weight:950;letter-spacing:.09em;text-transform:uppercase}.tracker-panel h2{margin:6px 0 0;font-size:27px}.tracker-panel header p{max-width:760px;margin:8px 0 0;color:#96928c;font-size:13px;line-height:1.5}.tracker-panel>header button{min-height:40px;display:inline-flex;align-items:center;gap:8px;border:1px solid #4b3a25;padding:0 13px;color:#f1c17a;background:#18140f;font-weight:900;cursor:pointer}.tracker-panel>header button:hover{border-color:var(--orange,#f5a332)}.tracker-panel>header button:disabled{opacity:.45}.tracker-overall{display:grid;grid-template-columns:minmax(260px,.7fr) 1.3fr;align-items:center;gap:34px;border-bottom:1px solid #342c22;padding:22px 25px}.tracker-overall__copy{display:grid;grid-template-columns:1fr auto;gap:3px 16px}.tracker-overall__copy>span{color:#888;font-size:9px;font-weight:900;text-transform:uppercase}.tracker-overall__copy>strong{grid-row:1/3;grid-column:2;font:850 31px "Fira Code",monospace;color:var(--orange,#f5a332)}.tracker-overall__copy>small{color:#777;font-size:10px}.tracker-panel progress{width:100%;height:10px;border:0;background:#24201a}.tracker-panel progress::-webkit-progress-bar{background:#24201a}.tracker-panel progress::-webkit-progress-value{background:linear-gradient(90deg,#9e5b1f,var(--orange,#f5a332))}.tracker-panel progress::-moz-progress-bar{background:var(--orange,#f5a332)}.tracker-projects details{border-bottom:1px solid #2b2824}.tracker-projects details:last-child{border:0}.tracker-projects summary{display:flex;align-items:center;justify-content:space-between;gap:22px;padding:17px 24px;cursor:pointer;list-style:none}.tracker-projects summary::-webkit-details-marker{display:none}.tracker-projects summary:hover{background:#151411}.project-identity{display:flex;align-items:center;gap:13px;min-width:0}.project-identity h3{margin:0;font-size:15px}.project-identity small{display:block;margin-top:3px;color:#777;font-size:9px;text-transform:uppercase}.project-status{min-width:72px;border:1px solid currentColor;padding:4px 6px;font-size:8px;font-weight:950;text-align:center;text-transform:uppercase}.project-status--done{color:#72cd8b}.project-status--in_progress{color:#f5b84b}.project-status--idea{color:#9da8bc}.project-status--planned{color:#c29af4}.project-status--blocked{color:#f06b62}.project-progress{width:min(330px,38vw);display:grid;grid-template-columns:48px 1fr 18px;align-items:center;gap:10px}.project-progress strong{font:800 11px "Fira Code",monospace;color:#ddd}.project-progress progress{height:6px}.project-progress svg{color:#777;transition:transform 150ms ease}.tracker-projects details[open] .project-progress svg{transform:rotate(180deg)}.project-body{border-top:1px solid #27241f;background:#0d0d0c}.project-context{display:grid;grid-template-columns:1fr 1fr;gap:22px;padding:17px 24px}.project-context p{margin:0;color:#999;font-size:11px;line-height:1.5}.project-context p span{display:block;margin-bottom:5px;color:var(--orange,#f5a332);font-size:8px;font-weight:950;text-transform:uppercase}.slice-list article{display:grid;grid-template-columns:10px minmax(0,1fr) minmax(150px,.55fr);align-items:center;gap:13px;border-top:1px solid #24221e;padding:12px 24px}.slice-mark{width:8px;height:8px;border:1px solid #666;background:#333}.slice-mark--done{border-color:#72cd8b;background:#72cd8b}.slice-mark--in_progress{border-color:#f5b84b;background:#f5b84b}.slice-mark--planned{border-color:#a67bdc}.slice-mark--blocked{border-color:#f06b62;background:#f06b62}.slice-list h4{margin:0;color:#ddd;font-size:11px}.slice-list p{margin:4px 0 0;color:#777;font-size:10px}.slice-result{text-align:right}.slice-result strong{display:block;color:#aaa;font-size:8px;text-transform:uppercase}.slice-result small{display:block;margin-top:4px;color:#666;font-size:9px}.unscoped{margin:0;border-top:1px solid #24221e;padding:18px 24px;color:#777;font-size:11px}.tracker-panel>footer{display:flex;justify-content:space-between;gap:15px;border-top:1px solid #342c22;padding:11px 24px;color:#666;font-size:9px}.tracker-panel>footer code{color:#9eabc1}.tracker-error{border-left:3px solid #e3544d;padding:16px 20px;color:#ffd8d4;background:rgba(190,58,50,.1)}
@media(max-width:760px){.tracker-panel>header{align-items:stretch;flex-direction:column}.tracker-panel>header button{justify-content:center}.tracker-overall{grid-template-columns:1fr}.project-progress{width:auto;grid-template-columns:42px minmax(70px,1fr) 18px}.project-context{grid-template-columns:1fr}.slice-list article{grid-template-columns:10px minmax(0,1fr)}.slice-result{grid-column:2;text-align:left}.tracker-panel>footer{flex-direction:column}}
@media(prefers-reduced-motion:reduce){.project-progress svg{transition:none}}
</style>
