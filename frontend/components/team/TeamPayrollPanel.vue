<template>
  <section class="payroll-panel" aria-labelledby="payroll-title">
    <header class="payroll-header">
      <div>
        <p class="eyebrow"><Banknote :size="16" /> Contract outlook</p>
        <h2 id="payroll-title">Team payroll</h2>
        <p>Contracts, control years, commitments, and competitive-balance-tax outlook.</p>
      </div>
      <a v-if="payroll?.source_url" :href="payroll.source_url" target="_blank" rel="noreferrer">Source <ExternalLink :size="14" /></a>
    </header>

    <div v-if="pending" class="panel-state">Loading payroll snapshot...</div>
    <div v-else-if="error" class="panel-state error">{{ error.message }}</div>

    <template v-else-if="payroll">
      <div class="summary-grid">
        <article><span>{{ payroll.season }} estimate</span><strong>{{ payroll.estimated_payroll || '--' }}</strong></article>
        <article><span>Luxury tax estimate</span><strong>{{ payroll.estimated_luxury_tax_payroll[String(payroll.season)] || '--' }}</strong></article>
        <article><span>Guaranteed deals</span><strong>{{ payroll.guaranteed_players.length }}</strong></article>
        <article><span>Refresh status</span><strong :class="{ due: payroll.refresh_due }">{{ payroll.refresh_due ? 'Update due' : 'Current' }}</strong></article>
      </div>

      <div class="snapshot-note">
        <CalendarClock :size="17" />
        <span>Snapshot {{ formatDate(payroll.source_updated_at) }} · Next review {{ formatDate(payroll.next_refresh_due) }}</span>
      </div>

      <nav class="payroll-tabs" aria-label="Payroll sections">
        <button v-for="tab in tabs" :key="tab.key" type="button" :aria-pressed="activeTab === tab.key" @click="activeTab = tab.key">
          {{ tab.label }} <small>{{ tab.count }}</small>
        </button>
      </nav>

      <div v-if="activePlayers" class="section-block">
        <div class="section-heading">
          <div><span>{{ activeMeta.eyebrow }}</span><h3>{{ activeMeta.title }}</h3></div>
          <strong>{{ activePlayers.length }} players</strong>
        </div>
        <div class="table-scroll" tabindex="0">
          <table class="player-table">
            <thead><tr><th>Player</th><th>Age</th><th>Service</th><th>Contract</th><th>AAV</th><th v-for="yearLabel in salaryYears" :key="yearLabel">{{ yearLabel }}</th></tr></thead>
            <tbody>
              <tr v-for="player in activePlayers" :key="player.name">
                <th scope="row">
                  <NuxtLink v-if="playerLink(player)" :to="playerLink(player)!">{{ player.name }}</NuxtLink>
                  <template v-else>{{ player.name }}</template>
                </th>
                <td>{{ player.age ?? '--' }}</td><td>{{ player.service_time || '--' }}</td><td>{{ player.contract }}</td><td>{{ player.aav || '--' }}</td>
                <td
                  v-for="yearLabel in salaryYears"
                  :key="yearLabel"
                  :class="statusClass(player.salary_statuses[yearLabel], player.salaries[yearLabel])"
                >
                  <span>{{ player.salaries[yearLabel] || '--' }}</span>
                  <small v-if="statusLabel(player.salary_statuses[yearLabel])" class="salary-status">
                    {{ statusLabel(player.salary_statuses[yearLabel]) }}
                  </small>
                </td>
              </tr>
            </tbody>
            <tfoot v-if="activeTab === 'prearb' && payroll.pre_arbitration_other_estimate">
              <tr><th colspan="5">Estimated salary for other pre-arbitration players</th><td>{{ payroll.pre_arbitration_other_estimate }}</td><td :colspan="Math.max(0, salaryYears.length - 1)" /></tr>
            </tfoot>
          </table>
        </div>
      </div>

      <template v-if="activeTab === 'dead'">
        <TeamPayrollLines title="Incentives" eyebrow="Earned escalators" :rows="payroll.incentives" :years="salaryYears" />
        <TeamPayrollLines title="Other payments" eyebrow="Buyouts and commitments" :rows="payroll.other_payments" :years="salaryYears" />
      </template>

      <template v-if="activeTab === 'outlook'">
        <div class="outlook-strip">
          <article v-for="yearLabel in salaryYears" :key="yearLabel">
            <span>{{ yearLabel }}</span><strong>{{ payroll.estimated_payroll_by_year[yearLabel] || '--' }}</strong><small>estimated payroll</small>
          </article>
        </div>
        <TeamPayrollLines title="Luxury tax payroll estimate" eyebrow="CBT calculation" :rows="payroll.luxury_tax_items" :years="salaryYears" :totals="payroll.estimated_luxury_tax_payroll" />
      </template>
    </template>
  </section>
</template>

<script setup lang="ts">
import { Banknote, CalendarClock, ExternalLink } from '@lucide/vue'
import type { TeamPayrollPlayer, TeamRosterPlayer } from '~/types/api'

type PayrollTab = 'contracts' | 'arbitration' | 'prearb' | 'dead' | 'outlook'
const props = defineProps<{ teamId: string; year: number; roster: TeamRosterPlayer[] }>()
const api = useApi()
const activeTab = ref<PayrollTab>('contracts')

const { data: payroll, pending, error } = await useLazyAsyncData(
  () => `team-payroll-${props.teamId}-${props.year}`,
  () => api.teamPayroll({ teamId: props.teamId, year: props.year }),
  { watch: [() => props.teamId, () => props.year] }
)

const tabs = computed(() => [
  { key: 'contracts' as const, label: 'Contracts', count: payroll.value?.guaranteed_players.length || 0 },
  { key: 'arbitration' as const, label: 'Arbitration', count: payroll.value?.arbitration_players.length || 0 },
  { key: 'prearb' as const, label: 'Pre-Arb', count: payroll.value?.pre_arbitration_players.length || 0 },
  { key: 'dead' as const, label: 'Commitments', count: (payroll.value?.off_roster_players.length || 0) + (payroll.value?.other_payments.length || 0) },
  { key: 'outlook' as const, label: 'Payroll outlook', count: salaryYears.value.length }
])

const activePlayers = computed<TeamPayrollPlayer[] | null>(() => {
  if (!payroll.value) return null
  if (activeTab.value === 'contracts') return payroll.value.guaranteed_players
  if (activeTab.value === 'arbitration') return payroll.value.arbitration_players
  if (activeTab.value === 'prearb') return payroll.value.pre_arbitration_players
  if (activeTab.value === 'dead') return payroll.value.off_roster_players
  return null
})

const activeMeta = computed(() => ({
  contracts: { eyebrow: 'Guaranteed salaries', title: 'Active contracts' },
  arbitration: { eyebrow: 'Club control', title: 'Arbitration eligible' },
  prearb: { eyebrow: 'Cost-controlled talent', title: 'Pre-arbitration players' },
  dead: { eyebrow: 'Off-roster obligations', title: 'Players outside the 40-man roster' },
  outlook: { eyebrow: '', title: '' }
})[activeTab.value])

const salaryYears = computed(() => {
  const years = new Set<string>()
  const value = payroll.value
  if (!value) return []
  ;[...value.guaranteed_players, ...value.arbitration_players, ...value.pre_arbitration_players, ...value.off_roster_players]
    .forEach(player => Object.keys(player.salaries).forEach(yearLabel => years.add(yearLabel)))
  ;[...value.incentives, ...value.other_payments, ...value.luxury_tax_items]
    .forEach(item => Object.keys(item.amounts).forEach(yearLabel => years.add(yearLabel)))
  Object.keys(value.estimated_payroll_by_year).forEach(yearLabel => years.add(yearLabel))
  return [...years].sort((a, b) => Number(a) - Number(b))
})

const rosterByName = computed(() => new Map(props.roster.map(player => [normalizeName(player.name), player])))

function playerLink(payrollPlayer: TeamPayrollPlayer) {
  const player = rosterByName.value.get(normalizeName(payrollPlayer.name))
  if (!player) return null
  if (player.group === 'Pitcher') {
    return { path: '/pitcher-personal', query: { year: props.year, role: player.role || 'All', team: props.teamId, pitcher_id: player.player_id } }
  }
  if (player.group === 'Batter') {
    return { path: '/batter-personal', query: { year: props.year, team: props.teamId, batter_id: player.player_id } }
  }
  return null
}

function normalizeName(value: string) { return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]/g, '') }

function formatDate(value: string | null) {
  return value ? new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric' }).format(new Date(value)) : 'not available'
}

function statusClass(status: string | undefined, value: string | undefined) {
  if (status) return `salary-${status.replaceAll('_', '-')}`
  if (!value) return ''
  const normalized = value.toLowerCase()
  if (normalized.includes('free agent')) return 'salary-free-agent'
  if (normalized.includes('arb')) return 'salary-arbitration'
  return ''
}

function statusLabel(status: string | undefined) {
  return ({
    club_option: 'Club option',
    player_option: 'Player option',
    mutual_option: 'Mutual option',
    vesting_option: 'Vesting option',
    exercised_club_option: 'Club option exercised',
    exercised_player_option: 'Player option exercised',
    exercised_mutual_option: 'Mutual option exercised',
    exercised_vesting_option: 'Vesting option exercised'
  } as Record<string, string>)[status || ''] || ''
}
</script>

<style scoped>
.payroll-panel { overflow: hidden; border: 1px solid var(--team-panel-border); border-radius: 18px; color: var(--color-text); background: var(--team-panel-bg); }
.payroll-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; padding: 24px 26px 18px; }
.eyebrow { display: flex; align-items: center; gap: 8px; margin: 0 0 7px; color: var(--team-accent); font-size: 11px; font-weight: 900; letter-spacing: .09em; text-transform: uppercase; }
.payroll-header h2 { margin: 0; font-size: clamp(25px, 2.6vw, 36px); }
.payroll-header > div > p:last-child { margin: 7px 0 0; color: var(--color-muted-text); }
.payroll-header a { display: inline-flex; align-items: center; gap: 6px; color: var(--color-muted-text); font-weight: 800; text-decoration: none; }
.summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; padding: 0 26px 16px; }
.summary-grid article { min-height: 88px; display: grid; align-content: center; gap: 7px; border: 1px solid var(--team-panel-border); border-radius: 13px; padding: 14px 16px; background: color-mix(in srgb, var(--color-background) 60%, transparent); }
.summary-grid span { color: var(--color-muted-text); font-size: 10px; font-weight: 850; text-transform: uppercase; }
.summary-grid strong { font: 900 21px "Fira Code", monospace; } .summary-grid .due { color: #f59e0b; }
.snapshot-note { display: flex; align-items: center; gap: 9px; margin: 0 26px 16px; border-radius: 10px; padding: 10px 13px; color: var(--color-muted-text); background: color-mix(in srgb, var(--team-primary) 10%, var(--color-background)); font-size: 12px; }
.payroll-tabs { display: flex; gap: 5px; overflow-x: auto; border-block: 1px solid var(--team-panel-border); padding: 9px 26px; background: color-mix(in srgb, var(--color-background) 58%, transparent); }
.payroll-tabs button { min-height: 38px; display: inline-flex; align-items: center; gap: 7px; border: 0; border-radius: 9px; padding: 8px 13px; color: var(--color-muted-text); background: transparent; font-size: 11px; font-weight: 850; white-space: nowrap; cursor: pointer; }
.payroll-tabs button[aria-pressed="true"] { color: #fff; background: var(--team-primary); }
.payroll-tabs small { min-width: 20px; border-radius: 99px; padding: 2px 5px; color: inherit; background: color-mix(in srgb, currentColor 12%, transparent); font: 800 9px "Fira Code", monospace; }
.section-block { border-bottom: 1px solid var(--team-panel-border); }
.section-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; padding: 19px 26px 13px; }
.section-heading span { color: var(--team-accent); font-size: 9px; font-weight: 900; letter-spacing: .08em; text-transform: uppercase; }
.section-heading h3 { margin: 4px 0 0; font-size: 18px; }
.section-heading > strong { color: var(--color-muted-text); font: 750 10px "Fira Code", monospace; }
.table-scroll { overflow-x: auto; scrollbar-color: var(--team-primary) var(--color-background); }
table { width: 100%; min-width: 1160px; border-collapse: collapse; font-variant-numeric: tabular-nums; }
th, td { border-top: 1px solid var(--team-panel-border); padding: 12px 14px; text-align: left; white-space: nowrap; }
thead th { color: var(--color-muted-text); background: color-mix(in srgb, var(--color-background) 82%, transparent); font-size: 9px; letter-spacing: .06em; text-transform: uppercase; }
tbody th { position: sticky; left: 0; z-index: 1; min-width: 175px; color: var(--color-text); background: var(--team-panel-bg); font-size: 13px; }
tbody th a { color: inherit; font-weight: 850; text-decoration: none; }
tbody th a:hover, tbody th a:focus-visible { color: var(--team-accent); text-decoration: underline; outline: none; }
tbody td { color: var(--color-muted-text); font-size: 11px; }
tbody td > span { display: block; }
tbody tr:hover td, tbody tr:hover th { background: color-mix(in srgb, var(--team-primary) 8%, var(--team-panel-bg)); }
.salary-status { display: block; margin-top: 4px; color: inherit; font-size: 8px; font-weight: 900; letter-spacing: .035em; text-transform: uppercase; }
.salary-club-option { color: #fff; background: #b9363e; }
.salary-player-option { color: #fff; background: #3b832c; }
.salary-mutual-option { color: #fff; background: #7450a8; }
.salary-vesting-option { color: #fff; background: #4f78a8; }
.salary-exercised-club-option,
.salary-exercised-player-option,
.salary-exercised-mutual-option,
.salary-exercised-vesting-option { color: #d8dee9; background: #343b46; box-shadow: inset 3px 0 #8b96a6; }
.salary-free-agent { color: #17120a; background: #f2c94c; font-size: 9px; font-weight: 900; }
.salary-arbitration { color: #b9dcff; background: rgba(62, 125, 190, .16); font-size: 9px; font-weight: 850; }
.salary-pre-arb { color: #b8e4d0; background: rgba(44, 139, 104, .15); font-size: 9px; font-weight: 850; }
tfoot th, tfoot td { color: var(--team-accent); background: color-mix(in srgb, var(--team-primary) 8%, transparent); font-size: 11px; }
.outlook-strip { display: grid; grid-template-columns: repeat(7, minmax(145px, 1fr)); overflow-x: auto; border-bottom: 1px solid var(--team-panel-border); padding: 18px 26px; gap: 8px; }
.outlook-strip article { display: grid; gap: 5px; border: 1px solid var(--team-panel-border); border-radius: 11px; padding: 13px; background: var(--color-background); }
.outlook-strip span { color: var(--team-accent); font: 850 10px "Fira Code", monospace; } .outlook-strip strong { font: 850 14px "Fira Code", monospace; } .outlook-strip small { color: var(--color-muted-text); font-size: 9px; }
.panel-state { margin: 0 26px 24px; border: 1px dashed var(--team-panel-border); border-radius: 12px; padding: 24px; color: var(--color-muted-text); text-align: center; } .panel-state.error { color: var(--color-destructive); }
@media (max-width: 760px) { .payroll-header { padding: 20px; } .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); padding: 0 20px 16px; } .snapshot-note { margin-inline: 20px; } .payroll-tabs { padding-inline: 20px; } .section-heading { padding-inline: 20px; } }
</style>
