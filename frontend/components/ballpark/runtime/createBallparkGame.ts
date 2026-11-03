import type Phaser from 'phaser'
import campusImage from '~/assets/ballpark/main-campus-v5.png'
import clubhouseImage from '~/assets/ballpark/clubhouse-corridor-v2.png'
import teamOfficeImage from '~/assets/ballpark/team-office-clean-v1.png'
import trainingLabImage from '~/assets/ballpark/training-lab-v1.png'
import videoGameRoomImage from '~/assets/ballpark/video-game-room-v1.png'
import kit from '~/assets/ballpark/scenes/scene-kit-v3.json'
import { canStand, moveOnScene, type CollisionShape, type Point } from './sceneGeometry'
import type { BallparkAvatarV1 } from '~/composables/useAuth'
import { createBallparkCharacter, loadBallparkCharacterArt, DEFAULT_APPEARANCE } from './ballparkCharacter'

export type BallparkInputSource = 'idle' | 'keyboard' | 'gamepad' | 'touch'
export type BallparkRoom = 'campus' | 'clubhouse' | 'team-office' | 'training-lab' | 'video-game-room'
export type BallparkPortalTarget = { room?: BallparkRoom; route?: string; action?: 'video' | 'admin'; spawn?: string }
type Portal = { id: string; label: string; bounds: [number, number, number, number]; arrival: Point; target: BallparkPortalTarget }
type Foreground = { id: string; depth_y: number; polygon: Point[] }
type Hotspot = { id: string; bounds: [number, number, number, number]; admin_only?: boolean; target: BallparkPortalTarget }
type SceneData = { image_size: Point; spawn: Point; collision: CollisionShape[]; foreground: Foreground[]; portals: Portal[]; hotspots: Hotspot[]; floor_labels?: { x: number; y: number; text: string }[] }
const SCENES = kit.scenes as unknown as Record<BallparkRoom, SceneData>
const IMAGES: Record<BallparkRoom, string> = { campus: campusImage, clubhouse: clubhouseImage, 'team-office': teamOfficeImage, 'training-lab': trainingLabImage, 'video-game-room': videoGameRoomImage }

export interface BallparkRuntimeState {
  status: 'ready' | 'paused'
  x: number
  y: number
  inputSource: BallparkInputSource
  renderer: 'webgl' | 'canvas'
  nearby: string | null
  characterWarning?: string
}
export interface BallparkRuntimeOptions {
  parent: HTMLElement
  room: BallparkRoom
  arrivalId?: string
  allowAdmin?: boolean
  reducedMotion: boolean
  avatar?: BallparkAvatarV1
  favoriteTeam?: string | null
  onState: (state: BallparkRuntimeState) => void
  onPortal: (target: BallparkPortalTarget) => void
  onError?: (error: Error) => void
}
export interface BallparkRuntimeHandle {
  destroy: () => void
  reset: () => void
  interact: () => void
  setPaused: (paused: boolean) => void
  setTouchVector: (x: number, y: number) => void
  setAppearance: (avatar: BallparkAvatarV1, favoriteTeam?: string | null) => void
}

export async function createBallparkGame(options: BallparkRuntimeOptions): Promise<BallparkRuntimeHandle> {
  const { default: P } = await import('phaser')
  const data = SCENES[options.room]
  const [width, height] = kit.world_size as [number, number]
  const candidateSpawn = data.portals.find(p => p.id === options.arrivalId)?.arrival || data.spawn
  const spawn = canStand(...candidateSpawn, data.collision, kit.footprint, kit.world_size) ? candidateSpawn : data.spawn
  let touch = { x: 0, y: 0 }, destroyed = false, paused = false
  let appearance = options.avatar || DEFAULT_APPEARANCE
  let favoriteTeam = options.favoriteTeam

  class BallparkScene extends P.Scene {
    private player!: Phaser.GameObjects.Container
    private character!: ReturnType<typeof createBallparkCharacter>
    private cursors!: Phaser.Types.Input.Keyboard.CursorKeys
    private keys!: Record<'up' | 'down' | 'left' | 'right', Phaser.Input.Keyboard.Key>
    private enterKeys!: Phaser.Input.Keyboard.Key[]
    private exitKey!: Phaser.Input.Keyboard.Key
    private nearby: Portal | null = null
    private triggered = false
    private lastReport = 0

    constructor() { super('ballpark-foundation') }

    preload() {
      this.load.on(P.Loader.Events.FILE_LOAD_ERROR, (file: Phaser.Loader.File) => { if (file.key === 'background') options.onError?.(new Error('Scene artwork could not load. Use the static map or retry.')) })
      this.load.image('background', IMAGES[options.room])
      loadBallparkCharacterArt(this)
    }

    create() {
      if (!this.textures.exists('background')) { options.onError?.(new Error('Scene artwork is missing. Open the static map to continue.')); return }
      this.cameras.main.setBounds(0, 0, width, height)
      this.add.image(0, 0, 'background').setOrigin(0, 0).setDisplaySize(width, height).setDepth(-10000)
      // One shared texture, independently editable silhouettes and foot-depths.
      for (const layer of data.foreground) {
        const graphics = this.make.graphics({ x: 0, y: 0 })
        graphics.fillStyle(0xffffff).fillPoints(layer.polygon.map(([x, y]) => new P.Math.Vector2(x, y)), true)
        const mask = graphics.createGeometryMask()
        const image = this.add.image(0, 0, 'background').setOrigin(0, 0).setDisplaySize(width, height).setDepth(layer.depth_y).setMask(mask)
        const xs = layer.polygon.map(p => p[0]), ys = layer.polygon.map(p => p[1])
        image.setCrop(Math.min(...xs) * data.image_size[0] / width, Math.min(...ys), (Math.max(...xs) - Math.min(...xs)) * data.image_size[0] / width, Math.max(...ys) - Math.min(...ys))
        this.events.once(P.Scenes.Events.SHUTDOWN, () => { image.clearMask(); mask.destroy(); graphics.destroy() })
      }
      this.character = createBallparkCharacter(this, appearance, options.reducedMotion, favoriteTeam)
      this.player = this.character.root.setPosition(spawn[0], spawn[1]).setDepth(spawn[1])

      for (const hotspot of data.hotspots) {
        if (hotspot.admin_only && !options.allowAdmin) continue
        const [x, y, w, h] = hotspot.bounds
        this.add.zone(x, y, w, h).setOrigin(0, 0).setDepth(10000).setInteractive({ useHandCursor: true })
          .on('pointerdown', () => { if (!paused) options.onPortal(hotspot.target) })
      }
      const exit = data.portals.find(p => p.id === 'return')
      if (exit) {
        const [x, y, w] = exit.bounds
        this.add.text(x + w / 2, y + 4, '▼ BALLPARK · R', { fontFamily: 'monospace', fontSize: '12px', color: '#efab3f', backgroundColor: '#111923' }).setOrigin(.5, 0).setDepth(-1)
      }
      for (const label of data.floor_labels || []) {
        this.add.text(label.x, label.y, label.text, { fontFamily: 'monospace', fontSize: '16px', color: '#ffd088', backgroundColor: '#111923', padding: { x: 5, y: 3 } }).setOrigin(.5, .5).setDepth(-1)
      }
      if (!this.input.keyboard) throw new Error('Keyboard input is unavailable')
      this.cursors = this.input.keyboard.createCursorKeys()
      this.keys = this.input.keyboard.addKeys({ up: P.Input.Keyboard.KeyCodes.W, down: P.Input.Keyboard.KeyCodes.S, left: P.Input.Keyboard.KeyCodes.A, right: P.Input.Keyboard.KeyCodes.D }) as typeof this.keys
      this.enterKeys = [this.input.keyboard.addKey(P.Input.Keyboard.KeyCodes.E), this.input.keyboard.addKey(P.Input.Keyboard.KeyCodes.ENTER)]
      this.exitKey = this.input.keyboard.addKey(P.Input.Keyboard.KeyCodes.R)
      this.cameras.main.setZoom(.8).startFollow(this.player, true, options.reducedMotion ? 1 : .12, options.reducedMotion ? 1 : .12)
      this.events.on('ballpark:reset', this.resetPlayer, this)
      this.events.on('ballpark:interact', this.interact, this)
      this.events.on('ballpark:appearance', this.changeAppearance, this)
      this.game.events.on(P.Core.Events.BLUR, this.clearInput, this)
      this.events.once(P.Scenes.Events.SHUTDOWN, this.cleanup, this)
      this.report('idle')
    }

    override update(time: number, delta: number) {
      if (!this.player) return
      const focused = document.activeElement?.tagName
      if (paused || document.hidden || focused === 'SELECT' || focused === 'INPUT' || focused === 'TEXTAREA') { this.character.animate(0, 0, false, 0); this.clearInput(); return }
      const keyboard = { x: Number(this.cursors.right.isDown || this.keys.right.isDown) - Number(this.cursors.left.isDown || this.keys.left.isDown), y: Number(this.cursors.down.isDown || this.keys.down.isDown) - Number(this.cursors.up.isDown || this.keys.up.isDown) }
      const pad = this.input.gamepad?.getAll()[0]
      const gamepad = { x: Math.abs(pad?.leftStick.x || 0) > .18 ? pad?.leftStick.x || 0 : 0, y: Math.abs(pad?.leftStick.y || 0) > .18 ? pad?.leftStick.y || 0 : 0 }
      let vector = touch, source: BallparkInputSource = touch.x || touch.y ? 'touch' : 'idle'
      if (gamepad.x || gamepad.y) { vector = gamepad; source = 'gamepad' }
      if (keyboard.x || keyboard.y) { vector = keyboard; source = 'keyboard' }
      const length = Math.hypot(vector.x, vector.y) || 1
      const distance = 230 * Math.min(delta, 50) / 1000
      const next = moveOnScene(this.player.x, this.player.y, vector.x / length * distance, vector.y / length * distance, data.collision, kit.footprint, kit.world_size)
      this.character.animate(vector.x, vector.y, Math.hypot(next.x - this.player.x, next.y - this.player.y) > .01, time)
      this.player.setPosition(next.x, next.y).setDepth(next.y)
      this.nearby = data.portals.find(({ bounds: [x, y, w, h] }) => next.x >= x - 18 && next.x <= x + w + 18 && next.y >= y - 12 && next.y <= y + h + 12) || null
      const enterPressed = this.enterKeys.some(key => P.Input.Keyboard.JustDown(key))
      const exitPressed = P.Input.Keyboard.JustDown(this.exitKey)
      const atExit = this.nearby?.id === 'return'
      if ((atExit ? exitPressed : enterPressed) || pad?.buttons[0]?.pressed) this.interact()
      if (time - this.lastReport >= 150) this.report(source)
    }

    private interact() {
      if (paused || !this.nearby || this.triggered) return
      this.triggered = this.nearby.target.action !== 'video'
      options.onPortal(this.nearby.target)
    }
    private resetPlayer() { this.player.setPosition(...spawn).setDepth(spawn[1]); this.clearInput(); this.triggered = false; this.nearby = null; this.report('idle') }
    private changeAppearance(value: BallparkAvatarV1) { this.character.setAppearance(value, favoriteTeam) }
    private clearInput() { touch = { x: 0, y: 0 }; this.input.keyboard?.resetKeys() }
    private report(inputSource: BallparkInputSource) {
      this.lastReport = this.time.now
      options.onState({ status: paused || document.hidden ? 'paused' : 'ready', x: Math.round(this.player.x), y: Math.round(this.player.y), inputSource, renderer: this.game.renderer.type === P.WEBGL ? 'webgl' : 'canvas', nearby: this.nearby?.label || null, characterWarning: this.character.warning })
    }
    private cleanup() {
      this.events.off('ballpark:reset', this.resetPlayer, this)
      this.events.off('ballpark:interact', this.interact, this)
      this.events.off('ballpark:appearance', this.changeAppearance, this)
      this.game.events.off(P.Core.Events.BLUR, this.clearInput, this)
    }
  }
  const game = new P.Game({ type: P.AUTO, parent: options.parent, width: 960, height: 540, backgroundColor: '#070707', banner: false, render: { antialias: false, roundPixels: true, pixelArt: true }, scale: { mode: P.Scale.FIT, autoCenter: P.Scale.CENTER_BOTH, width: 960, height: 540 }, fps: { target: 60 }, input: { gamepad: true }, scene: BallparkScene })
  const observer = new ResizeObserver(() => { if (!destroyed) game.scale.refresh() })
  observer.observe(options.parent)
  const visibility = () => { if (document.hidden) { touch = { x: 0, y: 0 }; game.scene.getScene('ballpark-foundation')?.input.keyboard?.resetKeys() } }
  document.addEventListener('visibilitychange', visibility)
  return {
    setAppearance(value, team) { appearance = value; favoriteTeam = team; game.scene.getScene('ballpark-foundation')?.events.emit('ballpark:appearance', value) },
    setTouchVector(x, y) { touch = { x, y } },
    setPaused(value) { paused = value; touch = { x: 0, y: 0 } },
    reset() { game.scene.getScene('ballpark-foundation')?.events.emit('ballpark:reset') },
    interact() { game.scene.getScene('ballpark-foundation')?.events.emit('ballpark:interact') },
    destroy() { if (destroyed) return; destroyed = true; observer.disconnect(); document.removeEventListener('visibilitychange', visibility); game.destroy(true); options.parent.replaceChildren() }
  }
}
