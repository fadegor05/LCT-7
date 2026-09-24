import { useState } from 'react'
import { useEquipmentClasses, useMethodology, useUpdateStageKit } from '@/api/methodology'
import type { StageKit } from '@/api/schemas'
import { Callout } from '@/components/ui/Callout'
import { Card } from '@/components/ui/Card'
import { QueryState } from '@/components/ui/QueryState'
import { StageKitEditor } from './StageKitEditor'
import styles from './Methodology.module.css'

function stageSubtitle(kit: StageKit): string {
  if (!kit.equipment_check) return 'Не проверяется по технике'
  const markers = kit.rules.filter((r) => r.is_marker).map((r) => r.name.toLowerCase())
  return markers.length ? `Комплект 1 · маркер: ${markers.join(', ')}` : 'Комплект 1 · маркеров нет'
}

/** Методика «этап → техника»: общий редактор для шага 2 создания и вкладки объекта. */
export function MethodologyEditor({ siteId }: { siteId: string }) {
  const methodology = useMethodology(siteId)
  const classes = useEquipmentClasses()
  const save = useUpdateStageKit(siteId)
  const [selected, setSelected] = useState<string | null>(null)

  return (
    <QueryState query={methodology}>
      {(kits) => {
        const current =
          kits.find((k) => k.stage_id === selected) ??
          kits.find((k) => k.equipment_check) ??
          kits[0]
        if (!current) return <p className="muted">В графике нет этапов.</p>
        return (
          <div className={styles.layout}>
            <div className={styles.aside}>
              <Card>
                <h3>Этапы графика</h3>
                <div className={styles.stageList}>
                  {kits.map((kit) => (
                    <button
                      key={kit.stage_id}
                      type="button"
                      className={styles.stageBtn}
                      aria-pressed={kit.stage_id === current.stage_id}
                      onClick={() => setSelected(kit.stage_id)}
                    >
                      <span>{kit.stage_name}</span>
                      <span className="sm muted">{stageSubtitle(kit)}</span>
                    </button>
                  ))}
                </div>
              </Card>
            </div>
            <div className={styles.main}>
              <StageKitEditor
                key={`${current.stage_id}-${JSON.stringify(current.rules)}-${current.equipment_check}`}
                kit={current}
                classes={classes.data ?? []}
                saving={save.isPending}
                onSave={(data) => save.mutate({ stageId: current.stage_id, data })}
              />
              {save.error && (
                <Callout tone="behind" title="Не сохранилось">
                  {save.error.message}
                </Callout>
              )}
              <p className="sm muted">
                Комплект — стартовый набор для этого крупного этапа, его можно править; техника
                задаётся на этап, не на мелкие работы. Минимум для подтверждения этапа — одна
                машина. «Обычно» — справочное число: устойчивая нехватка даёт лишь мягкий сигнал,
                отставание в днях по количеству не считается.
              </p>
            </div>
          </div>
        )
      }}
    </QueryState>
  )
}
