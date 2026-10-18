/** Геометрия сцены «кран собирает график»: изометрия и константы, общие для всех слоёв. */
export type Pt = [number, number]

/** Размер блока-этажа, зазор между этажами и шаг по вертикали. */
export const W = 130
export const D = 84
export const H = 50
export const GAP = 6
export const PITCH = H + GAP

/** Начало изометрических осей: задняя нижняя вершина башни, px. */
const ORIGIN_X = 450
const ORIGIN_Y = 520
const K = Math.sqrt(3) / 2
const HALF = 0.5

/** Рамка сцены с запасом справа: параллакс сдвигает слой, и кран не должен упираться в край. */
export const VIEW = { x: -20, y: -62, w: 960, h: 790 } as const

/** Башенный кран: ось мачты, высота стрелы, сдвиг поддона от башни, точка подвеса тележки. */
export const MAST = 850
export const JIB_Y = 40
export const TROLLEY_Y = JIB_Y + 14
export const PALLET_DX = -320
export const HOME_HOOK_Y = 96
export const HOOK_OFFSET = 26

/** Свет падает сверху-слева: тень смещается вправо-вниз на столько px на px высоты. */
export const SHADOW_X = 0.55
export const SHADOW_Y = 0.12

/** Точка изометрии (x вправо-вниз, y влево-вниз, z вверх) → экран. */
export const iso = (x: number, y: number, z: number): Pt => [
  ORIGIN_X + (x - y) * K,
  ORIGIN_Y + (x + y) * HALF - z,
]

/** Список точек для атрибута `points`. */
export const pts = (list: readonly Pt[]): string =>
  list.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ')

/** Центр крыши этажа `i`: сюда подвешивается груз. */
export const roofCenter = (i: number): Pt => iso(W / 2, D / 2, i * PITCH + H)

/** Ромб основания блока на высоте `z`, смещённый на экране на (dx, dy). */
export const diamond = (z: number, dx = 0, dy = 0): Pt[] =>
  ([iso(0, 0, z), iso(W, 0, z), iso(W, D, z), iso(0, D, z)] as Pt[]).map(([x, y]) => [
    x + dx,
    y + dy,
  ])

/** Светлее (`f > 1`) или темнее (`f < 1`) цвета `#rrggbb`. */
export function shade(hex: string, f: number): string {
  const n = parseInt(hex.slice(1), 16)
  const target = f < 1 ? 0 : 255
  const t = Math.abs(f - 1)
  return (
    '#' +
    [n >> 16, (n >> 8) & 255, n & 255]
      .map((v) =>
        Math.round(v + (target - v) * t)
          .toString(16)
          .padStart(2, '0'),
      )
      .join('')
  )
}

/** Выпуклая оболочка точек (алгоритм Эндрю) — контур тени от башни. */
export function hull(points: readonly Pt[]): Pt[] {
  const sorted = [...points].sort((a, b) => a[0] - b[0] || a[1] - b[1])
  const cross = (o: Pt, a: Pt, b: Pt) =>
    (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
  const half = (list: readonly Pt[]) => {
    const out: Pt[] = []
    for (const p of list) {
      while (out.length > 1 && cross(out[out.length - 2]!, out[out.length - 1]!, p) <= 0) out.pop()
      out.push(p)
    }
    out.pop()
    return out
  }
  return [...half(sorted), ...half([...sorted].reverse())]
}

/** Плавная ступенька: 0 при `x` у `a`, 1 при `x` у `b` (a может быть больше b). */
export function smoothstep(a: number, b: number, x: number): number {
  const t = Math.max(0, Math.min(1, (x - a) / (b - a)))
  return t * t * (3 - 2 * t)
}
