import { useState } from 'react'
import type { EquipmentClass, RuleKind } from '@/api/schemas'
import { Button } from '@/components/ui/Button'
import { SelectField } from '@/components/ui/SelectField'
import { ruleKindLabels } from '@/lib/labels'
import styles from './Methodology.module.css'

const kinds = (Object.keys(ruleKindLabels) as RuleKind[]).map((value) => ({
  value,
  label: ruleKindLabels[value],
}))

interface AddRuleFormProps {
  classes: readonly EquipmentClass[]
  onAdd: (equipmentClass: EquipmentClass, kind: RuleKind) => void
  onCancel: () => void
}

export function AddRuleForm({ classes, onAdd, onCancel }: AddRuleFormProps) {
  const [code, setCode] = useState(classes[0]?.code ?? '')
  const [kind, setKind] = useState<RuleKind>('normative')
  const selected = classes.find((c) => c.code === code)

  if (classes.length === 0) {
    return <p className="sm muted">Все классы техники уже в комплекте.</p>
  }
  return (
    <div className={styles.addRow}>
      <SelectField
        label="Машина"
        value={code}
        onChange={(event) => setCode(event.target.value)}
        options={classes.map((c) => ({ value: c.code, label: c.name_ru }))}
      />
      <SelectField
        label="Вид правила"
        value={kind}
        onChange={(event) => setKind(event.target.value as RuleKind)}
        options={kinds}
      />
      <Button
        variant="secondary"
        size="sm"
        disabled={!selected}
        onClick={() => selected && onAdd(selected, kind)}
      >
        Добавить
      </Button>
      <Button variant="ghost" size="sm" onClick={onCancel}>
        Отмена
      </Button>
    </div>
  )
}
