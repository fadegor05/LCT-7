import {
  PIECE_TOKENS,
  TETROMINOES,
  TETROMINO_TYPES,
  TOOL_TOKEN,
  pieceSvg,
  type TetrominoType,
} from './tetrominoes'
import { Well } from './well'

/** Шаг падения: фигура пересекает экран за 6–9 секунд. */
const STEP_MS = 400
/** Смягчение шага: движение по клеткам читается, но не дёргается. */
const EASE_MS = 80
/** Вспышка и исчезновение заполненного ряда. */
const CLEAR_MS = 260
/** Оседание высокой стопки. */
const SINK_MS = 700
/** Новая фигура — через 0,9–1,8 с. */
const SPAWN_MS = 900

/** Клетка на экране: 48 px, как высота поля ввода; на узких экранах меньше. */
export function cellSize(width: number): number {
  if (width >= 900) return 48
  if (width >= 600) return 40
  return 32
}

const easeOut = (k: number) => 1 - (1 - Math.min(1, Math.max(0, k))) ** 3

/**
 * Запускает фон «Стройтетрис» на canvas и возвращает функцию остановки.
 * Canvas растягивается на родителя. Без 2D-контекста фон не рисуется; при
 * `prefers-reduced-motion` стопка статична; на скрытой вкладке анимация на паузе.
 */
export function startBackdrop(canvas: HTMLCanvasElement): () => void {
  const context = canvas.getContext('2d')
  if (!context) return () => {}
  const ctx: CanvasRenderingContext2D = context
  const host = canvas.parentElement ?? canvas
  const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)')
  const tokens = getComputedStyle(document.documentElement)
  const color = (token: string) => tokens.getPropertyValue(token).trim()
  const accent = color('--accent')
  const tool = color(TOOL_TOKEN)

  let well = new Well(0, 0)
  let width = 0
  let height = 0
  let size = 0
  let dpr = 1
  let ox = 0
  let oy = 0
  let images = new Map<TetrominoType, HTMLImageElement>()
  let clearing: { rows: number[]; start: number } | null = null
  let sink: { rows: number; start: number } | null = null
  let lastStep = 0
  let nextSpawn = 0
  let raf = 0
  let resizeTimer = 0

  const buildImages = () => {
    const px = Math.round(size * dpr)
    images = new Map(
      TETROMINO_TYPES.map((type) => {
        const img = new Image()
        const { base, ink } = PIECE_TOKENS[type]
        img.onload = () => {
          if (!raf) draw(performance.now())
        }
        const svg = pieceSvg(type, { base: color(base), ink: color(ink), tool }, px)
        img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
        return [type, img]
      }),
    )
  }

  /** Каждая клетка рисует свой кусок картинки фигуры: очистка ряда честно режет технику. */
  const drawCell = (type: TetrominoType, cx: number, cy: number, x: number, y: number) => {
    const img = images.get(type)
    if (!img?.complete || !img.naturalWidth) return
    const s = Math.round(size * dpr)
    ctx.drawImage(img, cx * s, cy * s, s, s, x, y, size, size)
  }

  const draw = (now: number) => {
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.clearRect(0, 0, width, height)
    let shift = 0
    if (sink) {
      const k = (now - sink.start) / SINK_MS
      shift = -sink.rows * size * (1 - easeOut(k))
      if (k >= 1) sink = null
    }
    const clearK = clearing ? (now - clearing.start) / CLEAR_MS : 0
    well.board.forEach((row, r) => {
      ctx.globalAlpha = clearing?.rows.includes(r) ? 1 - easeOut(clearK) : 1
      row.forEach((cell, c) => {
        if (cell) drawCell(cell.type, cell.cx, cell.cy, ox + c * size, oy + r * size + shift)
      })
    })
    if (clearing) {
      ctx.globalAlpha = 0.6 * Math.sin(Math.PI * Math.min(1, clearK * 1.6))
      ctx.fillStyle = accent
      for (const r of clearing.rows) ctx.fillRect(ox, oy + r * size + shift, well.cols * size, size)
    }
    ctx.globalAlpha = 1
    const fall = easeOut((now - lastStep) / EASE_MS) - 1
    for (const piece of well.falling) {
      for (const [cx, cy] of TETROMINOES[piece.type].cells) {
        drawCell(piece.type, cx, cy, ox + (piece.x + cx) * size, oy + (piece.y + cy + fall) * size)
      }
    }
  }

  const settle = (now: number) => {
    const rows = well.sinkIfHigh()
    if (rows) sink = { rows, start: now }
  }

  const frame = (now: number) => {
    if (clearing) {
      if (now - clearing.start >= CLEAR_MS) {
        well.removeRows(clearing.rows)
        clearing = null
        settle(now)
        lastStep = now
      }
    } else if (now - lastStep >= STEP_MS) {
      lastStep = now
      const full = well.step()
      if (full.length) clearing = { rows: full, start: now }
      else settle(now)
    }
    if (!clearing && now >= nextSpawn) {
      well.spawn()
      nextSpawn = now + SPAWN_MS * (1 + Math.random())
    }
    draw(now)
    raf = requestAnimationFrame(frame)
  }

  const start = () => {
    if (raf || reduce?.matches || document.hidden) return
    lastStep = performance.now()
    raf = requestAnimationFrame(frame)
  }

  const stop = () => {
    if (raf) cancelAnimationFrame(raf)
    raf = 0
  }

  const layout = () => {
    const rect = host.getBoundingClientRect()
    width = rect.width
    height = rect.height
    dpr = Math.min(window.devicePixelRatio || 1, 2)
    size = cellSize(width)
    const cols = Math.floor(width / size)
    const rows = Math.ceil(height / size)
    ox = Math.round((width - cols * size) / 2)
    oy = Math.round(height - rows * size)
    canvas.width = Math.round(width * dpr)
    canvas.height = Math.round(height * dpr)
    well = new Well(cols, rows)
    well.warmup()
    clearing = null
    sink = null
    buildImages()
    draw(performance.now())
  }

  const onResize = () => {
    const rect = host.getBoundingClientRect()
    if (
      Math.round(rect.width) === Math.round(width) &&
      Math.round(rect.height) === Math.round(height)
    )
      return
    window.clearTimeout(resizeTimer)
    resizeTimer = window.setTimeout(() => {
      stop()
      layout()
      start()
    }, 150)
  }

  const onVisibility = () => {
    if (document.hidden) stop()
    else start()
  }

  const onMotion = () => {
    if (reduce?.matches) {
      stop()
      draw(performance.now())
    } else {
      start()
    }
  }

  const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(onResize)
  if (observer) observer.observe(host)
  else window.addEventListener('resize', onResize)
  document.addEventListener('visibilitychange', onVisibility)
  reduce?.addEventListener('change', onMotion)

  layout()
  start()

  return () => {
    stop()
    window.clearTimeout(resizeTimer)
    observer?.disconnect()
    window.removeEventListener('resize', onResize)
    document.removeEventListener('visibilitychange', onVisibility)
    reduce?.removeEventListener('change', onMotion)
  }
}
