import { Controller, type Control, type FieldErrors, type UseFormRegister } from 'react-hook-form'
import type { ObjectType, SiteCreate, WorkDays } from '@/api/schemas'
import { Card } from '@/components/ui/Card'
import { Segmented } from '@/components/ui/Segmented'
import { TextField } from '@/components/ui/TextField'
import { objectTypeLabels, workDaysLabels } from '@/lib/labels'
import styles from './NewSite.module.css'

const objectTypes = (Object.keys(objectTypeLabels) as ObjectType[]).map((value) => ({
  value,
  label: objectTypeLabels[value],
}))
const workDays = (Object.keys(workDaysLabels) as WorkDays[]).map((value) => ({
  value,
  label: workDaysLabels[value],
}))

interface ObjectFormProps {
  register: UseFormRegister<SiteCreate>
  control: Control<SiteCreate>
  errors: FieldErrors<SiteCreate>
}

/** Блок «Объект» первого шага: название, адрес, тип, рабочие дни. */
export function ObjectForm({ register, control, errors }: ObjectFormProps) {
  return (
    <Card>
      <h3>Объект</h3>
      <div className={styles.formGrid}>
        <TextField label="Название" error={errors.name?.message} {...register('name')} />
        <TextField label="Адрес или обозначение" {...register('address')} />
      </div>
      <div className={styles.formGrid}>
        <div className={styles.group}>
          <span className="lab">Тип объекта</span>
          <Controller
            control={control}
            name="object_type"
            render={({ field }) => (
              <Segmented
                label="Тип объекта"
                options={objectTypes}
                value={field.value}
                onChange={field.onChange}
              />
            )}
          />
        </div>
        <div className={styles.group}>
          <span className="lab">Рабочие дни</span>
          <Controller
            control={control}
            name="work_days"
            render={({ field }) => (
              <Segmented
                label="Рабочие дни"
                options={workDays}
                value={field.value}
                onChange={field.onChange}
              />
            )}
          />
          <p className="sm muted">В нерабочие дни отсутствие техники не считается отклонением.</p>
        </div>
      </div>
    </Card>
  )
}
