import { useMemo, useState } from 'react'
import { useCreateSet, useDeleteSet, useReplaceSet } from '@/api/methodology'
import type { EquipmentSet, EquipmentType, Requirement, SetWrite } from '@/api/schemas'
import { Button } from '@/components/ui/Button'
import { Callout } from '@/components/ui/Callout'
import { Icon } from '@/components/ui/Icon'
import { Pill } from '@/components/ui/Pill'
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
  /** null — новый комплект, уходит на сервер по «Сохранить». */
  set: EquipmentSet | null
  number: number
  types: readonly EquipmentType[]
  onDone?: () => void
}

/**
 * Комплект техники этапа. Черновик локальный, на сервер уходит целиком (PUT/POST).
 * Нормативная техника — маркер: этап подтверждают только маркеры, поэтому без неё комплект
 * не сохраняется — то же правило проверяет backend.
 */
export function SetEditor({ siteId, ruleId, set, number, types, onDone }: SetEditorProps) {
  const initial = useMemo(() => (set?.requirements ?? []).map(toDraft), [set])
  const [drafts, setDrafts] = useState<Draft[]>(initial)
  const [adding, setAdding] = useState(set === null)
  const create = useCreateSet(siteId)
  const replace = useReplaceSet(siteId)
  const remove = useDeleteSet(siteId)
  const busy = create.isPending || replace.isPending || remove.isPending
  const error = create.error ?? replace.error ?? remove.error

  const dirty = set === null || JSON.stringify(drafts) !== JSON.stringify(initial)
  const hasMarker = drafts.some((r) => r.obligation === 'normative')
  const available = types.filter((t) => !drafts.some((r) => r.equipment_type.id === t.id))

  const patch = (key: string, change: Partial<Draft>) =>
    setDrafts((list) => list.map((r) => (r.key === key ? { ...r, ...change } : r)))

  const save = () => {
    const data = toWrite(drafts)
    if (set) replace.mutate({ setId: set.id, data })
    else create.mutate({ ruleId, data }, { onSuccess: onDone })
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
                {r.obligation === 'normative' && (
                  <Pill tone="accent" icon="check">
                    Маркер
                  </Pill>
                )}
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
      {adding ? (
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
      ) : (
        <div>
          <Button variant="ghost" size="sm" icon="plus" onClick={() => setAdding(true)}>
            Добавить машину
          </Button>
        </div>
      )}
      {error && (
        <Callout tone="behind" title="Не сохранилось">
          {error.message}
        </Callout>
      )}
      <div className={styles.footer}>
        <p className="sm muted">{set && dirty ? 'Есть несохранённые изменения.' : ''}</p>
        {set ? (
          <>
            <Button
              variant="ghost"
              disabled={busy}
              onClick={() => remove.mutate(set.id)}
              aria-label={`Удалить комплект ${number}`}
            >
              Удалить комплект
            </Button>
            <Button variant="ghost" onClick={() => setDrafts(initial)} disabled={!dirty || busy}>
              Отмена
            </Button>
          </>
        ) : (
          <Button variant="ghost" onClick={onDone} disabled={busy}>
            Отмена
          </Button>
        )}
        <Button onClick={save} disabled={!dirty || !hasMarker || busy}>
          Сохранить
        </Button>
      </div>
    </section>
  )
}
