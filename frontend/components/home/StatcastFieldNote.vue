<template>
  <button class="note-trigger" type="button" aria-haspopup="dialog" :aria-expanded="open" @click="openNote">
    note
  </button>

  <Teleport to="body">
    <Transition name="note-fade">
      <div v-if="open" class="note-backdrop" @click.self="closeNote" @keydown.esc="closeNote">
        <section class="note-dialog" role="dialog" aria-modal="true" aria-labelledby="statcast-note-title">
          <header class="note-header">
            <div>
              <span>Statcast CSV</span>
              <h2 id="statcast-note-title">欄位備忘錄</h2>
              <p>英文欄位、中文對照與簡短定義。</p>
            </div>
            <button class="close-button" type="button" aria-label="關閉欄位備忘錄" @click="closeNote">
              <X :size="21" />
            </button>
          </header>

          <div class="note-controls">
            <label class="search-control">
              <span>搜尋欄位</span>
              <div>
                <Search :size="18" />
                <input ref="searchInput" v-model="query" type="search" placeholder="例如：release_speed、擊球初速" />
              </div>
            </label>
            <label>
              <span>分類</span>
              <select v-model="selectedGroup">
                <option value="All">全部分類</option>
                <option v-for="group in groups" :key="group" :value="group">{{ group }}</option>
              </select>
            </label>
          </div>

          <div class="table-wrap">
            <table>
              <thead>
                <tr><th>Statcast 欄位</th><th>中文對照</th><th>定義備忘</th></tr>
              </thead>
              <tbody>
                <tr v-for="item in filteredFields" :key="item.field" :class="{ deprecated: item.deprecated }">
                  <td><code>{{ item.field }}</code><small>{{ item.group }}</small></td>
                  <td>{{ item.zh }}</td>
                  <td>{{ item.detail }}</td>
                </tr>
              </tbody>
            </table>
            <p v-if="!filteredFields.length" class="empty-state">找不到符合的欄位。</p>
          </div>

          <footer>
            <span>顯示 {{ filteredFields.length }}／{{ statcastFieldNotes.length }} 個欄位</span>
            <small>停用欄位以灰色標示；來源為 Statcast Search CSV Documentation。</small>
          </footer>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { Search, X } from '@lucide/vue'
import { statcastFieldNotes } from '~/data/statcastFieldNotes'

const open = ref(false)
const query = ref('')
const selectedGroup = ref('All')
const searchInput = ref<HTMLInputElement | null>(null)
let previousBodyOverflow = ''

const groups = [...new Set(statcastFieldNotes.map(item => item.group))]
const filteredFields = computed(() => {
  const term = query.value.trim().toLocaleLowerCase()
  return statcastFieldNotes.filter((item) => {
    if (selectedGroup.value !== 'All' && item.group !== selectedGroup.value) return false
    if (!term) return true
    return [item.field, item.zh, item.detail, item.group].some(value => value.toLocaleLowerCase().includes(term))
  })
})

async function openNote() {
  open.value = true
  await nextTick()
  searchInput.value?.focus()
}

function closeNote() {
  open.value = false
}

watch(open, (value) => {
  if (!import.meta.client) return
  if (value) {
    previousBodyOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
  } else {
    document.body.style.overflow = previousBodyOverflow
  }
})

onBeforeUnmount(() => {
  if (import.meta.client) document.body.style.overflow = previousBodyOverflow
})
</script>

<style scoped>
.note-trigger { border: 0; padding: 0; color: var(--home-text); background: transparent; cursor: pointer; font-family: "Brush Script MT", "Segoe Script", "Lucida Handwriting", cursive; font-size: clamp(26px, 3vw, 42px); line-height: 1; transition: color .16s ease; }
.note-trigger:hover, .note-trigger:focus-visible { color: var(--home-orange); }
.note-backdrop { position: fixed; inset: 0; z-index: 1000; display: grid; place-items: center; padding: 24px; background: rgba(3, 7, 14, .78); backdrop-filter: blur(8px); }
.note-dialog { width: min(1180px, 100%); max-height: min(880px, calc(100vh - 48px)); display: grid; grid-template-rows: auto auto minmax(0, 1fr) auto; overflow: hidden; border: 1px solid var(--color-border-strong); border-radius: 20px; color: var(--color-text); background: var(--color-surface); box-shadow: 0 28px 100px rgba(0, 0, 0, .48); }
.note-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 22px; border-bottom: 1px solid var(--color-border); padding: 24px 26px 20px; background: radial-gradient(circle at 88% 8%, color-mix(in srgb, var(--color-primary) 18%, transparent), transparent 23rem); }
.note-header span, .note-controls label > span { color: var(--color-primary); font-size: 11px; font-weight: 900; letter-spacing: .09em; text-transform: uppercase; }
.note-header h2 { margin: 6px 0 0; color: var(--color-foreground); font-size: clamp(28px, 4vw, 42px); line-height: 1.1; letter-spacing: -.01em; }
.note-header p { margin: 8px 0 0; color: var(--color-muted-text); font-size: 14px; }
.close-button { width: 42px; height: 42px; display: grid; flex: 0 0 auto; place-items: center; border: 1px solid var(--color-border); border-radius: 11px; color: var(--color-muted-text); background: var(--color-background); cursor: pointer; }
.close-button:hover { color: var(--color-foreground); border-color: var(--color-primary); }
.note-controls { display: grid; grid-template-columns: minmax(260px, 1fr) 200px; gap: 12px; border-bottom: 1px solid var(--color-border); padding: 14px 18px; }
.note-controls label { display: grid; gap: 6px; }
.search-control div { position: relative; }
.search-control svg { position: absolute; top: 13px; left: 13px; color: var(--color-muted-text); pointer-events: none; }
input, select { width: 100%; min-height: 44px; border: 1px solid var(--color-border-strong); border-radius: 10px; color: var(--color-text); background: var(--color-background); font: inherit; }
input { padding: 0 14px 0 40px; }
select { padding: 0 12px; }
.table-wrap { min-height: 0; overflow: auto; background: var(--color-background); }
table { width: 100%; border-collapse: collapse; table-layout: fixed; }
th, td { border-bottom: 1px solid var(--color-border); padding: 13px 16px; text-align: left; vertical-align: top; }
th { position: sticky; top: 0; z-index: 2; color: var(--color-muted-text); background: color-mix(in srgb, var(--color-surface) 94%, transparent); font-size: 11px; letter-spacing: .06em; text-transform: uppercase; backdrop-filter: blur(10px); }
th:first-child { width: 28%; }
th:nth-child(2) { width: 23%; }
td { color: var(--color-text); font-size: 13px; line-height: 1.5; }
td code { display: block; color: var(--color-foreground); font-family: "Fira Code", Consolas, monospace; font-size: 12px; font-weight: 750; overflow-wrap: anywhere; }
td small { display: block; margin-top: 4px; color: var(--color-primary); font-size: 9px; font-weight: 850; letter-spacing: .06em; text-transform: uppercase; }
tr.deprecated td { color: var(--color-muted-text); opacity: .68; }
.empty-state { margin: 0; padding: 48px 20px; color: var(--color-muted-text); text-align: center; }
.note-dialog > footer { display: flex; justify-content: space-between; gap: 18px; border-top: 1px solid var(--color-border); padding: 12px 18px; color: var(--color-muted-text); background: var(--color-surface); font-size: 11px; }
.note-dialog > footer span { color: var(--color-foreground); font-weight: 800; }
.note-fade-enter-active, .note-fade-leave-active { transition: opacity .16s ease; }
.note-fade-enter-from, .note-fade-leave-to { opacity: 0; }
@media (max-width: 700px) { .note-backdrop { padding: 0; } .note-dialog { max-height: 100vh; height: 100vh; border-radius: 0; } .note-controls { grid-template-columns: 1fr; } th:first-child { width: 40%; } th:nth-child(2) { width: 34%; } th:nth-child(3), td:nth-child(3) { display: none; } .note-dialog > footer { align-items: flex-start; flex-direction: column; } }
@media (prefers-reduced-motion: reduce) { .note-fade-enter-active, .note-fade-leave-active { transition: none; } }
</style>
