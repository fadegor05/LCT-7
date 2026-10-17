import type { Ctx } from './ctx'
import { D, H, PITCH, W, iso, roofCenter, shade, type Pt } from './geometry'
import { drawChip } from './siteArt'
import { el, isoBox, line, poly } from './svg'
import { STATUS, type TowerStage } from './timeline'

type Quad = [Pt, Pt, Pt, Pt]

/** Прямоугольник на левой (передней) грани блока: по x и высоте. */
const onLeft = (x0: number, x1: number, z0: number, z1: number): Quad => [
  iso(x0, D, z0),
  iso(x1, D, z0),
  iso(x1, D, z1),
  iso(x0, D, z1),
]
/** Прямоугольник на правой грани блока: по y и высоте. */
const onRight = (y0: number, y1: number, z0: number, z1: number): Quad => [
  iso(W, y0, z0),
  iso(W, y1, z0),
  iso(W, y1, z1),
  iso(W, y0, z1),
]
const roofOf = (top: number): Quad => [
  iso(0, 0, top),
  iso(W, 0, top),
  iso(W, D, top),
  iso(0, D, top),
]

/** Грани блока, объём от градиентов, особенности этапа и блики на рёбрах. */
function drawBlock(g: SVGGElement, ref: Ctx['ref'], stage: TowerStage, z: number, top: number) {
  const c = stage.color
  const left = onLeft(0, W, z, top)
  const right = onRight(D, 0, z, top)
  poly(g, left, shade(c, 0.93))
  poly(g, right, shade(c, 0.72))
  poly(g, roofOf(top), shade(c, 1.18))
  poly(g, left, ref('shl'))
  poly(g, right, ref('shr'))

  switch (stage.kind) {
    case 'base': // опалубка: щиты со стяжками
      for (let x = 0; x <= W; x += 26) {
        line(g, iso(x, D, z), iso(x, D, top), '#000', 1, { opacity: 0.18 })
        for (const zz of [z + 12, top - 12]) {
          const [cx, cy] = iso(x + 13, D, zz)
          el('circle', { cx, cy, r: 1.6, fill: '#000', opacity: 0.28 }, g)
        }
      }
      for (let y = 0; y <= D; y += 28)
        line(g, iso(W, y, z), iso(W, y, top), '#000', 1, { opacity: 0.18 })
      line(g, iso(0, D, z + H / 2), iso(W, D, z + H / 2), '#000', 1, { opacity: 0.15 })
      break
    case 'slab': // плита: рёбра и закладные детали
      for (let k = 1; k < 4; k++) {
        line(g, iso(0, D, z + (k * H) / 4), iso(W, D, z + (k * H) / 4), '#fff', 1, {
          opacity: 0.28,
        })
        line(g, iso(W, D, z + (k * H) / 4), iso(W, 0, z + (k * H) / 4), '#000', 1, {
          opacity: 0.14,
        })
      }
      for (let x = 18; x < W; x += 34)
        poly(g, onLeft(x, x + 10, z + 20, z + 30), shade(c, 0.6), { opacity: 0.8 })
      for (let y = 14; y < D; y += 30)
        poly(g, onRight(y, y + 10, z + 20, z + 30), shade(c, 0.5), { opacity: 0.8 })
      break
    case 'frame': // каркас: колонны, ригели, тёмные проёмы
      poly(g, onLeft(8, W - 8, z + 6, top - 6), shade(c, 0.42), { opacity: 0.9 })
      poly(g, onRight(8, D - 8, z + 6, top - 6), shade(c, 0.34), { opacity: 0.9 })
      for (const x of [8, W / 3, (2 * W) / 3, W - 14])
        poly(g, onLeft(x, x + 6, z, top), shade(c, 1.02))
      for (const y of [8, D / 2, D - 14]) poly(g, onRight(y, y + 6, z, top), shade(c, 0.82))
      poly(g, onLeft(0, W, z, z + 6), shade(c, 1.08))
      poly(g, onLeft(0, W, top - 6, top), shade(c, 1.08))
      poly(g, onRight(0, D, z, z + 6), shade(c, 0.88))
      poly(g, onRight(0, D, top - 6, top), shade(c, 0.88))
      for (let k = 1; k < 4; k++) {
        line(g, iso(8, D, z + 6 + k * 8), iso(W - 8, D, z + 6 + k * 8), '#fff', 0.8, {
          opacity: 0.16,
        })
      }
      break
    case 'glass': // остекление: стёкла, импосты, блики
      for (let w = 0; w < 4; w++) {
        const x0 = 9 + w * 30
        poly(g, onLeft(x0, x0 + 22, z + 8, top - 8), ref('glass'))
        poly(
          g,
          [
            iso(x0 + 4, D, top - 10),
            iso(x0 + 10, D, top - 10),
            iso(x0 + 19, D, z + 10),
            iso(x0 + 13, D, z + 10),
          ],
          '#fff',
          { opacity: 0.5 },
        )
      }
      for (let w = 0; w < 3; w++) {
        const y0 = D - 9 - w * 27
        poly(g, onRight(y0 - 20, y0, z + 8, top - 8), ref('glass'), { opacity: 0.9 })
      }
      poly(g, onLeft(0, W, z, z + 7), shade(c, 1.1))
      poly(g, onLeft(0, W, top - 7, top), shade(c, 1.1))
      break
    case 'roof': {
      // кровля: парапет, вентустановки, антенна
      poly(g, roofOf(top), shade(c, 1.2))
      poly(
        g,
        [iso(0, 0, top), iso(W, 0, top), iso(W, 0, top + 7), iso(0, 0, top + 7)],
        shade(c, 0.78),
      )
      poly(
        g,
        [iso(0, 0, top), iso(0, D, top), iso(0, D, top + 7), iso(0, 0, top + 7)],
        shade(c, 0.9),
      )
      poly(
        g,
        [iso(4, 4, top), iso(W - 4, 4, top), iso(W - 4, D - 4, top), iso(4, D - 4, top)],
        shade(c, 1.3),
      )
      isoBox(g, [16, 14, top], [34, 22, 13], '#d6d4cf')
      isoBox(g, [70, 20, top], [30, 26, 10], '#cfcdc8')
      const [fx, fy] = iso(33, 25, top + 13)
      el('ellipse', { cx: fx, cy: fy, rx: 9, ry: 4.5, fill: '#8b8983' }, g)
      poly(g, [iso(0, D, top), iso(W, D, top), iso(W, D, top + 7), iso(0, D, top + 7)], shade(c, 1))
      poly(
        g,
        [iso(W, D, top), iso(W, 0, top), iso(W, 0, top + 7), iso(W, D, top + 7)],
        shade(c, 0.68),
      )
      const [ax, ay] = iso(W - 14, 10, top)
      line(g, [ax, ay], [ax, ay - 44], '#4a4743', 1.8)
      el('circle', { cx: ax, cy: ay - 46, r: 2.6, fill: '#cc3608' }, g)
      line(g, [ax - 8, ay - 30], [ax + 8, ay - 30], '#4a4743', 1.4)
      line(g, [ax - 5, ay - 38], [ax + 5, ay - 38], '#4a4743', 1.4)
      break
    }
  }

  // «ещё не начато» — штриховка
  if (c === STATUS.idle) {
    poly(g, left, ref('hatch'))
    poly(g, right, ref('hatch'), { opacity: 0.7 })
  }
  // блики на рёбрах и тёмный нижний шов
  line(g, iso(W, D, z), iso(W, D, top), '#fff', 1.4, { opacity: 0.55 })
  line(g, iso(0, D, top), iso(W, D, top), '#fff', 1.2, { opacity: 0.55 })
  line(g, iso(W, D, top), iso(W, 0, top), '#fff', 1, { opacity: 0.35 })
  line(g, iso(0, D, z), iso(W, D, z), '#000', 1.2, { opacity: 0.22 })
  line(g, iso(W, D, z), iso(W, 0, z), '#000', 1.2, { opacity: 0.28 })
}

export interface Dust {
  e: SVGCircleElement
  from: Pt
  dir: number
  on: boolean
}

export interface TowerBlock {
  index: number
  group: SVGGElement
  chip: SVGGElement
  /** Центр крыши на своём месте. */
  topX: number
  topY: number
  /** Вершины крыши относительно центра: сюда крепятся стропы. */
  corners: Pt[]
  flash: SVGPolygonElement[]
  dust: Dust[]
}

/** Блок-этап: фигура, вспышка и пыль при посадке, подпись-плашка. */
export function drawTowerBlock(ctx: Ctx, stage: TowerStage, i: number): TowerBlock {
  const z = i * PITCH
  const top = z + H
  const group = el('g', { opacity: 0 }, ctx.layers.blocks)
  drawBlock(group, ctx.ref, stage, z, top)
  const flash = [
    poly(group, onLeft(0, W, z, top), '#fff', { opacity: 0 }),
    poly(group, onRight(D, 0, z, top), '#fff', { opacity: 0 }),
    poly(group, roofOf(top), '#fff', { opacity: 0 }),
  ]
  const [topX, topY] = roofCenter(i)
  const corners = roofOf(top).map(([x, y]): Pt => [x - topX, y - topY])
  const dust: Dust[] = []
  for (const from of [iso(0, D, z), iso(W, D, z), iso(W, 0, z)]) {
    for (const dir of [-1, 0, 1]) {
      const e = el(
        'circle',
        { cx: from[0], cy: from[1], r: 2, fill: '#d6d3cc', opacity: 0 },
        ctx.layers.fx,
      )
      dust.push({ e, from, dir, on: false })
    }
  }
  const anchor = iso(W, D * 0.15, z + H / 2)
  const chip = drawChip(
    ctx,
    anchor,
    stage.name,
    stage.status,
    stage.color,
    stage.color === STATUS.idle,
  )
  return { index: i, group, chip, topX, topY, corners, flash, dust }
}
