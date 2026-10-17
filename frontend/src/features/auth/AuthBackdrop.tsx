import { useEffect, useRef } from 'react'
import { startBackdrop } from './backdrop'
import styles from './AuthBackdrop.module.css'

/**
 * Фон страниц входа и регистрации: фигуры тетриса в виде строительной техники падают за карточкой.
 * Декоративный: скрыт от экранных читалок и пропускает клики. Родитель задаёт `position: relative`.
 */
export function AuthBackdrop() {
  const ref = useRef<HTMLCanvasElement>(null)

  useEffect(() => (ref.current ? startBackdrop(ref.current) : undefined), [])

  return <canvas ref={ref} className={styles.canvas} aria-hidden="true" />
}
