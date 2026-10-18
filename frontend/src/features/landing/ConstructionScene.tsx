import { useEffect, useId, useRef } from 'react'
import { LAYERS, type Ctx, type LayerName } from './scene/ctx'
import { VIEW } from './scene/geometry'
import { createScene } from './scene/scene'
import styles from './ConstructionScene.module.css'

/**
 * Сцена лендинга: башенный кран по одному ставит на башню блоки-этапы графика.
 * Цвет блока — статус отклонения, подписи — этап и отставание. Рисуется императивно в SVG:
 * за кадр обновляется около сорока атрибутов, перерисовок React нет.
 */
export function ConstructionScene() {
  const uid = useId().replace(/:/g, '')
  const svg = useRef<SVGSVGElement>(null)

  useEffect(() => {
    const root = svg.current
    if (!root) return undefined
    const layers = Object.fromEntries(
      LAYERS.map((name) => [name, root.querySelector<SVGGElement>(`[data-layer="${name}"]`)]),
    ) as Record<LayerName, SVGGElement>
    const ctx: Ctx = { layers, ref: (n) => `url(#${uid}-${n})`, id: (n) => `${uid}-${n}` }
    const roofClip = root.querySelector<SVGPolygonElement>(`#${uid}-roofclip polygon`)!
    const scene = createScene(ctx, roofClip)

    // «Уменьшить движение»: показываем собранную башню без анимации.
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
      scene.render(scene.end + 1, 0)
      return () => LAYERS.forEach((n) => layers[n].replaceChildren())
    }

    // Время сцены копится по кадрам: пока блок вне экрана или вкладка в фоне, кран стоит и не греет CPU.
    let time = 0
    let last = 0
    let raf = 0
    let visible = true
    const frame = (now: number) => {
      const dt = Math.max(0, Math.min(0.05, (now - last) / 1000))
      last = now
      time += dt
      const t = time % scene.cycle
      if (t < dt + 0.02) scene.reset()
      scene.render(t, dt)
      raf = visible ? requestAnimationFrame(frame) : 0
    }
    const start = () => {
      if (raf) return
      last = performance.now()
      raf = requestAnimationFrame(frame)
    }
    const observer =
      typeof IntersectionObserver === 'undefined'
        ? null
        : new IntersectionObserver(
            ([entry]) => {
              visible = entry?.isIntersecting ?? true
              if (visible) start()
            },
            { threshold: 0.05 },
          )
    observer?.observe(root)
    start()
    return () => {
      observer?.disconnect()
      if (raf) cancelAnimationFrame(raf)
      LAYERS.forEach((n) => layers[n].replaceChildren())
    }
  }, [uid])

  return (
    <svg
      ref={svg}
      className={styles.scene}
      viewBox={`${VIEW.x} ${VIEW.y} ${VIEW.w} ${VIEW.h}`}
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        <pattern
          id={`${uid}-hatch`}
          width="8"
          height="8"
          patternUnits="userSpaceOnUse"
          patternTransform="rotate(45)"
        >
          <path d="M0 0V8" stroke="#fff" strokeWidth="3" opacity=".35" />
        </pattern>
        <linearGradient id={`${uid}-shl`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#fff" stopOpacity=".2" />
          <stop offset=".55" stopColor="#fff" stopOpacity="0" />
          <stop offset="1" stopColor="#000" stopOpacity=".14" />
        </linearGradient>
        <linearGradient id={`${uid}-shr`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#fff" stopOpacity=".06" />
          <stop offset=".5" stopColor="#000" stopOpacity=".05" />
          <stop offset="1" stopColor="#000" stopOpacity=".26" />
        </linearGradient>
        <linearGradient id={`${uid}-glass`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#e8f3fb" />
          <stop offset=".55" stopColor="#a9c9de" />
          <stop offset="1" stopColor="#7ea3bb" />
        </linearGradient>
        <radialGradient id={`${uid}-site`} cx=".5" cy=".5" r=".5">
          <stop offset="0" stopColor="#e7e5e0" />
          <stop offset=".7" stopColor="#efeeea" />
          <stop offset="1" stopColor="#efeeea" stopOpacity="0" />
        </radialGradient>
        <filter id={`${uid}-blur6`} x="-30%" y="-60%" width="160%" height="220%">
          <feGaussianBlur stdDeviation="6" />
        </filter>
        <filter id={`${uid}-blur3`} x="-30%" y="-60%" width="160%" height="220%">
          <feGaussianBlur stdDeviation="3" />
        </filter>
        <filter id={`${uid}-chipsh`} x="-10%" y="-20%" width="130%" height="160%">
          <feDropShadow dx="0" dy="3" stdDeviation="4" floodColor="#141414" floodOpacity=".12" />
        </filter>
        <clipPath id={`${uid}-roofclip`}>
          <polygon points="0,0" />
        </clipPath>
      </defs>
      {/* Слои глубины для параллакса: небо далеко, площадка и кран в середине, рабочие у камеры. */}
      <g data-layer="sky" data-depth="0.3" />
      <g data-depth="0.9">
        <g data-layer="ground" />
        <g data-layer="gshadow" />
        <g data-layer="props" />
        <g data-layer="crane" />
        <g data-layer="blocks" />
        <g data-layer="fx" />
      </g>
      <g data-layer="front" data-depth="1.5" />
      <g data-depth="0.9">
        <g data-layer="labels" />
        <g data-layer="rig" />
      </g>
    </svg>
  )
}
