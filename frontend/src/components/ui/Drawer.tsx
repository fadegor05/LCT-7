import { useId, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { Button } from './Button'
import { useDismissable } from './useDismissable'
import styles from './Drawer.module.css'

interface DrawerProps {
  title: string
  onClose: () => void
  children: ReactNode
}

/** Шторка справа на всю высоту: закрывается по Escape и клику по фону. */
export function Drawer({ title, onClose, children }: DrawerProps) {
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
        className={styles.sheet}
      >
        <div className={styles.head}>
          <h2 id={titleId}>{title}</h2>
          <Button variant="ghost" size="icon" icon="close" aria-label="Закрыть" onClick={onClose} />
        </div>
        <div className={styles.body}>{children}</div>
      </div>
    </div>,
    document.body,
  )
}
