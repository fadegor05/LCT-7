import { useId, type ReactNode, type Ref, type TextareaHTMLAttributes } from 'react'
import { Icon } from './Icon'
import styles from './Field.module.css'

interface TextAreaFieldProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string
  hint?: ReactNode
  error?: string
  ref?: Ref<HTMLTextAreaElement>
}

/** Многострочное поле ввода с подписью, подсказкой и ошибкой. Совместимо с react-hook-form `register`. */
export function TextAreaField({
  label,
  hint,
  error,
  id,
  className,
  ref,
  ...textarea
}: TextAreaFieldProps) {
  const autoId = useId()
  const textareaId = id ?? autoId
  const noteId = `${textareaId}-note`
  return (
    <div className={[styles.field, className].filter(Boolean).join(' ')}>
      <label className={styles.label} htmlFor={textareaId}>
        {label}
      </label>
      <textarea
        ref={ref}
        id={textareaId}
        className={[styles.textarea, error && styles.invalid].filter(Boolean).join(' ')}
        aria-invalid={error ? true : undefined}
        aria-describedby={error || hint ? noteId : undefined}
        {...textarea}
      />
      {error ? (
        <p id={noteId} className={`${styles.note} ${styles.error}`}>
          <Icon name="alert" size={16} />
          {error}
        </p>
      ) : hint ? (
        <p id={noteId} className={styles.note}>
          {hint}
        </p>
      ) : null}
    </div>
  )
}
