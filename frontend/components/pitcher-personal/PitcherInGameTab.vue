<template>
  <section class="in-game-tab" aria-label="Pitcher In game" :aria-busy="loading">
    <p v-if="!pitcherId" class="state-message">Select a pitcher to view In game.</p>
    <p v-else-if="loading" class="state-message" role="status">Loading outings…</p>
    <p v-else-if="errorMessage" class="state-message error" role="alert">{{ errorMessage }} <button type="button" @click="loadOutings">Retry</button></p>
    <template v-else-if="outings.length">
      <div class="outing-toolbar">
        <label>Game
          <select v-model.number="selectedGamePk" aria-label="In game outing">
            <option v-for="outing in outings" :key="outing.gamePk" :value="outing.gamePk">{{ outing.label }}</option>
          </select>
        </label>
        <span>{{ outings.length }} outings · latest first</span>
      </div>
      <LazyPitchReplayPanel v-if="selectedGamePk" :key="`${year}:${pitcherId}:${selectedGamePk}`" title="In game" :year="year" :game-pk="selectedGamePk" :pitcher-id="pitcherId!" :pitcher-name="pitcherName" @select-pitch="emit('select-pitch', $event)" />
    </template>
    <p v-else class="state-message">No outings are available for this pitcher in {{ year }}.</p>
  </section>
</template>

<script setup lang="ts">
import { inGameOutings, initialInGameOuting, type InGameOuting, type InGameRow } from '~/utils/pitcherInGame'

const props = defineProps<{ year: number; pitcherId: number | null; pitcherName: string; initialGamePk?: number; refreshToken?: number }>()
const emit = defineEmits<{ 'select-pitch': [pitch: InGameRow]; 'select-game': [gamePk: number] }>()
const api = useApi()
const outings = ref<InGameOuting[]>([])
const selectedGamePk = ref<number | null>(null)
const loading = ref(false)
const errorMessage = ref('')
let requestVersion = 0
async function loadOutings() {
  const version = ++requestVersion
  outings.value = []
  selectedGamePk.value = null
  errorMessage.value = ''
  loading.value = false
  if (!props.pitcherId) return
  loading.value = true
  try {
    const result = await api.personalOutings({ year: props.year, pitcherId: props.pitcherId })
    if (version !== requestVersion) return
    outings.value = inGameOutings(result.tables.outings?.rows || [])
    selectedGamePk.value = initialInGameOuting(outings.value, props.initialGamePk)
  } catch (error) {
    if (version === requestVersion) errorMessage.value = error instanceof Error ? error.message : 'Outings request failed'
  } finally {
    if (version === requestVersion) loading.value = false
  }
}
watch(() => [props.year, props.pitcherId, props.refreshToken], loadOutings, { immediate: true })
watch(selectedGamePk, value => { if (value) emit('select-game', value) })
onBeforeUnmount(() => { requestVersion += 1 })
</script>

<style scoped>
.in-game-tab { display:grid; gap:14px; min-width:0; }
.outing-toolbar { display:flex; align-items:end; flex-wrap:wrap; gap:12px; border:1px solid var(--color-border); border-radius:var(--radius-md); padding:14px; background:var(--color-surface); }
.outing-toolbar label { display:grid; gap:7px; min-width:0; flex:0 1 560px; color:var(--color-muted-text); font-size:12px; font-weight:800; }
select { width:100%; min-width:0; min-height:42px; padding:8px 12px; border:1px solid var(--color-border); border-radius:6px; color:var(--color-foreground); background:var(--color-surface); font:inherit; }
.outing-toolbar span,.state-message { color:var(--color-muted-text); }
.state-message { margin:0; padding:14px; }
.error { color:#ef4444; }
select:focus-visible,button:focus-visible { outline:2px solid var(--color-primary); outline-offset:3px; }
button { min-height:40px; cursor:pointer; }
</style>
