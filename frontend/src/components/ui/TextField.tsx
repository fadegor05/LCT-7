import { useId, type InputHTMLAttributes, type Ref } from 'react'
import { Icon } from './Icon'
import styles from './Field.module.css'

interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  hint?: string
  error?: string
  ref?: Ref<HTMLInputElement>
}

/** Поле ввода с подписью, подсказкой и ошибкой. Совместимо с react-hook-form `register`. */
export function TextField({ label, hint, error, id, className, ref, ...input }: TextFieldProps) {
  const autoId = useId()
  const inputId = id ?? autoId
  const noteId = `${inputId}-note`
  return (
    <div className={[styles.field, className].filter(Boolean).join(' ')}>
      <label className={styles.label} htmlFor={inputId}>
        {label}
      </label>
      <input
        ref={ref}
        id={inputId}
        className={[styles.input, error && styles.invalid].filter(Boolean).join(' ')}
        aria-invalid={error ? true : undefined}
        aria-describedby={error || hint ? noteId : undefined}
        {...input}
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
