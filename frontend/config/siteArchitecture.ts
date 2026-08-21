export type SiteNode = {
  label: string
  path: string
  status: 'Live' | 'Lab'
}

export type SiteGroup = {
  label: string
  description: string
  nodes: SiteNode[]
}

export type SharedModule = {
  name: string
  layer: 'Frontend' | 'Backend' | 'Data'
  purpose: string
  consumers: string
  source: string
}

export const siteGroups: SiteGroup[] = [
  {
    label: 'Entry & teams',
    description: 'Discovery, search, club context, roster operations and game video.',
    nodes: [
      { label: 'Home', path: '/', status: 'Live' },
      { label: 'Team dashboard', path: '/teams/AZ', status: 'Live' },
      { label: 'Games', path: '/games/today', status: 'Live' },
      { label: 'Data operations', path: '/admin/updates', status: 'Live' }
    ]
  },
  {
    label: 'Pitcher station',
    description: 'Pitcher discovery, personal analysis, outings, comparison and rotation.',
    nodes: [
      { label: 'Pitchers', path: '/pitchers', status: 'Live' },
      { label: 'Pitcher personal', path: '/pitcher-personal', status: 'Live' },
      { label: 'Pitcher comparison', path: '/comparison/personal', status: 'Live' },
      { label: 'Period comparison', path: '/comparison/period', status: 'Live' },
      { label: 'Starter rotation', path: '/rotation/starter', status: 'Live' },
      { label: 'Bullpen', path: '/rotation/reliever', status: 'Live' },
      { label: 'Fatigue lab', path: '/rotation/fatigue-lab', status: 'Lab' }
    ]
  },
  {
    label: 'Model labs',
    description: 'Model inspection, hypothetical scoring and league surfaces.',
    nodes: [
      { label: 'Stuff lab', path: '/lab/stuff', status: 'Lab' },
      { label: 'Stuff calculator', path: '/lab/stuff-calculator', status: 'Lab' },
      { label: 'Location lab', path: '/lab/location', status: 'Lab' }
    ]
  },
  {
    label: 'Batter & fielding',
    description: 'Batter production, swing decisions and catcher sequence analysis.',
    nodes: [
      { label: 'Batter station', path: '/batters', status: 'Live' },
      { label: 'Batter leaderboard', path: '/batters/leaderboard', status: 'Live' },
      { label: 'Batter lab', path: '/batters/lab', status: 'Lab' },
      { label: 'Stuff Attack', path: '/batters/lab/stuff-attack', status: 'Lab' },
      { label: 'Batter personal', path: '/batter-personal', status: 'Live' },
      { label: 'Fielders', path: '/fielders', status: 'Lab' },
      { label: 'Catcher sequence', path: '/fielders/catchers/sequence', status: 'Live' }
    ]
  }
]

export const sharedModules: SharedModule[] = [
  { name: 'MovementChart', layer: 'Frontend', purpose: 'Scatter, average and per-pitch Stuff+ movement views', consumers: 'Personal, comparison, outings', source: 'components/charts/MovementChart.vue' },
  { name: 'Strike-zone charts', layer: 'Frontend', purpose: 'Location scatter, zones and heat surfaces', consumers: 'Personal, comparison, labs', source: 'components/charts/*StrikeZone*' },
  { name: 'Stuff score cache', layer: 'Backend', purpose: 'Precomputed per-pitch Stuff+ lookup', consumers: 'Movement, fatigue, personal, outings', source: 'services/pitch_stuff_cache_service.py' },
  { name: 'Location+ store', layer: 'Data', purpose: 'Per-pitch and aggregated Location+ scores', consumers: 'Location lab, fatigue, outings', source: 'data/derived/location_plus_scores.duckdb' },
  { name: 'Pitch normalization', layer: 'Backend', purpose: 'Canonical pitch names and display labels', consumers: 'All pitcher surfaces', source: 'services/personal_service.py' },
  { name: 'Player imagery', layer: 'Frontend', purpose: 'MLB player headshots with graceful fallback', consumers: 'Personal, teams, rotation', source: 'components/PlayerHeadshot.vue' },
  { name: 'DataTable', layer: 'Frontend', purpose: 'Reusable sortable analysis table', consumers: 'All stations and labs', source: 'components/DataTable.vue' },
  { name: 'Update pipeline', layer: 'Backend', purpose: 'Pitch, video, official lines, roster and model refresh', consumers: 'Data operations', source: 'services/admin_job_service.py' }
]
