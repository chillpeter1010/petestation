import type Phaser from 'phaser'
import type { BallparkAvatarV1 } from '~/composables/useAuth'
import { ballparkCharacterColors } from '~/config/ballparkUniform'
import kit from '~/assets/ballpark/characters/character-kit-v1.json'
import detailUrl from '~/assets/ballpark/characters/user-detail-v1.png'
import skinUrl from '~/assets/ballpark/characters/user-skin-v1.png'
import uniformUrl from '~/assets/ballpark/characters/user-uniform-v1.png'
import accentUrl from '~/assets/ballpark/characters/user-accent-v1.png'
import neutralUrl from '~/assets/ballpark/characters/user-preview-v1.png'
import numbersUrl from '~/assets/ballpark/characters/numbers-v1.png'

export const DEFAULT_APPEARANCE: BallparkAvatarV1 = { avatar_version: 1, body_id: 'tone_2', uniform_id: 'neutral_home', palette_id: 'orange', number: null, bats: 'R', throws: 'R' }
const materialUrls = { detail: detailUrl, skin: skinUrl, uniform: uniformUrl, accent: accentUrl }
type Direction = 'north' | 'east' | 'south' | 'west'
const directions = kit.directions as Direction[]
const frameSize = kit.roles.user.frame_size as [number, number]
const tint = (color: string) => Number.parseInt(color.slice(1), 16)

export function loadBallparkCharacterArt(scene: Phaser.Scene) {
  const [frameWidth, frameHeight] = frameSize
  for (const [material, url] of Object.entries(materialUrls)) scene.load.spritesheet(`avatar-${material}`, url, { frameWidth, frameHeight })
  scene.load.spritesheet('avatar-neutral', neutralUrl, { frameWidth, frameHeight })
  scene.load.spritesheet('avatar-numbers', numbersUrl, { frameWidth: 12, frameHeight: 10 })
}

export function createBallparkCharacter(scene: Phaser.Scene, appearance: BallparkAvatarV1, reducedMotion: boolean, favoriteTeam?: string | null) {
  const root = scene.add.container(0, 0).setScale(kit.roles.user.world_height / frameSize[1])
  const custom = Object.keys(materialUrls).every(name => scene.textures.exists(`avatar-${name}`))
  const layers: Partial<Record<keyof typeof materialUrls, Phaser.GameObjects.Sprite>> = {}
  let neutral: Phaser.GameObjects.Sprite | undefined
  let warning: string | undefined
  if (custom) {
    for (const material of Object.keys(materialUrls) as (keyof typeof materialUrls)[]) {
      layers[material] = scene.add.sprite(0, 0, `avatar-${material}`, 24).setOrigin(.5, 1)
      root.add(layers[material]!)
    }
  } else if (scene.textures.exists('avatar-neutral')) {
    neutral = scene.add.sprite(0, 0, 'avatar-neutral', 24).setOrigin(.5, 1)
    root.add(neutral)
    warning = 'Some character layers are unavailable. A neutral character is shown; your saved appearance is retained.'
  } else {
    const silhouette = scene.add.graphics().fillStyle(0x263548).fillRoundedRect(-20, -125, 40, 42, 8).fillRoundedRect(-25, -82, 50, 70, 8)
    root.add(silhouette)
    warning = 'Character artwork is unavailable. A temporary silhouette is shown; your saved appearance is retained.'
  }
  const number = custom && scene.textures.exists('avatar-numbers') ? scene.add.sprite(0, 0, 'avatar-numbers', 0).setOrigin(.5, .5) : undefined
  if (number) root.add(number)
  let saved = appearance, facing: Direction = 'south', action: 'idle' | 'walk' = 'idle', started = 0, current = -1

  function setAppearance(value: BallparkAvatarV1, team = favoriteTeam) {
    favoriteTeam = team
    saved = value || DEFAULT_APPEARANCE
    const colors = ballparkCharacterColors(saved, favoriteTeam)
    layers.skin?.setTint(tint(colors.skin))
    layers.uniform?.setTint(tint(colors.uniform))
    layers.accent?.setTint(tint(colors.accent))
    current = -1
  }

  function animate(x: number, y: number, moving: boolean, time: number) {
    const nextFacing: Direction = x || y ? (Math.abs(x) > Math.abs(y) ? x > 0 ? 'east' : 'west' : y > 0 ? 'south' : 'north') : facing
    const nextAction = moving && !reducedMotion ? 'walk' : 'idle'
    if (nextFacing !== facing || nextAction !== action) { facing = nextFacing; action = nextAction; started = time }
    const clip = kit.clips[action]
    const offset = reducedMotion ? 0 : Math.floor(Math.max(0, time - started) * clip.fps / 1000) % clip.frames
    const frame = directions.indexOf(facing) * 12 + (action === 'walk' ? 4 : 0) + offset
    if (current === frame) return
    current = frame
    for (const sprite of Object.values(layers)) sprite?.setFrame(frame)
    neutral?.setFrame(frame)
    const position = kit.roles.user.number_positions[frame]
    const validNumber = Number.isInteger(saved.number) && saved.number !== null && saved.number >= 0 && saved.number <= 99
    number?.setVisible(Boolean(position && validNumber))
    if (number && position && validNumber) number.setFrame(saved.number!).setPosition(position[0]! - frameSize[0] / 2, position[1]! - frameSize[1])
  }
  setAppearance(appearance)
  animate(0, 0, false, 0)
  return { root, animate, setAppearance, warning }
}
