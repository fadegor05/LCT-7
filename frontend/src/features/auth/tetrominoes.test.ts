import { CELL, TETROMINOES, TETROMINO_TYPES, pieceSvg, type Tetromino } from './tetrominoes'

const colors = { base: '#base', ink: '#ink', tool: '#tool' }

type Point = readonly [number, number]

/** Фигуры рисунка: опорные точки контура и половина толщины обводки. */
function outlines(svg: string): { points: Point[]; closed: boolean; pad: number }[] {
  const result: { points: Point[]; closed: boolean; pad: number }[] = []
  for (const [, tag, body] of svg.matchAll(/<(rect|circle|path)\s([^>]*?)\/>/g)) {
    const attrs = Object.fromEntries(
      [...body!.matchAll(/([\w-]+)="([^"]*)"/g)].map((m) => [m[1]!, m[2]!]),
    )
    const num = (name: string) => Number(attrs[name] ?? 0)
    const pad = attrs.stroke ? num('stroke-width') / 2 : 0
    if (tag === 'rect') {
      const [x, y, w, h] = [num('x'), num('y'), num('width'), num('height')]
      const points: Point[] = [
        [x, y],
        [x + w, y],
        [x + w, y + h],
        [x, y + h],
      ]
      result.push({ points, closed: true, pad })
    } else if (tag === 'circle') {
      const [cx, cy, r] = [num('cx'), num('cy'), num('r')]
      const points = Array.from({ length: 16 }, (_, i): Point => {
        const a = (i / 16) * 2 * Math.PI
        return [cx + r * Math.cos(a), cy + r * Math.sin(a)]
      })
      result.push({ points, closed: true, pad })
    } else {
      // Все пути рисунков — абсолютные M, L, H, V, Q, Z. Для Q берём опорную точку: кривая внутри.
      const tokens = attrs.d!.match(/[MLHVQZ]|-?\d*\.?\d+/g)!
      let points: Point[] = []
      let cmd = ''
      let x = 0
      let y = 0
      const flush = (closed: boolean) => {
        if (points.length) result.push({ points, closed, pad })
        points = []
      }
      for (let i = 0; i < tokens.length;) {
        if (/[A-Z]/.test(tokens[i]!)) cmd = tokens[i++]!
        const next = () => Number(tokens[i++])
        if (cmd === 'M') {
          flush(false)
          x = next()
          y = next()
        } else if (cmd === 'L') {
          x = next()
          y = next()
        } else if (cmd === 'H') x = next()
        else if (cmd === 'V') y = next()
        else if (cmd === 'Q') {
          points.push([next(), next()])
          x = next()
          y = next()
        } else if (cmd === 'Z') {
          flush(true)
          continue
        }
        points.push([x, y])
      }
      flush(false)
    }
  }
  return result
}

/** Точка лежит в занятой клетке фигуры (границы клеток включительно, допуск 0,25). */
function inside(piece: Tetromino, [x, y]: Point): boolean {
  const tol = 0.25
  return piece.cells.some(
    ([cx, cy]) =>
      x >= cx * CELL - tol &&
      x <= (cx + 1) * CELL + tol &&
      y >= cy * CELL - tol &&
      y <= (cy + 1) * CELL + tol,
  )
}

/** Точки, которые не помещаются в клетки: контур обходится с шагом 0,5 и раздувается на обводку. */
function escapes(piece: Tetromino): Point[] {
  const out: Point[] = []
  const offsets: Point[] = [[0, 0]]
  for (const { points, closed, pad } of outlines(piece.draw(colors))) {
    if (pad) {
      for (let i = 0; i < 8; i++) {
        const a = (i / 8) * 2 * Math.PI
        offsets.push([pad * Math.cos(a), pad * Math.sin(a)])
      }
    }
    const segments = closed ? points.length : points.length - 1
    for (let s = 0; s < Math.max(segments, 1); s++) {
      const [ax, ay] = points[s]!
      const [bx, by] = points[(s + 1) % points.length]!
      const steps = Math.max(1, Math.ceil(Math.hypot(bx - ax, by - ay) / 0.5))
      for (let k = 0; k <= steps; k++) {
        const px = ax + ((bx - ax) * k) / steps
        const py = ay + ((by - ay) * k) / steps
        for (const [dx, dy] of offsets) {
          if (!inside(piece, [px + dx, py + dy])) out.push([px + dx, py + dy])
        }
      }
    }
    offsets.length = 1
  }
  return out
}

describe('tetrominoes', () => {
  it.each(TETROMINO_TYPES)('%s has four distinct cells inside its box', (type) => {
    const { w, h, cells } = TETROMINOES[type]
    expect(cells).toHaveLength(4)
    expect(new Set(cells.map(([x, y]) => `${x}:${y}`)).size).toBe(4)
    for (const [x, y] of cells) {
      expect(x).toBeLessThan(w)
      expect(y).toBeLessThan(h)
    }
  })

  it.each(TETROMINO_TYPES)('%s keeps the machine inside its own cells', (type) => {
    expect(escapes(TETROMINOES[type])).toEqual([])
  })

  it.each(TETROMINO_TYPES)('%s highlights the working tool', (type) => {
    expect(TETROMINOES[type].draw(colors)).toContain('#tool')
  })

  it('draws the cells and the machine at the requested scale', () => {
    const svg = pieceSvg('L', colors, 48)
    expect(svg).toContain('viewBox="0 0 72 48"')
    expect(svg).toContain('width="144" height="96"')
    expect(svg.match(/width="22.5"/g)).toHaveLength(4)
    expect(svg).toContain('#ink')
  })

  it('catches a machine that sticks out of its cells', () => {
    const broken: Tetromino = {
      ...TETROMINOES.L,
      draw: (c) => `<rect x="2" y="2" width="10" height="10" fill="${c.ink}"/>`,
    }
    expect(escapes(broken).length).toBeGreaterThan(0)
  })
})
