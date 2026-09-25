import type { ScheduleReport } from '@/api/schemas'
import { plural } from '@/lib/labels'

/** Текст блока «Что проверить в графике» по отчёту импорта. */
export function describeIssues(report: ScheduleReport): string[] {
  const lines = report.issues.map(
    (i) => `Строка ${i.row_number} не разобрана: ${i.reason.replace(/\.$/, '')}.`,
  )
  const noDates = report.stages_without_dates
  if (noDates) {
    lines.push(
      `${noDates === 1 ? 'У одного этапа' : `У ${noDates} ${plural(noDates, ['этапа', 'этапов', 'этапов'])}`} нет дат: задайте их вручную, иначе этап не оценивается.`,
    )
  }
  return lines
}
