import assert from 'node:assert/strict'
import fs from 'node:fs'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const ts = require('typescript')
const source = fs.readFileSync(new URL('../components/ballpark/runtime/sceneGeometry.ts', import.meta.url), 'utf8')
const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 } }).outputText
const { canStand, moveOnScene } = await import('data:text/javascript;base64,' + Buffer.from(js).toString('base64'))
const version = process.argv[2] || 'v1'
if (!['v1', 'v2', 'd2-5-v1', 'v3', 'e2-2-v1', 'e2-3-4-v1', 'clubhouse-annex-v1'].includes(version)) throw new Error('Unknown scene-kit version')
const kit = JSON.parse(fs.readFileSync(new URL(`../assets/ballpark/scenes/scene-kit-${version}.json`, import.meta.url), 'utf8'))
const foot = kit.footprint, world = kit.world_size
const failures = [], evidence = []
const check = (ok, message) => { if (!ok) failures.push(message) }
const baseVersion = version === 'd2-5-v1' ? 'v2' : ['e2-2-v1', 'e2-3-4-v1', 'clubhouse-annex-v1'].includes(version) ? 'v3' : null
const base = baseVersion ? JSON.parse(fs.readFileSync(new URL(`../assets/ballpark/scenes/scene-kit-${baseVersion}.json`, import.meta.url), 'utf8')) : kit
const scenes = { ...base.scenes, ...kit.scenes }
for (const [room, additions] of Object.entries(kit.portal_additions || {})) {
  scenes[room] = { ...scenes[room], portals: [...scenes[room].portals, ...additions] }
  for (const portal of additions) {
    check(canStand(...portal.arrival, scenes[room].collision, foot, world), room + ': clear added door arrival')
    check(Boolean(scenes[portal.target.room]), room + ': added door destination exists')
  }
}
check(JSON.stringify(kit.world_size) === JSON.stringify(base.world_size), 'package world size agrees with runtime')
check(JSON.stringify(kit.footprint) === JSON.stringify(base.footprint), 'package footprint agrees with runtime')
for (const [room, overrides] of Object.entries(kit.portal_overrides || {})) {
  for (const [id, target] of Object.entries(overrides)) {
    check(Boolean(scenes[room]?.portals.some(p => p.id === id)), `override source exists: ${room}/${id}`)
    check(Boolean(scenes[target.room]), `override destination exists: ${room}/${id}`)
  }
}
const fence = [{ id: 'thin-wall', polygon: [[50, 0], [52, 0], [52, 100], [50, 100]] }]
assert.equal(canStand(51, 50, fence, foot, world), false)
assert.ok(moveOnScene(25, 50, 150, 0, fence, foot, world).x <= 41)
assert.ok(moveOnScene(40, 20, 20, 50, fence, foot, world).y > 60, 'slide along wall')
for (const [room, scene] of Object.entries(kit.scenes)) {
  const stand = (x, y) => canStand(x, y, scene.collision, foot, world)
  const ids = scene.collision.map(v => v.id).concat(scene.foreground.map(v => 'fg-' + v.id), scene.portals.map(v => 'p-' + v.id))
  check(new Set(ids).size === ids.length, room + ': unique geometry IDs')
  for (const shape of [...scene.collision, ...scene.foreground]) {
    check(shape.polygon.length >= 3 && shape.polygon.every(([x, y]) => x >= 0 && y >= 0 && x <= world[0] && y <= world[1]), room + ': polygon bounds ' + shape.id)
  }
  check(stand(...scene.spawn), room + ': clear spawn')
  if (room === 'clubhouse' && version === 'v2') {
    const direct = moveOnScene(810, 825, 0, -225, scene.collision, foot, world)
    check(Math.abs(direct.y - 600) < .1, 'clubhouse: central corridor must be directly passable from entrance')
  }
  for (const p of scene.checks.walkable) check(stand(...p), room + ': expected clear ' + p)
  for (const p of scene.checks.blocked) check(!stand(...p), room + ': expected blocked ' + p)
  for (const object of scene.objects || []) {
    check(stand(...object.approach), room + ': clear object approach ' + object.id)
    check(object.collision_refs.every(id => scene.collision.some(shape => shape.id === id)), room + ': object collision refs ' + object.id)
    check(object.foreground_refs.every(id => scene.foreground.some(shape => shape.id === id)), room + ': object foreground refs ' + object.id)
  }
  // Six-pixel grid; every edge uses the SAME swept foot solver as runtime.
  const step = 6, key = (x, y) => `${x},${y}`, spawn = scene.spawn.map(v => Math.round(v / step) * step)
  const queue = [spawn], seen = new Set([key(...spawn)]), portals = new Set()
  for (let i = 0; i < queue.length; i++) {
    const [x, y] = queue[i]
    for (const portal of scene.portals) {
      const [a, b, w, h] = portal.bounds
      if (x >= a - 18 && x <= a + w + 18 && y >= b - 12 && y <= b + h + 12) portals.add(portal.id)
    }
    for (const [dx, dy] of [[step, 0], [-step, 0], [0, step], [0, -step]]) {
      const nx = x + dx, ny = y + dy, k = key(nx, ny)
      if (seen.has(k) || nx < 10 || ny < 12 || nx > world[0] - 10 || ny > world[1] - 1) continue
      const next = moveOnScene(x, y, dx, dy, scene.collision, foot, world)
      if (Math.abs(next.x - nx) > .01 || Math.abs(next.y - ny) > .01) continue
      seen.add(k); queue.push([nx, ny])
    }
  }
  for (const portal of scene.portals) {
    check(portals.has(portal.id), room + ': unreachable portal ' + portal.id)
    check(stand(...portal.arrival), room + ': blocked arrival ' + portal.id)
    const target = portal.target
    if (target.room) {
      const destination = scenes[target.room]
      check(Boolean(destination), room + ': destination room exists ' + portal.id)
      check(!target.spawn || Boolean(destination?.portals.some(p => p.id === target.spawn)), room + ': return arrival exists ' + portal.id)
    }
  }
  for (const object of scene.objects || []) {
    check([...seen].some(value => { const [x, y] = value.split(',').map(Number); return Math.hypot(x - object.approach[0], y - object.approach[1]) <= step }), room + ': reachable object approach ' + object.id)
  }
  evidence.push({ room, reachable_portals: [...portals], tested_positions: seen.size, collision_shapes: scene.collision.length, foreground_masks: scene.foreground.length })
}
console.log(JSON.stringify({ status: failures.length ? 'FAIL' : 'PASS', failures, scenes: evidence }, null, 2))
if (failures.length) process.exitCode = 1
