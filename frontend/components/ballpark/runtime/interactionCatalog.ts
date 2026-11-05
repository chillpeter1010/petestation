import kit from '~/assets/ballpark/scenes/scene-kit-v4.json'
import { canStand, type Point, type CollisionShape } from './sceneGeometry'

export type Room = keyof typeof kit.scenes
export type PanelKind = 'links' | 'roster' | 'games' | 'pitcher' | 'batter' | 'in-game' | 'videos' | 'dialogue' | 'unavailable'
export type ObjectIntent = { objectId: string; path?: string }
export type Interaction = {
  id: string; room: Room; label: string; kind: PanelKind
  bounds: [number, number, number, number]; approach: Point
  links: { label: string; path: string }[]; message?: string; npc?: boolean; adminOnly?: boolean; pointerOnly?: boolean
}
type Definition = [Room, string, string, PanelKind, [number, number, number, number] | null, Point | null, { label: string; path: string }[], string?]
const link = (label: string, path: string) => ({ label, path })
const definitions: Definition[] = [
  ['campus', 'scoreboard', 'Leaderboard', 'links', [750,45,175,100], [838,160], [link('Leaderboards','/leaderboards')]],
  ['clubhouse', 'player-list', 'PLAYER LIST', 'roster', null, [1070,313], [link('Team dashboard','/teams')]],
  ['clubhouse', 'north-lockers', 'North lockers · player directory', 'roster', [350,160,700,110], [700,310], [link('Team dashboard','/teams')]],
  ['clubhouse', 'south-lockers', 'South lockers · player directory', 'roster', [980,568,360,192], [1100,800], [link('Team dashboard','/teams')]],
  ['team-office', 'coach-rotation', 'Rotation board', 'links', [105,200,175,185], [220,405], [link('Team rotation','/teams'),link('Starter rotation','/rotation/starter')]],
  ['team-office', 'coach-lineup', 'Lineup board', 'links', [280,200,210,185], [390,405], [link('Team lineup','/teams')]],
  ['team-office', 'coach-bullpen', 'Bullpen board', 'links', [490,200,174,185], [600,405], [link('Team bullpen','/teams'),link('Bullpen tools','/rotation/reliever')]],
  ['team-office', 'coach-workspace', 'Coach workspace', 'links', [250,440,236,88], [350,565], [link('Team dashboard','/teams')]],
  ['team-office', 'gm-trades', 'Trades monitor', 'links', [1010,200,175,185], [1100,405], [link('Team transactions','/teams')]],
  ['team-office', 'gm-payroll', 'Payroll monitor', 'links', [1185,200,175,185], [1270,405], [link('Team payroll','/teams')]],
  ['team-office', 'gm-contracts', 'Contracts monitor', 'links', [1360,200,180,185], [1450,405], [link('Team contracts','/teams')]],
  ['team-office', 'gm-workspace', 'General Manager workspace', 'links', [1165,430,276,79], [1300,540], [link('Team dashboard','/teams')]],
  ['team-office', 'admin-frame', 'Per aspera ad astra', 'links', [785,152,104,55], [837,440], [link('Updates','/admin/updates')]],
  ['training-lab', 'lab-directory', 'Lab directory', 'links', null, [1280,590], [link('Lab hub','/lab')]],
  ['training-lab', 'stuff-location', 'Stuff+ / Location+', 'links', null, [1280,610], [link('Stuff lab','/lab/stuff'),link('Location lab','/lab/location')]],
  ['training-lab', 'stamina-performance', 'Stamina / Performance State', 'links', null, [1515,430], [link('Stamina research','/rotation/fatigue-lab')], 'Research tools retain their existing release and data limitations.'],
  ['training-lab', 'comparison-calculator', 'Comparison / calculator', 'links', [1100,618,160,135], [1170,780], [link('Pitcher comparison','/comparison/personal'),link('Stuff calculator','/lab/stuff-calculator')]],
  ['training-lab', 'cross-domain-directory', 'Cross-domain research', 'links', [1260,618,161,135], [1365,780], [link('Research hub','/lab')]],
  ['video-game-room', 'recommended-screen', 'Recommended videos', 'videos', null, [440,327], [link('Home recommendations','/')]],
  ['video-game-room', 'video-library', 'Video library', 'videos', null, [350,460], [link('Home recommendations','/')]],
  ['video-game-room', 'future-minigames', 'Game Room · coming later', 'unavailable', null, null, [], 'Mini-games are not available yet.'],
  ['game-center', 'schedule-board', 'Schedule / scores', 'games', null, [836,470], [link('Game Center','/games/today')]],
  ['game-center', 'game-analysis-console', 'Game analysis', 'games', null, [470,510], [link('Game Center','/games/today')]],
  ['game-center', 'replay-screen', 'In game / pitch video', 'games', null, [1225,520], [link('Game Center','/games/today')]],
  ['batting-cages', 'batter-directory', 'Batter directory', 'batter', null, [225,785], [link('Batters','/batters')]],
  ['batting-cages', 'batter-analysis', 'Batter personal analysis', 'batter', null, [220,470], [link('Batters','/batters')]],
  ['batting-cages', 'batter-comparison', 'Batter comparison', 'links', null, [1460,470], [link('Compare batters','/batters/comparison')]],
  ['batting-cages', 'batter-lab', 'Batter Lab', 'links', null, [1460,785], [link('Batter Lab','/batters/lab')]],
  ['pitcher-mound', 'pitcher-directory', 'Pitcher directory', 'pitcher', null, [225,802], [link('Pitchers','/pitchers')]],
  ['pitcher-mound', 'pitch-analysis', 'Shape / location / spin', 'pitcher', null, [260,495], [link('Pitcher personal','/pitcher-personal')]],
  ['pitcher-mound', 'pitcher-comparison', 'Pitcher comparison', 'links', null, [1450,490], [link('Compare pitchers','/comparison/personal')]],
  ['pitcher-mound', 'pitcher-tools', 'Pitcher tools', 'links', null, [1450,802], [link('Starter tools','/rotation/starter'),link('Bullpen tools','/rotation/reliever')]],
  ['pitcher-mound', 'in-game-west', 'West bullpen · In game', 'in-game', null, [560,760], [link('Pitcher personal','/pitcher-personal')]],
  ['pitcher-mound', 'in-game-east', 'East bullpen · In game', 'in-game', null, [1115,760], [link('Pitcher personal','/pitcher-personal')]],
  ['clubhouse-smoking-area', 'chat-spot-west', 'Courtyard guide · west', 'dialogue', null, [600,600], []],
  ['clubhouse-smoking-area', 'chat-spot-east', 'Courtyard guide · east', 'dialogue', null, [1070,600], []]
]

function geometryBounds(room: Room, id: string): [number, number, number, number] {
  const indexed = kit.object_index.find(o => o.id === `${room}/${id}`)
  if (!indexed) throw new Error(`Unknown Ballpark object: ${room}/${id}`)
  if (indexed.bounds) return indexed.bounds as [number, number, number, number]
  const scene = kit.scenes[room]
  const points: number[][] = []
  for (const ref of indexed.geometry_refs) {
    const [group, key] = ref.split('/')
    if (group === 'collision' || group === 'foreground') {
      const shape = scene[group].find(p => p.id === key)
      if (shape) points.push(...shape.polygon)
    }
  }
  if (!points.length) throw new Error(`Missing interaction bounds: ${indexed.id}`)
  const xs = points.map(p => p[0]!), ys = points.map(p => p[1]!)
  const x = Math.min(...xs), y = Math.min(...ys)
  return [x, y, Math.max(...xs)-x, Math.max(...ys)-y]
}

// Interaction anchors are independent of the accepted collision/background package.
// Resolve a nearby valid foot position; never remove furniture collision to make an action reachable.
function safeApproach(room: Room, desired: Point): Point {
  const valid = (p: Point) => canStand(...p, kit.scenes[room].collision as unknown as CollisionShape[], kit.footprint, kit.world_size)
  if (valid(desired)) return desired
  for (let radius = 8; radius <= 240; radius += 8) {
    for (let i=0; i<24; i++) {
      const p: Point = [Math.round(desired[0]+Math.cos(i*Math.PI/12)*radius), Math.round(desired[1]+Math.sin(i*Math.PI/12)*radius)]
      if (valid(p)) return p
    }
  }
  throw new Error(`No safe interaction approach: ${room}/${desired}`)
}

export const INTERACTIONS: Interaction[] = definitions.map(([room,id,label,kind,authored,approach,links,message]) => {
  const bounds = authored || geometryBounds(room,id)
  const [x,y,w,h] = bounds
  return { id: `${room}/${id}`, room, label, kind, bounds, approach: id==='scoreboard' || id==='admin-frame' ? approach! : safeApproach(room, approach || [x+w/2,y+h+35]), links, message,
    ...(id === 'scoreboard' ? {pointerOnly:true} : {}),
    ...(id === 'admin-frame' ? { adminOnly: true, pointerOnly: true } : {}),
    ...(kind === 'dialogue' ? { npc: true } : {}) }
})

export const ROOM_LABELS: Record<Room,string> = {
  campus:'Campus', clubhouse:'Clubhouse', 'team-office':'Team Office', 'training-lab':'Training & Lab', 'video-game-room':'Video / Game Room',
  'game-center':'Game Center', 'batting-cages':'Batting Cages', 'pitcher-mound':'Pitcher Mound', 'clubhouse-smoking-area':'Smoking area'
}
for (const room of Object.keys(ROOM_LABELS) as Room[]) {
  if (room === 'clubhouse-smoking-area') continue
  const spawn = kit.scenes[room].spawn
  // Campus spawn offset falls behind the west entry-fence foreground (depth 815).
  // Keep the guide in the open plaza; do not raise actors above all scenery.
  const approach = safeApproach(room, room === 'campus' ? [850,745] : [spawn[0]-100,spawn[1]-70])
  INTERACTIONS.push({ id:`${room}/guide`, room, label:`${ROOM_LABELS[room]} guide`, kind:'dialogue', npc:true,
    bounds:[approach[0]-24,approach[1]-100,48,100], approach, links:[] })
}

export function roomInteractions(room: Room, allowAdmin = false) {
  return INTERACTIONS.filter(o => o.room === room && (!o.adminOnly || allowAdmin))
}
export function nearestInteraction(objects: Interaction[], x: number, y: number): Interaction | null {
  return objects.filter(o => !o.pointerOnly && Math.hypot(x-o.approach[0],y-o.approach[1]) <= 78)
    .sort((a,b) => Math.hypot(x-a.approach[0],y-a.approach[1])-Math.hypot(x-b.approach[0],y-b.approach[1]) || a.id.localeCompare(b.id))[0] || null
}
export function createActivationGate() {
  let last = -Infinity
  return (now: number) => { if (!Number.isFinite(now) || now-last < 400) return false; last=now; return true }
}
export function positiveId(value: unknown): number | undefined {
  if (typeof value !== 'string' && typeof value !== 'number') return undefined
  const n=Number(value); return Number.isSafeInteger(n) && n>0 ? n : undefined
}
