import { useId, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { Button } from './Button'
import { useDismissable } from './useDismissable'
import styles from './Dialog.module.css'

interface DialogProps {
  title: string
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
  wide?: boolean
}

/** Модальное окно: закрывается по Escape и клику по фону, фокус уходит внутрь. */
export function Dialog({ title, onClose, children, footer, wide }: DialogProps) {
  const titleId = useId()
  const ref = useRef<HTMLDivElement>(null)

  useDismissable(onClose, ref)

  return createPortal(
    <div
      className={styles.scrim}
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className={[styles.dialog, wide && styles.wide].filter(Boolean).join(' ')}
      >
        <div className={styles.head}>
          <h2 id={titleId}>{title}</h2>
          <Button variant="ghost" size="icon" icon="close" aria-label="Закрыть" onClick={onClose} />
        </div>
        {children}
        {footer && <div className={styles.footer}>{footer}</div>}
      </div>
    </div>,
    document.body,
  )
}
