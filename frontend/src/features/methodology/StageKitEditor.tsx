import { useState } from 'react'
import { useUpdateRule } from '@/api/methodology'
import type { EquipmentType, MarkerPeriod, Rule, Stage } from '@/api/schemas'
import { Button } from '@/components/ui/Button'
import { Callout } from '@/components/ui/Callout'
import { Card } from '@/components/ui/Card'
import { Segmented } from '@/components/ui/Segmented'
import { TextField } from '@/components/ui/TextField'
import { formatWindow } from '@/lib/format'
import { MarkerNote } from './MarkerNote'
import { SetEditor } from './SetEditor'
import styles from './Methodology.module.css'

const checkOptions = [
  { value: 'yes', label: 'Проверяется' },
  { value: 'no', label: 'Не проверяется' },
] as const

interface StageKitEditorProps {
  siteId: string
  rule: Rule
  stage: Stage | undefined
  types: readonly EquipmentType[]
  /** Периоды маркеров из последнего пересчёта; undefined — пересчёта ещё не было. */
  markers?: readonly MarkerPeriod[]
}

/**
 * Правило этапа (UC-2): проверяется ли этап по технике и каким комплектом. Комплект у этапа
 * один; у этапа без комплекта сразу открыт пустой. Правка пересчитывает выводы на сервере.
 */
export function StageKitEditor({ siteId, rule, stage, types, markers }: StageKitEditorProps) {
  const update = useUpdateRule(siteId)
  const [check, setCheck] = useState(rule.is_verifiable)
  const [reason, setReason] = useState(rule.unverifiable_reason ?? '')
  const [reasonError, setReasonError] = useState<string>()

  const dirty =
    check !== rule.is_verifiable || (!check && reason !== (rule.unverifiable_reason ?? ''))

  const saveCheck = () => {
    if (!check && !reason.trim()) return setReasonError('Укажите причину')
    setReasonError(undefined)
    update.mutate({
      ruleId: rule.id,
      data: { is_verifiable: check, unverifiable_reason: check ? null : reason.trim() },
    })
  }

  return (
    <Card>
      <div className={styles.editorHead}>
        <div>
          <h2>{rule.stage_name ?? 'Этап'}</h2>
          <p className="sm muted" style={{ marginTop: 'var(--space-1)' }}>
            Плановое окно:{' '}
            <span className="data">
              {formatWindow(stage?.planned_start ?? null, stage?.planned_end ?? null)}
            </span>
          </p>
        </div>
        <Segmented
          label="Проверка по технике"
          options={checkOptions}
          value={check ? 'yes' : 'no'}
          onChange={(v) => setCheck(v === 'yes')}
        />
      </div>

      {!check && (
        <TextField
          label="Почему этап не проверяется"
          value={reason}
          error={reasonError}
          onChange={(event) => setReason(event.target.value)}
        />
      )}
      {dirty && (
        <div className={styles.footer}>
          <p className="sm muted">
            {check && rule.sets.length === 0
              ? 'После сохранения добавьте комплект техники.'
              : 'Есть несохранённые изменения.'}
          </p>
          <Button
            variant="ghost"
            disabled={update.isPending}
            onClick={() => {
              setCheck(rule.is_verifiable)
              setReason(rule.unverifiable_reason ?? '')
            }}
          >
            Отмена
          </Button>
          <Button onClick={saveCheck} disabled={update.isPending}>
            Сохранить
          </Button>
        </div>
      )}
      {update.error && (
        <Callout tone="behind" title="Не сохранилось">
          {update.error.message}
        </Callout>
      )}

      {rule.is_verifiable && check ? (
        <>
          {rule.sets.length === 0 && (
            <Callout tone="caution" title="Комплекта нет">
              Добавьте технику в комплект, иначе этап нечем подтвердить.
            </Callout>
          )}
          {rule.sets.map((set, i) => (
            <SetEditor
              key={`${set.id}-${JSON.stringify(set.requirements)}`}
              siteId={siteId}
              ruleId={rule.id}
              set={set}
              number={i + 1}
              types={types}
              markers={markers}
            />
          ))}
          {markers && <MarkerNote markers={markers} />}
          {rule.sets.length === 0 && (
            <SetEditor siteId={siteId} ruleId={rule.id} set={null} number={1} types={types} />
          )}
        </>
      ) : (
        !dirty && (
          <Callout title="Этап не проверяется по технике">
            {rule.unverifiable_reason ?? 'Этап остаётся в графике, но статус по нему не выводится.'}
          </Callout>
        )
      )}
    </Card>
  )
}
