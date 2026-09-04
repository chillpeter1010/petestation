import type {
  AnalysisResponse,
  BatterLeaderboardRow,
  BatterOption,
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
  OptionItem,
  PersonalOverviewResponse,
  PitcherLeaderboardRow,
  PitcherOption,
  PitchingOverviewResponse,
  PitchingPitcherResponse,
  TeamDashboardResponse,
  TeamHittingIntelligenceResponse,
  TeamPayrollResponse,
  TeamPitchVideoResponse,
  TeamTransactionsResponse,
  StuffCalculatorInput,
  StuffCalculatorResponse
} from '~/types/api'

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
    stuffLeaderboard: (year: number) =>
      $fetch<AnalysisResponse>(`${apiBase}/stuff/leaderboard`, { query: { year } }),
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
      $fetch<ComparisonOptionsResponse>(`${apiBase}/comparison/personal/options`, { query: { year } }),
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
      $fetch<ComparisonOptionsResponse>(`${apiBase}/comparison/period/options`, { query: { year } }),
    comparisonPeriodDateRange: (params: { year: number; pitcherId: number }) =>
      $fetch<{ year: number; pitcher_id: number; start_date: string | null; end_date: string | null; pitches: number }>(`${apiBase}/comparison/period/date-range`, {
        query: { year: params.year, pitcher_id: params.pitcherId }
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
      $fetch<{ year: number; batter_id: number; start_date: string | null; end_date: string | null; pitches: number }>(`${apiBase}/batter-comparison/period/date-range`, {
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
        pitch_result: params.pitchResult
      }
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
    gamesList: (params: { year: number; date?: string; limit?: number }) =>
      $fetch<Record<string, unknown>>(`${apiBase}/games`, {
        query: {
          year: params.year,
          date: params.date || undefined,
          limit: params.limit || 100
        }
      }),
    gamePitching: (params: { year: number; gamePk: number }) =>
      $fetch<Record<string, unknown>>(`${apiBase}/games/${params.gamePk}`, {
        query: { year: params.year }
      }),
    adminStatus: (year: number) =>
      $fetch<Record<string, unknown>>(`${apiBase}/admin/status`, { query: { year } }),
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
    adminJob: (jobId: string) =>
      $fetch<Record<string, unknown>>(`${apiBase}/admin/jobs/${jobId}`)
  }
}
