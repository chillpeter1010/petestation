import type Phaser from 'phaser'
import campusImage from '~/assets/ballpark/main-campus-v5.png'
import clubhouseImage from '~/assets/ballpark/clubhouse-backdoor-v1.png'
import smokingAreaImage from '~/assets/ballpark/clubhouse-smoking-area-v1.png'
import teamOfficeImage from '~/assets/ballpark/team-office-clean-v1.png'
import trainingLabImage from '~/assets/ballpark/training-lab-v1.png'
import videoGameRoomImage from '~/assets/ballpark/video-game-room-v1.png'
import gameCenterImage from '~/assets/ballpark/game-center-v1.png'
import battingCagesImage from '~/assets/ballpark/batting-cages-v1.png'
import pitcherMoundImage from '~/assets/ballpark/pitcher-mound-v2.png'
import kit from '~/assets/ballpark/scenes/scene-kit-v4.json'
import { moveOnScene, type CollisionShape, type Point } from './sceneGeometry'
import type { BallparkAvatarV1 } from '~/composables/useAuth'
import { createBallparkCharacter, loadBallparkCharacterArt, DEFAULT_APPEARANCE } from './ballparkCharacter'
import { createGamepadGate } from './runtimeGuards'
import { roomInteractions, nearestInteraction, createActivationGate, type Interaction, type ObjectIntent } from './interactionCatalog'
import { resolveWorldPosition, type WorldPosition, type Facing } from './worldState'
import { runtimeLifecycle } from './runtimeTelemetry'

export type BallparkInputSource = 'idle' | 'keyboard' | 'gamepad' | 'touch'
export type BallparkRoom = 'campus' | 'clubhouse' | 'team-office' | 'training-lab' | 'video-game-room' | 'game-center' | 'batting-cages' | 'pitcher-mound' | 'clubhouse-smoking-area'
export type BallparkPortalTarget = { room?: BallparkRoom; route?: string; action?: 'video' | 'admin'; spawn?: string }
type Portal = { id: string; label: string; activation_key?: 'C'; bounds: [number, number, number, number]; arrival: Point; target: BallparkPortalTarget }
type Foreground = { id: string; depth_y: number; polygon: Point[] }
type Hotspot = { id: string; bounds: [number, number, number, number]; admin_only?: boolean; target: BallparkPortalTarget }
type SceneData = { image_size: Point; spawn: Point; collision: CollisionShape[]; foreground: Foreground[]; portals: Portal[]; hotspots: Hotspot[]; floor_labels?: { x: number; y: number; text: string }[] }
const SCENES = kit.scenes as unknown as Record<BallparkRoom, SceneData>
const IMAGES: Record<BallparkRoom, string> = { campus: campusImage, clubhouse: clubhouseImage, 'team-office': teamOfficeImage, 'training-lab': trainingLabImage, 'video-game-room': videoGameRoomImage, 'game-center': gameCenterImage, 'batting-cages': battingCagesImage, 'pitcher-mound': pitcherMoundImage, 'clubhouse-smoking-area': smokingAreaImage }

export interface BallparkRuntimeState {
  room: BallparkRoom
  facing: Facing
  status: 'ready' | 'paused'
  x: number
  y: number
  inputSource: BallparkInputSource
  renderer: 'webgl' | 'canvas'
  nearby: string | null
  nearbyObject?: string | null
  characterWarning?: string
  restoreWarning?: string
}
export interface BallparkRuntimeOptions {
  parent: HTMLElement
  signal?: AbortSignal
  room: BallparkRoom
  arrivalId?: string
  savedPosition?: WorldPosition
  allowAdmin?: boolean
  reducedMotion: boolean
  preferCanvas?: boolean
  onFrame?: (active:boolean,moving:boolean) => void
  avatar?: BallparkAvatarV1
  favoriteTeam?: string | null
  onState: (state: BallparkRuntimeState) => void
  onPortal: (target: BallparkPortalTarget) => void
  onObject: (intent: ObjectIntent) => void
  onError?: (error: Error) => void
}
export interface BallparkRuntimeHandle {
  snapshot: () => BallparkRuntimeState | undefined
  destroy: () => void
  reset: () => void
  interact: () => void
  setPaused: (paused: boolean) => void
  setTouchVector: (x: number, y: number) => void
  setAppearance: (avatar: BallparkAvatarV1, favoriteTeam?: string | null) => void
}

export async function createBallparkGame(options: BallparkRuntimeOptions): Promise<BallparkRuntimeHandle> {
  if (options.signal?.aborted) throw new DOMException('Ballpark load cancelled', 'AbortError')
  const { default: P } = await import('phaser')
  if (options.signal?.aborted) throw new DOMException('Ballpark load cancelled', 'AbortError')
  const data = SCENES[options.room]
  const [width, height] = kit.world_size as [number, number]
  const objectApproach = roomInteractions(options.room,options.allowAdmin).find(o=>o.id===options.savedPosition?.objectId)?.approach
  const restored = resolveWorldPosition(options.room,options.savedPosition,options.arrivalId,objectApproach)
  const spawn:Point = [restored.position.x,restored.position.y]
  let touch = { x: 0, y: 0 }, destroyed = false, paused = false, focused = document.hasFocus()
  const gamepadGate = createGamepadGate()
  const objects = roomInteractions(options.room, options.allowAdmin)
  const acceptActivation = createActivationGate()
  const movementBlocked = () => paused || !focused || document.hidden || Boolean(document.activeElement?.closest('input, select, textarea, [contenteditable]:not([contenteditable="false"]), [role="dialog"]'))
  let appearance = options.avatar || DEFAULT_APPEARANCE
  let favoriteTeam = options.favoriteTeam
  const contextLost=()=>{if(!destroyed)options.onError?.(new Error('The graphics context was lost. Retry, choose Canvas, or open Classic UI.'))}

  class BallparkScene extends P.Scene {
    private player!: Phaser.GameObjects.Container
    private character!: ReturnType<typeof createBallparkCharacter>
    private cursors!: Phaser.Types.Input.Keyboard.CursorKeys
    private keys!: Record<'up' | 'down' | 'left' | 'right', Phaser.Input.Keyboard.Key>
    private enterKeys!: Phaser.Input.Keyboard.Key[]
    private exitKey!: Phaser.Input.Keyboard.Key
    private sideDoorKey!: Phaser.Input.Keyboard.Key
    private nearby: Portal | null = null
    private nearbyObject: Interaction | null = null
    private guides: ReturnType<typeof createBallparkCharacter>[] = []
    private prompt!: Phaser.GameObjects.Text
    private triggered = false
    private lastReport = 0

    constructor() { super('ballpark-foundation') }

    preload() {
      this.load.on(P.Loader.Events.FILE_LOAD_ERROR, (file: Phaser.Loader.File) => { if (file.key === 'background') options.onError?.(new Error('Scene artwork could not load. Use the static map or retry.')) })
      this.load.image('background', IMAGES[options.room])
      loadBallparkCharacterArt(this)
    }

    create() {
      if (destroyed) return
      this.game.canvas.addEventListener('webglcontextlost',contextLost)
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
      this.character.setFacing(restored.position.facing)

      this.prompt = this.add.text(0,0,'', { fontFamily:'monospace', fontSize:'20px', fontStyle:'bold', color:'#ffffff', backgroundColor:'#071318', stroke:'#071318', strokeThickness:3, padding:{x:12,y:8} }).setResolution(2).setOrigin(.5,1).setDepth(20000).setVisible(false)
      for (const object of objects) {
        if (object.npc) {
          const guide = createBallparkCharacter(this, { ...DEFAULT_APPEARANCE, palette_id:'teal' }, options.reducedMotion)
          guide.root.setPosition(...object.approach).setDepth(object.approach[1])
          this.guides.push(guide)
          this.add.text(object.approach[0],object.approach[1]-135,'GUIDE · generic', {fontFamily:'monospace',fontSize:'18px',fontStyle:'bold',color:'#e7fbff',backgroundColor:'#071318',stroke:'#071318',strokeThickness:3,padding:{x:10,y:6}}).setResolution(2).setOrigin(.5,1).setDepth(10000)
        }
        const [x,y,w,h]=object.bounds
        const links=object.kind==='links'&&object.links.length>1?object.links.map(l=>l.path):[undefined]
        links.forEach((path,i)=>this.add.zone(x+w*i/links.length,y,w/links.length,h).setOrigin(0,0).setDepth(10001+100000/(w*h)).setInteractive({useHandCursor:true})
          .on('pointerdown',()=>this.activateObject(object,path)))
      }

      for (const hotspot of data.hotspots) {
        if (objects.some(o => (hotspot.id === 'leaderboard' && o.id === 'campus/scoreboard') || o.id === `${options.room}/${hotspot.id}`)) continue
        if (hotspot.admin_only && !options.allowAdmin) continue
        const [x, y, w, h] = hotspot.bounds
        this.add.zone(x, y, w, h).setOrigin(0, 0).setDepth(10000).setInteractive({ useHandCursor: true })
          .on('pointerdown', () => { if (!movementBlocked() && !destroyed) options.onPortal(hotspot.target) })
      }
      const exit = data.portals.find(p => p.id === 'return')
      if (exit) {
        const [x, y, w] = exit.bounds
        this.add.text(x + w / 2, y + 4, options.room === 'clubhouse-smoking-area' ? '▼ CLUBHOUSE · R' : '▼ BALLPARK · R', { fontFamily:'monospace',fontSize:'20px',fontStyle:'bold',color:'#ffd477',backgroundColor:'#071318',stroke:'#071318',strokeThickness:3,padding:{x:10,y:6} }).setResolution(2).setOrigin(.5,0).setDepth(10000)
      }
      for (const label of data.floor_labels || []) {
        this.add.text(label.x,label.y,label.text,{fontFamily:'monospace',fontSize:'22px',fontStyle:'bold',color:'#ffdd91',backgroundColor:'#071318',stroke:'#071318',strokeThickness:3,padding:{x:10,y:6}}).setResolution(2).setOrigin(.5,.5).setDepth(-1)
      }
      if (!this.input.keyboard) throw new Error('Keyboard input is unavailable')
      this.cursors = this.input.keyboard.createCursorKeys()
      this.keys = this.input.keyboard.addKeys({ up: P.Input.Keyboard.KeyCodes.W, down: P.Input.Keyboard.KeyCodes.S, left: P.Input.Keyboard.KeyCodes.A, right: P.Input.Keyboard.KeyCodes.D }) as typeof this.keys
      this.enterKeys = [this.input.keyboard.addKey(P.Input.Keyboard.KeyCodes.E), this.input.keyboard.addKey(P.Input.Keyboard.KeyCodes.ENTER)]
      this.exitKey = this.input.keyboard.addKey(P.Input.Keyboard.KeyCodes.R)
      this.sideDoorKey = this.input.keyboard.addKey(P.Input.Keyboard.KeyCodes.C)
      this.input.keyboard.enabled = !paused
      if (paused) this.input.keyboard.clearCaptures()
      this.cameras.main.setZoom(.8).startFollow(this.player, true, options.reducedMotion ? 1 : .12, options.reducedMotion ? 1 : .12)
      this.events.on('ballpark:reset', this.resetPlayer, this)
      this.events.on('ballpark:interact', this.interact, this)
      this.events.on('ballpark:appearance', this.changeAppearance, this)
      this.game.events.on(P.Core.Events.BLUR, this.loseFocus, this)
      this.game.events.on(P.Core.Events.FOCUS, this.gainFocus, this)
      this.events.once(P.Scenes.Events.SHUTDOWN, this.cleanup, this)
      this.report('idle')
    }

    override update(time: number, delta: number) {
      if (!this.player) return
      if (destroyed) return
      if (movementBlocked()) {
        options.onFrame?.(false,false)
        this.prompt.setVisible(false)
        this.character.animate(0, 0, false, 0); this.clearInput()
        for (const guide of this.guides) guide.animate(0,0,false,0)
        if (time - this.lastReport >= 150) this.report('idle')
        return
      }
      const keyboard = { x: Number(this.cursors.right.isDown || this.keys.right.isDown) - Number(this.cursors.left.isDown || this.keys.left.isDown), y: Number(this.cursors.down.isDown || this.keys.down.isDown) - Number(this.cursors.up.isDown || this.keys.up.isDown) }
      const pad = this.input.gamepad?.getAll()[0]
      const gamepad = gamepadGate.sample(pad?.leftStick.x || 0, pad?.leftStick.y || 0, Boolean(pad?.buttons[0]?.pressed))
      let vector = touch, source: BallparkInputSource = touch.x || touch.y ? 'touch' : 'idle'
      if (gamepad.x || gamepad.y) { vector = gamepad; source = 'gamepad' }
      if (keyboard.x || keyboard.y) { vector = keyboard; source = 'keyboard' }
      const length = Math.hypot(vector.x, vector.y) || 1
      const distance = 230 * Math.min(delta, 50) / 1000
      const next = moveOnScene(this.player.x, this.player.y, vector.x / length * distance, vector.y / length * distance, data.collision, kit.footprint, kit.world_size)
      const moving=Math.hypot(next.x-this.player.x,next.y-this.player.y)>.01
      this.character.animate(vector.x, vector.y, moving, time)
      options.onFrame?.(true,moving)
      this.player.setPosition(next.x, next.y).setDepth(next.y)
      for (const guide of this.guides) guide.animate(0,0,false,time)
      this.nearby = data.portals.find(({ bounds: [x, y, w, h] }) => next.x >= x - 18 && next.x <= x + w + 18 && next.y >= y - 12 && next.y <= y + h + 12) || null
      this.nearbyObject = nearestInteraction(objects,next.x,next.y)
      // Room exits and the C-door always win. Route-only legacy portals share object intents.
      const portalWins = Boolean(this.nearby?.target.room)
      if (portalWins) this.nearbyObject = null
      const label = this.nearbyObject ? `${this.nearbyObject.label} · E / Enter` : this.nearby ? `${this.nearby.label} · ${this.nearby.id === 'return' ? 'R' : this.nearby.activation_key || 'E / Enter'}` : ''
      this.prompt.setText(label).setPosition(next.x,next.y-140).setVisible(Boolean(label))
      const enterPressed = this.enterKeys.some(key => P.Input.Keyboard.JustDown(key))
      const exitPressed = P.Input.Keyboard.JustDown(this.exitKey)
      const sideDoorPressed = P.Input.Keyboard.JustDown(this.sideDoorKey)
      const atExit = this.nearby?.id === 'return'
      if ((atExit ? exitPressed : this.nearby?.activation_key === 'C' ? sideDoorPressed : enterPressed) || gamepad.interact) this.interact()
      if (time - this.lastReport >= 150) this.report(source)
    }

    private interact() {
      if (movementBlocked() || destroyed || this.triggered) return
      if (this.nearbyObject) { this.activateObject(this.nearbyObject); return }
      if (!this.nearby || !acceptActivation(performance.now())) return
      const legacyIds: Record<string,string> = {roster:'clubhouse/player-list',coach:'team-office/coach-workspace',manager:'team-office/gm-workspace',lab:'training-lab/lab-directory',recommendations:'video-game-room/recommended-screen'}
      const legacy = objects.find(o => o.id === legacyIds[this.nearby!.id])
      if (legacy) { options.onObject({objectId:legacy.id}); return }
      this.triggered = Boolean(this.nearby.target.room)
      options.onPortal(this.nearby.target)
    }
    private activateObject(object: Interaction,path?:string) {
      if (movementBlocked() || destroyed || !acceptActivation(performance.now())) return
      options.onObject({ objectId:object.id,path })
    }
    private resetPlayer() { const {position}=resolveWorldPosition(options.room,undefined,options.arrivalId);this.player.setPosition(position.x,position.y).setDepth(position.y);this.character.setFacing('south');this.clearInput();this.triggered=false;this.nearby=null;this.nearbyObject=null;this.report('idle') }
    private changeAppearance(value: BallparkAvatarV1) { this.character.setAppearance(value, favoriteTeam) }
    private clearInput() { touch = { x: 0, y: 0 }; gamepadGate.block(); this.input.keyboard?.resetKeys() }
    private loseFocus() { focused = false; this.clearInput() }
    private gainFocus() { focused = true; this.clearInput() }
    private report(inputSource: BallparkInputSource) {
      this.lastReport = this.time.now
      const state=this.snapshot(inputSource)
      if (!destroyed && state) options.onState(state)
    }
    snapshot(inputSource:BallparkInputSource='idle'):BallparkRuntimeState|undefined {
      if(!this.player)return
      return {room:options.room,facing:this.character.getFacing(),status:movementBlocked()?'paused':'ready',x:this.player.x,y:this.player.y,inputSource,renderer:this.game.renderer.type===P.WEBGL?'webgl':'canvas',nearby:this.nearbyObject?.label||this.nearby?.label||null,nearbyObject:this.nearbyObject?.id||null,characterWarning:this.character.warning,restoreWarning:restored.recovered?'The saved position is no longer walkable. Returned to a safe arrival.':undefined}
    }
    private cleanup() {
      this.events.off('ballpark:reset', this.resetPlayer, this)
      this.events.off('ballpark:interact', this.interact, this)
      this.events.off('ballpark:appearance', this.changeAppearance, this)
      this.game.events.off(P.Core.Events.BLUR, this.loseFocus, this)
      this.game.events.off(P.Core.Events.FOCUS, this.gainFocus, this)
    }
  }
  const game = new P.Game({ type: options.preferCanvas ? P.CANVAS : P.AUTO, parent: options.parent, width: 960, height: 540, backgroundColor: '#070707', banner: false, render: { antialias: false, roundPixels: true, pixelArt: true }, scale: { mode: P.Scale.FIT, autoCenter: P.Scale.CENTER_BOTH, width: 960, height: 540 }, fps: { target: 60 }, input: { gamepad: true }, scene: BallparkScene })
  runtimeLifecycle.created++
  game.events.once(P.Core.Events.DESTROY,()=>{runtimeLifecycle.destroyed++})
  const observer = typeof ResizeObserver === 'undefined' ? undefined : new ResizeObserver(() => { if (!destroyed) game.scale.refresh() })
  observer?.observe(options.parent)
  const clearControls = () => { touch = { x: 0, y: 0 }; gamepadGate.block(); game.scene.getScene('ballpark-foundation')?.input.keyboard?.resetKeys() }
  const visibility = () => { focused = document.hasFocus(); clearControls() }
  document.addEventListener('visibilitychange', visibility)
  function destroy() {
    if (destroyed) return
    destroyed = true
    runtimeLifecycle.destroyRequested++
    clearControls()
    observer?.disconnect()
    document.removeEventListener('visibilitychange', visibility)
    options.signal?.removeEventListener('abort', destroy)
    game.canvas?.removeEventListener('webglcontextlost',contextLost)
    // Phaser destroys on its next frame; never clear a newer mount's canvas.
    if (game.canvas?.parentNode === options.parent) game.canvas.remove()
    game.destroy(true)
  }
  options.signal?.addEventListener('abort', destroy, { once: true })
  return {
    snapshot() { return destroyed ? undefined : (game.scene.getScene('ballpark-foundation') as BallparkScene)?.snapshot() },
    setAppearance(value, team) { appearance = value; favoriteTeam = team; game.scene.getScene('ballpark-foundation')?.events.emit('ballpark:appearance', value) },
    setTouchVector(x, y) { if (!movementBlocked() && !destroyed) touch = { x, y } },
    setPaused(value) {
      if (paused !== value) {
        paused = value; clearControls()
        const keyboard = game.scene.getScene('ballpark-foundation')?.input.keyboard
        if (keyboard) {
          keyboard.enabled = !value
          if (value) keyboard.clearCaptures()
          else keyboard.addCapture(['W','A','S','D','E','R','C','ENTER','UP','DOWN','LEFT','RIGHT','SPACE','SHIFT'])
        }
      }
    },
    reset() { game.scene.getScene('ballpark-foundation')?.events.emit('ballpark:reset') },
    interact() { game.scene.getScene('ballpark-foundation')?.events.emit('ballpark:interact') },
    destroy
  }
}
