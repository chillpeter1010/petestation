import type Phaser from 'phaser'
import campusImage from '~/assets/ballpark/main-campus-v5.png'
import clubhouseImage from '~/assets/ballpark/clubhouse-v2.png'
import teamOfficeImage from '~/assets/ballpark/team-office-v4.png'

export type BallparkInputSource = 'idle' | 'keyboard' | 'gamepad' | 'touch'
export type BallparkRoom = 'campus' | 'clubhouse' | 'team-office'
export type BallparkPortalTarget = { room?: BallparkRoom; route?: string; action?: 'video' | 'admin' }

type Rect = readonly [number, number, number, number]
type Portal = { label: string; bounds: Rect; target: BallparkPortalTarget }
type SceneData = { image: string; spawn: { x: number; y: number }; obstacles: Rect[]; portals: Portal[] }

const SCENES: Record<BallparkRoom, SceneData> = {
  campus: {
    image: campusImage,
    spawn: { x: 840, y: 820 },
    obstacles: [
      [0, 0, 430, 335], [430, 0, 70, 335], [500, 0, 675, 440], [1175, 0, 135, 445],
      [1300, 0, 80, 335],
      [745, 440, 185, 94], [1340, 0, 332, 340],
      [590, 440, 155, 100], [930, 440, 155, 100], [1085, 400, 90, 115],
      [0, 380, 425, 196], [1420, 370, 252, 206], [0, 600, 555, 230], [1117, 600, 555, 230],
      [555, 580, 215, 260], [982, 580, 205, 260], [775, 755, 52, 101], [910, 755, 62, 101],
      [0, 875, 760, 66], [1000, 875, 672, 66]
    ],
    portals: [
      { label: 'Game', bounds: [790, 535, 100, 40], target: { route: '/games/today' } },
      { label: 'Batting Cages', bounds: [330, 338, 85, 40], target: { route: '/batters' } },
      { label: 'Pitcher Mound', bounds: [1425, 340, 110, 40], target: { route: '/pitchers' } },
      { label: 'Training & Lab', bounds: [165, 576, 140, 40], target: { route: '/lab' } },
      { label: 'Video Room', bounds: [1500, 576, 125, 40], target: { action: 'video' } },
      { label: 'Clubhouse', bounds: [245, 825, 165, 42], target: { room: 'clubhouse' } },
      { label: 'Team Office', bounds: [1335, 825, 165, 42], target: { room: 'team-office' } }
    ]
  },
  clubhouse: {
    image: clubhouseImage,
    spawn: { x: 820, y: 520 },
    obstacles: [
      [0, 0, 1672, 90], [1380, 90, 292, 800], [340, 90, 710, 180], [1100, 90, 255, 180],
      [190, 320, 350, 220], [1100, 320, 225, 175], [300, 580, 260, 180], [620, 610, 300, 95],
      [970, 580, 365, 180], [0, 800, 400, 141], [400, 800, 850, 141]
    ],
    portals: [
      { label: 'Player roster', bounds: [900, 450, 110, 100], target: { route: '/teams' } },
      { label: 'Return to Ballpark', bounds: [700, 740, 190, 55], target: { room: 'campus' } }
    ]
  },
  'team-office': {
    image: teamOfficeImage,
    spawn: { x: 835, y: 520 },
    obstacles: [
      [0, 0, 1672, 120], [0, 120, 120, 675], [1550, 120, 122, 675],
      [240, 395, 250, 100], [215, 580, 290, 125], [1190, 400, 270, 100], [1210, 635, 255, 130],
      [680, 120, 70, 300], [930, 120, 70, 300], [0, 795, 1672, 146]
    ],
    portals: [
      { label: 'Coach Office', bounds: [495, 420, 110, 100], target: { route: '/teams' } },
      { label: 'General Manager Office', bounds: [1070, 420, 110, 100], target: { route: '/teams' } },
      { label: 'Return to Ballpark', bounds: [765, 735, 140, 55], target: { room: 'campus' } }
    ]
  }
}

export interface BallparkRuntimeState {
  status: 'ready' | 'paused'
  x: number
  y: number
  inputSource: BallparkInputSource
  renderer: 'webgl' | 'canvas'
  nearby: string | null
}

export interface BallparkRuntimeOptions {
  parent: HTMLElement
  room: BallparkRoom
  reducedMotion: boolean
  onState: (state: BallparkRuntimeState) => void
  onPortal: (target: BallparkPortalTarget) => void
}

export interface BallparkRuntimeHandle {
  destroy: () => void
  reset: () => void
  interact: () => void
  setTouchVector: (x: number, y: number) => void
}

const WORLD_WIDTH = 1672
const WORLD_HEIGHT = 941
const PLAYER_SPEED = 230

export async function createBallparkGame(options: BallparkRuntimeOptions): Promise<BallparkRuntimeHandle> {
  const module = await import('phaser')
  const PhaserRuntime = module.default
  let touchVector = { x: 0, y: 0 }
  let destroyed = false
  const sceneData = SCENES[options.room]

  class BallparkScene extends PhaserRuntime.Scene {
    private player!: Phaser.Physics.Arcade.Image
    private cursors!: Phaser.Types.Input.Keyboard.CursorKeys
    private keys!: Record<'up' | 'down' | 'left' | 'right', Phaser.Input.Keyboard.Key>
    private interactKeys!: Phaser.Input.Keyboard.Key[]
    private nearbyPortal: Portal | null = null
    private portalTriggered = false
    private lastStateAt = 0

    constructor() {
      super('ballpark-foundation')
    }

    preload() {
      this.load.image('ballpark-background', sceneData.image)
    }

    create() {
      this.physics.world.setBounds(0, 0, WORLD_WIDTH, WORLD_HEIGHT)
      this.cameras.main.setBounds(0, 0, WORLD_WIDTH, WORLD_HEIGHT)
      this.add.image(0, 0, 'ballpark-background').setOrigin(0, 0)

      const playerTexture = this.add.graphics()
      for (const [x, y, width, height, color] of [
        [7, 42, 7, 6, 0x111923], [19, 42, 7, 6, 0x111923],
        [8, 32, 7, 11, 0x263548], [18, 32, 7, 11, 0x263548],
        [4, 19, 24, 15, 0xf3efe3], [4, 26, 24, 4, 0xf39b2d],
        [0, 21, 4, 12, 0xdca875], [28, 21, 4, 12, 0xdca875],
        [7, 8, 18, 14, 0xdca875], [5, 6, 22, 7, 0x111923],
        [3, 9, 26, 4, 0x111923], [13, 7, 6, 3, 0xf39b2d],
        [10, 15, 2, 2, 0x111923], [20, 15, 2, 2, 0x111923]
      ]) {
        playerTexture.fillStyle(color, 1)
        playerTexture.fillRect(x, y, width, height)
      }
      playerTexture.generateTexture('ballpark-player-v0', 32, 48)
      playerTexture.destroy()

      this.player = this.physics.add.image(sceneData.spawn.x, sceneData.spawn.y, 'ballpark-player-v0')
      this.player.setSize(20, 12).setOffset(6, 35)
      this.player.setCollideWorldBounds(true)
      this.player.setDepth(10)

      const obstacles = this.physics.add.staticGroup()
      for (const [x, y, width, height] of sceneData.obstacles) {
        obstacles.add(this.add.rectangle(x + width / 2, y + height / 2, width, height, 0x000000, 0))
      }
      this.physics.add.collider(this.player, obstacles)

      if (!this.input.keyboard) throw new Error('Keyboard input is unavailable')
      this.cursors = this.input.keyboard.createCursorKeys()
      this.keys = this.input.keyboard.addKeys({
        up: PhaserRuntime.Input.Keyboard.KeyCodes.W,
        down: PhaserRuntime.Input.Keyboard.KeyCodes.S,
        left: PhaserRuntime.Input.Keyboard.KeyCodes.A,
        right: PhaserRuntime.Input.Keyboard.KeyCodes.D
      }) as Record<'up' | 'down' | 'left' | 'right', Phaser.Input.Keyboard.Key>
      this.interactKeys = [
        this.input.keyboard.addKey(PhaserRuntime.Input.Keyboard.KeyCodes.E),
        this.input.keyboard.addKey(PhaserRuntime.Input.Keyboard.KeyCodes.ENTER)
      ]

      this.cameras.main.startFollow(this.player, true, options.reducedMotion ? 1 : 0.12, options.reducedMotion ? 1 : 0.12)
      this.events.on('ballpark:reset', this.resetPlayer, this)
      this.events.on('ballpark:interact', this.interact, this)
      this.game.events.on(PhaserRuntime.Core.Events.BLUR, this.handleBlur, this)
      this.game.events.on(PhaserRuntime.Core.Events.FOCUS, this.reportReady, this)
      this.events.once(PhaserRuntime.Scenes.Events.SHUTDOWN, this.cleanupScene, this)
      this.reportState('idle')
    }

    override update(time: number) {
      const keyboard = {
        x: Number(this.cursors.right.isDown || this.keys.right.isDown) - Number(this.cursors.left.isDown || this.keys.left.isDown),
        y: Number(this.cursors.down.isDown || this.keys.down.isDown) - Number(this.cursors.up.isDown || this.keys.up.isDown)
      }
      const pad = this.input.gamepad?.getAll()[0]
      const gamepad = {
        x: Math.abs(pad?.leftStick.x || 0) > 0.18 ? pad?.leftStick.x || 0 : 0,
        y: Math.abs(pad?.leftStick.y || 0) > 0.18 ? pad?.leftStick.y || 0 : 0
      }

      let vector = touchVector
      let source: BallparkInputSource = touchVector.x || touchVector.y ? 'touch' : 'idle'
      if (gamepad.x || gamepad.y) {
        vector = gamepad
        source = 'gamepad'
      }
      if (keyboard.x || keyboard.y) {
        vector = keyboard
        source = 'keyboard'
      }

      const length = Math.hypot(vector.x, vector.y) || 1
      this.player.setVelocity(vector.x / length * PLAYER_SPEED, vector.y / length * PLAYER_SPEED)
      this.nearbyPortal = sceneData.portals.find(({ bounds: [x, y, width, height] }) =>
        this.player.x >= x - 28 && this.player.x <= x + width + 28 &&
        this.player.y + 18 >= y - 28 && this.player.y + 18 <= y + height + 28
      ) || null
      if (this.interactKeys.some(key => PhaserRuntime.Input.Keyboard.JustDown(key))) this.interact()
      if (time - this.lastStateAt >= 200) this.reportState(source)
    }

    private interact() {
      if (!this.nearbyPortal || this.portalTriggered) return
      this.portalTriggered = this.nearbyPortal.target.action !== 'video'
      this.player.setVelocity(0, 0)
      options.onPortal(this.nearbyPortal.target)
    }

    private resetPlayer() {
      this.player.setPosition(sceneData.spawn.x, sceneData.spawn.y)
      this.player.setVelocity(0, 0)
      touchVector = { x: 0, y: 0 }
      this.cameras.main.centerOn(sceneData.spawn.x, sceneData.spawn.y)
      this.portalTriggered = false
      this.reportState('idle')
    }

    private handleBlur() {
      this.player?.setVelocity(0, 0)
      touchVector = { x: 0, y: 0 }
      options.onState({
        status: 'paused',
        x: Math.round(this.player?.x || sceneData.spawn.x),
        y: Math.round(this.player?.y || sceneData.spawn.y),
        inputSource: 'idle',
        renderer: this.game.renderer.type === PhaserRuntime.WEBGL ? 'webgl' : 'canvas',
        nearby: this.nearbyPortal?.label || null
      })
    }

    private reportReady() {
      this.reportState('idle')
    }

    private reportState(inputSource: BallparkInputSource) {
      this.lastStateAt = this.time.now
      options.onState({
        status: 'ready',
        x: Math.round(this.player.x),
        y: Math.round(this.player.y),
        inputSource,
        renderer: this.game.renderer.type === PhaserRuntime.WEBGL ? 'webgl' : 'canvas',
        nearby: this.nearbyPortal?.label || null
      })
    }

    private cleanupScene() {
      this.events.off('ballpark:reset', this.resetPlayer, this)
      this.events.off('ballpark:interact', this.interact, this)
      this.game.events.off(PhaserRuntime.Core.Events.BLUR, this.handleBlur, this)
      this.game.events.off(PhaserRuntime.Core.Events.FOCUS, this.reportReady, this)
      this.player?.setVelocity(0, 0)
    }
  }

  const game = new PhaserRuntime.Game({
    type: PhaserRuntime.AUTO,
    parent: options.parent,
    width: 960,
    height: 540,
    backgroundColor: '#070707',
    transparent: false,
    banner: false,
    render: { antialias: false, roundPixels: true, pixelArt: true },
    scale: {
      mode: PhaserRuntime.Scale.FIT,
      autoCenter: PhaserRuntime.Scale.CENTER_BOTH,
      width: 960,
      height: 540
    },
    fps: { target: 60 },
    physics: {
      default: 'arcade',
      arcade: { gravity: { x: 0, y: 0 }, fixedStep: true, fps: 60, debug: false }
    },
    input: { gamepad: true },
    scene: BallparkScene
  })

  const resizeObserver = new ResizeObserver(() => {
    if (!destroyed) game.scale.refresh()
  })
  resizeObserver.observe(options.parent)
  const handleVisibility = () => {
    if (document.hidden) touchVector = { x: 0, y: 0 }
  }
  document.addEventListener('visibilitychange', handleVisibility)

  return {
    setTouchVector(x, y) {
      touchVector = { x, y }
    },
    reset() {
      game.scene.getScene('ballpark-foundation')?.events.emit('ballpark:reset')
    },
    interact() {
      game.scene.getScene('ballpark-foundation')?.events.emit('ballpark:interact')
    },
    destroy() {
      if (destroyed) return
      destroyed = true
      touchVector = { x: 0, y: 0 }
      resizeObserver.disconnect()
      document.removeEventListener('visibilitychange', handleVisibility)
      game.destroy(true)
      options.parent.replaceChildren()
    }
  }
}
