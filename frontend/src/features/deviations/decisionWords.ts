/** Кнопки по типу гипотезы (clean-mvp): «Подтвердить простой» / «Простоя не было» и т. д. */
export function decisionWords(type: string) {
  switch (type) {
    case 'idle':
      return {
        confirm: 'Подтвердить простой',
        reject: 'Простоя не было',
        confirmed: 'Простой подтверждён',
        rejected: 'Простоя не было',
      }
    case 'out_of_zone':
      return {
        confirm: 'Подтвердить',
        reject: 'Машина в зоне',
        confirmed: 'Подтверждено',
        rejected: 'Машина в зоне',
      }
    case 'extra_equipment':
      return {
        confirm: 'Подтвердить',
        reject: 'Техника уместна',
        confirmed: 'Подтверждено',
        rejected: 'Техника уместна',
      }
    default:
      return {
        confirm: 'Подтвердить',
        reject: 'Отклонить',
        confirmed: 'Подтверждено',
        rejected: 'Отклонено',
      }
  }
}
