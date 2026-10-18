import { HOME_HOOK_Y, HOOK_OFFSET, PALLET_DX, roofCenter } from './geometry'

/** Цвета статусов — зеркало токенов `--status-*` (в SVG их считаем в оттенки, поэтому hex). */
export const STATUS = {
  ahead: '#0a5cad',
  ontrack: '#0b7a63',
  behind: '#c4162a',
  idle: '#cfcdc9',
} as const

export type BlockKind = 'base' | 'slab' | 'frame' | 'glass' | 'roof'

export interface TowerStage {
  name: string
  status: string
  color: string
  kind: BlockKind
}

/** Этапы снизу вверх: каждый блок башни — этап графика, цвет — статус отклонения. */
export const TOWER_STAGES: readonly TowerStage[] = [
  { name: 'Котлован и основание', status: 'опережает на 1 дн.', color: STATUS.ahead, kind: 'base' },
  { name: 'Фундаментная плита', status: 'по плану', color: STATUS.ontrack, kind: 'slab' },
  { name: 'Каркас, этажи 1–3', status: 'по плану', color: STATUS.ontrack, kind: 'frame' },
  { name: 'Каркас, этажи 4–6', status: 'отстаёт на 4 дн.', color: STATUS.behind, kind: 'frame' },
  { name: 'Фасад и остекление', status: 'отстаёт на 2 дн.', color: STATUS.behind, kind: 'glass' },
  { name: 'Кровля', status: 'не начат', color: STATUS.idle, kind: 'roof' },
]

type Ease = 'io' | 'out' | 'lin'

interface Key {
  t: number
  v: number
  e: Ease
}

export interface BlockEvent {
  /** Блок появляется на поддоне. */
  appear: number
  /** Кран подхватил блок. */
  attach: number
  /** Блок встал на башню, крюк отпущен. */
  release: number
}

export interface Timeline {
  tx: Key[]
  hy: Key[]
  events: BlockEvent[]
  /** Конец монтажа, с. */
  end: number
  /** Полный цикл: монтаж, пауза с готовой башней, плавное исчезновение. */
  cycle: number
}

/** Множитель скорости: меньше — кран работает быстрее. */
const SPEED = 0.72
const HOLD = 7
const FADE = 1.4
/** Один блок: подъезд, зацеп, подъём, перевоз, посадка, отпускание — длительность в «секундах сценария». */
const BLOCK_SPAN = 13.4

export const FADE_SECONDS = FADE
export const HOLD_SECONDS = HOLD

const EASE: Record<Ease, (p: number) => number> = {
  io: (p) => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2),
  out: (p) => 1 - Math.pow(1 - p, 3),
  lin: (p) => p,
}

/** Значение траектории (тележки или крюка) в момент `t`. */
export function valueAt(keys: readonly Key[], t: number): number {
  const last = keys[keys.length - 1]!
  if (t >= last.t) return last.v
  let j = 1
  while (keys[j]!.t < t) j++
  const a = keys[j - 1]!
  const b = keys[j]!
  const p = (t - a.t) / Math.max(b.t - a.t, 1e-6)
  return a.v + (b.v - a.v) * EASE[b.e](p)
}

export function buildTimeline(): Timeline {
  const tx: Key[] = [{ t: 0, v: 480, e: 'lin' }]
  const hy: Key[] = [{ t: 0, v: HOME_HOOK_Y, e: 'lin' }]
  const events: BlockEvent[] = []
  const palletX = roofCenter(0)[0] + PALLET_DX
  const pickHy = roofCenter(0)[1] - HOOK_OFFSET
  const s = (v: number) => v * SPEED
  let c = 0
  TOWER_STAGES.forEach((_, i) => {
    const [topX, topY] = roofCenter(i)
    const finalHy = topY - HOOK_OFFSET
    const carryHy = finalHy - 130
    tx.push({ t: c + s(2.8), v: palletX, e: 'io' })
    hy.push({ t: c + s(2.0), v: HOME_HOOK_Y, e: 'lin' }, { t: c + s(4.6), v: pickHy, e: 'io' })
    hy.push({ t: c + s(5.0), v: pickHy, e: 'lin' }, { t: c + s(7.0), v: carryHy, e: 'io' })
    tx.push({ t: c + s(7.0), v: palletX, e: 'lin' }, { t: c + s(10.0), v: topX, e: 'io' })
    hy.push({ t: c + s(10.0), v: carryHy, e: 'lin' }, { t: c + s(13.0), v: finalHy, e: 'out' })
    hy.push({ t: c + s(13.4), v: finalHy, e: 'lin' }, { t: c + s(14.6), v: HOME_HOOK_Y, e: 'io' })
    tx.push({ t: c + s(13.4), v: topX, e: 'lin' })
    events.push({ appear: c, attach: c + s(5.0), release: c + s(13.4) })
    c += s(BLOCK_SPAN)
  })
  const end = c + s(1.2)
  return { tx, hy, events, end, cycle: end + HOLD + FADE }
}
