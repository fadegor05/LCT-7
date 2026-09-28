import type { ScheduleReport } from '@/api/schemas'
import { Callout } from '@/components/ui/Callout'
import { describeIssues } from './describeIssues'
import styles from './NewSite.module.css'

export function ImportSummary({ data }: { data: ScheduleReport }) {
  const stats = [
    [data.rows_total, 'строк в файле'],
    [data.rows_parsed, 'этапов разобрано'],
    [data.stages_with_dates, 'с плановыми датами'],
    [data.stages_without_dates, 'без дат'],
  ] as const
  const lines = describeIssues(data)
  return (
    <>
      <dl className={styles.stats}>
        {stats.map(([value, label]) => (
          <div key={label} className={styles.stat}>
            <dd className={styles.statValue}>{value}</dd>
            <dt className="sm muted">{label}</dt>
          </div>
        ))}
      </dl>
      {data.parse_method === 'llm' && (
        <Callout tone="caution" title="График разобран языковой моделью">
          Названия и даты модель переписала из файла — сверьте их с оригиналом. Даты, которых нет в
          строке файла, она не подставляет: такие строки попадают в список ошибок.
        </Callout>
      )}
      {lines.length > 0 && (
        <Callout tone="caution" title="Что проверить в графике">
          {lines.join(' ')}
        </Callout>
      )}
    </>
  )
}
