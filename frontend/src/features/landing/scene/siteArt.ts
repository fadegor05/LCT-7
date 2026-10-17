import type { Ctx } from './ctx'
import { D, W, iso, type Pt } from './geometry'
import { el, isoBox, line, poly, text } from './svg'

/** Детерминированный генератор: щебень на плите всегда ложится одинаково. */
function mulberry32(seed: number) {
  let a = seed
  return () => {
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export interface Cloud {
  g: SVGGElement
  x: number
  y: number
}

const CLOUD_SPECS: readonly [number, number, number][] = [
  [80, -10, 1],
  [420, 30, 0.8],
  [640, -25, 1.15],
]

/** Облака: разные размеры, дрейфуют по ветру. */
export function drawSky({ layers }: Ctx): Cloud[] {
  return CLOUD_SPECS.map(([x, y, s]) => {
    const g = el('g', { opacity: 0.9 }, layers.sky)
    const puffs: [number, number, number, number][] = [
      [0, 0, 60, 16],
      [34, -10, 40, 16],
      [-30, 4, 34, 11],
      [62, 4, 34, 10],
    ]
    for (const [cx, cy, rx, ry] of puffs) {
      el('ellipse', { cx: cx * s, cy: cy * s, rx: rx * s, ry: ry * s, fill: '#f1f0ed' }, g)
    }
    return { g, x, y }
  })
}

/** Площадка: мягкое пятно земли, бетонная плита-основание со щебнем и разметкой. */
export function drawGround({ layers, ref }: Ctx) {
  const g = layers.ground
  const plate = (pad: number, z: number): Pt[] => [
    iso(-pad, -pad, z),
    iso(W + pad, -pad, z),
    iso(W + pad, D + pad, z),
    iso(-pad, D + pad, z),
  ]
  el('ellipse', { cx: 470, cy: 640, rx: 480, ry: 84, fill: ref('site') }, g)
  poly(g, plate(22, -8), '#c9c6bf')
  poly(g, plate(22, 0), '#dcd9d2')
  poly(
    g,
    [iso(-22, D + 22, 0), iso(W + 22, D + 22, 0), iso(W + 22, D + 22, -8), iso(-22, D + 22, -8)],
    '#bdbab3',
  )
  poly(
    g,
    [iso(W + 22, D + 22, 0), iso(W + 22, -22, 0), iso(W + 22, -22, -8), iso(W + 22, D + 22, -8)],
    '#aeaba4',
  )
  const rnd = mulberry32(7)
  for (let i = 0; i < 46; i++) {
    const [cx, cy] = iso(-18 + rnd() * (W + 36), -18 + rnd() * (D + 36), 0)
    el('circle', { cx, cy, r: 0.8 + rnd() * 1.1, fill: '#b6b2aa', opacity: 0.7 }, g)
  }
  poly(g, plate(8, 0), 'none', {
    stroke: '#fff',
    'stroke-width': 1.2,
    'stroke-dasharray': '6 5',
    opacity: 0.7,
  })
}

/** Бытовка за башней и материалы на переднем плане: трубы, арматура, кирпич, бункер. */
export function drawProps({ layers }: Ctx) {
  const cabin = el('g', {}, layers.props)
  isoBox(cabin, [-78, 96, 0], [64, 34, 34], '#e4e1da')
  poly(cabin, [iso(-78, 130, 0), iso(-14, 130, 0), iso(-14, 130, 5), iso(-78, 130, 5)], '#bdb8ae')
  for (const x of [-74, -56]) {
    poly(
      cabin,
      [iso(x, 130, 12), iso(x + 12, 130, 12), iso(x + 12, 130, 26), iso(x, 130, 26)],
      '#8fb0c4',
    )
  }
  poly(cabin, [iso(-32, 130, 3), iso(-20, 130, 3), iso(-20, 130, 28), iso(-32, 130, 28)], '#cc3608')
  line(cabin, iso(-78, 96, 34), iso(-14, 96, 34), '#fff', 1, { opacity: 0.6 })

  // Материалы лежат у камеры: тот же слой глубины, что у рабочих, — они смещаются сильнее площадки.
  const pipes = el('g', {}, layers.front)
  for (let r = 0; r < 3; r++) {
    for (let c = 0; c < 4 - r; c++) {
      const [cx, cy] = iso(120 + c * 9 + r * 4.5, 168, r * 7)
      el(
        'circle',
        { cx, cy: cy - 5, r: 4.4, fill: '#7c8a95', stroke: '#4f5b64', 'stroke-width': 0.8 },
        pipes,
      )
    }
  }
  // поддон кирпича и бункер для мусора: площадка не обрывается на трубах
  const bricks = el('g', {}, layers.front)
  isoBox(bricks, [95, 225, 0], [46, 26, 5], '#9b7a52')
  isoBox(bricks, [97, 227, 5], [42, 22, 18], '#b5603f')
  for (let k = 1; k < 4; k++)
    line(bricks, iso(97, 249, 5 + k * 4.5), iso(139, 249, 5 + k * 4.5), '#7a3f27', 0.8, {
      opacity: 0.6,
    })
  const skip = el('g', {}, layers.front)
  isoBox(skip, [205, 140, 0], [52, 32, 18], '#c9a227')
  line(skip, iso(205, 172, 18), iso(257, 172, 18), '#fff', 1, { opacity: 0.5 })
  const [bx, by] = iso(154, 150, 0)
  poly(
    pipes,
    [
      [bx - 26, by],
      [bx + 26, by - 12],
      [bx + 26, by - 4],
      [bx - 26, by + 8],
    ],
    '#9b6a43',
  )
  for (let i = 0; i < 5; i++) {
    const [ax, ay] = iso(154 + i * 5, 150, 5)
    line(pipes, [ax - 26, ay + 3], [ax + 26, ay - 9], '#6e4a2d', 1.2)
  }
}

export interface Worker {
  arm: SVGGElement
}

function worker(parent: Element, x: number, y: number, vest: string, hat: string): Worker {
  const g = el('g', { transform: `translate(${x} ${y})` }, parent)
  el('ellipse', { cx: 3, cy: 2, rx: 11, ry: 3, fill: '#141414', opacity: 0.2 }, g)
  el('rect', { x: -4, y: -14, width: 3.4, height: 14, rx: 1.5, fill: '#3b4a63' }, g)
  el('rect', { x: 0.6, y: -14, width: 3.4, height: 14, rx: 1.5, fill: '#334159' }, g)
  el('rect', { x: -6, y: -30, width: 12, height: 17, rx: 3, fill: vest }, g)
  el('rect', { x: -6, y: -24, width: 12, height: 2.4, fill: '#fff', opacity: 0.8 }, g)
  el('circle', { cx: 0, cy: -35, r: 4.6, fill: '#e8c3a0' }, g)
  el('path', { d: 'M-5.4 -36a5.4 5.4 0 0 1 10.8 0z', fill: hat }, g)
  el('rect', { x: -6.6, y: -36.2, width: 13.2, height: 1.8, rx: 0.9, fill: hat }, g)
  const arm = el('g', { transform: 'translate(5 -28)' }, g)
  el('rect', { x: -1.6, y: 0, width: 3.2, height: 12, rx: 1.6, fill: vest }, arm)
  return { arm }
}

/** Сигнальщик у поддона, прораб с планшетом и конусы. */
export function drawWorkers({ layers }: Ctx) {
  const front = layers.front
  const signaler = worker(front, 298, 646, '#ff6a1a', '#ffc400')
  const foreman = worker(front, 612, 648, '#ffc400', '#fff')
  el(
    'rect',
    {
      x: -12,
      y: -24,
      width: 9,
      height: 12,
      rx: 1,
      fill: '#2a2a2a',
      transform: 'translate(612 648) rotate(-12)',
    },
    front,
  )
  for (const [x, y] of [
    [336, 652],
    [356, 656],
    [500, 655],
  ] as const) {
    const g = el('g', { transform: `translate(${x} ${y})` }, front)
    el('ellipse', { cx: 2, cy: 1, rx: 7, ry: 2, fill: '#141414', opacity: 0.2 }, g)
    el('rect', { x: -6, y: -2, width: 12, height: 3, rx: 1, fill: '#262423' }, g)
    el('path', { d: 'M-4.5 -2L-1.6 -17h3.2L4.5 -2z', fill: '#ff6a1a' }, g)
    el('rect', { x: -3.2, y: -11, width: 6.4, height: 2.4, fill: '#fff' }, g)
  }
  return { signaler, foreman }
}

/** Подпись-плашка этапа справа от башни: карточка с полосой статуса. */
export function drawChip(
  { layers, ref }: Ctx,
  anchor: Pt,
  name: string,
  status: string,
  color: string,
  muted: boolean,
) {
  const lx = 634
  const g = el('g', { opacity: 0 }, layers.labels)
  line(g, anchor, [lx, anchor[1]], '#85837f', 1, { 'stroke-dasharray': '3 3' })
  el('circle', { cx: anchor[0], cy: anchor[1], r: 3.2, fill: '#141414' }, g)
  el(
    'rect',
    {
      x: lx,
      y: anchor[1] - 20,
      width: 190,
      height: 40,
      rx: 10,
      fill: '#fff',
      stroke: '#dddcdb',
      filter: ref('chipsh'),
    },
    g,
  )
  el(
    'rect',
    { x: lx, y: anchor[1] - 12, width: 4, height: 24, rx: 2, fill: muted ? '#a8a6a1' : color },
    g,
  )
  text(
    g,
    { x: lx + 16, y: anchor[1] - 3, style: 'font:500 13px var(--font-sans);fill:#141414' },
    name,
  )
  text(
    g,
    {
      x: lx + 16,
      y: anchor[1] + 13,
      style: `font:500 11px var(--font-mono);fill:${muted ? '#5a5a5a' : color}`,
    },
    status,
  )
  return g
}
