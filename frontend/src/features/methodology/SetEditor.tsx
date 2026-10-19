import { useMemo, useState } from 'react'
import { useCreateSet, useReplaceSet } from '@/api/methodology'
import type {
  EquipmentSet,
  EquipmentType,
  MarkerPeriod,
  Requirement,
  SetWrite,
} from '@/api/schemas'
import { Button } from '@/components/ui/Button'
import { Callout } from '@/components/ui/Callout'
import { Icon } from '@/components/ui/Icon'
import { Pill } from '@/components/ui/Pill'
import { formatPeriod } from '@/lib/format'
import { obligationLabels } from '@/lib/labels'
import { AddRuleForm } from './AddRuleForm'
import styles from './Methodology.module.css'

type Draft = Omit<Requirement, 'id'> & { key: string }

const toDraft = (r: Requirement): Draft => ({ ...r, key: r.id })

const toWrite = (drafts: readonly Draft[]): SetWrite => ({
  requirements: drafts.map((r) => ({
    equipment_type_id: r.equipment_type.id,
    min_count: r.min_count,
    obligation: r.obligation,
    gesn_code: r.gesn_code,
    source_note: r.source_note,
  })),
})

interface SetEditorProps {
  siteId: string
  ruleId: string
  /** null — этап без комплекта: новый комплект уходит на сервер по «Сохранить». */
  set: EquipmentSet | null
  number: number
  types: readonly EquipmentType[]
  markers?: readonly MarkerPeriod[]
}

/**
 * Комплект техники этапа. Черновик локальный, на сервер уходит целиком (PUT/POST).
 * Нормативная техника — маркер: этап подтверждают только маркеры, поэтому без неё комплект
 * не сохраняется — то же правило проверяет backend. Комплект у этапа один (альтернативные — P2),
 * поэтому ни добавить второй, ни удалить комплект отсюда нельзя.
 */
export function SetEditor({ siteId, ruleId, set, number, types, markers }: SetEditorProps) {
  const initial = useMemo(() => (set?.requirements ?? []).map(toDraft), [set])
  const [drafts, setDrafts] = useState<Draft[]>(initial)
  const [adding, setAdding] = useState(set === null)
  const create = useCreateSet(siteId)
  const replace = useReplaceSet(siteId)
  const busy = create.isPending || replace.isPending
  const error = create.error ?? replace.error

  const dirty = JSON.stringify(drafts) !== JSON.stringify(initial)
  const hasMarker = drafts.some((r) => r.obligation === 'normative')
  const available = types.filter((t) => !drafts.some((r) => r.equipment_type.id === t.id))

  const patch = (key: string, change: Partial<Draft>) =>
    setDrafts((list) => list.map((r) => (r.key === key ? { ...r, ...change } : r)))

  const save = () => {
    const data = toWrite(drafts)
    if (set) replace.mutate({ setId: set.id, data })
    else create.mutate({ ruleId, data })
  }

  return (
    <section className={styles.rules} aria-label={`Комплект ${number}`}>
      <p className="lab muted">Комплект {number}</p>
      {drafts.length > 0 && (
        <ul className={styles.rules} aria-label={`Техника комплекта ${number}`}>
          {drafts.map((r) => (
            <li key={r.key} className={styles.rule}>
              <span className={styles.machine}>
                <Icon name="truck" size={24} />
                <span className="lab">{r.equipment_type.title}</span>
              </span>
              <span className={`sm ${styles.ruleObligation}`}>
                {obligationLabels[r.obligation]}
                <br />
                <span className="muted">{r.gesn_code ? `ГЭСН ${r.gesn_code}` : r.source_note}</span>
              </span>
              <label className={styles.qty}>
                <span className="sm muted">Минимум</span>
                <input
                  className={styles.qtyInput}
                  inputMode="numeric"
                  aria-label={`Минимум машин: ${r.equipment_type.title}`}
                  value={r.min_count}
                  onChange={(event) => {
                    const n = Number.parseInt(event.target.value, 10)
                    patch(r.key, { min_count: Number.isFinite(n) && n > 0 ? n : 1 })
                  }}
                />
              </label>
              <span>
                {r.obligation === 'normative' &&
                  (() => {
                    // Маркер — только если отличает этап от соседних (после пересчёта)
                    const own = markers?.filter((p) => p.equipment_type_id === r.equipment_type.id)
                    if (markers && !own?.length)
                      return <span className="sm muted">общая с соседними этапами</span>
                    return (
                      <>
                        <Pill tone="accent" icon="check">
                          Маркер
                        </Pill>
                        {own?.length ? (
                          <span className="sm muted">
                            {' '}
                            {own.map((p) => formatPeriod(p.start, p.end)).join(', ')}
                          </span>
                        ) : null}
                      </>
                    )
                  })()}
              </span>
              <Button
                variant="ghost"
                size="icon"
                icon="close"
                className={styles.ruleRemove}
                aria-label={`Убрать машину: ${r.equipment_type.title}`}
                onClick={() => setDrafts((list) => list.filter((x) => x.key !== r.key))}
              />
            </li>
          ))}
        </ul>
      )}
      {!hasMarker && (
        <Callout tone="caution" title="В комплекте нет маркера">
          Добавьте нормативную машину: логическая и вспомогательная техника не подтверждают этап.
        </Callout>
      )}
      {adding && (
        <AddRuleForm
          types={available}
          onCancel={() => setAdding(false)}
          onAdd={(type, obligation, source) => {
            setDrafts((list) => [
              ...list,
              { key: `new-${type.id}`, equipment_type: type, min_count: 1, obligation, ...source },
            ])
            setAdding(false)
          }}
        />
      )}
      {error && (
        <Callout tone="behind" title="Не сохранилось">
          {error.message}
        </Callout>
      )}
      <div className={styles.footer}>
        {!adding && (
          <Button variant="ghost" size="sm" icon="plus" onClick={() => setAdding(true)}>
            Добавить машину
          </Button>
        )}
        <p className="sm muted">{dirty ? 'Есть несохранённые изменения.' : ''}</p>
        <Button variant="ghost" onClick={() => setDrafts(initial)} disabled={!dirty || busy}>
          Отмена
        </Button>
        <Button onClick={save} disabled={!dirty || !hasMarker || busy}>
          Сохранить
        </Button>
      </div>
    </section>
  )
}
