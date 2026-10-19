import { useState } from 'react'
import { useDecision } from '@/api/deviations'
import type { DeviationDetail } from '@/api/schemas'
import { Button } from '@/components/ui/Button'
import { Callout } from '@/components/ui/Callout'
import { Card } from '@/components/ui/Card'
import { TextAreaField } from '@/components/ui/TextAreaField'
import { formatDateTime } from '@/lib/format'
import { decisionWords } from './decisionWords'
import styles from './Deviation.module.css'

/**
 * «Решение инженера» по гипотезе (clean-mvp, §8.8). Подписывает вошедший пользователь;
 * решение переживает пересчёт. Итог по объекту от него не зависит.
 */
export function DecisionPanel({
  siteId,
  deviation: d,
}: {
  siteId: string
  deviation: DeviationDetail
}) {
  const decide = useDecision(siteId, d.id)
  const [comment, setComment] = useState('')
  const words = decisionWords(d.type)
  const decision = d.decision

  if (decision) {
    return (
      <Card className={styles.decision} aria-label="Решение инженера">
        <h3>{decision.decision === 'confirmed' ? words.confirmed : words.rejected}</h3>
        <p className="sm">
          Решил: {decision.decided_by_name} · {formatDateTime(decision.decided_at)}
          {decision.comment && `. Комментарий: ${decision.comment.replace(/[.!?…]+$/, '')}`}.{' '}
          {decision.decision === 'confirmed'
            ? 'Остаётся в списке и в отчёте с пометкой; решение не теряется при пересчёте.'
            : 'Ушло в архив, в списках и отчёте его нет; на итог по объекту не влияет.'}
        </p>
        <Button
          variant="secondary"
          disabled={decide.isPending}
          onClick={() => decide.mutate({ decision: null })}
        >
          Изменить решение
        </Button>
        {decide.error && <Callout tone="behind">{decide.error.message}</Callout>}
      </Card>
    )
  }

  const submit = (choice: 'confirmed' | 'rejected') =>
    decide.mutate(
      { decision: choice, comment: comment.trim() || null },
      { onSuccess: () => setComment('') },
    )

  return (
    <Card className={styles.decision} aria-label="Решение инженера">
      <h3>Решение инженера</h3>
      <p className="sm muted">
        Сервис лишь предполагает {d.type === 'idle' ? 'простой' : 'отклонение'}. Проверьте снимки и
        решите сами.
      </p>
      <TextAreaField
        label="Комментарий (необязательно)"
        maxLength={2000}
        value={comment}
        onChange={(e) => setComment(e.target.value)}
      />
      <div className={styles.choice}>
        <Button disabled={decide.isPending} onClick={() => submit('confirmed')}>
          {words.confirm}
        </Button>
        <span className="sm muted">
          Останется в списке отклонений и в отчёте с пометкой «Проверено инженером». Итог по объекту
          не изменится.
        </span>
      </div>
      <div className={styles.choice}>
        <Button variant="secondary" disabled={decide.isPending} onClick={() => submit('rejected')}>
          {words.reject}
        </Button>
        <span className="sm muted">Уйдёт в архив, в отчёт не попадёт.</span>
      </div>
      {decide.error && <Callout tone="behind">{decide.error.message}</Callout>}
    </Card>
  )
}
