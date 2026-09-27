import { useState } from 'react'
import type { Stage } from '@/api/schemas'
import { Button } from '@/components/ui/Button'
import { formatWindow, parseRuDate } from '@/lib/format'
import { plural, pluralWorks } from '@/lib/labels'
import styles from './NewSite.module.css'

const VISIBLE_WORKS = 4

function matchLabel(stage: Stage): string {
  switch (stage.match_kind) {
    case 'exact':
      return 'Справочник · точное'
    case 'fuzzy':
      return `Справочник · нечёткое · ${Math.round((stage.match_score ?? 0) * 100)}%`
    case 'manual':
      return 'Вручную'
    case 'none':
      return 'Не сопоставлен'
  }
}

interface StagesTableProps {
  stages: readonly Stage[]
  year: number
  onConfirmMatch: (stageId: string) => void
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

/** Таблица «Крупные этапы»: состав, окно, сопоставление со справочником, проверка по технике. */
export function StagesTable({
  stages,
  year,
  onConfirmMatch,
  onSetDates,
  pending,
}: StagesTableProps) {
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <caption className="srOnly">Крупные этапы графика</caption>
        <thead>
          <tr>
            <th scope="col">Крупный этап</th>
            <th scope="col">Вошедшие работы</th>
            <th scope="col">Плановое окно</th>
            <th scope="col">Проверка по технике</th>
          </tr>
        </thead>
        <tbody>
          {stages.map((stage) => {
            const hidden = stage.works.length - VISIBLE_WORKS
            return (
              <tr key={stage.id}>
                <th scope="row" style={{ fontWeight: 400 }}>
                  <div className={styles.cell}>
                    <span style={{ fontSize: 16 }}>{stage.name}</span>
                    <span className="sm muted">{matchLabel(stage)}</span>
                    {!stage.match_confirmed && (
                      <button
                        type="button"
                        className={styles.linkButton}
                        onClick={() => onConfirmMatch(stage.id)}
                        disabled={pending}
                      >
                        Подтвердить сопоставление
                      </button>
                    )}
                  </div>
                </th>
                <td>
                  <div className={styles.works}>
                    <span className="lab">{pluralWorks(stage.works.length)}</span>
                    {stage.works.slice(0, VISIBLE_WORKS).map((w) => (
                      <span key={w.id} className="sm muted">
                        {w.name}
                      </span>
                    ))}
                    {hidden > 0 && <span className="sm muted">ещё {hidden}</span>}
                  </div>
                </td>
                <td>
                  {stage.planned_start && stage.planned_end ? (
                    <div className={styles.cell}>
                      <span className="data">
                        {formatWindow(stage.planned_start, stage.planned_end)}
                      </span>
                      {stage.merged_windows > 1 && (
                        <span className="sm muted">
                          объединено из {stage.merged_windows}{' '}
                          {plural(stage.merged_windows, ['окна', 'окон', 'окон'])}
                        </span>
                      )}
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
                <td>
                  {stage.equipment_check ? (
                    'Проверяется'
                  ) : (
                    <span className="muted">Не проверяется · нет крупной техники</span>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
