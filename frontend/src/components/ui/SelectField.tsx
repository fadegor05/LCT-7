import { useId, type SelectHTMLAttributes } from 'react'
import styles from './Field.module.css'

interface SelectFieldProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string
  options: readonly { value: string; label: string }[]
}

export function SelectField({ label, options, id, className, ...select }: SelectFieldProps) {
  const autoId = useId()
  const selectId = id ?? autoId
  return (
    <div className={[styles.field, className].filter(Boolean).join(' ')}>
      <label className={styles.label} htmlFor={selectId}>
        {label}
      </label>
      <span className={styles.select}>
        <select id={selectId} className={styles.input} {...select}>
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </span>
    </div>
  )
}
