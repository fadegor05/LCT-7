import { useState } from 'react'
import type { EquipmentType, Obligation } from '@/api/schemas'
import { Button } from '@/components/ui/Button'
import { SelectField } from '@/components/ui/SelectField'
import { TextField } from '@/components/ui/TextField'
import { obligationLabels } from '@/lib/labels'
import styles from './Methodology.module.css'

const obligations = (Object.keys(obligationLabels) as Obligation[]).map((value) => ({
  value,
  label: obligationLabels[value],
}))

/** Номер расценки ГЭСН: 06-01-001-16. Всё остальное считается текстом источника. */
const GESN = /^\d{2}-\d{2}-\d{3}-\d{2}$/

export interface RequirementSource {
  gesn_code: string | null
  source_note: string | null
}

function toSource(value: string): RequirementSource {
  const text = value.trim()
  return GESN.test(text)
    ? { gesn_code: text, source_note: null }
    : { gesn_code: null, source_note: text || null }
}

interface AddRuleFormProps {
  types: readonly EquipmentType[]
  onAdd: (type: EquipmentType, obligation: Obligation, source: RequirementSource) => void
  onCancel: () => void
}

/** Добавление машины в комплект: тип техники, обязательность и основание (ГЭСН или источник). */
export function AddRuleForm({ types, onAdd, onCancel }: AddRuleFormProps) {
  const [typeId, setTypeId] = useState(types[0]?.id ?? '')
  const [obligation, setObligation] = useState<Obligation>('normative')
  const [source, setSource] = useState('')
  const [error, setError] = useState<string>()
  const selected = types.find((t) => t.id === typeId)

  if (types.length === 0) {
    return <p className="sm muted">Вся техника справочника уже в комплекте.</p>
  }
  const add = () => {
    if (!selected) return
    if (!source.trim()) return setError('Укажите номер ГЭСН или источник')
    onAdd(selected, obligation, toSource(source))
  }
  return (
    <div className={styles.addForm}>
      <div className={styles.addRow}>
        <SelectField
          className={styles.addType}
          label="Машина"
          value={typeId}
          onChange={(event) => setTypeId(event.target.value)}
          options={types.map((t) => ({ value: t.id, label: t.title }))}
        />
        <SelectField
          className={styles.addObligation}
          label="Обязательность"
          value={obligation}
          onChange={(event) => setObligation(event.target.value as Obligation)}
          options={obligations}
        />
      </div>
      <div className={styles.addRow}>
        <TextField
          className={styles.addSource}
          label="ГЭСН или источник"
          placeholder="06-01-001-16 или «по смыслу работы»"
          value={source}
          error={error}
          onChange={(event) => setSource(event.target.value)}
        />
        <Button variant="secondary" size="sm" onClick={add}>
          Добавить
        </Button>
        <Button variant="ghost" size="sm" onClick={onCancel}>
          Отмена
        </Button>
      </div>
    </div>
  )
}
