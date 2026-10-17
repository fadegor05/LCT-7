import type { Ctx } from './ctx'
import { ANEMOMETER_Y, drawCrane, drawRig } from './craneArt'
import {
  GAP,
  HOOK_OFFSET,
  MAST,
  PALLET_DX,
  PITCH,
  H,
  SHADOW_X,
  SHADOW_Y,
  TROLLEY_Y,
  diamond,
  hull,
  pts,
  smoothstep,
  type Pt,
} from './geometry'
import { drawGround, drawProps, drawSky, drawWorkers } from './siteArt'
import { el } from './svg'
import { drawTowerBlock } from './towerArt'
import { FADE_SECONDS, HOLD_SECONDS, TOWER_STAGES, buildTimeline, valueAt } from './timeline'

export interface Scene {
  /** Нарисовать сцену в момент `t` (секунды цикла) через `dt` секунд после прошлого кадра. */
  render: (t: number, dt: number) => void
  /** Сбросить инерцию груза и тень (начало нового цикла). */
  reset: () => void
  /** Длина цикла, с. */
  cycle: number
  /** Момент, когда башня собрана целиком, с. */
  end: number
}

/** Затухающие качания груза: маятник, который возбуждает ускорение тележки. */
const SWAY = { drive: 0.035, spring: 4.4, damping: 1.5, limit: 16 }

/** Строит сцену в слоях `ctx` и возвращает функцию отрисовки кадра. */
export function createScene(ctx: Ctx, roofClip: SVGPolygonElement): Scene {
  const timeline = buildTimeline()
  const { layers } = ctx
  const clouds = drawSky(ctx)
  drawGround(ctx)
  drawProps(ctx)
  const crane = drawCrane(ctx)
  const blocks = TOWER_STAGES.map((stage, i) => drawTowerBlock(ctx, stage, i))

  // тени: башня растёт вместе с этажами, груз отбрасывает тень на землю или на кровлю
  const stackShadow = el(
    'polygon',
    { fill: '#141414', opacity: 0, filter: ctx.ref('blur6') },
    layers.gshadow,
  )
  const loadGround = el('polygon', { fill: '#141414', filter: ctx.ref('blur6') }, layers.gshadow)
  const roofShadow = el('g', { 'clip-path': ctx.ref('roofclip') }, layers.blocks)
  const loadRoof = el('polygon', { fill: '#141414', filter: ctx.ref('blur3') }, roofShadow)

  const workers = drawWorkers(ctx)
  const rig = drawRig(ctx)

  let sway = 0
  let swayV = 0
  let prevV = 0
  let prevX = valueAt(timeline.tx, 0)
  let towerShadowZ = 0
  let shadowBefore = -1

  const reset = () => {
    sway = 0
    swayV = 0
    prevV = 0
    prevX = valueAt(timeline.tx, 0)
    towerShadowZ = 0
  }

  const render = (t: number, dt: number) => {
    const { events, end } = timeline
    const fade =
      t > end + HOLD_SECONDS ? Math.max(0, 1 - (t - end - HOLD_SECONDS) / FADE_SECONDS) : 1
    const tx = valueAt(timeline.tx, t)
    const hy = valueAt(timeline.hy, t)
    if (dt > 0) {
      const v = (tx - prevX) / dt
      const a = (v - prevV) / dt
      prevV = v
      prevX = tx
      swayV += (-a * SWAY.drive - SWAY.spring * sway - SWAY.damping * swayV) * dt
      sway = Math.max(-SWAY.limit, Math.min(SWAY.limit, sway)) + swayV * dt
    }
    const hx = tx + sway
    rig.trolley.setAttribute('transform', `translate(${tx.toFixed(1)} 0)`)
    rig.ropes.forEach((rope, k) => {
      const o = k ? 4 : -4
      rope.setAttribute('x1', String(tx + o))
      rope.setAttribute('y1', String(TROLLEY_Y))
      rope.setAttribute('x2', String(hx + o * 0.7))
      rope.setAttribute('y2', String(hy - 22))
    })
    rig.hook.setAttribute('transform', `translate(${hx.toFixed(1)} ${hy.toFixed(1)})`)

    let carried = -1
    let placed = 0
    let live: { i: number; dx: number; dy: number } | null = null
    blocks.forEach((b, i) => {
      const ev = events[i]!
      if (t < ev.appear) {
        b.group.setAttribute('opacity', '0')
        b.chip.setAttribute('opacity', '0')
        return
      }
      let dx = PALLET_DX
      let dy = i * PITCH
      if (t >= ev.release) {
        dx = 0
        dy = 0
        placed++
      } else if (t >= ev.attach) {
        dx = hx - b.topX
        dy = hy + HOOK_OFFSET - b.topY
        carried = i
      }
      if (t < ev.release) live = { i, dx, dy }
      b.group.setAttribute('transform', `translate(${dx.toFixed(1)} ${dy.toFixed(1)})`)
      b.group.setAttribute('opacity', String(Math.min(1, (t - ev.appear) / 0.8) * fade))
      const since = t - ev.release
      b.chip.setAttribute('opacity', String((since >= 0 ? Math.min(1, since / 0.9) : 0) * fade))
      // вспышка и пыль в момент посадки
      const flash = since >= 0 && since < 0.7 ? 0.5 * (1 - since / 0.7) : 0
      b.flash.forEach((f) => f.setAttribute('opacity', String(flash)))
      for (const d of b.dust) {
        if (since < 0 || since > 1.4) {
          if (d.on) {
            d.e.setAttribute('opacity', '0')
            d.on = false
          }
          continue
        }
        d.on = true
        const p = since / 1.4
        d.e.setAttribute('cx', (d.from[0] + d.dir * 18 * p).toFixed(1))
        d.e.setAttribute('cy', (d.from[1] - 3 - p * 8).toFixed(1))
        d.e.setAttribute('r', (3 + p * 13).toFixed(1))
        d.e.setAttribute('opacity', (0.55 * (1 - p) * (1 - p) * fade).toFixed(2))
      }
    })

    // тень башни подтягивается к высоте плавно, без скачка при посадке блока
    const target = placed ? (placed - 1) * PITCH + H : 0
    towerShadowZ = dt > 0 ? towerShadowZ + (target - towerShadowZ) * Math.min(1, dt * 4) : target
    const base: Pt[] = diamond(0)
    const shifted = base.map(([x, y]): Pt => [
      x + SHADOW_X * towerShadowZ,
      y + SHADOW_Y * towerShadowZ,
    ])
    stackShadow.setAttribute('points', pts(hull([...base, ...shifted])))
    stackShadow.setAttribute('opacity', (0.27 * fade).toFixed(2))

    // тень груза: на земле или на кровле башни — смотря над чем он сейчас
    const active = live as { i: number; dx: number; dy: number } | null
    if (active && fade > 0) {
      const { i, dx, dy } = active
      const lift = i * PITCH - dy
      const onTower = i > 0 ? smoothstep(150, 40, Math.abs(dx)) : 0
      loadGround.setAttribute('points', pts(diamond(0, dx + SHADOW_X * lift, SHADOW_Y * lift)))
      loadGround.setAttribute(
        'opacity',
        (0.26 * Math.max(0, 1 - lift / 520) * (1 - onTower) * fade).toFixed(3),
      )
      if (i > 0) {
        const roofZ = i * PITCH - GAP
        const above = Math.max(0, -dy) + GAP
        roofClip.setAttribute('points', pts(diamond(roofZ)))
        loadRoof.setAttribute(
          'points',
          pts(diamond(roofZ, dx + SHADOW_X * above, SHADOW_Y * above)),
        )
        loadRoof.setAttribute(
          'opacity',
          (0.34 * Math.max(0, 1 - above / 300) * onTower * fade).toFixed(3),
        )
        if (shadowBefore !== i) {
          layers.blocks.insertBefore(roofShadow, blocks[i]!.group)
          shadowBefore = i
        }
      } else {
        loadRoof.setAttribute('opacity', '0')
      }
    } else {
      loadGround.setAttribute('opacity', '0')
      loadRoof.setAttribute('opacity', '0')
      shadowBefore = -1
    }

    rig.slings.forEach((s, k) => {
      if (carried < 0) {
        s.setAttribute('opacity', '0')
        return
      }
      const corner = blocks[carried]!.corners[k]!
      s.setAttribute('x1', String(hx))
      s.setAttribute('y1', String(hy + 10))
      s.setAttribute('x2', (hx + corner[0]).toFixed(1))
      s.setAttribute('y2', (hy + HOOK_OFFSET + corner[1]).toFixed(1))
      s.setAttribute('opacity', '0.85')
    })

    // жизнь вокруг: облака, огни, анемометр, сигнальщик
    clouds.forEach((c, k) => {
      c.g.setAttribute('transform', `translate(${((c.x + t * (5 + k * 2)) % 1100) - 120} ${c.y})`)
    })
    const blink = Math.sin(t * 4) > 0.2
    crane.beacon.setAttribute('opacity', blink ? '1' : '0.25')
    crane.beaconGlow.setAttribute('opacity', blink ? '0.22' : '0')
    crane.jibLight.setAttribute('opacity', blink ? '0.25' : '1')
    crane.cups.setAttribute('transform', `rotate(${(t * 420) % 360} ${MAST} ${ANEMOMETER_Y})`)
    workers.signaler.arm.setAttribute(
      'transform',
      `translate(5 -28) rotate(${carried >= 0 ? -150 + Math.sin(t * 5) * 22 : -8})`,
    )
    workers.foreman.arm.setAttribute(
      'transform',
      `translate(5 -28) rotate(${-20 + Math.sin(t * 1.6) * 6})`,
    )
  }

  return { render, reset, cycle: timeline.cycle, end: timeline.end }
}
