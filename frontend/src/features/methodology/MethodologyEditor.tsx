import { useState } from 'react'
import { useEquipmentTypes, useMethodology, useApplyDefaults } from '@/api/methodology'
import { useSchedule } from '@/api/schedule'
import { useStageStatuses } from '@/api/deviations'
import type { Rule, StageStatus } from '@/api/schemas'
import { Button } from '@/components/ui/Button'
import { Callout } from '@/components/ui/Callout'
import { Card } from '@/components/ui/Card'
import { Dialog } from '@/components/ui/Dialog'
import { QueryState } from '@/components/ui/QueryState'
import { plural } from '@/lib/labels'
import { StageKitEditor } from './StageKitEditor'
import styles from './Methodology.module.css'

/**
 * Подпись этапа в списке (clean-mvp): настоящие маркеры — техника, которая отличает этап от
 * идущих одновременно (по последнему пересчёту), или «Нет отличительной техники». Пока
 * пересчёта не было — нормативная техника комплектов.
 */
function ruleSubtitle(rule: Rule, status: StageStatus | undefined): string {
  if (!rule.is_verifiable) return 'Не проверяется по технике'
  if (status?.marker_periods) {
    const names = [...new Set(status.marker_periods.map((p) => p.name.toLowerCase()))]
    return names.length ? `маркер: ${names.join(', ')}` : 'Нет отличительной техники'
  }
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
  const [showDialog, setShowDialog] = useState(false)
  const applyDefaults = useApplyDefaults(siteId)
  const statuses = useStageStatuses(siteId)
  const statusOf = (rule: Rule) => statuses.data?.find((s) => s.stage_id === rule.stage_id)

  // Выбор по умолчанию фиксируется при первой загрузке: иначе после «Не проверяется»
  // редактор перепрыгнул бы на следующий проверяемый этап.
  const rules = methodology.data
  const fallback = rules?.find((r) => r.is_verifiable) ?? rules?.[0]
  if (selected === null && fallback) setSelected(fallback.id)

  const handleApplyDefaults = () => {
    applyDefaults.mutate(undefined)
  }

  return (
    <QueryState query={methodology}>
      {(rules) => {
        const current = rules.find((r) => r.id === selected) ?? rules[0]
        if (!current) return <p className="muted">В графике нет этапов.</p>
        return (
          <div className={styles.layout}>
            <div className={styles.aside}>
              <Card>
                <div className={styles.asideHead}>
                  <h3>Этапы графика</h3>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setShowDialog(true)}
                    disabled={applyDefaults.isPending}
                  >
                    Подставить базовые комплекты
                  </Button>
                </div>
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
                      <span className="sm muted">{ruleSubtitle(rule, statusOf(rule))}</span>
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
                markers={statusOf(current)?.marker_periods}
              />
              <p className="sm muted">
                Комплект — набор техники, которым подтверждается этап. Маркер — нормативная машина,
                которой нет у этапов, идущих в это же время: только маркеры дают даты этапа.
                Логическая обязательна по смыслу работы, но одна этап не подтверждает.
                Вспомогательная может присутствовать, её отсутствие — не отклонение.
              </p>
            </div>

            {showDialog && (
              <Dialog
                title="Подставить базовые комплекты"
                onClose={() => setShowDialog(false)}
                footer={
                  <div
                    style={{ display: 'flex', gap: 'var(--space-2)', justifyContent: 'flex-end' }}
                  >
                    <Button variant="ghost" onClick={() => setShowDialog(false)}>
                      Отмена
                    </Button>
                    <Button onClick={handleApplyDefaults} disabled={applyDefaults.isPending}>
                      Применить
                    </Button>
                  </div>
                }
              >
                {applyDefaults.error && (
                  <div style={{ marginBottom: 'var(--space-2)' }}>
                    <Callout tone="behind" title="Ошибка">
                      {applyDefaults.error.message}
                    </Callout>
                  </div>
                )}
                <p>Подставить базовые комплекты для этапов без комплектов?</p>
                {applyDefaults.data && (
                  <div style={{ marginTop: 'var(--space-2)' }}>
                    <Callout tone="neutral" title="Результат">
                      {applyDefaults.data.eligible === 0
                        ? 'Нет этапов без комплекта — подставлять нечего.'
                        : `Комплекты подставлены для ${applyDefaults.data.applied} из ${applyDefaults.data.eligible} этапов.${applyDefaults.data.unmatched > 0 ? ` ${applyDefaults.data.unmatched} ${plural(applyDefaults.data.unmatched, ['этап', 'этапа', 'этапов'])} ${plural(applyDefaults.data.unmatched, ['не подошёл', 'не подошли', 'не подошли'])} ни под одно правило — задайте вручную.` : ''}`}
                    </Callout>
                  </div>
                )}
              </Dialog>
            )}
          </div>
        )
      }}
    </QueryState>
  )
}
