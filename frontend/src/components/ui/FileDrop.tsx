import { useRef, useState } from 'react'
import { Button } from './Button'
import { Icon } from './Icon'
import styles from './FileDrop.module.css'

interface FileDropProps {
  title: string
  hint: string
  accept?: string
  multiple?: boolean
  disabled?: boolean
  buttonLabel?: string
  onFiles: (files: File[]) => void
}

/** Зона «перетащите файл» + кнопка выбора (скрытый input). */
export function FileDrop({
  title,
  hint,
  accept,
  multiple,
  disabled,
  buttonLabel = 'Выбрать файл',
  onFiles,
}: FileDropProps) {
  const input = useRef<HTMLInputElement>(null)
  const [active, setActive] = useState(false)

  const take = (list: FileList | null) => {
    const files = list ? Array.from(list) : []
    if (files.length > 0) onFiles(files)
  }

  return (
    <div
      className={[styles.drop, active && styles.active].filter(Boolean).join(' ')}
      data-testid="file-drop"
      onDragOver={(event) => {
        event.preventDefault()
        setActive(true)
      }}
      onDragLeave={() => setActive(false)}
      onDrop={(event) => {
        event.preventDefault()
        setActive(false)
        if (!disabled) take(event.dataTransfer.files)
      }}
    >
      <Icon name="upload" size={24} />
      <p className={styles.title}>{title}</p>
      <p className="sm muted">{hint}</p>
      <Button variant="ghost" disabled={disabled} onClick={() => input.current?.click()}>
        {buttonLabel}
      </Button>
      <input
        ref={input}
        type="file"
        hidden
        accept={accept}
        multiple={multiple}
        aria-label={buttonLabel}
        onChange={(event) => {
          take(event.target.files)
          event.target.value = ''
        }}
      />
    </div>
  )
}
