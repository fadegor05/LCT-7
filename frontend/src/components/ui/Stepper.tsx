import { Fragment } from 'react'
import { Icon } from './Icon'
import styles from './Stepper.module.css'

interface StepperProps {
  steps: readonly string[]
  /** Индекс текущего шага, с нуля. */
  current: number
}

export function Stepper({ steps, current }: StepperProps) {
  return (
    <nav aria-label="Шаги создания стройки">
      <ol className={styles.steps}>
        {steps.map((label, index) => {
          const state = index < current ? 'done' : index === current ? 'current' : 'upcoming'
          return (
            <Fragment key={label}>
              {index > 0 && <li aria-hidden="true" className={styles.line} />}
              <li
                className={`${styles.step} ${styles[state]}`}
                aria-current={state === 'current' ? 'step' : undefined}
              >
                <span className={styles.num}>
                  {state === 'done' ? <Icon name="check" size={16} /> : index + 1}
                </span>
                <span className={styles.label}>{label}</span>
              </li>
            </Fragment>
          )
        })}
      </ol>
    </nav>
  )
}
