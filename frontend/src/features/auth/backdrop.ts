import {
  PIECE_TOKENS,
  TETROMINOES,
  TETROMINO_TYPES,
  TOOL_TOKEN,
  pieceSvg,
  type TetrominoType,
} from './tetrominoes'
import { WARMUP_SHARE, Well, type BoardCell, type FallingPiece } from './well'

/** Базовый темп падения: клетка за столько; фигура пересекает экран за 6–9 секунд. */
const STEP_MS = 400
/** Вспышка и исчезновение заполненного ряда. */
const CLEAR_MS = 260
/** Оседание высокой стопки. */
const SINK_MS = 700
/** Новая фигура — через 0,9–1,8 с. */
const SPAWN_MS = 900
/** Ввод в поле сбрасывает фигуру не чаще, чем раз в столько. */
const TYPE_DROP_MS = 250
/** Вспышка верхнего ряда по кнопке входа. */
const PULSE_MS = 320
/** Встряска стопки при ошибке входа. */
const SHAKE_MS = 420
/** Успех: ряды гаснут волной снизу вверх за столько, затем переход. */
const SUCCESS_MS = 620
const WAVE_ROW_MS = 260
/** Пока фокус в поле, фон замедляется до этой доли скорости. */
const CALM_SPEED = 0.3
/** Если после успеха переход не случился (демо), стопка строится заново через столько. */
const REGROW_MS = 900
/** Приземление: затухающий отскок, длительность и высота в долях клетки. */
const LAND_MS = 360
const LAND_HOP = 0.14
/** Пыль из-под машины при приземлении. */
const DUST_MS = 340
const DUST_GRAVITY = 160
/** Стройка каскадом: падение одной фигуры, общий разброс стартов и наибольший интервал. */
const BUILD_FALL_MS = 420
const BUILD_SPREAD_MS = 1100
const BUILD_STAGGER_MS = 70
/** Регистрация: фундамент и слой за каждое верно заполненное поле, в долях высоты колодца. */
const FOUNDATION_SHARE = 0.08
const LAYER_SHARE = 0.1

/** Темп машин: тяжёлые опускаются медленнее. Поверх — разброс ±10 %. */
const PIECE_SPEED: Record<TetrominoType, number> = {
  I: 1,
  O: 1.15,
  T: 0.75,
  S: 0.9,
  Z: 1.2,
  J: 0.8,
  L: 1,
}

export type BackdropSignal = 'error' | 'success'

/** `ambient` — стройка идёт сама (вход); `build` — стопку достраивают поля формы (регистрация). */
export type BackdropMode = 'ambient' | 'build'

export interface BackdropOptions {
  mode?: BackdropMode
  /** У каждой машины свой темп. */
  varied?: boolean
}

const signals = new EventTarget()
let animating = 0

/** Страница сообщает фону о результате входа: ошибка встряхивает стопку, успех гасит её. */
export function signalBackdrop(kind: BackdropSignal): void {
  signals.dispatchEvent(new Event(kind))
}

/** Регистрация: сколько полей заполнено верно. Каждое новое добавляет слой стройки. */
export function setBackdropProgress(steps: number): void {
  signals.dispatchEvent(new CustomEvent('progress', { detail: steps }))
}

/** Выполняет `fn`, когда фон доиграет волну успеха; без анимации — сразу. */
export function afterBackdrop(fn: () => void): void {
  if (animating > 0) window.setTimeout(fn, SUCCESS_MS)
  else fn()
}

/** Клетка на экране: 48 px, как высота поля ввода; на узких экранах меньше. */
export function cellSize(width: number): number {
  if (width >= 900) return 48
  if (width >= 600) return 40
  return 32
}

const clamp01 = (k: number) => Math.min(1, Math.max(0, k))
const easeOut = (k: number) => 1 - (1 - clamp01(k)) ** 3
const easeIn = (k: number) => clamp01(k) ** 2

interface Incoming {
  piece: FallingPiece
  start: number
  /** На сколько рядов фигура падает до своего места. */
  drop: number
  landed: boolean
}

interface Dust {
  x: number
  y: number
  vx: number
  vy: number
  size: number
  start: number
}

/**
 * Запускает фон «Стройтетрис» на canvas и возвращает функцию остановки.
 * Canvas растягивается на родителя. Без 2D-контекста фон не рисуется; при
 * `prefers-reduced-motion` стопка статична; на скрытой вкладке анимация на паузе.
 */
export function startBackdrop(
  canvas: HTMLCanvasElement,
  { mode = 'ambient', varied = true }: BackdropOptions = {},
): () => void {
  const context = canvas.getContext('2d')
  if (!context) return () => {}
  const ctx: CanvasRenderingContext2D = context
  const host = canvas.parentElement ?? canvas
  const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)')
  const tokens = getComputedStyle(document.documentElement)
  const color = (token: string) => tokens.getPropertyValue(token).trim()
  const accent = color('--accent')
  const success = color('--status-ontrack')
  const dustColor = color('--line-control')
  const tool = color(TOOL_TOKEN)

  let well = new Well(0, 0)
  let width = 0
  let height = 0
  let size = 0
  let dpr = 1
  let ox = 0
  let oy = 0
  let images = new Map<TetrominoType, HTMLImageElement>()
  let clearing: {
    rows: number[]
    start: number
    ms: number
    flash: string
    wave: boolean
    regrow: boolean
  } | null = null
  let incoming = new Map<BoardCell, Incoming>()
  let landed = new Map<BoardCell, number>()
  let dust: Dust[] = []
  let motion = new Map<FallingPiece, { speed: number; progress: number }>()
  let pulse: { row: number; start: number } | null = null
  let sink: { rows: number; start: number } | null = null
  let shake = -Infinity
  let speed = 1
  let speedTarget = 1
  let built = 0
  let buildUntil = 0
  let regrowAt = 0
  let lastFrame = 0
  let lastTypeDrop = 0
  let nextSpawn = 0
  let raf = 0
  let resizeTimer = 0

  const animated = () => !reduce?.matches

  const targetHeight = () =>
    Math.round(
      well.rows * (mode === 'build' ? FOUNDATION_SHARE + built * LAYER_SHARE : WARMUP_SHARE),
    )

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

  const pieceCells = (piece: FallingPiece) =>
    TETROMINOES[piece.type].cells.flatMap(([cx, cy]) => {
      const cell = well.board[piece.y + cy]?.[piece.x + cx]
      return cell ? [cell] : []
    })

  /** Приземление: отскок клеток фигуры и пыль из-под её нижнего края. */
  const land = (piece: FallingPiece, at: number) => {
    for (const cell of pieceCells(piece)) landed.set(cell, at)
    const cells = TETROMINOES[piece.type].cells
    for (const [cx, cy] of cells) {
      if (cells.some(([x, y]) => x === cx && y === cy + 1)) continue
      const bottom = oy + (piece.y + cy + 1) * size - size * 0.08
      for (const side of [-1, 1]) {
        dust.push({
          x: ox + (piece.x + cx + 0.5 + side * 0.35) * size,
          y: bottom,
          vx: side * (25 + Math.random() * 35),
          vy: -(20 + Math.random() * 30),
          size: 2 + Math.random() * 2,
          start: at,
        })
      }
    }
  }

  /** Стройка каскадом: фигуры уже лежат в стопке, а на экране падают туда одна за другой. */
  const cascade = (pieces: FallingPiece[], now: number, spread = BUILD_SPREAD_MS) => {
    if (!pieces.length) return
    const stagger = Math.min(BUILD_STAGGER_MS, spread / pieces.length)
    pieces.forEach((piece, i) => {
      const entry = {
        piece,
        start: now + i * stagger,
        drop: piece.y + TETROMINOES[piece.type].h,
        landed: false,
      }
      for (const cell of pieceCells(piece)) incoming.set(cell, entry)
    })
    buildUntil = Math.max(buildUntil, now + (pieces.length - 1) * stagger + BUILD_FALL_MS)
  }

  /** Строит стопку до нужной высоты: каскадом, а без анимации — сразу. */
  const build = (now: number, spread?: number) => {
    const pieces = well.fillTo(targetHeight())
    if (animated()) cascade(pieces, now, spread)
    else well.removeRows(well.fullRows())
  }

  const hop = (cell: BoardCell, now: number) => {
    const at = landed.get(cell)
    if (at === undefined) return 0
    const k = (now - at) / LAND_MS
    if (k >= 1) {
      landed.delete(cell)
      return 0
    }
    return LAND_HOP * Math.abs(Math.sin(k * Math.PI * 2)) * (1 - k) ** 2
  }

  /** Насколько погас ряд: волна идёт от нижнего ряда к верхнему. */
  const rowFade = (r: number, now: number) => {
    if (!clearing) return 0
    if (!clearing.wave) return (now - clearing.start) / clearing.ms
    const order = [...clearing.rows].sort((a, b) => b - a)
    const step = (clearing.ms - WAVE_ROW_MS) / Math.max(1, order.length - 1)
    return (now - clearing.start - order.indexOf(r) * step) / WAVE_ROW_MS
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
    const shakeK = (now - shake) / SHAKE_MS
    const jolt = shakeK < 1 ? Math.sin(shakeK * Math.PI * 7) * 6 * (1 - shakeK) : 0

    well.board.forEach((row, r) => {
      const clearingRow = clearing?.rows.includes(r)
      ctx.globalAlpha = clearingRow ? 1 - easeOut(rowFade(r, now)) : 1
      row.forEach((cell, c) => {
        if (!cell) return
        const entry = incoming.get(cell)
        let offset = -hop(cell, now)
        if (entry && !entry.landed) {
          const k = (now - entry.start) / BUILD_FALL_MS
          if (k < 0) return
          offset = -entry.drop * (1 - easeIn(k))
        }
        drawCell(
          cell.type,
          cell.cx,
          cell.cy,
          ox + c * size + jolt,
          oy + (r + offset) * size + shift,
        )
      })
    })

    if (clearing) {
      ctx.fillStyle = clearing.flash
      for (const r of clearing.rows) {
        const k = rowFade(r, now)
        if (k < 0) continue
        ctx.globalAlpha = 0.6 * Math.sin(Math.PI * Math.min(1, k * 1.6))
        ctx.fillRect(ox, oy + r * size + shift, well.cols * size, size)
      }
    }
    if (pulse) {
      const k = (now - pulse.start) / PULSE_MS
      ctx.fillStyle = accent
      ctx.globalAlpha = 0.45 * Math.sin(Math.PI * Math.min(1, k))
      ctx.fillRect(ox, oy + pulse.row * size + shift, well.cols * size, size)
      if (k >= 1) pulse = null
    }

    ctx.fillStyle = dustColor
    dust = dust.filter((d) => {
      const t = (now - d.start) / 1000
      const k = t / (DUST_MS / 1000)
      if (k >= 1) return false
      if (k < 0) return true
      ctx.globalAlpha = 0.55 * (1 - k)
      const x = d.x + d.vx * t
      const y = d.y + d.vy * t + (DUST_GRAVITY * t * t) / 2
      ctx.fillRect(x - d.size / 2, y - d.size / 2, d.size, d.size)
      return true
    })

    ctx.globalAlpha = 1
    for (const piece of well.falling) {
      const offset = motion.get(piece)?.progress ?? 0
      for (const [cx, cy] of TETROMINOES[piece.type].cells) {
        drawCell(
          piece.type,
          cx,
          cy,
          ox + (piece.x + cx) * size,
          oy + (piece.y + cy + offset) * size,
        )
      }
    }
  }

  const settle = (now: number) => {
    const rows = well.sinkIfHigh()
    if (rows) sink = { rows, start: now }
  }

  const spawn = () => {
    const piece = well.spawn()
    if (piece) {
      const pace = varied ? PIECE_SPEED[piece.type] * (0.9 + Math.random() * 0.2) : 1
      motion.set(piece, { speed: pace, progress: 0 })
    }
    return piece
  }

  const frame = (now: number) => {
    const dt = lastFrame ? now - lastFrame : 0
    lastFrame = now
    speed += (speedTarget - speed) * Math.min(1, dt / 300)

    for (const entry of new Set(incoming.values())) {
      if (entry.landed || now < entry.start + BUILD_FALL_MS) continue
      entry.landed = true
      land(entry.piece, entry.start + BUILD_FALL_MS)
    }
    if (now >= buildUntil) incoming.clear()

    if (clearing) {
      if (now - clearing.start >= clearing.ms) {
        well.removeRows(clearing.rows)
        if (clearing.regrow) regrowAt = now + REGROW_MS
        clearing = null
        settle(now)
      }
    } else {
      let touched = false
      for (const piece of [...well.falling]) {
        const m = motion.get(piece) ?? { speed: 1, progress: 0 }
        motion.set(piece, m)
        m.progress += (dt * speed * m.speed) / STEP_MS
        while (m.progress >= 1) {
          m.progress -= 1
          if (well.advance(piece)) {
            land(piece, now)
            motion.delete(piece)
            touched = true
            break
          }
        }
      }
      // На регистрации стопка только растёт: полные ряды фундамента не гасим.
      if (mode === 'ambient' && now >= buildUntil) {
        const full = well.fullRows()
        if (full.length) {
          clearing = {
            rows: full,
            start: now,
            ms: CLEAR_MS,
            flash: accent,
            wave: false,
            regrow: false,
          }
        } else if (touched) {
          settle(now)
        }
      }
    }

    if (regrowAt && now >= regrowAt) {
      regrowAt = 0
      build(now)
    }
    if (mode === 'ambient' && !clearing && !regrowAt && now >= buildUntil && now >= nextSpawn) {
      spawn()
      nextSpawn = now + (SPAWN_MS * (1 + Math.random())) / speed
    }
    draw(now)
    raf = requestAnimationFrame(frame)
  }

  const start = () => {
    if (raf || reduce?.matches || document.hidden) return
    lastFrame = 0
    animating++
    raf = requestAnimationFrame(frame)
  }

  const stop = () => {
    if (!raf) return
    cancelAnimationFrame(raf)
    raf = 0
    animating--
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
    clearing = null
    sink = null
    pulse = null
    incoming = new Map()
    landed = new Map()
    dust = []
    motion = new Map()
    buildUntil = 0
    regrowAt = 0
    buildImages()
    build(performance.now())
    draw(performance.now())
  }

  /** Ввод в поле сбрасывает фигуру: фон отвечает на набор логина и пароля. */
  const onInput = () => {
    const now = performance.now()
    if (!raf || mode !== 'ambient' || now - lastTypeDrop < TYPE_DROP_MS) return
    lastTypeDrop = now
    if (spawn()) nextSpawn = now + SPAWN_MS
  }

  /** Отправка формы подсвечивает верх стопки. */
  const onSubmit = () => {
    const top = well.rows - well.stackHeight()
    if (raf && top < well.rows) pulse = { row: top, start: performance.now() }
  }

  const onError = () => {
    if (raf) shake = performance.now()
  }

  /** Успех: стопка гаснет волной снизу вверх, падающие фигуры исчезают. */
  const onSuccess = () => {
    if (!raf) return
    const rows = well.board.flatMap((row, r) => (row.some(Boolean) ? [r] : []))
    well.falling.length = 0
    motion.clear()
    incoming.clear()
    buildUntil = 0
    clearing = {
      rows,
      start: performance.now(),
      ms: SUCCESS_MS,
      flash: success,
      wave: true,
      regrow: true,
    }
  }

  /** Регистрация: новое верно заполненное поле добавляет слой стройки. */
  const onProgress = (event: Event) => {
    const steps = (event as CustomEvent<number>).detail
    const grew = steps > built
    built = steps
    if (!grew || mode !== 'build' || clearing) return
    build(performance.now(), 500)
    if (!raf) draw(performance.now())
  }

  /** Пока фокус в поле, фон замедляется и бледнеет; без фокуса — оживает. */
  const onFocus = () => {
    const active = document.activeElement
    const typing = active instanceof HTMLInputElement && host.contains(active)
    speedTarget = typing ? CALM_SPEED : 1
    canvas.dataset.calm = String(typing)
  }
  const onFocusOut = () => window.setTimeout(onFocus)

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

  host.addEventListener('input', onInput)
  host.addEventListener('submit', onSubmit)
  host.addEventListener('focusin', onFocus)
  host.addEventListener('focusout', onFocusOut)
  signals.addEventListener('error', onError)
  signals.addEventListener('success', onSuccess)
  signals.addEventListener('progress', onProgress)
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
    host.removeEventListener('input', onInput)
    host.removeEventListener('submit', onSubmit)
    host.removeEventListener('focusin', onFocus)
    host.removeEventListener('focusout', onFocusOut)
    signals.removeEventListener('error', onError)
    signals.removeEventListener('success', onSuccess)
    signals.removeEventListener('progress', onProgress)
  }
}
