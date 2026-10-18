import { StatusBadge } from '@/components/ui/StatusBadge'
import type { Stage, StageStatus } from '@/api/schemas'
import { formatWindow } from '@/lib/format'
import { stageBasis } from './reportText'
import styles from './Report.module.css'

interface ReportStagesProps {
  rows: readonly StageStatus[]
  /** Этапы графика — источник плановых окон. */
  stages: readonly Stage[]
}

/** Этапы в отчёте: план, статус с основанием (как на обзоре, без ссылок). */
export function ReportStages({ rows, stages }: ReportStagesProps) {
  return (
    <table className={styles.table}>
      <caption className="srOnly">Этапы</caption>
      <thead>
        <tr>
          <th scope="col">Этап</th>
          <th scope="col">План</th>
          <th scope="col">Статус</th>
          <th scope="col">Основание</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => {
          const stage = stages.find((s) => s.id === row.stage_id)
          return (
            <tr key={row.stage_id}>
              <td>
                {row.stage_name}
                {row.confidence_reason && (
                  <span className={styles.sub}>{row.confidence_reason}</span>
                )}
              </td>
              <td className={styles.nowrap}>
                {formatWindow(stage?.planned_start ?? null, stage?.planned_end ?? null, '–')}
              </td>
              <td>
                <StatusBadge
                  status={row.status}
                  plannedStart={stage ? stage.planned_start : undefined}
                />
              </td>
              <td>{stageBasis(row)}</td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
