import type { Observation } from '@/api/schemas'

/** «Гусеничный экскаватор 2, самосвал 1 (максимум по снимкам).» */
export function observationSentence(obs: Observation): string {
  if (obs.equipment.length === 0) return 'Техники на снимках не найдено.'
  const list = obs.equipment
    .map(
      (e, i) => `${i === 0 ? e.equipment_title : e.equipment_title.toLowerCase()} ${e.count_min}`,
    )
    .join(', ')
  const idle = obs.equipment.filter((e) => e.activity === 'idle')
  const idleText = idle.length
    ? ` Простаивает: ${idle.map((e) => e.equipment_title.toLowerCase()).join(', ')}.`
    : ''
  return `${list} (максимум по снимкам).${idleText}`
}
