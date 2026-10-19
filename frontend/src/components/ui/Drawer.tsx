import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { Button } from './Button'
import { useDismissable } from './useDismissable'
import styles from './Drawer.module.css'

interface DrawerProps {
  title: string
  onClose: () => void
  children: ReactNode
}

/**
 * Шторка справа на всю высоту: закрывается по Escape и клику по фону.
 * Выезжает и уезжает с анимацией; `onClose` зовётся, когда уход доигран.
 */
export function Drawer({ title, onClose, children }: DrawerProps) {
  const titleId = useId()
  const scrimRef = useRef<HTMLDivElement>(null)
  const ref = useRef<HTMLDivElement>(null)
  const [closing, setClosing] = useState(false)
  // Стабильная ссылка: иначе useDismissable перезапускается на каждый рендер и дёргает фокус
  const requestClose = useCallback(() => setClosing(true), [])
  useDismissable(requestClose, ref)

  useEffect(() => {
    if (!closing) return
    // Ждём анимации ухода. Если их нет (prefers-reduced-motion, jsdom без
    // getAnimations), закрываем сразу. Только анимации фона (с его ::before) и
    // панели: бесконечный спиннер в содержимом не должен держать шторку открытой
    const scrim = scrimRef.current
    const animations = (scrim?.getAnimations?.({ subtree: true }) ?? []).filter((animation) => {
      const target = (animation.effect as KeyframeEffect | null)?.target
      return target === scrim || target === ref.current
    })
    let cancelled = false
    void Promise.allSettled(animations.map((animation) => animation.finished)).then(() => {
      if (!cancelled) onClose()
    })
    return () => {
      cancelled = true
    }
  }, [closing, onClose])

  return createPortal(
    <div
      ref={scrimRef}
      className={styles.scrim}
      data-closing={closing || undefined}
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) requestClose()
      }}
    >
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className={styles.sheet}
      >
        <div className={styles.head}>
          <h2 id={titleId}>{title}</h2>
          <Button
            variant="ghost"
            size="icon"
            icon="close"
            aria-label="Закрыть"
            onClick={requestClose}
          />
        </div>
        <div className={styles.body}>{children}</div>
      </div>
    </div>,
    document.body,
  )
}
