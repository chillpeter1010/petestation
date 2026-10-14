<template>
  <main class="leaderboard-page">
    <ComparisonPageHeader
      eyebrow="Leaderboards"
      title="Pitcher Rankings"
      description="Switch between traditional results and Pete Stuff+, Location+, Pitching+, and observed-season Stamina+ rankings."
      back-to="/"
      back-label="Home"
    />

    <details class="column-guide">
      <summary><span>欄位說明</span><small>點擊展開目前頁籤的自定義指標</small></summary>
      <div class="column-guide__grid">
        <article v-for="item in metricGlossary" :key="item.key">
          <strong>{{ item.key }}</strong>
          <p>{{ item.description }}</p>
        </article>
      </div>
    </details>

    <nav class="view-tabs" aria-label="Leaderboard view">
      <button type="button" :class="{ active: activeView === 'basic' }" :aria-pressed="activeView === 'basic'" @click="activeView = 'basic'">Basic</button>
      <button type="button" :class="{ active: activeView === 'stuff' }" :aria-pressed="activeView === 'stuff'" @click="activeView = 'stuff'">Stuff+</button>
      <button type="button" :class="{ active: activeView === 'location' }" :aria-pressed="activeView === 'location'" @click="activeView = 'location'">Location+</button>
      <button type="button" :class="{ active: activeView === 'pitching' }" :aria-pressed="activeView === 'pitching'" @click="activeView = 'pitching'">Pitching+</button>
      <button type="button" :class="{ active: activeView === 'stamina' }" :aria-pressed="activeView === 'stamina'" @click="activeView = 'stamina'">Stamina+</button>
    </nav>

    <section class="filter-panel">
      <label>
        Year
        <select v-model.number="year">
          <option v-for="option in visibleYearOptions" :key="option" :value="option">{{ option }}</option>
        </select>
      </label>
      <fieldset class="role-filter">
        <legend>Role</legend>
        <div class="role-checkbox-row">
          <label class="checkbox-pill">
            <input v-model="includeStarters" type="checkbox" :disabled="activeView === 'stamina'">
            <span>Starter</span>
          </label>
          <label class="checkbox-pill">
            <input v-model="includeRelievers" type="checkbox" :disabled="activeView === 'stamina'">
            <span>Reliever</span>
          </label>
        </div>
      </fieldset>
      <label>
        Team
        <select v-model="team">
          <option value="All">All</option>
          <option v-for="option in teamOptions" :key="option" :value="option">{{ option }}</option>
        </select>
      </label>
      <label class="search-label">
        Search
        <input v-model.trim="searchText" type="search" placeholder="Pitcher, team, role...">
      </label>
      <label v-if="activeView !== 'basic'">
        Minimum IP
        <input v-model.number="minimumIp" type="number" min="0" step="10">
      </label>
    </section>

    <aside v-if="activeView !== 'basic' && activeView !== 'stamina' && qualityData" class="data-note">
      <span>Data through {{ qualityData.data_as_of || 'unknown' }}</span>
      <span :class="['status-chip', qualityData.cache_status]">{{ qualityData.cache_status }}</span>
      <span>{{ qualityData.model_version }}</span>
      <span v-if="qualityData.pitching_model_version">{{ qualityData.pitching_model_version }}</span>
      <span v-if="activeView === 'pitching' && qualityData.pitching_data_as_of" class="metric-cutoff">
        Pitching+ through {{ qualityData.pitching_data_as_of }}
      </span>
      <span v-for="(status, metric) in qualityData.source_status" :key="metric" :class="['metric-status', status]">
        {{ metricLabel(metric) }} {{ status }}
      </span>
      <span v-if="qualityData.warnings.length" class="warning">{{ qualityData.warnings.join(' ') }}</span>
    </aside>

    <aside v-if="activeView === 'stamina' && staminaData" class="data-note">
      <span>Data through {{ staminaData.data_as_of || 'unknown' }}</span>
      <span class="status-chip current">VALIDATED OBSERVED STATE</span>
      <span>{{ staminaData.contract_version }}</span>
      <span>Developed {{ staminaData.development_year }} · untouched test {{ staminaData.test_year }}</span>
      <span v-if="staminaData.warnings.length" class="warning">{{ staminaData.warnings.join(' ') }}</span>
    </aside>

    <p v-if="activePending" class="empty-state">Loading pitcher stats...</p>
    <p v-else-if="activeError" class="empty-state">Could not load pitcher stats.</p>
    <DataTable
      v-else-if="activeView === 'basic'"
      class="leaderboard-table"
      title="Pitcher Basic Stats"
      :table="leaderboardTable"
      :max-rows="500"
      link-column="Pitcher"
      headshot-column="Pitcher"
      :link-to="leaderboardPlayerLink"
    />
    <DataTable
      v-else-if="activeView === 'stamina'"
      class="leaderboard-table quality-table stamina-table"
      title="Observed Season Stamina+ Rankings"
      :table="staminaTable"
      :max-rows="1000"
      link-column="Name"
      headshot-column="Name"
      :link-to="leaderboardPlayerLink"
      expandable
      row-key="player_id"
      @row-toggle="toggleStaminaDetail"
    >
      <template #expanded="{ row }">
        <StaminaTimeline
          compact
          three-signal
          :response="staminaDetails[Number(row.player_id)] || null"
          :physical-response="staminaPhysicalDetails[Number(row.player_id)] || null"
          :command-response="staminaCommandDetails[Number(row.player_id)] || null"
          :loading="Boolean(staminaDetailLoading[Number(row.player_id)])"
          :error="staminaDetailErrors[Number(row.player_id)] || ''"
          :errors="staminaSignalErrors[Number(row.player_id)] || []"
        />
      </template>
    </DataTable>
    <DataTable
      v-else
      class="leaderboard-table quality-table"
      :title="`${activeMetric.label} Rankings`"
      :table="plusTable"
      :max-rows="1000"
      link-column="Name"
      headshot-column="Name"
      :link-to="leaderboardPlayerLink"
    />
  </main>
</template>

<script setup lang="ts">
import type { PitcherLeaderboardRow, StaminaCommandRetentionResponse, StaminaGameStatesResponse, StaminaPhysicalStabilityResponse, TablePayload } from '~/types/api'

const api = useApi()

const year = ref(2026)
type LeaderboardView = 'basic' | 'stuff' | 'location' | 'pitching' | 'stamina'
type PlusView = Exclude<LeaderboardView, 'basic' | 'stamina'>

const activeView = ref<LeaderboardView>('basic')
const includeStarters = ref(true)
const includeRelievers = ref(true)
const team = ref('All')
const searchText = ref('')
const minimumIp = ref(0)
const staminaDetails = ref<Record<number, StaminaGameStatesResponse>>({})
const staminaPhysicalDetails = ref<Record<number, StaminaPhysicalStabilityResponse>>({})
const staminaCommandDetails = ref<Record<number, StaminaCommandRetentionResponse>>({})
const staminaDetailLoading = ref<Record<number, boolean>>({})
const staminaDetailLoaded = ref<Record<number, boolean>>({})
const staminaDetailErrors = ref<Record<number, string>>({})
const staminaSignalErrors = ref<Record<number, string[]>>({})
const yearOptions = [2026, 2025, 2024, 2023, 2022, 2021]
const visibleYearOptions = computed(() => activeView.value === 'stamina' ? [2026] : yearOptions)
const pitchCodes = ['FA', 'SI', 'FC', 'FS', 'SL', 'CU', 'CH', 'KC', 'FO']
const metricConfig = {
  stuff: { label: 'Stuff+', prefix: 'Stf+', scoreKey: 'stuff_plus', pitchScoresKey: 'pitch_type_scores' },
  location: { label: 'Location+', prefix: 'Loc+', scoreKey: 'location_plus', pitchScoresKey: 'location_pitch_type_scores' },
  pitching: { label: 'Pitching+', prefix: 'Pit+', scoreKey: 'pitching_plus', pitchScoresKey: 'pitching_pitch_type_scores' }
} as const

const activeMetric = computed(() => metricConfig[
  (activeView.value === 'basic' || activeView.value === 'stamina' ? 'stuff' : activeView.value) as PlusView
])

const pitchCodeNote = '分球種縮寫：FA 四縫線／一般速球、SI 伸卡球、FC 卡特球、FS 指叉球、SL 滑球、CU 曲球、CH 變速球、KC 彈指曲球、FO 其他慢速球。'
const metricGlossary = computed(() => {
  if (activeView.value === 'basic') return [
    { key: 'Avg GS', description: '平均 Game Score，用單場先發內容概括投球局數、三振、安打、保送與失分；越高通常代表先發內容越好。' },
    { key: 'GR', description: '後援出賽場次；同一球季兼任先發與後援時，可與 GS 一起判讀角色。' },
    { key: 'NP', description: '該球季資料中的總投球數。' }
  ]
  if (activeView.value === 'stuff') return [
    { key: 'Stuff+', description: '以球速、轉速、位移、出手條件等估計球本身的威力；100 為聯盟平均，越高越好。' },
    { key: 'Stf+ FA…FO', description: `各球種的 Stuff+，只有具備必要追蹤資料的球才會納入。${pitchCodeNote}` }
  ]
  if (activeView.value === 'location') return [
    { key: 'Location+', description: '衡量球落點、好球帶位置與球數情境的執行品質；100 為聯盟平均，越高越好。' },
    { key: 'Loc+ FA…FO', description: `各球種的 Location+；缺值表示沒有足夠有效資料，不會補成 0。${pitchCodeNote}` }
  ]
  if (activeView.value === 'pitching') return [
    { key: 'Pitching+', description: '完整逐球模型綜合球質、控球與情境後的預期壓制能力；不是 Stuff+ 與 Location+ 的簡單相加。' },
    { key: 'Pit+ FA…FO', description: `各球種的 Pitching+；只使用完整特徵且通過資料截止日門檻的球。${pitchCodeNote}` }
  ]
  return [
    { key: 'Stamina+', description: '正式排行榜使用的校正後球季球質維持分數，也是目前排名依據；100 為聯盟平均。' },
    { key: 'Q-Stm+', description: 'Quality Stamina+ 的縮寫：合格單場球質維持分數的球季平均。這是研究用逐場平均，不等同正式校正後 Stamina+。' },
    { key: 'Phy-Stb+', description: 'Physical Stability+ 的縮寫：球速、轉速、位移、出手點、延伸與臂角等公開追蹤訊號的單場穩定度球季平均。' },
    { key: 'Cmd-Ret+', description: 'Command Retention+ 的縮寫：Location+ 相對同場早段合理預期的維持程度球季平均。' },
    { key: 'Rel', description: '正式 Stamina+ 的可靠度，顯示資料對個人分數的支持程度；顯示到小數點後三位。' },
    { key: 'Stm G', description: '符合正式 Stamina+ 單場資料門檻的先發場次。' },
    { key: 'Avg Pit', description: '該投手先發場次的平均投球數；只描述使用深度，不直接當作體能分數。' },
    { key: 'Stm+ FB / BRK / OFF', description: '速球、變化球與慢速球族群的正式球季 Stamina+；各族群不足自己的樣本或可靠度門檻時顯示「-」。' },
    { key: '80% Low / High', description: '正式 Stamina+ 的 80% 不確定區間下限與上限；範圍越窄通常代表估計越穩定。' },
    { key: '三項研究欄門檻', description: 'Q-Stm+、Phy-Stb+、Cmd-Ret+ 各自至少需要 10 場合格單場資料；不足時維持空值，不補 0，也不改變正式排名。' }
  ]
})

const selectedRole = computed<'All' | 'SP' | 'RP'>(() => {
  if (includeStarters.value && includeRelievers.value) {
    return 'All'
  }
  if (includeStarters.value) {
    return 'SP'
  }
  if (includeRelievers.value) {
    return 'RP'
  }
  return 'All'
})

const { data: leaderboardRows, pending, error } = await useAsyncData(
  () => `leaderboard-basic-${year.value}-${selectedRole.value}`,
  () => api.pitcherLeaderboard({ year: year.value, role: selectedRole.value }),
  { watch: [year, selectedRole], default: () => [] }
)

const { data: qualityData, pending: qualityPending, error: qualityError } = await useAsyncData(
  () => `leaderboard-quality-${year.value}-${selectedRole.value}-${team.value}-${minimumIp.value}`,
  () => api.stuffLeaderboard({
    year: year.value,
    role: selectedRole.value,
    team: team.value,
    minimumIp: minimumIp.value
  }),
  { watch: [year, selectedRole, team, minimumIp] }
)

const { data: staminaData, pending: staminaPending, error: staminaError } = await useAsyncData(
  'leaderboard-stamina-2026',
  () => api.staminaLeaderboard(2026)
)

const activePending = computed(() => {
  if (activeView.value === 'basic') return pending.value
  if (activeView.value === 'stamina') return staminaPending.value || pending.value
  return qualityPending.value
})
const activeError = computed(() => {
  if (activeView.value === 'basic') return error.value
  if (activeView.value === 'stamina') return staminaError.value || error.value
  return qualityError.value
})

const teamOptions = computed(() => [...new Set(leaderboardRows.value.map((pitcher) => pitcher.team).filter(Boolean))].sort())

const filteredPitchers = computed(() => {
  const query = searchText.value.toLowerCase()
  return leaderboardRows.value.filter((pitcher) => {
    const teamMatch = team.value === 'All' || pitcher.team === team.value
    const queryMatch = !query || [pitcher.name, pitcher.team, pitcher.role].some((value) => String(value).toLowerCase().includes(query))
    return teamMatch && queryMatch
  })
})

const leaderboardTable = computed<TablePayload>(() => ({
  columns: [
    { key: 'Pitcher', label: 'Pitcher' },
    { key: 'Team', label: 'Team' },
    { key: 'Role', label: 'Role' },
    { key: 'G', label: 'G' },
    { key: 'GS', label: 'GS' },
    { key: 'Avg GS', label: 'Avg GS' },
    { key: 'GR', label: 'GR' },
    { key: 'IP', label: 'IP' },
    { key: 'ERA', label: 'ERA' },
    { key: 'WHIP', label: 'WHIP' },
    { key: 'H', label: 'H' },
    { key: 'R', label: 'R' },
    { key: 'ER', label: 'ER' },
    { key: 'BB', label: 'BB' },
    { key: 'SO', label: 'SO' },
    { key: 'HR', label: 'HR' },
    { key: 'NP', label: 'NP' },
    { key: 'K%', label: 'K%' },
    { key: 'BB%', label: 'BB%' }
  ],
  rows: filteredPitchers.value.map((pitcher) => ({
    Pitcher: pitcher.name,
    Team: pitcher.team || '-',
    Role: pitcher.role,
    G: pitcher.games,
    GS: pitcher.starts,
    'Avg GS': formatNumber(pitcher.avg_game_score, 1),
    GR: pitcher.relief_games,
    IP: formatNumber(pitcher.ip, 1),
    ERA: formatNumber(pitcher.era, 2),
    WHIP: formatNumber(pitcher.whip, 3),
    H: formatInteger(pitcher.hits),
    R: formatInteger(pitcher.runs),
    ER: formatInteger(pitcher.earned_runs),
    BB: formatInteger(pitcher.walks),
    SO: formatInteger(pitcher.strikeouts),
    HR: formatInteger(pitcher.home_runs),
    NP: formatInteger(pitcher.pitches),
    'K%': formatPercent(pitcher.strikeout_rate),
    'BB%': formatPercent(pitcher.walk_rate),
    player_id: pitcher.player_id,
    _role: playerRole(pitcher)
  }))
}))

const plusTable = computed<TablePayload>(() => {
  const metric = activeMetric.value
  return {
    columns: [
      { key: '#', label: '#' },
      { key: 'Name', label: 'Name' },
      { key: 'Team', label: 'Team' },
      { key: 'IP', label: 'IP' },
      ...pitchCodes.map((code) => ({ key: `${metric.prefix} ${code}`, label: `${metric.prefix} ${code}` })),
      { key: metric.label, label: metric.label }
    ],
    rows: (qualityData.value?.rows || [])
      .filter((pitcher) => {
        const query = searchText.value.toLowerCase()
        return !query || [pitcher.name, pitcher.team, pitcher.role].some((value) => String(value).toLowerCase().includes(query))
      })
      .map((pitcher, index) => {
        const pitchScores = pitcher[metric.pitchScoresKey] || {}
        return {
          '#': index + 1,
          Name: pitcher.name,
          Team: pitcher.team || '-',
          IP: pitcher.ip,
          ...Object.fromEntries(pitchCodes.map((code) => [`${metric.prefix} ${code}`, pitchScores[code]])),
          [metric.label]: pitcher[metric.scoreKey],
          player_id: pitcher.player_id,
          _role: pitcher.role
        }
      })
  }
})

const basicPitcherLookup = computed(() => new Map(
  leaderboardRows.value.map((pitcher) => [Number(pitcher.player_id), pitcher])
))

const staminaTable = computed<TablePayload>(() => ({
  columns: [
    { key: '#', label: '#' },
    { key: 'Name', label: 'Name' },
    { key: 'Team', label: 'Team' },
    { key: 'GS', label: 'GS' },
    { key: 'Stm G', label: 'Stm G' },
    { key: 'IP', label: 'IP' },
    { key: 'Rel', label: 'Rel' },
    { key: 'Stamina+', label: 'Stamina+' },
    { key: 'Q-Stm+', label: 'Q-Stm+' },
    { key: 'Phy-Stb+', label: 'Phy-Stb+' },
    { key: 'Cmd-Ret+', label: 'Cmd-Ret+' },
    { key: 'Avg Pit', label: 'Avg Pit' },
    { key: 'Stm+ FB', label: 'Stm+ FB' },
    { key: 'Stm+ BRK', label: 'Stm+ BRK' },
    { key: 'Stm+ OFF', label: 'Stm+ OFF' },
    { key: '80% Low', label: '80% Low' },
    { key: '80% High', label: '80% High' }
  ],
  rows: (staminaData.value?.rows || [])
    .filter((pitcher) => {
      const basic = basicPitcherLookup.value.get(Number(pitcher.pitcher_id))
      const query = searchText.value.toLowerCase()
      const teamMatch = team.value === 'All' || pitcher.team === team.value
      const queryMatch = !query || [pitcher.name, displayPitcherName(pitcher.name), pitcher.team, 'SP']
        .some((value) => String(value).toLowerCase().includes(query))
      return teamMatch && queryMatch && Number(basic?.ip || 0) >= minimumIp.value
    })
    .map((pitcher) => {
      const basic = basicPitcherLookup.value.get(Number(pitcher.pitcher_id))
      return {
        '#': pitcher.rank,
        Name: displayPitcherName(pitcher.name),
        Team: pitcher.team || '-',
        GS: pitcher.starts,
        'Stm G': pitcher.eligible_games,
        IP: formatNumber(basic?.ip ?? null, 1),
        Rel: formatNumber(pitcher.reliability, 3),
        'Stamina+': formatNumber(pitcher.stamina_plus, 1),
        'Q-Stm+': formatNumber(pitcher.quality_game_stamina_plus ?? null, 1),
        'Phy-Stb+': formatNumber(pitcher.physical_stability_plus ?? null, 1),
        'Cmd-Ret+': formatNumber(pitcher.command_retention_plus ?? null, 1),
        'Avg Pit': formatNumber(pitcher.average_pitches, 1),
        'Stm+ FB': formatNumber(pitcher.fastball_stamina_plus ?? null, 1),
        'Stm+ BRK': formatNumber(pitcher.breaking_stamina_plus ?? null, 1),
        'Stm+ OFF': formatNumber(pitcher.offspeed_stamina_plus ?? null, 1),
        '80% Low': formatNumber(pitcher.ci_low, 1),
        '80% High': formatNumber(pitcher.ci_high, 1),
        player_id: pitcher.pitcher_id,
        _role: 'SP'
      }
    })
}))

watch([year, selectedRole], () => {
  team.value = 'All'
})

watch(activeView, (view) => {
  if (view === 'stamina') {
    year.value = 2026
    includeStarters.value = true
    includeRelievers.value = false
  }
})

watch([includeStarters, includeRelievers], ([hasStarters, hasRelievers]) => {
  if (!hasStarters && !hasRelievers) {
    includeStarters.value = true
    includeRelievers.value = true
  }
})

function playerRole(pitcher: PitcherLeaderboardRow) {
  if (pitcher.role === 'RP') {
    return 'RP'
  }
  return pitcher.starts > 0 ? 'SP' : 'RP'
}

function leaderboardPlayerLink(row: Record<string, unknown>) {
  const pitcherId = Number(row.player_id)
  if (!Number.isFinite(pitcherId) || pitcherId <= 0) {
    return undefined
  }
  return {
    path: '/pitcher-personal',
    query: {
      year: year.value,
      role: String(row._role || row.Role || 'SP'),
      team: String(row.Team || ''),
      pitcher_id: pitcherId,
      tab: activeView.value === 'stamina' ? 'stamina' : undefined
    }
  }
}

async function toggleStaminaDetail(row: Record<string, unknown>, expanded: boolean) {
  const pitcherId = Number(row.player_id)
  if (!expanded || !Number.isFinite(pitcherId) || staminaDetailLoaded.value[pitcherId] || staminaDetailLoading.value[pitcherId]) {
    return
  }
  staminaDetailLoading.value = { ...staminaDetailLoading.value, [pitcherId]: true }
  staminaDetailErrors.value = { ...staminaDetailErrors.value, [pitcherId]: '' }
  staminaSignalErrors.value = { ...staminaSignalErrors.value, [pitcherId]: [] }
  try {
    const [quality, physical, command] = await Promise.allSettled([
      api.staminaGameStates(2026, pitcherId),
      api.staminaPhysicalStability(2026, pitcherId),
      api.staminaCommandRetention(2026, pitcherId)
    ])
    if (quality.status === 'fulfilled') staminaDetails.value = { ...staminaDetails.value, [pitcherId]: quality.value }
    if (physical.status === 'fulfilled') staminaPhysicalDetails.value = { ...staminaPhysicalDetails.value, [pitcherId]: physical.value }
    if (command.status === 'fulfilled') staminaCommandDetails.value = { ...staminaCommandDetails.value, [pitcherId]: command.value }
    staminaDetailErrors.value = {
      ...staminaDetailErrors.value,
      [pitcherId]: quality.status === 'rejected' ? 'Quality Stamina+ could not be loaded.' : ''
    }
    staminaSignalErrors.value = {
      ...staminaSignalErrors.value,
      [pitcherId]: [
        physical.status === 'rejected' ? 'Physical Stability+ could not be loaded.' : '',
        command.status === 'rejected' ? 'Command Retention+ could not be loaded.' : ''
      ].filter(Boolean)
    }
    staminaDetailLoaded.value = { ...staminaDetailLoaded.value, [pitcherId]: true }
  } catch (error) {
    staminaDetailErrors.value = {
      ...staminaDetailErrors.value,
      [pitcherId]: error instanceof Error ? error.message : 'Could not load game-by-game Stamina+.'
    }
  } finally {
    staminaDetailLoading.value = { ...staminaDetailLoading.value, [pitcherId]: false }
  }
}

function formatInteger(value: number | null) {
  if (value === null || value === undefined) {
    return '-'
  }
  return Math.round(value).toLocaleString()
}

function displayPitcherName(value: string) {
  const [lastName, ...givenNameParts] = value.split(',')
  const givenName = givenNameParts.join(',').trim()
  return givenName ? `${givenName} ${lastName.trim()}` : value
}

function formatNumber(value: number | null, digits: number) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '-'
  }
  return value.toFixed(digits)
}

function formatPercent(value: number | null) {
  if (value === null || value === undefined) {
    return '-'
  }
  return `${(value * 100).toFixed(1)}%`
}

function metricLabel(metric: string) {
  return ({ stuff_plus: 'Stuff+', location_plus: 'Location+', pitching_plus: 'Pitching+' } as Record<string, string>)[metric] || metric
}
</script>

<style scoped>
.leaderboard-page {
  max-width: 1320px;
  margin: 0 auto;
  padding: 104px 20px 56px;
}

.column-guide {
  margin-top: 18px;
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}

.column-guide summary {
  display: flex;
  min-height: 48px;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 0 16px;
  color: var(--color-foreground);
  cursor: pointer;
  font-size: 15px;
  font-weight: 900;
  list-style-position: inside;
}

.column-guide summary:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.column-guide summary small {
  color: var(--color-muted-text);
  font-size: 12px;
  font-weight: 700;
}

.column-guide__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1px;
  border-top: 1px solid var(--color-border);
  background: var(--color-border);
}

.column-guide__grid article {
  min-width: 0;
  padding: 13px 16px;
  background: var(--color-surface);
}

.column-guide__grid strong {
  color: var(--color-primary);
  font-size: 14px;
}

.column-guide__grid p {
  margin: 5px 0 0;
  color: var(--color-muted-text);
  font-size: 13px;
  line-height: 1.55;
}

.filter-panel,
.leaderboard-table,
.view-tabs,
.data-note {
  border: 1px solid var(--color-border);
  border-radius: 0;
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}

.filter-panel {
  display: grid;
  grid-template-columns: 140px 220px 160px minmax(220px, 1fr) 140px;
  gap: 14px;
  margin-top: 18px;
  padding: 16px;
}

.view-tabs {
  display: inline-flex;
  margin-top: 18px;
  padding: 4px;
}

.view-tabs button {
  border: 0;
  padding: 9px 16px;
  color: var(--color-muted-text);
  background: transparent;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  font-weight: 900;
}

.view-tabs button.active {
  color: white;
  background: var(--color-primary);
}

.view-tabs button:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.data-note {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-top: 16px;
  padding: 10px 14px;
  color: var(--color-muted-text);
  font-size: 12px;
}

.status-chip {
  padding: 3px 7px;
  color: var(--color-foreground);
  background: var(--color-muted);
  font-weight: 900;
  text-transform: uppercase;
}

.status-chip.current {
  color: #d8ffe8;
  background: #177245;
}

.status-chip.stale,
.warning {
  color: var(--color-warning, #d89b3c);
}

.metric-status {
  font-weight: 800;
}

.metric-cutoff {
  color: var(--color-foreground);
  font-weight: 900;
}

.metric-status.stale,
.metric-status.unavailable {
  color: var(--color-warning, #d89b3c);
}

.quality-table {
  --leaderboard-table-width: 1480px;
}

.stamina-table {
  --leaderboard-table-width: 1840px;
}

.quality-table :deep(table) {
  min-width: var(--leaderboard-table-width);
}

.leaderboard-table :deep(.data-table-wrap) {
  border-radius: 0;
}

.leaderboard-table :deep(table) {
  font-size: 14px;
}

.leaderboard-table :deep(.table-header h2) {
  font-size: 17px;
}

.leaderboard-table :deep(.table-header span) {
  font-size: 15px;
}

label,
.role-filter {
  display: grid;
  gap: 8px;
  color: var(--color-foreground);
  font-size: 12px;
  font-weight: 900;
  text-transform: uppercase;
}

.role-filter {
  border: 0;
  margin: 0;
  padding: 0;
  align-self: end;
}

.role-filter legend {
  padding: 0;
}

.role-checkbox-row {
  display: flex;
  gap: 8px;
  min-width: 0;
}

.checkbox-pill {
  display: flex;
  min-width: 0;
  height: 44px;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 0 12px;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  color: var(--color-text);
  cursor: pointer;
  font-size: 13px;
  font-weight: 900;
  text-transform: none;
}

.checkbox-pill input {
  width: 15px;
  height: 15px;
  min-width: 15px;
  padding: 0;
  accent-color: var(--color-primary);
}

.checkbox-pill:has(input:disabled) {
  cursor: not-allowed;
  opacity: 0.72;
}

select,
input {
  min-width: 0;
  height: 44px;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  padding: 0 12px;
  color: var(--color-text);
  background: var(--color-surface);
  font: inherit;
  font-size: 14px;
  font-weight: 800;
  text-transform: none;
}

.leaderboard-table {
  margin-top: 16px;
}

.leaderboard-table header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--color-border);
}

h2 {
  margin: 0;
  color: var(--color-foreground);
}

.leaderboard-table header span,
.empty-state {
  color: var(--color-muted-text);
}

.table-scroll {
  max-height: 680px;
  overflow: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

th,
td {
  padding: 10px 14px;
  border-bottom: 1px solid var(--color-border);
  text-align: left;
  white-space: nowrap;
}

th {
  position: sticky;
  top: 0;
  z-index: 1;
  color: var(--color-foreground);
  background: var(--color-muted);
}

td {
  color: var(--color-text);
}

.numeric {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.player-link {
  border: 0;
  padding: 0;
  color: var(--color-primary);
  background: transparent;
  cursor: pointer;
  font-weight: 900;
  font: inherit;
  text-decoration: none;
}

.player-link:hover {
  text-decoration: underline;
}

.empty-state {
  margin: 0;
  padding: 18px 16px;
}

@media (max-width: 860px) {
  .column-guide summary {
    align-items: flex-start;
    flex-direction: column;
    padding-top: 12px;
    padding-bottom: 12px;
  }

  .column-guide__grid {
    grid-template-columns: 1fr;
  }

  .filter-panel {
    grid-template-columns: 1fr;
  }
}
</style>
