import { useState } from 'react'
import { useEquipmentTypes, useMethodology } from '@/api/methodology'
import { useSchedule } from '@/api/schedule'
import type { Rule } from '@/api/schemas'
import { Card } from '@/components/ui/Card'
import { QueryState } from '@/components/ui/QueryState'
import { plural } from '@/lib/labels'
import { StageKitEditor } from './StageKitEditor'
import styles from './Methodology.module.css'

/** Маркеры — нормативная техника всех комплектов: только она даёт даты этапа (§8 п. 8). */
function ruleSubtitle(rule: Rule): string {
  if (!rule.is_verifiable) return 'Не проверяется по технике'
  const markers = [
    ...new Set(
      rule.sets.flatMap((s) =>
        s.requirements
          .filter((r) => r.obligation === 'normative')
          .map((r) => r.equipment_type.title.toLowerCase()),
      ),
    ),
  ]
  const sets = `${rule.sets.length} ${plural(rule.sets.length, ['комплект', 'комплекта', 'комплектов'])}`
  return markers.length ? `${sets} · маркер: ${markers.join(', ')}` : `${sets} · маркеров нет`
}

/** Методика «этап → техника»: общий редактор для шага 2 создания и вкладки объекта. */
export function MethodologyEditor({ siteId }: { siteId: string }) {
  const methodology = useMethodology(siteId)
  const types = useEquipmentTypes()
  const schedule = useSchedule(siteId)
  const [selected, setSelected] = useState<string | null>(null)

  // Выбор по умолчанию фиксируется при первой загрузке: иначе после «Не проверяется»
  // редактор перепрыгнул бы на следующий проверяемый этап.
  const rules = methodology.data
  const fallback = rules?.find((r) => r.is_verifiable) ?? rules?.[0]
  if (selected === null && fallback) setSelected(fallback.id)

  return (
    <QueryState query={methodology}>
      {(rules) => {
        const current = rules.find((r) => r.id === selected) ?? rules[0]
        if (!current) return <p className="muted">В графике нет этапов.</p>
        return (
          <div className={styles.layout}>
            <div className={styles.aside}>
              <Card>
                <h3>Этапы графика</h3>
                <div className={styles.stageList}>
                  {rules.map((rule) => (
                    <button
                      key={rule.id}
                      type="button"
                      className={styles.stageBtn}
                      aria-pressed={rule.id === current.id}
                      onClick={() => setSelected(rule.id)}
                    >
                      <span>{rule.stage_name ?? 'Этап'}</span>
                      <span className="sm muted">{ruleSubtitle(rule)}</span>
                    </button>
                  ))}
                </div>
              </Card>
            </div>
            <div className={styles.main}>
              <StageKitEditor
                key={`${current.id}-${current.updated_at}`}
                siteId={siteId}
                rule={current}
                stage={schedule.data?.stages.find((s) => s.id === current.stage_id)}
                types={types.data ?? []}
              />
              <p className="sm muted">
                Комплект — набор техники, которым подтверждается этап; комплектов может быть
                несколько (альтернативные способы работ). Нормативная техника — маркер: только она
                даёт даты этапа. Логическая обязательна по смыслу работы, но одна этап не
                подтверждает. Вспомогательная может присутствовать, её отсутствие — не отклонение.
              </p>
            </div>
          </div>
        )
      }}
    </QueryState>
  )
}
