import type { Pt } from './geometry'
import { iso, pts, shade } from './geometry'

const NS = 'http://www.w3.org/2000/svg'

export type Attrs = Record<string, string | number>

/** Создаёт SVG-элемент с атрибутами и сразу кладёт его в `parent`. */
export function el<K extends keyof SVGElementTagNameMap>(
  tag: K,
  attrs: Attrs,
  parent?: Element | null,
): SVGElementTagNameMap[K] {
  const node = document.createElementNS(NS, tag)
  for (const [name, value] of Object.entries(attrs)) node.setAttribute(name, String(value))
  parent?.appendChild(node)
  return node
}

export const poly = (parent: Element, points: readonly Pt[], fill: string, more: Attrs = {}) =>
  el('polygon', { points: pts(points), fill, ...more }, parent)

export const line = (
  parent: Element,
  a: Pt,
  b: Pt,
  stroke: string,
  width: number,
  more: Attrs = {},
) =>
  el(
    'line',
    {
      x1: a[0].toFixed(1),
      y1: a[1].toFixed(1),
      x2: b[0].toFixed(1),
      y2: b[1].toFixed(1),
      stroke,
      'stroke-width': width,
      ...more,
    },
    parent,
  )

export function text(parent: Element, attrs: Attrs, content: string) {
  const node = el('text', attrs, parent)
  node.textContent = content
  return node
}

/** Изометрический параллелепипед: вентустановки, бытовка и т. п. */
export function isoBox(
  parent: Element,
  [x, y, z]: [number, number, number],
  [w, d, h]: [number, number, number],
  color: string,
) {
  poly(
    parent,
    [iso(x, y + d, z), iso(x + w, y + d, z), iso(x + w, y + d, z + h), iso(x, y + d, z + h)],
    shade(color, 0.94),
  )
  poly(
    parent,
    [iso(x + w, y + d, z), iso(x + w, y, z), iso(x + w, y, z + h), iso(x + w, y + d, z + h)],
    shade(color, 0.74),
  )
  poly(
    parent,
    [iso(x, y, z + h), iso(x + w, y, z + h), iso(x + w, y + d, z + h), iso(x, y + d, z + h)],
    shade(color, 1.14),
  )
}
