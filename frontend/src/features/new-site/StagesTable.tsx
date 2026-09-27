import { useState } from 'react'
import type { Stage } from '@/api/schemas'
import { Button } from '@/components/ui/Button'
import { formatWindow, parseRuDate } from '@/lib/format'
import styles from './NewSite.module.css'

interface StagesTableProps {
  stages: readonly Stage[]
  year: number
  onSetDates: (stageId: string, start: string, end: string) => void
  pending?: boolean
}

function ManualDates({
  stage,
  year,
  onSave,
  pending,
}: {
  stage: Stage
  year: number
  onSave: (start: string, end: string) => void
  pending?: boolean
}) {
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [error, setError] = useState<string | null>(null)

  const save = () => {
    const s = parseRuDate(start, year)
    const e = parseRuDate(end, year)
    if (!s || !e) return setError('Даты в формате дд.мм')
    if (e < s) return setError('Окончание раньше начала')
    setError(null)
    onSave(s, e)
  }

  return (
    <div className={styles.cell}>
      <div className={styles.dates}>
        <input
          className={styles.dateInput}
          placeholder="дд.мм"
          aria-label={`Дата начала: ${stage.name}`}
          value={start}
          onChange={(event) => setStart(event.target.value)}
        />
        <span aria-hidden="true">—</span>
        <input
          className={styles.dateInput}
          placeholder="дд.мм"
          aria-label={`Дата окончания: ${stage.name}`}
          value={end}
          onChange={(event) => setEnd(event.target.value)}
        />
        <Button variant="ghost" size="sm" onClick={save} disabled={pending}>
          Задать
        </Button>
      </div>
      <span
        className="sm"
        style={{ color: error ? 'var(--status-behind)' : 'var(--caution)' }}
        role={error ? 'alert' : undefined}
      >
        {error ?? 'Дат в файле нет: задайте вручную'}
      </span>
    </div>
  )
}

/** Таблица этапов графика: порядок и плановое окно; даты, которых нет в файле, задаются вручную. */
export function StagesTable({ stages, year, onSetDates, pending }: StagesTableProps) {
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <caption className="srOnly">Этапы графика</caption>
        <thead>
          <tr>
            <th scope="col">№</th>
            <th scope="col">Этап</th>
            <th scope="col">Плановое окно</th>
          </tr>
        </thead>
        <tbody>
          {stages.map((stage) => (
            <tr key={stage.id}>
              <td className="data">{stage.position}</td>
              <th scope="row" style={{ fontWeight: 400, fontSize: 16 }}>
                {stage.name}
              </th>
              <td>
                {stage.planned_start && stage.planned_end ? (
                  <div className={styles.cell}>
                    <span className="data">
                      {formatWindow(stage.planned_start, stage.planned_end)}
                    </span>
                    {stage.dates_source === 'manual' && (
                      <span className="sm muted">задано вручную</span>
                    )}
                  </div>
                ) : (
                  <ManualDates
                    stage={stage}
                    year={year}
                    pending={pending}
                    onSave={(start, end) => onSetDates(stage.id, start, end)}
                  />
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
