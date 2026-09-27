import type { ImportIssue } from '@/api/schemas'
import { plural } from '@/lib/labels'

const count = (issues: ImportIssue[], kind: ImportIssue['kind']) =>
  issues.filter((i) => i.kind === kind)

/** Текст блока «Что нужно поправить до создания» из списка проблем импорта. */
export function describeIssues(issues: ImportIssue[]): string[] {
  const lines: string[] = []
  const rows = count(issues, 'row_unparsed')
  if (rows.length) {
    const numbers = rows.map((r) => r.row_number).join(' и ')
    lines.push(
      `${rows.length} ${plural(rows.length, ['строка не разобрана', 'строки не разобраны', 'строк не разобрано'])} (${plural(rows.length, ['строка', 'строки', 'строки'])} ${numbers} файла: нет названия этапа).`,
    )
  }
  const noDates = count(issues, 'no_dates').length
  if (noDates)
    lines.push(
      `${noDates === 1 ? 'У одного этапа' : `У ${noDates} этапов`} нет дат: задайте их вручную.`,
    )
  const fuzzy = count(issues, 'fuzzy_match').length
  if (fuzzy)
    lines.push(
      `${fuzzy === 1 ? 'Один этап сопоставлен' : `${fuzzy} этапа сопоставлены`} нечётко: подтвердите.`,
    )
  const overlap = count(issues, 'window_overlap')
  if (overlap.length)
    lines.push(...overlap.map((i) => `${i.message}: объедините этапы или поправьте даты.`))
  return lines
}
