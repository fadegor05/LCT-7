import { Link } from 'react-router'
import type { Stage, StageStatus } from '@/api/schemas'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { stageAnchorId } from '@/features/assistant/linkifyAnswer'
import type { DeviationItem } from '@/lib/deviations'
import { formatWindow, stageDelayText } from '@/lib/format'
import { deviationTypeLabels, levelLabels } from '@/lib/labels'
import styles from './Overview.module.css'

const NBSP = '\u00a0'

const lowerFirst = (name: string) => name.charAt(0).toLowerCase() + name.slice(1)

function meta(row: StageStatus): string | null {
  const delay = row.delay_days !== null && stageDelayText(row)
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
  /** Дата данных объекта: «Ещё не по плану» считается от неё, а не от сегодняшнего дня. */
  asOf?: string | null
}

/** Таблица «Этапы» обзора (UC-4): план, статус с основанием, связанные отклонения. */
export function StageStatusTable({
  siteId,
  rows,
  stages,
  deviations,
  asOf,
}: StageStatusTableProps) {
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <caption className="srOnly">Статусы этапов</caption>
        <thead>
          <tr>
            <th scope="col">Этап</th>
            <th scope="col">План</th>
            <th scope="col">Факт по маркеру</th>
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
                    {/* Маркер — техника, которая отличает этап от идущих одновременно */}
                    {row.marker_names && row.marker_names.length > 0 && (
                      <span className="sm muted">
                        Маркер: {row.marker_names.map(lowerFirst).join(', ')}
                      </span>
                    )}
                    {row.status === null &&
                    stage?.planned_start &&
                    asOf &&
                    stage.planned_start > asOf ? (
                      <span className="sm muted">Ещё не по плану</span>
                    ) : (
                      row.confidence_reason && (
                        <span className="sm muted">{row.confidence_reason}</span>
                      )
                    )}
                  </div>
                </th>
                <td className="data">
                  {/* Неразрывные пробелы: окно переносится только после тире, дата целиком */}
                  {formatWindow(
                    stage?.planned_start ?? null,
                    stage?.planned_end ?? null,
                    '–',
                  ).replace(/ /g, NBSP)}
                </td>
                <td className="data">
                  {row.start_fact
                    ? `с ${row.start_fact.slice(8, 10)}.${row.start_fact.slice(5, 7)}`
                    : '—'}
                </td>
                <td>
                  <div className={styles.statusCell}>
                    <StatusBadge
                      status={row.status}
                      plannedStart={stage ? stage.planned_start : undefined}
                      asOf={asOf}
                    />
                    {deviations
                      .filter((d) => d.stage_id === row.stage_id)
                      .map((d) => (
                        <Link key={d.id} to={`/sites/${siteId}/deviations/${d.id}`} className="sm">
                          {d.title ?? deviationTypeLabels[d.type]}
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
