import { Link } from 'react-router'
import type { Stage, StageStatus } from '@/api/schemas'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { stageAnchorId } from '@/features/assistant/linkifyAnswer'
import type { DeviationItem } from '@/lib/deviations'
import { formatWindow } from '@/lib/format'
import { deviationTypeLabels, levelLabels } from '@/lib/labels'
import styles from './Overview.module.css'

function meta(row: StageStatus): string | null {
  const delay =
    row.delay_days !== null &&
    `${row.status === 'ahead' ? 'опережение' : 'отставание'} ${row.delay_open ? 'от ' : ''}${row.delay_days} дн.`
  const parts = [
    delay,
    row.confidence && `уверенность ${levelLabels[row.confidence].toLowerCase()}`,
  ].filter(Boolean)
  return parts.length ? parts.join(' · ') : null
}

interface StageStatusTableProps {
  siteId: string
  rows: readonly StageStatus[]
  /** Этапы графика — источник плановых окон. */
  stages: readonly Stage[]
  deviations: readonly DeviationItem[]
}

/** Таблица «Этапы» обзора (UC-4): план, статус с основанием, связанные отклонения. */
export function StageStatusTable({ siteId, rows, stages, deviations }: StageStatusTableProps) {
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <caption className="srOnly">Статусы этапов</caption>
        <thead>
          <tr>
            <th scope="col">Этап</th>
            <th scope="col">План</th>
            <th scope="col">Статус и отклонения</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const stage = stages.find((s) => s.id === row.stage_id)
            return (
              <tr key={row.stage_id} id={stageAnchorId(row.stage_id)} tabIndex={-1}>
                <th scope="row">
                  <div className={styles.stageName}>
                    <span style={{ fontSize: 16 }}>{row.stage_name}</span>
                    {row.confidence_reason && (
                      <span className="sm muted">{row.confidence_reason}</span>
                    )}
                  </div>
                </th>
                <td className="data">
                  {formatWindow(stage?.planned_start ?? null, stage?.planned_end ?? null, '–')}
                </td>
                <td>
                  <div className={styles.statusCell}>
                    <StatusBadge
                      status={row.status}
                      plannedStart={stage ? stage.planned_start : undefined}
                    />
                    {deviations
                      .filter((d) => d.stage_id === row.stage_id)
                      .map((d) => (
                        <Link key={d.id} to={`/sites/${siteId}/deviations/${d.id}`} className="sm">
                          {deviationTypeLabels[d.type]}
                          {d.is_hypothesis && ' (гипотеза)'}
                        </Link>
                      ))}
                    {meta(row) && <span className="sm muted">{meta(row)}</span>}
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
