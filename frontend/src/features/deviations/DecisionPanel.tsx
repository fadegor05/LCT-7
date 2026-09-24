import { useState } from 'react'
import { useDecision } from '@/api/deviations'
import type { DeviationDetail, DeviationType } from '@/api/schemas'
import { Button } from '@/components/ui/Button'
import { Callout } from '@/components/ui/Callout'
import { Card } from '@/components/ui/Card'
import { TextField } from '@/components/ui/TextField'
import { formatDateTime } from '@/lib/format'
import styles from './Deviation.module.css'

interface Wording {
  confirm: string
  reject: string
  confirmed: string
  rejected: string
  hint: string
}

const DEFAULT: Wording = {
  confirm: 'Подтвердить',
  reject: 'Не подтверждается',
  confirmed: 'Гипотеза подтверждена',
  rejected: 'Не подтверждается',
  hint: 'Сервис лишь предполагает отклонение. Проверьте кадры и решите сами.',
}

const WORDING: Partial<Record<DeviationType, Wording>> = {
  idle: {
    confirm: 'Подтвердить простой',
    reject: 'Простоя не было',
    confirmed: 'Простой подтверждён',
    rejected: 'Простоя не было',
    hint: 'Сервис лишь предполагает простой. Проверьте кадры и решите сами.',
  },
}

/** Решение инженера по гипотезе (UC-10). Итог по объекту решение не меняет. */
export function DecisionPanel({ deviation }: { deviation: DeviationDetail }) {
  const w = WORDING[deviation.type] ?? DEFAULT
  const { decide, undo } = useDecision(deviation.id, deviation.site_id)
  const [comment, setComment] = useState('')
  const record = deviation.decision_record
  const error = decide.error ?? undo.error
  const busy = decide.isPending || undo.isPending

  return (
    <Card as="aside" aria-label="Решение инженера">
      <h3>Решение инженера</h3>
      {record ? (
        <>
          <p className="lab">{record.decision === 'confirmed' ? w.confirmed : w.rejected}</p>
          <p className="sm">
            Решил: {record.decided_by_name} · {formatDateTime(record.decided_at)}.
            {record.comment && ` Комментарий: ${record.comment}.`}{' '}
            {record.decision === 'confirmed'
              ? 'Остаётся в списке и в отчёте с пометкой; решение не теряется при пересчёте методики.'
              : 'Ушло в архив, не влияет на итог по объекту.'}
          </p>
          <div>
            <Button variant="ghost" size="sm" disabled={busy} onClick={() => undo.mutate()}>
              Изменить решение
            </Button>
          </div>
        </>
      ) : (
        <>
          <p className="sm">{w.hint}</p>
          <TextField
            label="Комментарий (необязательно)"
            placeholder="Например: ждёт погрузки"
            value={comment}
            onChange={(event) => setComment(event.target.value)}
          />
          <div className={styles.decisionButtons}>
            <Button
              disabled={busy}
              onClick={() => decide.mutate({ decision: 'confirmed', comment: comment || null })}
            >
              {w.confirm}
            </Button>
            <p className="sm muted">
              Останется в списке отклонений и в отчёте с пометкой «Проверено инженером». Итог по
              объекту не изменится.
            </p>
            <Button
              variant="ghost"
              disabled={busy}
              onClick={() => decide.mutate({ decision: 'rejected', comment: comment || null })}
            >
              {w.reject}
            </Button>
            <p className="sm muted">Уйдёт в архив, в отчёт не попадёт.</p>
          </div>
        </>
      )}
      {error && (
        <Callout tone="behind" title="Решение не сохранено">
          {error.message}
        </Callout>
      )}
    </Card>
  )
}
