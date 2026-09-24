import type { ScheduleImport } from '@/api/schemas'
import { Callout } from '@/components/ui/Callout'
import { describeIssues } from './describeIssues'
import styles from './NewSite.module.css'

export function ImportSummary({ data }: { data: ScheduleImport }) {
  const stats = [
    [data.works_total, 'работ в файле'],
    [data.stages_total, 'крупных этапов'],
    [data.window_overlaps, 'пересечений окон'],
    [data.checked_stages, 'проверяются по технике'],
  ] as const
  const lines = describeIssues(data.issues)
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
      {lines.length > 0 && (
        <Callout
          tone={data.window_overlaps > 0 ? 'behind' : 'caution'}
          title="Что нужно поправить до создания"
        >
          {lines.join(' ')} Если окна этапов пересекутся, дальше пройти нельзя, пока их не
          объединят.
        </Callout>
      )}
    </>
  )
}
