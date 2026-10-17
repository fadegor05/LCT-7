import { useEffect, useRef } from 'react'
import { signalBackdrop, startBackdrop, type BackdropMode } from './backdrop'
import styles from './AuthBackdrop.module.css'

/**
 * Фон страниц входа и регистрации: фигуры тетриса в виде строительной техники падают за карточкой.
 * Декоративный: скрыт от экранных читалок и пропускает клики. Родитель задаёт `position: relative`.
 * `mode="build"` — стопку достраивают поля формы через `setBackdropProgress`.
 */
export function AuthBackdrop({ mode = 'ambient' }: { mode?: BackdropMode }) {
  const ref = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    if (!ref.current) return undefined
    // Эксперимент: `?speeds=same` — все машины падают с одной скоростью.
    const varied = new URLSearchParams(window.location.search).get('speeds') !== 'same'
    return startBackdrop(ref.current, { mode, varied })
  }, [mode])

  return (
    <>
      <canvas ref={ref} className={styles.canvas} aria-hidden="true" />
      {import.meta.env.DEV && new URLSearchParams(window.location.search).has('demo') && (
        <div className={styles.demo} role="group" aria-label="Демо эффектов фона">
          <button type="button" onClick={() => signalBackdrop('success')}>
            Успех
          </button>
          <button type="button" onClick={() => signalBackdrop('error')}>
            Ошибка
          </button>
        </div>
      )}
    </>
  )
}
