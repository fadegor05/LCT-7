import { useMemo, useState } from 'react'
import type {
  EquipmentClass,
  KitRule,
  KitRuleInput,
  RuleKind,
  StageKit,
  StageKitUpdate,
} from '@/api/schemas'
import { Button } from '@/components/ui/Button'
import { Callout } from '@/components/ui/Callout'
import { Card } from '@/components/ui/Card'
import { Icon } from '@/components/ui/Icon'
import { Pill } from '@/components/ui/Pill'
import { Segmented } from '@/components/ui/Segmented'
import { formatWindow } from '@/lib/format'
import { ruleKindLabels } from '@/lib/labels'
import { AddRuleForm } from './AddRuleForm'
import styles from './Methodology.module.css'

type RuleDraft = Omit<KitRule, 'id'> & { key: string }

const DEFAULT_SOURCE: Record<RuleKind, string | null> = {
  normative: 'ГЭСН [номер расценки]',
  logical: 'по смыслу работы',
  auxiliary: null,
}

const toDraft = (rule: KitRule): RuleDraft => ({ ...rule, key: rule.id })

function toUpdate(check: boolean, rules: readonly RuleDraft[]): StageKitUpdate {
  return {
    equipment_check: check,
    rules: rules.map((r): KitRuleInput => ({
      equipment_class: r.equipment_class,
      equipment_group: r.equipment_group,
      rule_kind: r.rule_kind,
      source_ref: r.source_ref,
      typical_qty: r.typical_qty,
    })),
  }
}

interface StageKitEditorProps {
  kit: StageKit
  classes: readonly EquipmentClass[]
  saving: boolean
  onSave: (data: StageKitUpdate) => void
}

const checkOptions = [
  { value: 'yes', label: 'Проверяется' },
  { value: 'no', label: 'Не проверяется' },
] as const

/**
 * Комплект техники крупного этапа (UC-2). Черновик локальный, на сервер уходит целиком
 * по «Сохранить»; маркеры сервер пересчитывает сам и возвращает в ответе.
 */
export function StageKitEditor({ kit, classes, saving, onSave }: StageKitEditorProps) {
  const initial = useMemo(() => kit.rules.map(toDraft), [kit.rules])
  const [check, setCheck] = useState(kit.equipment_check)
  const [rules, setRules] = useState<RuleDraft[]>(initial)
  const [adding, setAdding] = useState(false)

  const dirty = check !== kit.equipment_check || JSON.stringify(rules) !== JSON.stringify(initial)
  const available = classes.filter((c) => !rules.some((r) => r.equipment_class === c.code))

  const patch = (key: string, change: Partial<RuleDraft>) =>
    setRules((list) => list.map((r) => (r.key === key ? { ...r, ...change } : r)))

  const reset = () => {
    setCheck(kit.equipment_check)
    setRules(initial)
    setAdding(false)
  }

  return (
    <Card>
      <div className={styles.editorHead}>
        <div>
          <h2>{kit.stage_name}</h2>
          <p className="sm muted" style={{ marginTop: 'var(--space-1)' }}>
            Плановое окно:{' '}
            <span className="data">{formatWindow(kit.planned_start, kit.planned_end)}</span>
          </p>
        </div>
        <Segmented
          label="Проверка по технике"
          options={checkOptions}
          value={check ? 'yes' : 'no'}
          onChange={(v) => setCheck(v === 'yes')}
        />
      </div>

      {!check ? (
        <Callout title="Этап не проверяется по технике">
          {kit.not_checked_reason ?? 'Этап остаётся в графике, но статус по нему не выводится.'}
        </Callout>
      ) : (
        <div className={styles.rules}>
          <p className="lab muted">Комплект 1</p>
          {rules.length === 0 && (
            <Callout tone="caution" title="В комплекте нет техники">
              Добавьте хотя бы одну машину, иначе этап нечем подтвердить.
            </Callout>
          )}
          <ul className={styles.rules} aria-label="Техника комплекта">
            {rules.map((r) => (
              <li key={r.key} className={styles.rule}>
                <span className={styles.machine}>
                  <Icon name="truck" size={24} />
                  <span className="lab">{r.name}</span>
                </span>
                <span className="sm">
                  {ruleKindLabels[r.rule_kind]}
                  {r.source_ref && (
                    <>
                      <br />
                      <span className="muted">{r.source_ref}</span>
                    </>
                  )}
                </span>
                <label className={styles.qty}>
                  <span className="sm muted">Обычно</span>
                  <input
                    className={styles.qtyInput}
                    inputMode="numeric"
                    aria-label={`Типовое количество: ${r.name}`}
                    value={r.typical_qty ?? ''}
                    onChange={(event) => {
                      const n = Number.parseInt(event.target.value, 10)
                      patch(r.key, { typical_qty: Number.isFinite(n) && n > 0 ? n : null })
                    }}
                  />
                </label>
                <span>
                  {r.is_marker && (
                    <Pill tone="accent" icon="check">
                      Маркер
                    </Pill>
                  )}
                </span>
                <Button
                  variant="ghost"
                  size="icon"
                  icon="close"
                  aria-label={`Убрать машину: ${r.name}`}
                  onClick={() => setRules((list) => list.filter((x) => x.key !== r.key))}
                />
              </li>
            ))}
          </ul>
          {adding ? (
            <AddRuleForm
              classes={available}
              onCancel={() => setAdding(false)}
              onAdd={(cls, kind) => {
                setRules((list) => [
                  ...list,
                  {
                    key: `new-${cls.code}`,
                    equipment_class: cls.code,
                    equipment_group: null,
                    name: cls.name_ru,
                    rule_kind: kind,
                    source_ref: DEFAULT_SOURCE[kind],
                    typical_qty: null,
                    is_marker: false,
                  },
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
          {kit.marker_explanation && (
            <Callout title="Маркерная техника этапа">
              {kit.marker_explanation}
              {dirty && ' Маркеры пересчитаются после сохранения.'}
            </Callout>
          )}
        </div>
      )}

      <div className={styles.footer}>
        <p className="sm muted">{dirty ? 'Есть несохранённые изменения.' : ''}</p>
        <Button variant="ghost" onClick={reset} disabled={!dirty || saving}>
          Отмена
        </Button>
        <Button onClick={() => onSave(toUpdate(check, rules))} disabled={!dirty || saving}>
          Сохранить
        </Button>
      </div>
    </Card>
  )
}
