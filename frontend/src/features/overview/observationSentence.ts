import type { Observation } from '@/api/schemas'

/** «Экскаватор 2, самосвал 1 (максимум по кадрам). Простаивает: самосвал (гипотеза).» */
export function observationSentence(obs: Observation): string {
  if (obs.equipment.length === 0) return 'Техники на кадрах не найдено.'
  const list = obs.equipment
    .map((e, i) => `${i === 0 ? e.name : e.name.toLowerCase()} ${e.min_count}`)
    .join(', ')
  const idle = obs.equipment.filter((e) => e.activity === 'idle')
  const idleText = idle.length
    ? ` Простаивает: ${idle.map((e) => `${e.name.toLowerCase()}${e.activity_hypothesis ? ' (гипотеза)' : ''}`).join(', ')}.`
    : ''
  return `${list} (максимум по кадрам).${idleText}`
}
