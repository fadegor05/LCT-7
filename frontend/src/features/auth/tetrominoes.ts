/**
 * Фигуры «Стройтетриса» — фона страниц входа и регистрации. Каждая фигура тетриса нарисована
 * как машина из справочника техники (backend/app/domains/methodology/seed.py).
 *
 * Правила набора: силуэт занимает только клетки своей фигуры; фигуры не вращаются;
 * акцентом выделен только рабочий орган (ковш, крюк, отвал, шнек).
 */

export type TetrominoType = 'I' | 'O' | 'T' | 'S' | 'Z' | 'J' | 'L'

/** Сторона клетки в единицах рисунка — та же сетка 24, что у иконок. */
export const CELL = 24

export interface PieceColors {
  /** Клетка; ею же вырезаны окна и ступицы. */
  base: string
  /** Корпус машины. */
  ink: string
  /** Рабочий орган. */
  tool: string
}

export interface Tetromino {
  /** Размер фигуры в клетках. */
  w: number
  h: number
  /** Занятые клетки `[столбец, строка]`. */
  cells: readonly (readonly [number, number])[]
  /** Машина из справочника техники. */
  name: string
  /** Рисунок машины в координатах фигуры (клетка = `CELL`). */
  draw: (c: PieceColors) => string
}

export const TETROMINO_TYPES: readonly TetrominoType[] = ['I', 'O', 'T', 'S', 'Z', 'J', 'L']

/** Палитра «классика»: у каждой фигуры свой статусный токен, как цвета в оригинальном тетрисе. */
export const PIECE_TOKENS: Record<TetrominoType, { base: string; ink: string }> = {
  I: { base: '--status-ahead-soft', ink: '--status-ahead' },
  O: { base: '--caution-soft', ink: '--caution' },
  T: { base: '--status-unobserved-soft', ink: '--status-unobserved' },
  S: { base: '--status-ontrack-soft', ink: '--status-ontrack' },
  Z: { base: '--status-behind-soft', ink: '--status-behind' },
  J: { base: '--status-notstarted-soft', ink: '--status-notstarted' },
  L: { base: '--accent-soft', ink: '--accent-strong' },
}

/** Рабочий орган во всех фигурах одного цвета. */
export const TOOL_TOKEN = '--ink'

const rect = (x: number, y: number, w: number, h: number, fill: string, rx = 0) =>
  `<rect x="${x}" y="${y}" width="${w}" height="${h}"${rx ? ` rx="${rx}"` : ''} fill="${fill}"/>`

const shape = (d: string, fill: string) => `<path d="${d}" fill="${fill}"/>`

const line = (d: string, stroke: string, width: number) =>
  `<path d="${d}" fill="none" stroke="${stroke}" stroke-width="${width}" stroke-linecap="round" stroke-linejoin="round"/>`

/** Решётка мачты или стрелы: контур без заливки. */
const frame = (x: number, y: number, w: number, h: number, stroke: string) =>
  `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="none" stroke="${stroke}" stroke-width="1.3"/>`

const round = (v: number) => Math.round(v * 100) / 100

const wheel = (cx: number, cy: number, r: number, c: PieceColors) =>
  `<circle cx="${cx}" cy="${cy}" r="${r}" fill="${c.ink}"/>` +
  `<circle cx="${cx}" cy="${cy}" r="${round(r * 0.4)}" fill="${c.base}"/>`

/** Гусеница с катками. */
function track(x: number, y: number, w: number, h: number, rollers: number, c: PieceColors) {
  const from = x + h / 2
  const to = x + w - h / 2
  let svg = rect(x, y, w, h, c.ink, h / 2)
  for (let i = 0; i < rollers; i++) {
    const cx = round(from + ((to - from) * i) / (rollers - 1))
    svg += `<circle cx="${cx}" cy="${round(y + h / 2)}" r="${round(h * 0.2)}" fill="${c.base}"/>`
  }
  return svg
}

export const TETROMINOES: Record<TetrominoType, Tetromino> = {
  I: {
    w: 4,
    h: 1,
    cells: [
      [0, 0],
      [1, 0],
      [2, 0],
      [3, 0],
    ],
    name: 'Автокран',
    draw: (c) =>
      rect(5, 12, 84, 4, c.ink, 1) +
      rect(8, 7.5, 22, 5, c.ink, 1) +
      shape('M10 4.6 L92 3.2 L92 5.8 L10 9 Z', c.ink) +
      rect(36, 3, 0.9, 6.5, c.base) +
      rect(62, 3, 0.9, 5, c.base) +
      shape('M74 16 V6.5 Q74 6 74.5 6 H85.5 L91 11.5 V16 Z', c.ink) +
      shape('M76.5 8 H84.6 L88 11.5 H76.5 Z', c.base) +
      wheel(16, 17.6, 3.6, c) +
      wheel(25, 17.6, 3.6, c) +
      wheel(57, 17.6, 3.6, c) +
      wheel(82, 17.6, 3.6, c) +
      line('M92 5.6 V7.6', c.ink, 0.8) +
      rect(90.4, 7.4, 3.2, 3.2, c.tool, 0.7),
  },
  O: {
    w: 2,
    h: 2,
    cells: [
      [0, 0],
      [1, 0],
      [0, 1],
      [1, 1],
    ],
    name: 'Бульдозер',
    draw: (c) =>
      track(4, 36, 32, 9, 4, c) +
      rect(6, 27.5, 28, 8, c.ink, 1) +
      rect(19, 21, 15, 7, c.ink, 1) +
      rect(27.5, 14, 2.6, 7.5, c.ink) +
      rect(7, 9, 13, 19, c.ink, 1.5) +
      rect(9.5, 11.5, 8, 7.5, c.base, 0.8) +
      line('M33 32 L39.5 38', c.ink, 2.4) +
      line('M33 23.5 L39.5 27', c.ink, 1.6) +
      shape('M38 20.5 H43.5 Q40.5 32.5 45 45 H38 Z', c.tool),
  },
  T: {
    w: 3,
    h: 2,
    cells: [
      [0, 0],
      [1, 0],
      [2, 0],
      [1, 1],
    ],
    name: 'Башенный кран',
    draw: (c) =>
      frame(32, 13, 8, 31, c.ink) +
      line('M32 44 L40 38.8 L32 33.6 L40 28.4 L32 23.2 L40 18 L32 13', c.ink, 0.9) +
      rect(27, 43, 18, 2.5, c.ink, 0.6) +
      rect(5, 10.5, 28, 3, c.ink) +
      rect(6, 13.5, 8, 6, c.ink, 0.6) +
      line('M36 9 H69 M36 14 H69 M69 9 V14', c.ink, 1.3) +
      line('M40 14 L44.5 9 L49 14 L53.5 9 L58 14 L62.5 9 L67 14', c.ink, 0.9) +
      shape('M32.5 10.5 L36 2.5 L39.5 10.5 Z', c.ink) +
      line('M36 3 L68 9 M36 3 L6 10.5', c.ink, 0.8) +
      rect(40.5, 14, 7, 6, c.ink, 0.8) +
      rect(42, 15.3, 4, 2.6, c.base) +
      rect(57, 14, 5, 1.8, c.ink) +
      line('M59.5 15.8 V18.2', c.ink, 0.8) +
      rect(57.8, 18, 3.4, 3, c.tool, 0.7),
  },
  S: {
    w: 3,
    h: 2,
    cells: [
      [1, 0],
      [2, 0],
      [0, 1],
      [1, 1],
    ],
    name: 'Автобетононасос',
    draw: (c) =>
      rect(13, 37, 33, 4, c.ink, 1) +
      shape('M3 41 V35.5 L8 30 H16 V41 Z', c.ink) +
      shape('M5.5 35.5 L9 32 H13.8 V35.5 Z', c.base) +
      rect(38, 31, 8, 6.5, c.ink, 0.8) +
      rect(25, 31, 10, 6.5, c.ink, 0.8) +
      line('M30 32 L44 12', c.ink, 3) +
      line('M44 12 L66 7.5', c.ink, 2.4) +
      `<circle cx="44" cy="12" r="1" fill="${c.base}"/>` +
      line('M66 7.5 V15', c.ink, 1.4) +
      rect(64.6, 14.5, 2.8, 6.5, c.tool, 1.2) +
      wheel(9, 41.6, 3.6, c) +
      wheel(31, 41.6, 3.6, c) +
      wheel(40, 41.6, 3.6, c),
  },
  Z: {
    w: 3,
    h: 2,
    cells: [
      [0, 0],
      [1, 0],
      [1, 1],
      [2, 1],
    ],
    name: 'Фронтальный погрузчик',
    draw: (c) =>
      rect(46, 29.5, 23, 9, c.ink, 2) +
      rect(27, 30, 20, 7, c.ink, 1) +
      rect(55, 25, 2.4, 5, c.ink) +
      rect(31, 9, 14, 22, c.ink, 1.5) +
      rect(33.5, 11.5, 9, 9, c.base, 0.8) +
      line('M32 30 L16 13', c.ink, 3.4) +
      line('M31 19 L19.5 10.5', c.ink, 1.5) +
      shape('M4.5 9.5 H16.5 L18 18 Q18 21 15 21 H8.5 Z', c.tool) +
      wheel(33, 38.5, 6.5, c) +
      wheel(59, 38.5, 6.5, c),
  },
  J: {
    w: 3,
    h: 2,
    cells: [
      [0, 0],
      [0, 1],
      [1, 1],
      [2, 1],
    ],
    name: 'Буровая установка',
    draw: (c) =>
      track(15, 37.5, 54, 7.5, 6, c) +
      rect(27, 29, 41, 8, c.ink, 1.5) +
      rect(25, 25.5, 12, 11.5, c.ink, 1) +
      rect(27, 27.5, 7.5, 4.5, c.base, 0.6) +
      line('M27 33 H15', c.ink, 3) +
      frame(8, 5, 8, 33, c.ink) +
      line('M8 38 L16 32.5 L8 27 L16 21.5 L8 16 L16 10.5 L8 5', c.ink, 0.9) +
      `<circle cx="12" cy="4.4" r="1.8" fill="${c.ink}"/>` +
      rect(6, 18, 12, 5, c.ink, 0.8) +
      rect(9.5, 37, 5, 8, c.tool, 1) +
      line('M9.8 40 L14.2 38.6 M9.8 43 L14.2 41.6', c.base, 0.9),
  },
  L: {
    w: 3,
    h: 2,
    cells: [
      [2, 0],
      [0, 1],
      [1, 1],
      [2, 1],
    ],
    name: 'Гусеничный экскаватор',
    draw: (c) =>
      track(4, 38.5, 52, 6.5, 6, c) +
      rect(4, 30, 12, 7.5, c.ink, 3) +
      rect(8, 31, 40, 6.5, c.ink, 1) +
      rect(34, 25, 12, 7, c.ink, 1) +
      rect(36, 26.5, 7.5, 3.5, c.base, 0.5) +
      line('M47 33 L60 6.5', c.ink, 4) +
      line('M44 31 L54 18', c.ink, 1.6) +
      line('M60 6.5 L67 16', c.ink, 3) +
      shape('M63 15.5 L69.5 13.5 L70 20 Q69 23 65.5 22.5 L61.5 21.5 Z', c.tool),
  },
}

/**
 * SVG фигуры: клетки с зазором 1,5 и машина поверх. `px` — размер клетки в пикселях картинки.
 */
export function pieceSvg(type: TetrominoType, colors: PieceColors, px: number): string {
  const piece = TETROMINOES[type]
  const cells = piece.cells
    .map(([x, y]) => rect(x * CELL + 0.75, y * CELL + 0.75, 22.5, 22.5, colors.base, 2.5))
    .join('')
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${piece.w * CELL} ${piece.h * CELL}"` +
    ` width="${piece.w * px}" height="${piece.h * px}">${cells}${piece.draw(colors)}</svg>`
  )
}
