import type { Ctx } from './ctx'
import { D, W, iso, pts, type Pt } from './geometry'
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

/** Бытовка стоит за плитой и не наезжает на неё; её левый задний угол. */
const CABIN_X = -94
const CABIN_Y = 80
const PIPE_R = 4.6

/** Пакет труб на подкладках: торцы с отверстием смотрят на зрителя, сверху блик. */
function drawPipes(parent: Element) {
  const g = el('g', {}, parent)
  for (const y of [162, 184]) isoBox(g, [114, y, 0], [46, 5, 3], '#9b6a43')
  // три слоя по порядку наложения: тела труб, лента поверх них, торцы ближе всего к зрителю
  const bodies = el('g', {}, g)
  const straps = el('g', {}, g)
  const ends = el('g', {}, g)
  ;[4, 3, 2].forEach((count, row) => {
    for (let c = 0; c < count; c++) {
      const x = 121 + c * 10.6 + row * 5.3
      const z = 3 + PIPE_R + row * 8.6
      const back = iso(x, 156, z)
      const front = iso(x, 192, z)
      line(bodies, back, front, '#6f7d88', PIPE_R * 2, { 'stroke-linecap': 'round' })
      line(
        bodies,
        [back[0], back[1] - PIPE_R * 0.55],
        [front[0], front[1] - PIPE_R * 0.55],
        '#b4c0c8',
        1.1,
        { opacity: 0.8 },
      )
      el(
        'circle',
        {
          cx: front[0],
          cy: front[1],
          r: PIPE_R,
          fill: '#8f9da8',
          stroke: '#4f5b64',
          'stroke-width': 0.8,
        },
        ends,
      )
      el('circle', { cx: front[0], cy: front[1], r: PIPE_R * 0.52, fill: '#38434b' }, ends)
    }
  })
  // монтажная лента обхватывает пакет: видны верх и правый бок
  const top = 3 + PIPE_R + 2 * 8.6 + PIPE_R
  for (const y of [166, 180]) {
    el(
      'polyline',
      {
        points: pts([
          iso(116.4, y, 3 + PIPE_R),
          iso(127, y, top),
          iso(147, y, top),
          iso(157.4, y, 3 + PIPE_R),
          iso(157.4, y, 3),
        ]),
        fill: 'none',
        stroke: '#d9a400',
        'stroke-width': 1.4,
        'stroke-linejoin': 'round',
      },
      straps,
    )
  }
}

/** Связка арматуры на подкладках: рифлёные прутки в два слоя, две проволочные скрутки. */
function drawRebar(parent: Element) {
  const g = el('g', {}, parent)
  for (const x of [148, 182]) isoBox(g, [x, 132, 0], [5, 20, 3], '#9b6a43')
  for (let i = 0; i < 10; i++) {
    const layer = Math.floor(i / 5)
    const y = 135 + (i % 5) * 3 + layer * 1.5
    const z = 4.2 + layer * 2.4
    const a = iso(138, y, z)
    const b = iso(198, y, z)
    line(g, a, b, i % 2 ? '#7a4a2e' : '#8f5a37', 1.7, { 'stroke-linecap': 'round' })
    line(g, [a[0], a[1] - 0.5], [b[0], b[1] - 0.5], '#c48a5c', 0.7, {
      'stroke-dasharray': '1 1.6',
      opacity: 0.9,
    })
  }
  for (const x of [156, 188]) line(g, iso(x, 133, 7.6), iso(x, 152, 7.6), '#2f2f2f', 1.1)
}

/** Бытовка за башней и материалы на переднем плане: трубы, арматура, кирпич, бункер. */
export function drawProps({ layers }: Ctx) {
  const cabin = el('g', {}, layers.props)
  const front = CABIN_Y + 34
  isoBox(cabin, [CABIN_X, CABIN_Y, 0], [64, 34, 34], '#e4e1da')
  poly(
    cabin,
    [
      iso(CABIN_X, front, 0),
      iso(CABIN_X + 64, front, 0),
      iso(CABIN_X + 64, front, 5),
      iso(CABIN_X, front, 5),
    ],
    '#bdb8ae',
  )
  for (const dx of [4, 22]) {
    const x = CABIN_X + dx
    poly(
      cabin,
      [iso(x, front, 12), iso(x + 12, front, 12), iso(x + 12, front, 26), iso(x, front, 26)],
      '#8fb0c4',
    )
  }
  poly(
    cabin,
    [
      iso(CABIN_X + 46, front, 3),
      iso(CABIN_X + 58, front, 3),
      iso(CABIN_X + 58, front, 28),
      iso(CABIN_X + 46, front, 28),
    ],
    '#cc3608',
  )
  line(cabin, iso(CABIN_X, CABIN_Y, 34), iso(CABIN_X + 64, CABIN_Y, 34), '#fff', 1, {
    opacity: 0.6,
  })

  // Материалы лежат у камеры: тот же слой глубины, что у рабочих, — они смещаются сильнее площадки.
  drawRebar(layers.front)
  drawPipes(layers.front)
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
