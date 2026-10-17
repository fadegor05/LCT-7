import { TETROMINOES, TETROMINO_TYPES, type TetrominoType } from './tetrominoes'

/** Клетка стопки: фигура и кусок её рисунка `[cx, cy]`, который здесь лежит. */
export interface BoardCell {
  type: TetrominoType
  cx: number
  cy: number
}

/** Падающая фигура; `y` — строка её верхнего края, над колодцем отрицательная. */
export interface FallingPiece {
  type: TetrominoType
  x: number
  y: number
}

interface Move {
  type: TetrominoType
  x: number
  score: number
}

/** Стопка выше этой доли колодца оседает на `SINK_SHARE` его высоты. */
const SINK_AT = 0.6
const SINK_SHARE = 0.3
/** До этой доли колодец заполняется сразу, чтобы фон не начинался с пустого экрана. */
const WARMUP_SHARE = 0.36
/** Одна падающая фигура на каждые столько столбцов: на широком экране их несколько. */
const COLS_PER_PIECE = 8
/**
 * Веса оценки хода, подобраны прогонами на колодцах 20 и 40 столбцов. Без вращения дыры
 * под T, S и Z неизбежны, поэтому дыры и неровность штрафуются сильнее, чем у обычных ботов.
 */
const WEIGHTS = { lines: 3, height: 0.3, holes: 0.9, bumpiness: 0.4 }
/** Случайная добавка к оценке, чтобы одинаковые стопки не складывались одинаково. */
const NOISE = 0.3

const span = (start: number, length: number) => Array.from({ length }, (_, i) => start + i)

/**
 * Колодец тетриса без отрисовки. Фигуры не вращаются, а столбец выбирают сами:
 * место, где меньше дыр и ниже стопка. Падающие фигуры не делят столбцы между собой.
 */
export class Well {
  readonly board: (BoardCell | null)[][]
  readonly falling: FallingPiece[] = []
  private bag: TetrominoType[] = []

  constructor(
    readonly cols: number,
    readonly rows: number,
    private readonly random: () => number = Math.random,
  ) {
    this.board = Array.from({ length: rows }, () => this.emptyRow())
  }

  collides(type: TetrominoType, x: number, y: number): boolean {
    return TETROMINOES[type].cells.some(([cx, cy]) => {
      const row = y + cy
      const col = x + cx
      if (col < 0 || col >= this.cols || row >= this.rows) return true
      return row >= 0 && this.board[row]?.[col] != null
    })
  }

  /** Строка, на которой фигура ляжет, если бросить её в столбец `x`. */
  landing(type: TetrominoType, x: number): number {
    let y = -TETROMINOES[type].h
    while (!this.collides(type, x, y + 1)) y++
    return y
  }

  /** Лучший столбец для фигуры или `null`, если она нигде не помещается целиком. */
  choose(type: TetrominoType): number | null {
    return this.bestMove(type, this.forecast())?.x ?? null
  }

  /** Новая фигура над колодцем или `null`, если падающих уже достаточно или места нет. */
  spawn(): FallingPiece | null {
    if (this.falling.length >= Math.max(1, Math.floor(this.cols / COLS_PER_PIECE))) return null
    const piece = this.pick()
    if (piece) this.falling.push(piece)
    return piece
  }

  /** Сразу кладёт следующую фигуру в стопку, без падения. */
  drop(): FallingPiece | null {
    const piece = this.pick()
    if (!piece) return null
    piece.y = this.landing(piece.type, piece.x)
    this.lock(piece)
    this.removeRows(this.fullRows())
    return piece
  }

  /** Шаг падения: фигуры опускаются на клетку, упавшие ложатся в стопку. Возвращает полные ряды. */
  step(): number[] {
    for (const piece of [...this.falling]) {
      if (!this.collides(piece.type, piece.x, piece.y + 1)) {
        piece.y++
      } else {
        this.lock(piece)
        this.falling.splice(this.falling.indexOf(piece), 1)
      }
    }
    return this.fullRows()
  }

  fullRows(): number[] {
    return this.board.flatMap((row, r) => (this.cols > 0 && row.every(Boolean) ? [r] : []))
  }

  removeRows(rows: readonly number[]): void {
    for (const r of [...rows].sort((a, b) => a - b)) {
      this.board.splice(r, 1)
      this.board.unshift(this.emptyRow())
    }
  }

  stackHeight(): number {
    const top = this.board.findIndex((row) => row.some(Boolean))
    return top === -1 ? 0 : this.rows - top
  }

  /** Высокая стопка уходит вниз, нижние ряды отбрасываются. Возвращает, на сколько рядов. */
  sinkIfHigh(): number {
    if (this.stackHeight() <= this.rows * SINK_AT) return 0
    const rows = Math.max(2, Math.round(this.rows * SINK_SHARE))
    this.board.splice(this.rows - rows, rows)
    for (let i = 0; i < rows; i++) this.board.unshift(this.emptyRow())
    return rows
  }

  /** Сразу укладывает фигуры, пока стопка не займёт около трети колодца. */
  warmup(): void {
    for (let guard = 0; guard < 300 && this.stackHeight() < this.rows * WARMUP_SHARE; guard++) {
      if (!this.drop()) return
    }
  }

  /**
   * Следующая фигура и столбец для неё. «Мешок из 7» решает, какие машины выпадут:
   * все семь за каждые семь фигур. Порядок внутри мешка подбирается под стопку,
   * иначе без вращения ряды почти не заполняются.
   */
  private pick(): FallingPiece | null {
    if (this.bag.length === 0) this.bag = [...TETROMINO_TYPES]
    const base = this.forecast()
    let best: Move | null = null
    for (const type of this.bag) {
      const move = this.bestMove(type, base)
      if (move && (!best || move.score > best.score)) best = move
    }
    if (!best) return null
    this.bag.splice(this.bag.indexOf(best.type), 1)
    return { type: best.type, x: best.x, y: -TETROMINOES[best.type].h }
  }

  /** Лучший ход фигуры: столбцы падающих фигур заняты, торчать над колодцем нельзя. */
  private bestMove(type: TetrominoType, base: boolean[][]): Move | null {
    const piece = TETROMINOES[type]
    const busy = new Set(this.falling.flatMap((f) => span(f.x, TETROMINOES[f.type].w)))
    let best: Move | null = null
    for (let x = 0; x + piece.w <= this.cols; x++) {
      if (span(x, piece.w).some((col) => busy.has(col))) continue
      const y = this.landing(type, x)
      const cells = piece.cells.map(([cx, cy]) => [x + cx, y + cy] as const)
      if (cells.some(([, row]) => row < 0)) continue
      const score = this.score(base, cells) + this.random() * NOISE
      if (!best || score > best.score) best = { type, x, score }
    }
    return best
  }

  /** Стопка, какой она станет, когда падающие фигуры лягут: их столбцы заняты только ими. */
  private forecast(): boolean[][] {
    const grid = this.board.map((row) => row.map(Boolean))
    for (const f of this.falling) {
      const y = this.landing(f.type, f.x)
      for (const [cx, cy] of TETROMINOES[f.type].cells) {
        const row = grid[y + cy]
        if (row) row[f.x + cx] = true
      }
    }
    return grid
  }

  /** Стопка после хода: заполненные ряды — хорошо; суммарная высота, дыры и неровность — плохо. */
  private score(base: boolean[][], cells: readonly (readonly [number, number])[]): number {
    const grid = base.map((row) => [...row])
    for (const [col, r] of cells) {
      const row = grid[r]
      if (row) row[col] = true
    }
    const kept = grid.filter((row) => !row.every(Boolean))
    const lines = grid.length - kept.length
    let height = 0
    let holes = 0
    let bumpiness = 0
    let previous = -1
    for (let col = 0; col < this.cols; col++) {
      const top = kept.findIndex((row) => row[col])
      const columnHeight = top === -1 ? 0 : kept.length - top
      if (top !== -1) {
        for (let r = top + 1; r < kept.length; r++) if (!kept[r]?.[col]) holes++
      }
      height += columnHeight
      if (previous >= 0) bumpiness += Math.abs(columnHeight - previous)
      previous = columnHeight
    }
    return (
      lines * WEIGHTS.lines -
      height * WEIGHTS.height -
      holes * WEIGHTS.holes -
      bumpiness * WEIGHTS.bumpiness
    )
  }

  private lock(piece: FallingPiece): void {
    for (const [cx, cy] of TETROMINOES[piece.type].cells) {
      const row = this.board[piece.y + cy]
      if (row) row[piece.x + cx] = { type: piece.type, cx, cy }
    }
  }

  private emptyRow(): (BoardCell | null)[] {
    return new Array<BoardCell | null>(this.cols).fill(null)
  }
}
