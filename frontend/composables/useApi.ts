import type {
  BatterZoneRatesResponse,
  AnalysisResponse,
  CatcherDescriptiveDetailResponse,
  CatcherDescriptiveLeaderboardResponse,
  CatcherDescriptivePairedDuoResponse,
  CatcherStrategyBridgeResponse,
  BatterLeaderboardRow,
  BatterOption,
  BatterPeriodDateRange,
  BatterLineupScenarioResponse,
  BatterPeriodComparisonResponse,
  BatterPeriodOptionsResponse,
  BatterTeamResearchResponse,
  StuffAttackResponse,
  SwingTimingPlayerDetailResponse,
  SwingTimingResponse,
  ComparisonOptionsResponse,
  ComparisonOverviewResponse,
  HomeRecommendationsResponse,
  LocationComparisonResponse,
  LocationHeatmapResponse,
  LocationLeaderboardResponse,
  LocationPitcherResponse,
  LeverageOverviewResponse,
  LeverageScenarioInput,
  LeverageScenarioResponse,
  StaminaOverviewResponse,
  StaminaResearchCurvesResponse,
  StaminaGameStatesResponse,
  StaminaPhysicalStabilityResponse,
  StaminaCommandRetentionResponse,
  StaminaSlice18Result,
  StaminaSeasonSummariesResponse,
  StaminaSlice13Result,
  StaminaSlice13AResult,
  StaminaLeaderboardResponse,
  OptionItem,
  PersonalOverviewResponse,
  PitcherLeaderboardRow,
  PitcherMetricExplorerResponse,
  PitcherOption,
  PitcherPeriodDateRange,
  PitchingOverviewResponse,
  PitchingPitcherResponse,
  PitchQualityLeaderboardResponse,
  PerformanceStateLeaderboardResponse,
  PerformanceStateV2LabResponse,
  PerformanceStatePlayerResponse,
  PerformanceStateShadowResponse,
  PerformanceStateTarget,
  TeamDashboardResponse,
  TeamHittingIntelligenceResponse,
  TeamPayrollResponse,
  TeamPitchVideoResponse,
  TeamTransactionsResponse,
  StuffCalculatorInput,
  StuffCalculatorResponse
} from '~/types/api'

const gameAnalysisRequests = new Map<string, { expiresAt: number; request: Promise<unknown> }>()

function cachedGameAnalysis<T>(key: string, requestFactory: () => Promise<T>): Promise<T> {
  if (import.meta.server) return requestFactory()
  const now = Date.now()
  const cached = gameAnalysisRequests.get(key)
  if (cached && cached.expiresAt > now) return cached.request as Promise<T>
  const request = requestFactory().catch((error) => {
    gameAnalysisRequests.delete(key)
    throw error
  })
  gameAnalysisRequests.set(key, { expiresAt: now + 5 * 60 * 1000, request })
  if (gameAnalysisRequests.size > 120) {
    const oldestKey = gameAnalysisRequests.keys().next().value
    if (oldestKey) gameAnalysisRequests.delete(oldestKey)
  }
  return request
}

export function useApi() {
  const config = useRuntimeConfig()
  const apiBase = config.public.apiBase
  const forwardedHeaders = import.meta.server ? useRequestHeaders(['cookie']) : undefined
  const $fetch = globalThis.$fetch.create({ credentials: 'include', headers: forwardedHeaders })

  return {
    pitchingOverview: (params: { year: number; minimumPitches?: number; minimumInnings?: number }) =>
      $fetch<PitchingOverviewResponse>(`${apiBase}/pitching/overview`, {
        query: {
          year: params.year,
          minimum_pitches: params.minimumPitches || 0,
          minimum_innings: params.minimumInnings || 0,
          _ts: Date.now()
        },
        cache: 'no-store'
      }),
    pitchingPitcher: (params: { year: number; pitcherId: number }) =>
      $fetch<PitchingPitcherResponse>(`${apiBase}/pitching/pitcher`, {
        query: { year: params.year, pitcher_id: params.pitcherId, _ts: Date.now() },
        cache: 'no-store'
      }),
    leverageOverview: (year: number) =>
      $fetch<LeverageOverviewResponse>(`${apiBase}/leverage/overview`, {
        query: { year, _ts: Date.now() },
        cache: 'no-store'
      }),
    leverageCalculator: (input: LeverageScenarioInput) =>
      $fetch<LeverageScenarioResponse>(`${apiBase}/leverage/calculator`, {
        method: 'POST',
        body: input
      }),
    staminaOverview: (year: number) =>
      $fetch<StaminaOverviewResponse>(`${apiBase}/stamina/overview`, {
        query: { year, _ts: Date.now() },
        cache: 'no-store'
      }),
    performanceStateLeaderboard: (params: { year: number; role: 'SP' | 'RP'; target: PerformanceStateTarget; minimumForecasts?: number }) =>
      $fetch<PerformanceStateLeaderboardResponse>(`${apiBase}/performance-state/leaderboard`, {
        query: {
          year: params.year,
          role: params.role,
          target: params.target,
          minimum_forecasts: params.minimumForecasts || 1,
          _ts: Date.now()
        },
        cache: 'no-store'
      }),
    performanceStateV2Lab: (params: { year: number; role: 'SP' | 'RP'; target: PerformanceStateTarget; minimumForecasts?: number }) =>
      $fetch<PerformanceStateV2LabResponse>(`${apiBase}/performance-state/v2-lab`, {
        query: {
          year: params.year,
          role: params.role,
          target: params.target,
          minimum_forecasts: params.minimumForecasts || 1,
          _ts: Date.now()
        },
        cache: 'no-store'
      }),
    performanceStatePlayer: (params: { year: number; pitcherId: number; role?: 'SP' | 'RP' }) =>
      $fetch<PerformanceStatePlayerResponse>(`${apiBase}/performance-state/player`, {
        query: {
          year: params.year,
          pitcher_id: params.pitcherId,
          role: params.role,
          _ts: Date.now()
        },
        cache: 'no-store'
      }),
    performanceStateShadow: () =>
      $fetch<PerformanceStateShadowResponse>(`${apiBase}/performance-state/shadow`, {
        query: { _ts: Date.now() },
        cache: 'no-store'
      }),
    staminaResearchCurves: (year: number, pitcherId: number) =>
      $fetch<StaminaResearchCurvesResponse>(`${apiBase}/stamina/research-curves`, {
        query: { year, pitcher_id: pitcherId, _ts: Date.now() },
        cache: 'no-store'
      }),
    staminaGameStates: (year: number, pitcherId: number) =>
      $fetch<StaminaGameStatesResponse>(`${apiBase}/stamina/game-states`, {
        query: { year, pitcher_id: pitcherId, _ts: Date.now() },
        cache: 'no-store'
      }),
    staminaPhysicalStability: (year: number, pitcherId: number) =>
      $fetch<StaminaPhysicalStabilityResponse>(`${apiBase}/stamina/physical-stability`, {
        query: { year, pitcher_id: pitcherId, _ts: Date.now() },
        cache: 'no-store'
      }),
    staminaCommandRetention: (year: number, pitcherId: number) =>
      $fetch<StaminaCommandRetentionResponse>(`${apiBase}/stamina/command-retention`, {
        query: { year, pitcher_id: pitcherId, _ts: Date.now() },
        cache: 'no-store'
      }),
    staminaIncrementalValidation: (year: number) =>
      $fetch<StaminaSlice18Result>(`${apiBase}/stamina/incremental-validation`, {
        query: { year, _ts: Date.now() },
        cache: 'no-store'
      }),
    staminaSeasonSummaries: (year: number) =>
      $fetch<StaminaSeasonSummariesResponse>(`${apiBase}/stamina/season-summaries`, {
        query: { year, _ts: Date.now() },
        cache: 'no-store'
      }),
    staminaExternalValidation: (year: number) =>
      $fetch<StaminaSlice13Result>(`${apiBase}/stamina/external-validation`, {
        query: { year, _ts: Date.now() },
        cache: 'no-store'
      }),
    staminaSeasonBiasRepair: (year: number) =>
      $fetch<StaminaSlice13AResult>(`${apiBase}/stamina/season-bias-repair`, {
        query: { year, _ts: Date.now() },
        cache: 'no-store'
      }),
    staminaLeaderboard: (year: number) =>
      $fetch<StaminaLeaderboardResponse>(`${apiBase}/stamina/leaderboard`, {
        query: { year, _ts: Date.now() },
        cache: 'no-store'
      }),
    homeRecommendations: (year = 2026) =>
      $fetch<HomeRecommendationsResponse>(`${apiBase}/home/recommendations`, { query: { year } }),
    homeVideoSearch: (params: { year: number; query: string; limit?: number }) =>
      $fetch<HomeRecommendationsResponse>(`${apiBase}/home/videos/search`, {
        query: { year: params.year, q: params.query, limit: params.limit || 12 }
      }),
    teamDashboard: (params: { year: number; teamId: string }) =>
      $fetch<TeamDashboardResponse>(`${apiBase}/teams/${params.teamId}/dashboard`, {
        query: { year: params.year, _ts: Date.now() },
        cache: 'no-store'
      }),
    teamHittingIntelligence: (params: { year: number; teamId: string }) =>
      $fetch<TeamHittingIntelligenceResponse>(`${apiBase}/teams/${params.teamId}/hitting-intelligence`, {
        query: { year: params.year, _ts: Date.now() },
        cache: 'no-store'
      }),
    teamTransactions: (params: { year: number; teamId: string; days?: number; limit?: number; refresh?: boolean }) =>
      $fetch<TeamTransactionsResponse>(`${apiBase}/teams/${params.teamId}/transactions`, {
        query: { year: params.year, days: params.days || 60, limit: params.limit || 40, refresh: params.refresh || undefined }
      }),
    teamPayroll: (params: { year: number; teamId: string }) =>
      $fetch<TeamPayrollResponse>(`${apiBase}/teams/${params.teamId}/payroll`, {
        query: { year: params.year }
      }),
    teamStarterWorkload: (params: { year: number; teamId: string; pitcherId: number; gamePk?: number | null }) =>
      $fetch<AnalysisResponse>(`${apiBase}/teams/${params.teamId}/starter-workload`, {
        query: {
          year: params.year,
          pitcher_id: params.pitcherId,
          game_pk: params.gamePk || undefined
        }
      }),
    teamStarterPitchVideos: (params: { year: number; teamId: string; pitcherId: number; gamePk: number }) =>
      $fetch<TeamPitchVideoResponse>(`${apiBase}/teams/${params.teamId}/starter-pitch-videos`, {
        query: { year: params.year, pitcher_id: params.pitcherId, game_pk: params.gamePk }
      }),
    teamDirectVideo: (playId: string) =>
      $fetch<{ play_id: string; video_url: string | null; direct_video_url: string | null; title: string | null }>(`${apiBase}/teams/media/video-direct`, {
        query: { play_id: playId }
      }),
    pitchers: (params: { year: number; role: string }) =>
      $fetch<PitcherOption[]>(`${apiBase}/pitchers`, {
        query: { year: params.year, role: params.role }
      }),
    pitcherLeaderboard: (params: { year: number; role?: string; team?: string }) =>
      $fetch<PitcherLeaderboardRow[]>(`${apiBase}/pitchers/leaderboard`, {
        query: {
          year: params.year,
          role: params.role || 'All',
          team: params.team || 'All'
        }
      }),
    pitcherMetricExplorer: (year: number) =>
      $fetch<PitcherMetricExplorerResponse>(`${apiBase}/pitchers/metric-explorer`, {
        query: { year, _ts: Date.now() },
        cache: 'no-store'
      }),
    batters: (params: { year: number; team?: string }) =>
      $fetch<BatterOption[]>(`${apiBase}/batters`, {
        query: { year: params.year, team: params.team || 'All', _ts: Date.now() },
        cache: 'no-store'
      }),
    batterLeaderboard: (params: { year: number; team?: string }) =>
      $fetch<BatterLeaderboardRow[]>(`${apiBase}/batters/leaderboard`, {
        query: { year: params.year, team: params.team || 'All' }
      }),
    batterStuffAttack: (params: { year: number; pitchGroup: string; pitchTypes?: string[]; pitcherHand?: 'All' | 'L' | 'R'; stuffBin: string; minimumPitches: number; batterId?: number | null }) =>
      $fetch<StuffAttackResponse>(`${apiBase}/batters/lab/stuff-attack`, {
        query: {
          year: params.year,
          pitch_group: params.pitchGroup,
          pitch_types: params.pitchTypes?.join(','),
          pitcher_hand: params.pitcherHand || 'All',
          stuff_bin: params.stuffBin,
          minimum_pitches: params.minimumPitches,
          batter_id: params.batterId || undefined
        }
      }),
    batterSwingTiming: (params: { year: number; pitchGroup: string; pitchType?: string; pitcherHand?: 'All' | 'L' | 'R'; batterSide?: 'All' | 'L' | 'R'; batterTeam?: string; pitcherTeam?: string; minimumSwings: number; minimumPlateAppearances: number }) =>
      $fetch<SwingTimingResponse>(`${apiBase}/batters/lab/swing-timing`, {
        query: {
          year: params.year,
          pitch_group: params.pitchGroup,
          pitch_type: params.pitchType || 'All',
          pitcher_hand: params.pitcherHand || 'All',
          batter_side: params.batterSide || 'All',
          batter_team: params.batterTeam || 'All',
          pitcher_team: params.pitcherTeam || 'All',
          minimum_swings: params.minimumSwings,
          minimum_plate_appearances: params.minimumPlateAppearances
        }
      }),
    batterSwingTimingPlayer: (params: { year: number; batterId: number; pitchGroup: string; pitchType?: string; pitcherHand?: 'All' | 'L' | 'R'; batterSide?: 'All' | 'L' | 'R'; pitcherTeam?: string }) =>
      $fetch<SwingTimingPlayerDetailResponse>(`${apiBase}/batters/lab/swing-timing/player`, {
        query: {
          year: params.year,
          batter_id: params.batterId,
          pitch_group: params.pitchGroup,
          pitch_type: params.pitchType || 'All',
          pitcher_hand: params.pitcherHand || 'All',
          batter_side: params.batterSide || 'All',
          pitcher_team: params.pitcherTeam || 'All',
          _ts: Date.now()
        },
        cache: 'no-store'
      }),
    batterZoneRates: (params: { year: number; batterId: number; pitcherHand: 'All' | 'L' | 'R' }) =>
      $fetch<BatterZoneRatesResponse>(`${apiBase}/batters/personal/zone-rates`, {
        query: { year: params.year, batter_id: params.batterId, pitcher_hand: params.pitcherHand }
      }),
    batterPersonalOverview: (params: { year: number; batterId: number }) =>
      $fetch<AnalysisResponse>(`${apiBase}/batters/personal/overview`, {
        query: { year: params.year, batter_id: params.batterId, _ts: Date.now() },
        cache: 'no-store'
      }),
    batterPersonalDiscipline: (params: {
      year: number
      batterId: number
      stand?: string
      count?: string
      pitch?: string
      pitchResult?: string
      startDate?: string
      endDate?: string
    }) =>
      $fetch<AnalysisResponse>(`${apiBase}/batters/personal/discipline`, {
        query: {
          year: params.year,
          batter_id: params.batterId,
          stand: params.stand || 'All',
          count: params.count || 'All',
          pitch: params.pitch || 'All',
          pitch_result: params.pitchResult || 'All',
          start_date: params.startDate || undefined,
          end_date: params.endDate || undefined,
          _ts: Date.now()
        },
        cache: 'no-store'
      }),
    catcherOptions: (year: number) =>
      $fetch<OptionItem[]>(`${apiBase}/catchers/options`, { query: { year } }),
    catcherDescriptiveLeaderboard: (params: { year: number; minimumOuts?: number }) =>
      $fetch<CatcherDescriptiveLeaderboardResponse>(`${apiBase}/catchers/descriptive/leaderboard`, {
        query: { year: params.year, minimum_outs: params.minimumOuts || 0, _ts: Date.now() },
        cache: 'no-store'
      }),
    catcherDescriptivePairedDuoLeaderboard: (params: { year: number; minimumOuts?: number }) =>
      $fetch<CatcherDescriptivePairedDuoResponse>(`${apiBase}/catchers/descriptive/pairs/leaderboard`, {
        query: { year: params.year, minimum_outs: params.minimumOuts ?? 120, _ts: Date.now() },
        cache: 'no-store'
      }),
    catcherDescriptiveDetail: (params: { year: number; catcherId: number }) =>
      $fetch<CatcherDescriptiveDetailResponse>(`${apiBase}/catchers/descriptive/${params.catcherId}`, {
        query: { year: params.year, _ts: Date.now() },
        cache: 'no-store'
      }),
    catcherDescriptiveStrategyBridge: (params: { year: number; catcherId: number }) =>
      $fetch<CatcherStrategyBridgeResponse>(`${apiBase}/catchers/descriptive/${params.catcherId}/strategy-bridge`, {
        query: { year: params.year, _ts: Date.now() },
        cache: 'no-store'
      }),
    catcherPitchers: (params: { year: number; catcherId: string }) =>
      $fetch<OptionItem[]>(`${apiBase}/catchers/pitchers`, {
        query: { year: params.year, catcher_id: params.catcherId }
      }),
    catcherSequence: (params: {
      year: number
      catcherId: string
      pitcherId?: string | number
      startDate?: string
      endDate?: string
      currentPitch?: string
      stand?: string
      count?: string
      pitch?: string
      pitchResult?: string
      conditionCount?: string
      conditionPitch?: string
      detailCount?: string
      followupPitch?: string
    }) =>
      $fetch<AnalysisResponse>(`${apiBase}/catchers/sequence`, {
        query: {
          year: params.year,
          catcher_id: params.catcherId,
          pitcher_id: params.pitcherId === 'All' ? undefined : params.pitcherId,
          start_date: params.startDate || undefined,
          end_date: params.endDate || undefined,
          current_pitch: params.currentPitch || 'All',
          stand: params.stand,
          count: params.count,
          pitch: params.pitch,
          pitch_result: params.pitchResult,
          condition_count: params.conditionCount,
          condition_pitch: params.conditionPitch,
          detail_count: params.detailCount,
          followup_pitch: params.followupPitch
        }
      }),
    personalOverview: (params: { year: number; role: string; pitcherId: number }) =>
      $fetch<PersonalOverviewResponse>(`${apiBase}/personal/overview`, {
        query: { year: params.year, role: params.role, pitcher_id: params.pitcherId, _ts: Date.now() },
        cache: 'no-store'
      }),
    personalPitches: (params: { year: number; pitcherId: number; limit?: number }) =>
      $fetch<AnalysisResponse>(`${apiBase}/personal/pitches`, {
        query: { year: params.year, pitcher_id: params.pitcherId, limit: params.limit || 250, _ts: Date.now() },
        cache: 'no-store'
      }),
    personalOutings: (params: { year: number; pitcherId: number }) =>
      $fetch<AnalysisResponse>(`${apiBase}/personal/outings`, {
        query: { year: params.year, pitcher_id: params.pitcherId, _ts: Date.now() },
        cache: 'no-store'
      }),
    personalOutingReport: (params: { year: number; pitcherId: number; gamePk: number }) =>
      $fetch<AnalysisResponse>(`${apiBase}/personal/outing-report`, {
        query: { year: params.year, pitcher_id: params.pitcherId, game_pk: params.gamePk, _ts: Date.now() },
        cache: 'no-store'
      }),
    personalMovement: (params: { year: number; pitcherId: number; stand?: string; count?: string; pitch?: string; pitchResult?: string; inPlayResult?: string; paResult?: string; catcher?: string; includePitchStuff?: boolean }) =>
      $fetch<AnalysisResponse>(`${apiBase}/personal/movement`, {
        query: {
          year: params.year,
          pitcher_id: params.pitcherId,
          stand: params.stand,
          count: params.count,
          pitch: params.pitch,
          pitch_result: params.pitchResult,
          in_play_result: params.inPlayResult,
          pa_result: params.paResult,
          catcher: params.catcher,
          include_pitch_stuff: params.includePitchStuff,
          _ts: Date.now()
        },
        cache: 'no-store'
      }),
    personalDiscipline: (params: { year: number; pitcherId: number; stand?: string; count?: string; pitch?: string; catcher?: string }) =>
      $fetch<AnalysisResponse>(`${apiBase}/personal/discipline`, {
        query: { year: params.year, pitcher_id: params.pitcherId, stand: params.stand, count: params.count, pitch: params.pitch, catcher: params.catcher, _ts: Date.now() },
        cache: 'no-store'
      }),
    personalSequence: (params: { year: number; pitcherId: number; startDate?: string; endDate?: string; currentPitch?: string; stand?: string; count?: string; pitch?: string; pitchResult?: string; catcher?: string; conditionCount?: string; conditionPitch?: string; detailCount?: string; followupPitch?: string }) =>
      $fetch<AnalysisResponse>(`${apiBase}/personal/sequence`, {
        query: {
          year: params.year,
          pitcher_id: params.pitcherId,
          start_date: params.startDate || undefined,
          end_date: params.endDate || undefined,
          current_pitch: params.currentPitch || 'All',
          stand: params.stand,
          count: params.count,
          pitch: params.pitch,
          pitch_result: params.pitchResult,
          catcher: params.catcher,
          condition_count: params.conditionCount,
          condition_pitch: params.conditionPitch,
          detail_count: params.detailCount,
          followup_pitch: params.followupPitch,
          _ts: Date.now()
        },
        cache: 'no-store'
      }),
    personalRotation: (params: { year: number; pitcherId: number; gamePk?: number }) =>
      $fetch<AnalysisResponse>(`${apiBase}/personal/rotation`, {
        query: { year: params.year, pitcher_id: params.pitcherId, game_pk: params.gamePk, _ts: Date.now() },
        cache: 'no-store'
      }),
    personalVideos: (params: { year: number; pitcherId: number; limit?: number }) =>
      $fetch<AnalysisResponse>(`${apiBase}/personal/videos`, {
        query: { year: params.year, pitcher_id: params.pitcherId, limit: params.limit || 100 }
      }),
    personalTiming: (params: { year: number; pitcherId: number }) =>
      $fetch<AnalysisResponse>(`${apiBase}/personal/timing`, {
        query: { year: params.year, pitcher_id: params.pitcherId, _ts: Date.now() },
        cache: 'no-store'
      }),
    stuffLeaderboard: (params: { year: number; role?: string; team?: string; minimumIp?: number }) =>
      $fetch<PitchQualityLeaderboardResponse>(`${apiBase}/stuff/leaderboard`, {
        query: {
          year: params.year,
          role: params.role || 'All',
          team: params.team || 'All',
          minimum_ip: params.minimumIp || 0,
          _ts: Date.now()
        },
        cache: 'no-store'
      }),
    stuffFeatures: (params: { year: number; pitcherId: number; startDate?: string; endDate?: string }) =>
      $fetch<AnalysisResponse>(`${apiBase}/stuff/features`, {
        query: {
          year: params.year,
          pitcher_id: params.pitcherId,
          start_date: params.startDate || undefined,
          end_date: params.endDate || undefined
        }
      }),
    stuffScore: (params: { year: number; pitcherId: number; startDate?: string; endDate?: string; gamePk?: number; modelMode?: 'snapshot' | 'pete' }) =>
      $fetch<AnalysisResponse>(`${apiBase}/stuff/score`, {
        query: {
          year: params.year,
          pitcher_id: params.pitcherId,
          start_date: params.startDate || undefined,
          end_date: params.endDate || undefined,
          game_pk: params.gamePk || undefined,
          model_mode: params.modelMode || 'pete',
          _ts: Date.now()
        },
        cache: 'no-store'
      }),
    stuffCalculator: (body: StuffCalculatorInput) =>
      $fetch<StuffCalculatorResponse>(`${apiBase}/stuff/calculator`, {
        method: 'POST',
        body
      }),
    disciplineLeaderboard: (year: number) =>
      $fetch<AnalysisResponse>(`${apiBase}/discipline/leaderboard`, { query: { year } }),
    locationFeatures: (params: { year: number; pitcherId: number; startDate?: string; endDate?: string }) =>
      $fetch<AnalysisResponse>(`${apiBase}/location/features`, {
        query: {
          year: params.year,
          pitcher_id: params.pitcherId,
          start_date: params.startDate || undefined,
          end_date: params.endDate || undefined
        }
      }),
    locationScore: (params: { year: number; pitcherId: number; startDate?: string; endDate?: string }) =>
      $fetch<AnalysisResponse>(`${apiBase}/location/score`, {
        query: {
          year: params.year,
          pitcher_id: params.pitcherId,
          start_date: params.startDate || undefined,
          end_date: params.endDate || undefined
        }
      }),
    locationHeatmap: (params: { sample: string; pitcherHand: string; batterSide: string; pitchType: string; count: string }) =>
      $fetch<LocationHeatmapResponse>(`${apiBase}/location/heatmap`, {
        query: {
          sample: params.sample,
          pitcher_hand: params.pitcherHand,
          batter_side: params.batterSide,
          pitch_type: params.pitchType,
          count: params.count
        }
      }),
    locationLeaderboard: (params: { year: number; minimumPitches: number }) =>
      $fetch<LocationLeaderboardResponse>(`${apiBase}/location/leaderboard`, {
        query: { year: params.year, minimum_pitches: params.minimumPitches }
      }),
    locationPitcher: (params: { year: number; pitcherId: number; gamePk?: number | null }) =>
      $fetch<LocationPitcherResponse>(`${apiBase}/location/pitcher`, {
        query: { year: params.year, pitcher_id: params.pitcherId, game_pk: params.gamePk || undefined }
      }),
    locationComparison: (params: { year: number; minimumPitches: number }) =>
      $fetch<LocationComparisonResponse>(`${apiBase}/location/comparison`, {
        query: { year: params.year, minimum_pitches: params.minimumPitches }
      }),
    rotationStarter: (params: { year: number; team?: string; minGs?: number; minIpPerGs?: number; playerId?: number; fatigueGamePk?: number | null }) =>
      $fetch<AnalysisResponse>(`${apiBase}/rotation/starter`, {
        query: {
          year: params.year,
          team: params.team,
          min_gs: params.minGs,
          min_ip_per_gs: params.minIpPerGs,
          player_id: params.playerId,
          fatigue_game_pk: params.fatigueGamePk || undefined
        }
      }),
    rotationFatigueLab: (params: { year: number; team?: string; minGs?: number; minIpPerGs?: number; playerId?: number; gamePk?: number | null }) =>
      $fetch<AnalysisResponse>(`${apiBase}/rotation/starter/fatigue-lab`, {
        query: {
          year: params.year,
          team: params.team,
          min_gs: params.minGs,
          min_ip_per_gs: params.minIpPerGs,
          player_id: params.playerId,
          game_pk: params.gamePk || undefined
        }
      }),
    rotationReliever: (params: { year: number; team?: string; minGames?: number; playerId?: number; availabilityDate?: string }) =>
      $fetch<AnalysisResponse>(`${apiBase}/rotation/reliever`, {
        query: {
          year: params.year,
          team: params.team,
          min_games: params.minGames,
          player_id: params.playerId,
          availability_date: params.availabilityDate
        }
      }),
    rotationRelieverFatigueLab: (params: { year: number; team?: string; minGames?: number; playerId?: number; availabilityDate?: string }) =>
      $fetch<AnalysisResponse>(`${apiBase}/rotation/reliever/fatigue-lab`, {
        query: {
          year: params.year,
          team: params.team,
          min_games: params.minGames,
          player_id: params.playerId,
          availability_date: params.availabilityDate
        }
      }),
    comparisonPersonalOptions: (year: number) =>
      $fetch<ComparisonOptionsResponse>(`${apiBase}/comparison/personal/options`, {
        query: { year, _ts: Date.now() },
        cache: 'no-store'
      }),
    comparisonPersonalOverview: (params: {
      year?: number
      leftYear: number
      rightYear: number
      leftPitcherId: number
      rightPitcherId: number
      stand?: string
      count?: string
      pitch?: string
      pitchResult?: string
      inPlayResult?: string
      paResult?: string
    }) =>
      $fetch<ComparisonOverviewResponse>(`${apiBase}/comparison/personal/overview`, {
        query: {
          year: params.year || params.rightYear,
          left_year: params.leftYear,
          right_year: params.rightYear,
          left_pitcher_id: params.leftPitcherId,
          right_pitcher_id: params.rightPitcherId,
          stand: params.stand,
          count: params.count,
          pitch: params.pitch,
          pitch_result: params.pitchResult,
          in_play_result: params.inPlayResult,
          pa_result: params.paResult
        }
      }),
    comparisonPeriodOptions: (year: number) =>
      $fetch<ComparisonOptionsResponse>(`${apiBase}/comparison/period/options`, {
        query: { year, _ts: Date.now() },
        cache: 'no-store'
      }),
    comparisonPeriodDateRange: (params: { year: number; pitcherId: number }) =>
      $fetch<PitcherPeriodDateRange>(`${apiBase}/comparison/period/date-range`, {
        query: { year: params.year, pitcher_id: params.pitcherId, _ts: Date.now() },
        cache: 'no-store'
      }),
    comparisonPeriodOverview: (params: {
      pitcherId: number
      leftYear: number
      rightYear: number
      leftStart: string
      leftEnd: string
      rightStart: string
      rightEnd: string
      stand?: string
      count?: string
      pitch?: string
      pitchResult?: string
      inPlayResult?: string
      paResult?: string
      includePitchStuff?: boolean
    }) =>
      $fetch<ComparisonOverviewResponse>(`${apiBase}/comparison/period/overview`, {
        query: {
          pitcher_id: params.pitcherId,
          left_year: params.leftYear,
          right_year: params.rightYear,
          left_start: params.leftStart,
          left_end: params.leftEnd,
          right_start: params.rightStart,
          right_end: params.rightEnd,
          stand: params.stand,
          count: params.count,
          pitch: params.pitch,
          pitch_result: params.pitchResult,
          in_play_result: params.inPlayResult,
          pa_result: params.paResult,
          include_pitch_stuff: params.includePitchStuff
        }
      }),
    comparisonPeriodSequence: (params: {
      pitcherId: number
      leftYear: number
      rightYear: number
      leftStart: string
      leftEnd: string
      rightStart: string
      rightEnd: string
      stand?: string
      count?: string
      pitch?: string
      pitchResult?: string
    }) =>
      $fetch<{ left: AnalysisResponse; right: AnalysisResponse }>(`${apiBase}/comparison/period/sequence`, {
        query: {
          pitcher_id: params.pitcherId,
          left_year: params.leftYear,
          right_year: params.rightYear,
          left_start: params.leftStart,
          left_end: params.leftEnd,
          right_start: params.rightStart,
          right_end: params.rightEnd,
          stand: params.stand,
          count: params.count,
          pitch: params.pitch,
          pitch_result: params.pitchResult
        }
      }),
    batterPeriodOptions: (year: number) =>
      $fetch<BatterPeriodOptionsResponse>(`${apiBase}/batter-comparison/period/options`, { query: { year } }),
    batterPeriodDateRange: (params: { year: number; batterId: number }) =>
      $fetch<BatterPeriodDateRange>(`${apiBase}/batter-comparison/period/date-range`, {
        query: { year: params.year, batter_id: params.batterId }
      }),
    batterPeriodOverview: (params: {
      batterId: number
      leftYear: number
      rightYear: number
      leftStart: string
      leftEnd: string
      rightStart: string
      rightEnd: string
      batterSide?: string
      pitcherHand?: string
      pitchFamily?: string
      count?: string
      pitch?: string
      pitchResult?: string
      inPlayResult?: string
      paResult?: string
    }) => $fetch<BatterPeriodComparisonResponse>(`${apiBase}/batter-comparison/period/overview`, {
      query: {
        batter_id: params.batterId,
        left_year: params.leftYear,
        right_year: params.rightYear,
        left_start: params.leftStart,
        left_end: params.leftEnd,
        right_start: params.rightStart,
        right_end: params.rightEnd,
        batter_side: params.batterSide,
        pitcher_hand: params.pitcherHand,
        pitch_family: params.pitchFamily,
        count: params.count,
        pitch: params.pitch,
        pitch_result: params.pitchResult,
        in_play_result: params.inPlayResult,
        pa_result: params.paResult,
        _ts: Date.now()
      },
      cache: 'no-store'
    }),
    batterTeamResearch: (params: { year: number; team: string; opponentHand?: string }) =>
      $fetch<BatterTeamResearchResponse>(`${apiBase}/batter-comparison/team-research`, {
        query: { year: params.year, team: params.team, opponent_hand: params.opponentHand || 'All', _ts: Date.now() },
        cache: 'no-store'
      }),
    batterLineupScenarios: (params: { year: number; team: string; opponentHand: 'L' | 'R' }) =>
      $fetch<BatterLineupScenarioResponse>(`${apiBase}/batter-comparison/team-research/lineup-scenarios`, {
        query: { year: params.year, team: params.team, opponent_hand: params.opponentHand, _ts: Date.now() },
        cache: 'no-store'
      }),
    comparisonDirectVideo: (playId: string) =>
      $fetch<{ play_id: string; video_url: string; direct_video_url: string | null; title: string | null }>(`${apiBase}/comparison/video-direct`, {
        query: { play_id: playId }
      }),
    comparisonPitchVideo: (params: { gamePk: number; atBatNumber: number; pitchNumber: number }) =>
      $fetch<{
        game_pk: number
        at_bat_number: number
        pitch_number: number
        play_id: string | null
        video_url: string | null
        direct_video_url: string | null
        title: string | null
      }>(`${apiBase}/comparison/video-pitch`, {
        query: {
          game_pk: params.gamePk,
          at_bat_number: params.atBatNumber,
          pitch_number: params.pitchNumber
        }
      }),
    gamesList: (params: { year: number; date?: string; team?: string; limit?: number }) =>
      $fetch<Record<string, unknown>>(`${apiBase}/games`, {
        query: {
          year: params.year,
          date: params.date || undefined,
          team: params.team || undefined,
          limit: params.limit || 100
        }
      }),
    gamePitching: (params: { year: number; gamePk: number }) =>
      $fetch<Record<string, unknown>>(`${apiBase}/games/${params.gamePk}`, {
        query: { year: params.year }
      }),
    gamePitcherLocation: (params: { year: number; gamePk: number; pitcherId: number; stand?: string; count?: string; pitch?: string; pitchResult?: string; inPlayResult?: string; paResult?: string; catcher?: string }) => {
      const key = `location:${JSON.stringify(params)}`
      return cachedGameAnalysis(key, () => $fetch<AnalysisResponse>(`${apiBase}/games/${params.gamePk}/pitchers/${params.pitcherId}/location`, {
        query: {
          year: params.year,
          stand: params.stand,
          count: params.count,
          pitch: params.pitch,
          pitch_result: params.pitchResult,
          in_play_result: params.inPlayResult,
          pa_result: params.paResult,
          catcher: params.catcher
        }
      }))
    },
    gamePitcherSequence: (params: { year: number; gamePk: number; pitcherId: number; currentPitch?: string; stand?: string; count?: string; pitch?: string; pitchResult?: string; catcher?: string; conditionCount?: string; conditionPitch?: string; detailCount?: string; followupPitch?: string }) => {
      const key = `sequence:${JSON.stringify(params)}`
      return cachedGameAnalysis(key, () => $fetch<AnalysisResponse>(`${apiBase}/games/${params.gamePk}/pitchers/${params.pitcherId}/sequence`, {
        query: {
          year: params.year,
          current_pitch: params.currentPitch || 'All',
          stand: params.stand,
          count: params.count,
          pitch: params.pitch,
          pitch_result: params.pitchResult,
          catcher: params.catcher,
          condition_count: params.conditionCount,
          condition_pitch: params.conditionPitch,
          detail_count: params.detailCount,
          followup_pitch: params.followupPitch
        }
      }))
    },
    gamePitcherShape: (params: { year: number; gamePk: number; pitcherId: number }) => {
      const key = `shape:${JSON.stringify(params)}`
      return cachedGameAnalysis(key, () => $fetch<AnalysisResponse>(`${apiBase}/games/${params.gamePk}/pitchers/${params.pitcherId}/shape`, {
        query: { year: params.year }
      }))
    },
    gamePitcherReplay: (params: { year: number; gamePk: number; pitcherId: number }) => {
      const key = `replay:${JSON.stringify(params)}`
      return cachedGameAnalysis(key, () => $fetch<AnalysisResponse>(`${apiBase}/games/${params.gamePk}/pitchers/${params.pitcherId}/replay`, {
        query: { year: params.year }
      }))
    },
    inGameCountContext: (params:{year:number;pitcherId:number;batterId:number;batterSide:'L'|'R'|'unknown';pitcherHand:'L'|'R'|'unknown';balls:number;strikes:number}) =>
      $fetch<import('~/types/api').InGameCountContext>(`${apiBase}/games/matchup-context`,{query:{year:params.year,pitcher_id:params.pitcherId,batter_id:params.batterId,batter_side:params.batterSide,pitcher_hand:params.pitcherHand,balls:params.balls,strikes:params.strikes}}),
    gamePitcherTags: (params: { year: number; gamePk: number; pitcherId: number; role: 'SP' | 'RP' | string }) => {
      const key = `tags:${JSON.stringify(params)}`
      return cachedGameAnalysis(key, () => $fetch<Record<string, unknown>>(`${apiBase}/games/${params.gamePk}/pitchers/${params.pitcherId}/tags`, {
        query: { year: params.year, role: params.role }
      }))
    },
    adminStatus: (year: number) =>
      $fetch<Record<string, unknown>>(`${apiBase}/admin/status`, { query: { year } }),
    updateDailySettings: (gameUpdatesEnabled: boolean) =>
      $fetch<Record<string, unknown>>(`${apiBase}/admin/daily-update-settings`, {
        method: 'PUT',
        query: { game_updates_enabled: gameUpdatesEnabled }
      }),
    dataFreshness: (year: number) =>
      $fetch<Record<string, unknown>>(`${apiBase}/admin/data-freshness`, { query: { year } }),
    refreshDataFreshness: (year: number) =>
      $fetch<Record<string, unknown>>(`${apiBase}/admin/data-freshness/refresh`, {
        method: 'POST',
        query: { year }
      }),
    projectTracker: () =>
      $fetch<Record<string, unknown>>(`${apiBase}/admin/project-tracker`),
    playerArchetypeSlice3: (params: { year: number; population: 'pitcher' | 'batter'; role?: string }) =>
      $fetch<Record<string, any>>(`${apiBase}/derived/player-archetypes/slice3`, {
        query: { year: params.year, population: params.population, role: params.role || undefined, _ts: Date.now() },
        cache: 'no-store'
      }),
    pitcherDataStatus: (year: number) =>
      $fetch<Record<string, unknown>>(`${apiBase}/admin/pitcher-data-status`, { query: { year } }),
    videoLookupStatus: (year: number) =>
      $fetch<Record<string, unknown>>(`${apiBase}/admin/video-lookup-status`, { query: { year } }),
    refreshPitcherDataJob: (year: number) =>
      $fetch<Record<string, unknown>>(`${apiBase}/admin/jobs/refresh-pitcher-data`, {
        method: 'POST',
        query: { year }
      }),
    backfillVideoLookupJob: (params: { year: number; maxGames?: number; startDate?: string; endDate?: string; batchSize?: number }) =>
      $fetch<Record<string, unknown>>(`${apiBase}/admin/jobs/backfill-video-lookup`, {
        method: 'POST',
        query: {
          year: params.year,
          max_games: params.maxGames,
          start_date: params.startDate,
          end_date: params.endDate,
          batch_size: params.batchSize
        }
      }),
    backfillPitcherGameLinesJob: (params: { year: number; maxGames?: number; startDate?: string; endDate?: string; batchSize?: number }) =>
      $fetch<Record<string, unknown>>(`${apiBase}/admin/jobs/backfill-pitcher-game-lines`, {
        method: 'POST',
        query: {
          year: params.year,
          max_games: params.maxGames,
          start_date: params.startDate,
          end_date: params.endDate,
          batch_size: params.batchSize
        }
      }),
    refreshRosterDataJob: (year: number) =>
      $fetch<Record<string, unknown>>(`${apiBase}/admin/jobs/refresh-roster-data`, {
        method: 'POST',
        query: { year }
      }),
    backfillHistoricalPlusJob: (year: number) =>
      $fetch<Record<string, unknown>>(`${apiBase}/admin/jobs/backfill-historical-plus`, {
        method: 'POST',
        query: { year }
      }),
    historicalPlusStatus: () =>
      $fetch<Record<string, unknown>>(`${apiBase}/admin/jobs/historical-plus-status`),
    buildCatcherDescriptiveLedgerJob: (year: number) =>
      $fetch<Record<string, unknown>>(`${apiBase}/admin/jobs/catcher-descriptive-ledger`, {
        method: 'POST',
        query: { year }
      }),
    catcherDescriptiveLedgerStatus: () =>
      $fetch<Record<string, unknown>>(`${apiBase}/admin/jobs/catcher-descriptive-ledger-status`, {
        query: { _ts: Date.now() },
        cache: 'no-store'
      }),
    adminJob: (jobId: string) =>
      $fetch<Record<string, unknown>>(`${apiBase}/admin/jobs/${jobId}`)
  }
}
