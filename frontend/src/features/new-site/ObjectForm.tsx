import { Controller, type Control, type FieldErrors, type UseFormRegister } from 'react-hook-form'
import type { ObjectType, SiteCreate } from '@/api/schemas'
import { Card } from '@/components/ui/Card'
import { Segmented } from '@/components/ui/Segmented'
import { SelectField } from '@/components/ui/SelectField'
import { TextField } from '@/components/ui/TextField'
import { objectTypeLabels, WORKDAY_PRESETS, type WorkdayPreset, workdayPreset } from '@/lib/labels'
import styles from './NewSite.module.css'

interface ObjectFormProps {
  register: UseFormRegister<SiteCreate>
  control: Control<SiteCreate>
  errors: FieldErrors<SiteCreate>
}

const TYPE_OPTIONS = (Object.keys(objectTypeLabels) as ObjectType[]).map((value) => ({
  value,
  label: objectTypeLabels[value],
}))

/** Блок «Объект» первого шага (clean-mvp): название, адрес, тип объекта, рабочие дни. */
export function ObjectForm({ register, control, errors }: ObjectFormProps) {
  return (
    <Card>
      <h3>Объект</h3>
      <div className={styles.formGrid}>
        <TextField label="Название" error={errors.name?.message} {...register('name')} />
        <TextField
          label="Адрес или обозначение"
          error={errors.address?.message}
          {...register('address')}
        />
        <SelectField label="Тип объекта" options={TYPE_OPTIONS} {...register('object_type')} />
        <div className={styles.group}>
          <span className="sm muted">Рабочие дни</span>
          <Controller
            control={control}
            name="workdays"
            render={({ field }) => (
              <Segmented
                label="Рабочие дни"
                options={WORKDAY_PRESETS}
                value={workdayPreset(field.value) ?? ('' as WorkdayPreset)}
                onChange={(preset) =>
                  field.onChange([...WORKDAY_PRESETS.find((p) => p.value === preset)!.days])
                }
              />
            )}
          />
          <p className="sm muted">В нерабочие дни отсутствие техники не считается отклонением.</p>
        </div>
      </div>
    </Card>
  )
}
