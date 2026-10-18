import type { Ctx } from './ctx'
import { JIB_Y, MAST } from './geometry'
import { el } from './svg'

const YELLOW = '#f2b705'
const YELLOW_DARK = '#c99600'
const GRAPHITE = '#2b2926'
const MAST_TOP = JIB_Y + 22
const MAST_BOTTOM = 614
const APEX = -46
/** Центр вращения чашек анемометра на вершине оголовка. */
export const ANEMOMETER_Y = APEX - 9

export interface CraneParts {
  beacon: SVGCircleElement
  beaconGlow: SVGCircleElement
  jibLight: SVGCircleElement
  cups: SVGGElement
}

/** Башня K-раскосами, поворотная часть, кабина, стрела с тягами, противовес и огни. */
export function drawCrane({ layers, ref }: Ctx): CraneParts {
  const cr = layers.crane
  const add = <K extends keyof SVGElementTagNameMap>(
    tag: K,
    attrs: Record<string, string | number>,
  ) => el(tag, attrs, cr)
  const outline = { stroke: GRAPHITE, 'stroke-width': 1.2 }

  // башня: графитовая решётка между жёлтыми поясами
  let lattice = ''
  for (let y = MAST_TOP; y < MAST_BOTTOM; y += 34) {
    const y2 = Math.min(y + 34, MAST_BOTTOM)
    const flip = ((y - MAST_TOP) / 34) % 2 === 1
    lattice += `M${MAST - 14} ${flip ? y2 : y}L${MAST + 14} ${flip ? y : y2}M${MAST - 14} ${y}H${MAST + 14}`
  }
  add('path', { d: lattice, stroke: GRAPHITE, 'stroke-width': 1.7, fill: 'none' })
  const legH = MAST_BOTTOM - MAST_TOP
  add('rect', { x: MAST - 17, y: MAST_TOP, width: 6, height: legH, fill: YELLOW, ...outline })
  add('rect', { x: MAST + 11, y: MAST_TOP, width: 6, height: legH, fill: YELLOW_DARK, ...outline })
  add('rect', { x: MAST - 16, y: MAST_TOP, width: 2, height: legH, fill: '#fff', opacity: 0.45 })
  // стыки секций и площадки с ограждением
  for (let y = MAST_TOP + 136; y < MAST_BOTTOM - 60; y += 136) {
    add('rect', {
      x: MAST - 19,
      y: y - 3,
      width: 38,
      height: 6,
      rx: 1,
      fill: YELLOW_DARK,
      ...outline,
    })
    add('rect', { x: MAST - 26, y: y + 3, width: 52, height: 3, fill: GRAPHITE })
    add('path', {
      d: `M${MAST - 26} ${y + 3}v-14M${MAST + 26} ${y + 3}v-14M${MAST - 26} ${y - 11}H${MAST + 26}M${MAST - 26} ${y - 4}H${MAST + 26}`,
      stroke: GRAPHITE,
      'stroke-width': 1.2,
      fill: 'none',
    })
  }
  add('path', {
    d: `M${MAST - 9} ${MAST_TOP + 10}V${MAST_BOTTOM - 8}M${MAST - 4} ${MAST_TOP + 10}V${MAST_BOTTOM - 8}`,
    stroke: '#fff',
    'stroke-width': 0.8,
    opacity: 0.4,
    fill: 'none',
  })

  // основание: раскосы, плиты-балласт, анкерные болты
  add('path', {
    d: `M${MAST - 14} ${MAST_BOTTOM - 30}L${MAST - 44} ${MAST_BOTTOM + 2}M${MAST + 14} ${MAST_BOTTOM - 30}L${MAST + 44} ${MAST_BOTTOM + 2}`,
    stroke: GRAPHITE,
    'stroke-width': 2.2,
    fill: 'none',
  })
  add('rect', {
    x: MAST - 50,
    y: MAST_BOTTOM,
    width: 100,
    height: 20,
    rx: 2,
    fill: '#9d9a94',
    stroke: GRAPHITE,
    'stroke-width': 1.4,
  })
  add('rect', { x: MAST - 50, y: MAST_BOTTOM, width: 100, height: 5, fill: '#c1beb7' })
  add('rect', {
    x: MAST - 44,
    y: MAST_BOTTOM - 8,
    width: 88,
    height: 10,
    rx: 2,
    fill: YELLOW,
    stroke: GRAPHITE,
    'stroke-width': 1.4,
  })
  for (const dx of [-40, -28, 28, 36])
    add('circle', { cx: MAST + dx, cy: MAST_BOTTOM - 3, r: 2, fill: GRAPHITE })
  for (let k = 0; k < 4; k++) {
    add('rect', {
      x: MAST - 48 + k * 25,
      y: MAST_BOTTOM + 8,
      width: 23,
      height: 10,
      fill: 'none',
      stroke: '#7d7a74',
      'stroke-width': 1,
    })
  }

  // поворотная часть и оголовок-пирамида с тягами
  add('rect', { x: MAST - 22, y: JIB_Y + 12, width: 44, height: 12, rx: 2, fill: GRAPHITE })
  add('rect', { x: MAST - 22, y: JIB_Y + 12, width: 44, height: 3, fill: '#fff', opacity: 0.22 })
  add('rect', {
    x: MAST - 24,
    y: JIB_Y + 22,
    width: 48,
    height: 5,
    rx: 1.5,
    fill: YELLOW,
    ...outline,
  })
  add('rect', {
    x: MAST - 17,
    y: JIB_Y - 12,
    width: 34,
    height: 24,
    rx: 3,
    fill: YELLOW,
    stroke: GRAPHITE,
    'stroke-width': 1.4,
  })
  add('rect', {
    x: MAST - 17,
    y: JIB_Y - 12,
    width: 34,
    height: 5,
    rx: 2,
    fill: '#fff',
    opacity: 0.4,
  })
  const pyramid = `M${MAST - 10} ${JIB_Y - 12}L${MAST} ${APEX}L${MAST + 10} ${JIB_Y - 12}`
  add('path', {
    d: pyramid,
    stroke: YELLOW,
    'stroke-width': 4,
    fill: 'none',
    'stroke-linejoin': 'round',
  })
  add('path', { d: pyramid, stroke: GRAPHITE, 'stroke-width': 1, fill: 'none' })
  add('path', {
    d: `M${MAST - 8} ${JIB_Y - 24}H${MAST + 8}M${MAST - 6} ${JIB_Y - 38}H${MAST + 6}M${MAST - 8} ${JIB_Y - 24}L${MAST + 6} ${JIB_Y - 38}M${MAST + 8} ${JIB_Y - 24}L${MAST - 6} ${JIB_Y - 38}`,
    stroke: GRAPHITE,
    'stroke-width': 1.2,
    fill: 'none',
  })

  // стрела: ферма с двумя поясами, раскосами и поручнем
  const jibTop = JIB_Y - 10
  const jibBottom = JIB_Y + 8
  const jibStart = 88
  const jibEnd = MAST - 14
  let jib = ''
  for (let x = jibStart; x < jibEnd; x += 22) {
    jib += `M${x} ${jibTop}L${Math.min(x + 11, jibEnd)} ${jibBottom}L${Math.min(x + 22, jibEnd)} ${jibTop}M${x} ${jibTop}V${jibBottom}`
  }
  add('path', { d: jib, stroke: GRAPHITE, 'stroke-width': 1.3, fill: 'none' })
  add('rect', {
    x: jibStart,
    y: jibTop - 1.5,
    width: jibEnd - jibStart,
    height: 3.6,
    fill: YELLOW,
    ...outline,
  })
  add('rect', {
    x: jibStart,
    y: jibBottom - 1.5,
    width: jibEnd - jibStart,
    height: 3.6,
    fill: YELLOW_DARK,
    ...outline,
  })
  add('path', {
    d: `M${jibStart} ${jibTop - 1.5}L${jibStart - 14} ${jibBottom + 1}L${jibStart} ${jibBottom + 2}`,
    fill: YELLOW,
    ...outline,
  })
  add('rect', { x: jibStart - 4, y: jibBottom + 1, width: 6, height: 7, fill: GRAPHITE })
  add('rect', {
    x: jibStart,
    y: jibTop - 5.5,
    width: jibEnd - jibStart,
    height: 1.2,
    fill: GRAPHITE,
    opacity: 0.7,
  })
  for (let x = jibStart + 6; x < jibEnd; x += 44) {
    add('line', {
      x1: x,
      y1: jibTop - 1.5,
      x2: x,
      y2: jibTop - 5.5,
      stroke: GRAPHITE,
      'stroke-width': 1,
    })
  }

  // противовесная консоль: ферма, лебёдка, бетонные плиты
  const counterEnd = MAST + 50
  let counter = ''
  for (let x = MAST + 14; x < counterEnd; x += 14)
    counter += `M${x} ${jibTop}L${x + 7} ${jibBottom}L${x + 14} ${jibTop}`
  add('path', { d: counter, stroke: GRAPHITE, 'stroke-width': 1.3, fill: 'none' })
  add('rect', {
    x: MAST + 14,
    y: jibTop - 1.5,
    width: counterEnd - MAST - 14,
    height: 3.6,
    fill: YELLOW,
    ...outline,
  })
  add('rect', {
    x: MAST + 14,
    y: jibBottom - 1.5,
    width: counterEnd - MAST - 14,
    height: 3.6,
    fill: YELLOW_DARK,
    ...outline,
  })
  add('rect', {
    x: MAST + 20,
    y: jibTop - 17,
    width: 22,
    height: 15,
    rx: 2,
    fill: YELLOW,
    ...outline,
  })
  for (let k = 0; k < 4; k++) {
    add('line', {
      x1: MAST + 24 + k * 4.5,
      y1: jibTop - 14,
      x2: MAST + 24 + k * 4.5,
      y2: jibTop - 6,
      stroke: GRAPHITE,
      'stroke-width': 1,
    })
    const x = MAST + 18 + k * 8
    add('rect', {
      x,
      y: jibBottom + 3,
      width: 7.4,
      height: 30,
      rx: 1.5,
      fill: k % 2 ? '#8a8781' : '#a29f98',
      ...outline,
    })
    add('line', {
      x1: x + 1.5,
      y1: jibBottom + 8,
      x2: x + 1.5,
      y2: jibBottom + 28,
      stroke: '#fff',
      opacity: 0.35,
      'stroke-width': 1,
    })
  }

  // тяги от оголовка к стреле и контрконсоли
  add('path', {
    d: `M${MAST} ${APEX}L${jibStart + 4} ${jibTop - 1}M${MAST} ${APEX}L${MAST - 210} ${jibTop - 1}M${MAST} ${APEX}L${MAST - 420} ${jibTop - 1}M${MAST} ${APEX}L${counterEnd - 2} ${jibTop - 1}`,
    stroke: GRAPHITE,
    'stroke-width': 1.3,
    fill: 'none',
  })
  for (const px of [MAST - 210, MAST - 420])
    add('circle', { cx: px, cy: jibTop - 1, r: 2.6, fill: YELLOW, ...outline })

  // кабина: корпус, стекло с бликом, дверь, кондиционер
  add('rect', {
    x: MAST - 52,
    y: JIB_Y + 12,
    width: 30,
    height: 34,
    rx: 3,
    fill: YELLOW,
    stroke: GRAPHITE,
    'stroke-width': 1.4,
  })
  add('rect', {
    x: MAST - 52,
    y: JIB_Y + 12,
    width: 30,
    height: 5,
    rx: 2,
    fill: '#fff',
    opacity: 0.4,
  })
  add('rect', {
    x: MAST - 48,
    y: JIB_Y + 20,
    width: 19,
    height: 14,
    rx: 2,
    fill: ref('glass'),
    stroke: GRAPHITE,
    'stroke-width': 1,
  })
  add('path', {
    d: `M${MAST - 45} ${JIB_Y + 33}L${MAST - 39} ${JIB_Y + 21}h4L${MAST - 41} ${JIB_Y + 33}z`,
    fill: '#fff',
    opacity: 0.55,
  })
  add('rect', {
    x: MAST - 47,
    y: JIB_Y + 37,
    width: 8,
    height: 9,
    fill: YELLOW_DARK,
    stroke: GRAPHITE,
    'stroke-width': 0.8,
  })
  add('rect', {
    x: MAST - 46,
    y: JIB_Y + 5,
    width: 14,
    height: 7,
    rx: 1.5,
    fill: '#b9b7b2',
    stroke: GRAPHITE,
    'stroke-width': 0.9,
  })

  // анемометр и сигнальные огни
  add('line', { x1: MAST, y1: APEX, x2: MAST, y2: APEX - 9, stroke: GRAPHITE, 'stroke-width': 1.4 })
  const cups = el('g', {}, cr)
  for (let k = 0; k < 3; k++) {
    const a = k * 2.094
    const x = Math.cos(a) * 6
    const y = Math.sin(a) * 2.2
    el(
      'line',
      {
        x1: MAST,
        y1: APEX - 9,
        x2: MAST + x,
        y2: APEX - 9 + y,
        stroke: GRAPHITE,
        'stroke-width': 1,
      },
      cups,
    )
    el('circle', { cx: MAST + x, cy: APEX - 9 + y, r: 1.7, fill: '#cc3608' }, cups)
  }
  const beaconGlow = add('circle', { cx: MAST, cy: APEX + 4, r: 11, fill: '#ff3b30', opacity: 0.2 })
  const beacon = add('circle', {
    cx: MAST,
    cy: APEX + 4,
    r: 3.6,
    fill: '#ff3b30',
    stroke: GRAPHITE,
    'stroke-width': 0.8,
  })
  const jibLight = add('circle', { cx: jibStart - 8, cy: jibTop + 6, r: 2.6, fill: '#ff3b30' })
  el(
    'ellipse',
    {
      cx: MAST + 22,
      cy: MAST_BOTTOM + 22,
      rx: 64,
      ry: 8,
      fill: '#141414',
      opacity: 0.2,
      filter: ref('blur3'),
    },
    layers.gshadow,
  )

  return { beacon, beaconGlow, jibLight, cups }
}

export interface Rig {
  trolley: SVGGElement
  ropes: SVGLineElement[]
  slings: SVGLineElement[]
  hook: SVGGElement
}

/** Подвижная часть: тележка на стреле, двойной трос, крюковая подвеска и четыре стропы. */
export function drawRig({ layers }: Ctx): Rig {
  const rig = layers.rig
  const trolley = el('g', {}, rig)
  el(
    'rect',
    {
      x: -19,
      y: JIB_Y - 4,
      width: 38,
      height: 19,
      rx: 3,
      fill: YELLOW,
      stroke: GRAPHITE,
      'stroke-width': 1.3,
    },
    trolley,
  )
  el(
    'rect',
    { x: -19, y: JIB_Y - 4, width: 38, height: 4, rx: 2, fill: '#fff', opacity: 0.4 },
    trolley,
  )
  el('rect', { x: -9, y: JIB_Y + 1, width: 18, height: 8, rx: 2, fill: GRAPHITE }, trolley)
  for (const wx of [-13, 13]) {
    el(
      'circle',
      { cx: wx, cy: JIB_Y + 15, r: 4, fill: '#4a4743', stroke: GRAPHITE, 'stroke-width': 1 },
      trolley,
    )
    el('circle', { cx: wx, cy: JIB_Y + 15, r: 1.3, fill: '#b9b7b2' }, trolley)
  }
  const rope = () => el('line', { stroke: GRAPHITE, 'stroke-width': 1.5 }, rig)
  const ropes = [rope(), rope()]
  const slings = [0, 1, 2, 3].map(() =>
    el('line', { stroke: GRAPHITE, 'stroke-width': 1.3, opacity: 0 }, rig),
  )
  const hook = el('g', {}, rig)
  el('rect', { x: -11, y: -24, width: 22, height: 20, rx: 3, fill: GRAPHITE }, hook)
  el('rect', { x: -11, y: -12, width: 22, height: 5, fill: YELLOW }, hook)
  el('rect', { x: -11, y: -24, width: 22, height: 3, rx: 1.5, fill: '#fff', opacity: 0.25 }, hook)
  for (const sx of [-4.5, 4.5]) {
    el(
      'circle',
      { cx: sx, cy: -18, r: 3.6, fill: '#8c8a86', stroke: '#141414', 'stroke-width': 0.8 },
      hook,
    )
    el('circle', { cx: sx, cy: -18, r: 1, fill: GRAPHITE }, hook)
  }
  el(
    'path',
    {
      d: 'M0 -4v7a7 7 0 1 1-7 7',
      stroke: GRAPHITE,
      'stroke-width': 3.2,
      fill: 'none',
      'stroke-linecap': 'round',
    },
    hook,
  )
  el(
    'path',
    {
      d: 'M-6.5 3.5l7 5',
      stroke: '#cc3608',
      'stroke-width': 1.6,
      fill: 'none',
      'stroke-linecap': 'round',
    },
    hook,
  )
  return { trolley, ropes, slings, hook }
}
