import type { FieldErrors, UseFormRegister } from 'react-hook-form'
import type { SiteCreate } from '@/api/schemas'
import { Card } from '@/components/ui/Card'
import { TextField } from '@/components/ui/TextField'
import styles from './NewSite.module.css'

interface ObjectFormProps {
  register: UseFormRegister<SiteCreate>
  errors: FieldErrors<SiteCreate>
}

/** Блок «Объект» первого шага: название и адрес. */
export function ObjectForm({ register, errors }: ObjectFormProps) {
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
      </div>
    </Card>
  )
}
