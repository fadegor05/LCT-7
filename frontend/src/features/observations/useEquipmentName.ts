import { useCallback } from 'react'
import { useEquipmentClasses } from '@/api/methodology'

/** Подпись класса техники по коду из справочника (/equipment-classes). */
export function useEquipmentName(): (code: string) => string {
  const classes = useEquipmentClasses()
  return useCallback(
    (code: string) => classes.data?.find((c) => c.code === code)?.name_ru ?? code,
    [classes.data],
  )
}
