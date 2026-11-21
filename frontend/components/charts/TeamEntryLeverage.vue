<script setup lang="ts">
import type { TeamSubstitutionRow } from '~/types/api'

const props = defineProps<{ rows: TeamSubstitutionRow[] }>()

const bands = [
  { label: 'gmLI < 1', tone: 'low', wpa: 'entry_wpa_low', count: 'entry_wpa_low_moves' },
  { label: '1 ≤ gmLI ≤ 2', tone: 'mid', wpa: 'entry_wpa_mid', count: 'entry_wpa_mid_moves' },
  { label: 'gmLI > 2', tone: 'high', wpa: 'entry_wpa_high', count: 'entry_wpa_high_moves' }
] as const

const teams = computed(() => props.rows.map(row => {
  const known = bands.reduce((sum, band) => sum + (row[band.count] ?? 0), 0)
  return {
    team: row.team,
    moves: row.moves,
    known,
    highShare: known ? (row.entry_wpa_high_moves ?? 0) / known : -1,
    bins: bands.map(band => {
      const n = row[band.count] ?? null
      return { ...band, n, share: known && n !== null ? n / known : 0, value: row[band.wpa] ?? null }
    })
  }
}).sort((a, b) => b.highShare - a.highShare || a.team.localeCompare(b.team)))

const maxWpa = computed(() => Math.max(1, ...teams.value.flatMap(row => row.bins.map(bin => Math.abs(bin.value ?? 0)))))
const wpaFormat = new Intl.NumberFormat('en-US', {
  signDisplay: 'exceptZero', minimumFractionDigits: 2, maximumFractionDigits: 2
})

function asWpa(value: number | null) {
  return value === null ? '—' : wpaFormat.format(value)
}

function binText(label: string, n: number | null, share: number) {
  return n === null ? `${label}: unavailable` : `${label}: ${n} entries (${(share * 100).toFixed(1)}%)`
}
</script>

<template>
  <div class="entry-leverage">
    <p class="entry-description">Teams are ordered by their share of entries above gmLI 2. Bars show the mix of known entry gmLI; the three right-hand columns show total observed WPA in those situations.</p>
    <ul class="entry-legend" aria-label="Entry leverage bands">
      <li v-for="band in bands" :key="band.tone"><i :class="band.tone" aria-hidden="true" />{{ band.label }}</li>
    </ul>
    <div class="entry-scroll" role="region" aria-label="Team entry gmLI and WPA, horizontally scrollable" tabindex="0">
      <table>
        <caption class="entry-sr">Share of pitching entries and total stint WPA by entry gmLI band</caption>
        <thead>
          <tr><th scope="col">Team</th><th scope="col">Entry gmLI mix</th><th scope="col">Known / all</th>
            <th v-for="band in bands" :key="band.tone" scope="col">WPA · {{ band.label }}</th></tr>
        </thead>
        <tbody>
          <tr v-for="row in teams" :key="row.team">
            <th scope="row">{{ row.team }}</th>
            <td>
              <div v-if="row.known" class="entry-bar" aria-hidden="true">
                <span v-for="bin in row.bins" :key="bin.tone" :class="bin.tone"
                  :style="{ width: `${bin.share * 100}%` }" :title="binText(bin.label, bin.n, bin.share)" />
              </div>
              <div v-if="row.known" class="entry-counts">
                <span v-for="bin in row.bins" :key="bin.tone">
                  <span class="entry-sr">{{ bin.label }}: </span>{{ bin.n ?? '—' }}
                </span>
              </div>
              <span v-else>—</span>
            </td>
            <td>{{ row.known }} / {{ row.moves }}</td>
            <td v-for="bin in row.bins" :key="bin.tone" :class="bin.value === null ? '' : bin.value >= 0 ? 'gain' : 'loss'"
              :style="{ '--heat': `${40 * Math.abs(bin.value ?? 0) / maxWpa}%` }">
              {{ asWpa(bin.value) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <p class="entry-description">Counts under each bar follow the legend order. The heatmap uses one color scale across teams and bands. Higher totals can reflect more entries in a band.</p>
  </div>
</template>

<style scoped>
.entry-leverage{padding:14px 22px 20px}
.entry-description{color:var(--color-muted-text);margin:0;font-size:14px}
.entry-description:last-child{margin-top:12px}
.entry-legend{display:flex;flex-wrap:wrap;gap:8px 18px;list-style:none;margin:12px 0;padding:0;font-size:14px}
.entry-legend li{display:flex;align-items:center;gap:7px}
.entry-legend i{width:12px;height:12px}
.entry-scroll{overflow:auto;max-height:580px}
.entry-scroll table{width:100%;min-width:660px;border-collapse:separate;border-spacing:0;font-size:14px;font-variant-numeric:tabular-nums}
.entry-scroll th,.entry-scroll td{padding:8px 12px;border-bottom:1px solid var(--color-border);text-align:right;white-space:nowrap}
.entry-scroll thead th{position:sticky;top:0;background:var(--color-surface);z-index:1}
.entry-scroll th:first-child,.entry-scroll thead th:nth-child(2){text-align:left}
.entry-bar{display:flex;min-width:154px;height:13px;overflow:hidden;background:var(--color-border)}
.entry-counts{display:flex;justify-content:space-between;margin-top:3px;color:var(--color-muted-text);font-size:12px}
.low{background:#82a7e6}
.mid{background:#5ac9bb}
.high{background:#d99e51}
.gain{background:color-mix(in srgb,#157365 var(--heat),transparent)}
.loss{background:color-mix(in srgb,#ae4743 var(--heat),transparent)}
.entry-sr{position:absolute;width:1px;height:1px;padding:0;overflow:hidden;clip-path:inset(50%);white-space:nowrap}
</style>
