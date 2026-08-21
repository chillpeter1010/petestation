<template>
  <section v-if="rows.length" class="payroll-lines">
    <header><div><span>{{ eyebrow }}</span><h3>{{ title }}</h3></div><strong>{{ rows.length }} lines</strong></header>
    <div class="table-scroll" tabindex="0">
      <table>
        <thead><tr><th>Description</th><th v-for="yearLabel in years" :key="yearLabel">{{ yearLabel }}</th></tr></thead>
        <tbody>
          <tr v-for="row in rows" :key="row.description">
            <th scope="row">{{ row.description }}</th>
            <td v-for="yearLabel in years" :key="yearLabel">{{ row.amounts[yearLabel] || '--' }}</td>
          </tr>
        </tbody>
        <tfoot v-if="totals">
          <tr><th>Estimated total</th><td v-for="yearLabel in years" :key="yearLabel">{{ totals[yearLabel] || '--' }}</td></tr>
        </tfoot>
      </table>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { TeamPayrollLineItem } from '~/types/api'

defineProps<{
  title: string
  eyebrow: string
  rows: TeamPayrollLineItem[]
  years: string[]
  totals?: Record<string, string>
}>()
</script>

<style scoped>
.payroll-lines { border-bottom: 1px solid var(--team-panel-border); }
.payroll-lines > header { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; padding: 19px 26px 13px; }
.payroll-lines header span { color: var(--team-accent); font-size: 9px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }
.payroll-lines h3 { margin: 4px 0 0; color: var(--color-text); font-size: 18px; }
.payroll-lines header > strong { color: var(--color-muted-text); font: 750 10px "Fira Code", monospace; }
.table-scroll { overflow-x: auto; scrollbar-color: var(--team-primary) var(--color-background); }
table { width: 100%; min-width: 1160px; border-collapse: collapse; font-variant-numeric: tabular-nums; }
th, td { border-top: 1px solid var(--team-panel-border); padding: 12px 14px; text-align: left; white-space: nowrap; }
thead th { color: var(--color-muted-text); background: color-mix(in srgb, var(--color-background) 82%, transparent); font-size: 9px; letter-spacing: .06em; text-transform: uppercase; }
tbody th, tfoot th { position: sticky; left: 0; z-index: 1; min-width: 330px; color: var(--color-text); background: var(--team-panel-bg); font-size: 11px; }
tbody td { color: var(--color-muted-text); font-size: 11px; }
tfoot th, tfoot td { color: var(--team-accent); background: color-mix(in srgb, var(--team-primary) 9%, var(--team-panel-bg)); font-size: 11px; font-weight: 900; }
@media (max-width: 760px) { .payroll-lines > header { padding-inline: 20px; } }
</style>
