<template>
  <span
    ref="triggerEl"
    class="pitcher-tag-hover"
    @mouseenter="openCard"
    @mouseleave="closeCard"
    @focusin="openCard"
    @focusout="closeCard"
  >
    <NuxtLink :class="triggerClass" :to="to" :aria-describedby="open ? tooltipId : undefined">
      <slot />
    </NuxtLink>
    <Teleport to="body">
      <aside
        v-if="open"
        :id="tooltipId"
        class="pitcher-tag-card"
        :style="cardStyle"
        role="tooltip"
        aria-live="polite"
      >
        <span class="tag-kicker">Season pitcher profile</span>
        <strong>{{ pitcherName }}</strong>
        <p v-if="loading">Loading season tags…</p>
        <p v-else-if="errorMessage" class="tag-warning">{{ errorMessage }}</p>
        <template v-else-if="displaySource">
          <p v-if="usingReference" class="tag-warning">
            {{ year }} {{ role }} has no supported tag. Showing {{ displaySource.year }} {{ role }} as a reference only.
          </p>
          <p v-else>{{ displaySource.year }} {{ role }} full-season · {{ displaySource.support.pitches }} pitches</p>
          <div class="tag-chips">
            <span v-for="tag in displaySource.tags" :key="tag.code" :class="{ 'is-practical': tag.source === 'practical_v1' }">{{ tag.label }}</span>
          </div>
          <small>Descriptive season type, not this game's performance.<template v-if="hasPracticalTags"> Outlined profiles are Lab-first.</template></small>
        </template>
        <p v-else class="tag-warning">No supported same-role season tag is available yet.</p>
      </aside>
    </Teleport>
  </span>
</template>

<script setup lang="ts">
type TagItem = { code: string; label: string; kind: string; source?: string }
type TagSource = { year: number; support: { pitches: number; label: string; reliability?: number | null }; tags: TagItem[] }
type TagPayload = TagSource & { reference?: TagSource | null }

const props = defineProps<{
  year: number
  gamePk: number
  pitcherId: number
  pitcherName: string
  role: string
  to: string | Record<string, unknown>
  triggerClass?: string
}>()

const api = useApi()
const triggerEl = ref<HTMLElement | null>(null)
const open = ref(false)
const loading = ref(false)
const loaded = ref(false)
const errorMessage = ref('')
const payload = ref<TagPayload | null>(null)
const cardStyle = ref<Record<string, string>>({ left: '12px', top: '12px' })
const tooltipId = useId()
const role = computed(() => String(props.role || 'RP').toUpperCase())
const currentSource = computed<TagSource | null>(() => payload.value?.tags?.length ? payload.value : null)
const displaySource = computed<TagSource | null>(() => currentSource.value || payload.value?.reference || null)
const usingReference = computed(() => !currentSource.value && Boolean(payload.value?.reference))
const hasPracticalTags = computed(() => Boolean(displaySource.value?.tags.some(tag => tag.source === 'practical_v1')))

function updatePosition() {
  if (!import.meta.client || !triggerEl.value) return
  const rect = triggerEl.value.getBoundingClientRect()
  const cardWidth = Math.min(310, window.innerWidth - 24)
  const estimatedHeight = 248
  const left = Math.max(12, Math.min(rect.left, window.innerWidth - cardWidth - 12))
  const top = rect.bottom + estimatedHeight + 12 < window.innerHeight
    ? rect.bottom + 8
    : Math.max(12, rect.top - estimatedHeight - 8)
  cardStyle.value = { left: `${left}px`, top: `${top}px`, width: `${cardWidth}px` }
}

async function loadTags() {
  if (loaded.value || loading.value) return
  loading.value = true
  errorMessage.value = ''
  try {
    payload.value = await api.gamePitcherTags({
      year: props.year,
      gamePk: props.gamePk,
      pitcherId: props.pitcherId,
      role: role.value
    }) as unknown as TagPayload
    loaded.value = true
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Season tags are unavailable.'
  } finally {
    loading.value = false
  }
}

function openCard() {
  open.value = true
  updatePosition()
  void loadTags()
}

function closeCard() {
  open.value = false
}
</script>

<style scoped>
.pitcher-tag-hover{display:inline-flex;min-width:0}.pitcher-tag-hover>a{display:inline-flex;align-items:center;gap:9px;color:var(--color-foreground);font-weight:850;text-decoration:none}.pitcher-tag-hover>a:hover,.pitcher-tag-hover>a:focus-visible{color:var(--color-primary)}.pitcher-tag-card{position:fixed;z-index:1200;box-sizing:border-box;display:grid;gap:7px;border:1px solid color-mix(in srgb,var(--color-primary) 60%,var(--color-border));border-radius:10px;padding:12px;color:var(--color-foreground);background:color-mix(in srgb,var(--color-surface) 96%,#000);box-shadow:0 16px 44px #0008;pointer-events:none}.pitcher-tag-card strong{font-size:15px}.pitcher-tag-card p,.pitcher-tag-card small{margin:0;color:var(--color-muted-text);font-size:11px;line-height:1.45}.pitcher-tag-card .tag-kicker{color:var(--color-primary);font-size:9px;font-weight:900;letter-spacing:.08em;text-transform:uppercase}.tag-chips{display:flex;flex-wrap:wrap;gap:5px}.tag-chips span{border:1px solid color-mix(in srgb,var(--color-primary) 45%,var(--color-border));border-radius:999px;padding:4px 7px;color:var(--color-foreground);background:color-mix(in srgb,var(--color-primary) 12%,transparent);font-size:10px;font-weight:850}.tag-chips span.is-practical{border-style:dashed;border-color:#69d3c3}.pitcher-tag-card .tag-warning{color:#f6ad55}
@media(prefers-reduced-motion:reduce){.pitcher-tag-card{transition:none}}
</style>
