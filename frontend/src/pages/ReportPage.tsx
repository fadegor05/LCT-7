import { useEffect, useRef } from 'react'
import { Link, useSearchParams } from 'react-router'
import { useStageStatuses, useDeviations, useSummary } from '@/api/deviations'
import { useObservations, useUndatedPhotos } from '@/api/frames'
import { useSchedule } from '@/api/schedule'
import { useSite } from '@/api/sites'
import { SiteQueryState } from '@/components/layout/SiteQueryState'
import { Button } from '@/components/ui/Button'
import { Callout } from '@/components/ui/Callout'
import { QueryState } from '@/components/ui/QueryState'
import { ReportDeviations } from '@/features/report/ReportDeviations'
import { ReportStages } from '@/features/report/ReportStages'
import styles from '@/features/report/Report.module.css'
import {
  INSUFFICIENT_EXPLANATION,
  LIMITS_TEXT,
  VERDICT_EXPLANATION,
  stampDate,
} from '@/features/report/reportText'
import { verdictText } from '@/features/sites/verdict'
import { sortDeviations, withStages } from '@/lib/deviations'
import { formatDate, latestObservation, todayIso } from '@/lib/format'
import { levelLabels } from '@/lib/labels'
import { useRequiredParam } from '@/lib/useParam'

/**
 * Отчёт по объекту для печати и PDF: документ A4 без интерфейса — итог, отклонения с основанием,
 * этапы, состояние данных и то, чего отчёт не утверждает. Только данные, которые уже отдаёт API
 * стройки. `?print=1` (ссылка «Скачать отчёт PDF» на обзоре) открывает диалог печати, когда всё
 * загрузилось: «Сохранить как PDF» в нём и даёт файл.
 */
export function ReportPage() {
  const siteId = useRequiredParam('siteId')
  const [params] = useSearchParams()
  const site = useSite(siteId)
  const summary = useSummary(siteId)
  const deviations = useDeviations(siteId)
  const schedule = useSchedule(siteId)
  const statuses = useStageStatuses(siteId, Boolean(schedule.data))
  const observations = useObservations(siteId)
  const undated = useUndatedPhotos(siteId)

  const stages = schedule.data?.stages ?? []
  const items = sortDeviations(withStages(siteId, deviations.data ?? [], stages))
  const list = observations.data ?? []
  const last = latestObservation(list)
  const undatedCount = undated.data?.length ?? 0
  const dated = list.reduce((sum, o) => sum + o.photo_count, 0)

  const ready =
    site.isSuccess &&
    summary.isSuccess &&
    deviations.isSuccess &&
    schedule.isSuccess &&
    observations.isSuccess &&
    undated.isSuccess &&
    (!schedule.data || statuses.isSuccess)

  // «Сохранить как PDF» называет файл по заголовку страницы: у каждого отчёта своё имя
  const name = site.data?.name
  useEffect(() => {
    if (!name) return
    const previous = document.title
    document.title = `Отчёт — ${name} — ${stampDate(todayIso())}`
    return () => {
      document.title = previous
    }
  }, [name])

  const printed = useRef(false)
  useEffect(() => {
    if (!ready || params.get('print') !== '1' || printed.current) return
    printed.current = true
    window.print()
  }, [ready, params])

  return (
    <div className={styles.page}>
      <div className={styles.toolbar}>
        <Link to={`/sites/${siteId}`}>← К обзору</Link>
        <Button size="sm" onClick={() => window.print()}>
          Сохранить PDF
        </Button>
      </div>
      <SiteQueryState query={site}>
        {(s) => (
          <article className={styles.doc} data-report>
            {/* Не <header>: печатные стили интерфейса прячут шапку приложения по тегу */}
            <div className={styles.head}>
              <h1>Отчёт: {s.name}</h1>
              <p>
                {[s.address, last && `последнее наблюдение ${formatDate(last.observed_on)}`]
                  .filter(Boolean)
                  .join(' · ')}
              </p>
              <p className={styles.meta}>Сформирован {stampDate(todayIso())} · сервис «Веха»</p>
            </div>

            <section aria-labelledby="report-summary">
              <h2 id="report-summary">Итог по объекту</h2>
              <QueryState query={summary}>
                {(o) => (
                  <>
                    <p className={styles.verdict}>{verdictText(o)}</p>
                    <p>
                      {o.verdict === 'insufficient_data'
                        ? INSUFFICIENT_EXPLANATION
                        : VERDICT_EXPLANATION[o.verdict]}
                    </p>
                  </>
                )}
              </QueryState>
            </section>

            <section aria-labelledby="report-deviations">
              <h2 id="report-deviations">Отклонения: {items.length}</h2>
              <QueryState query={deviations}>{() => <ReportDeviations items={items} />}</QueryState>
            </section>

            <section aria-labelledby="report-stages">
              <h2 id="report-stages">Этапы</h2>
              <QueryState query={schedule}>
                {(graph) =>
                  graph ? (
                    <QueryState query={statuses}>
                      {(rows) => <ReportStages rows={rows} stages={graph.stages} />}
                    </QueryState>
                  ) : (
                    <Callout tone="caution" title="График не загружен">
                      Без графика этапы не оцениваются.
                    </Callout>
                  )
                }
              </QueryState>
            </section>

            <section aria-labelledby="report-data">
              <h2 id="report-data">Состояние данных</h2>
              {/* Без этих сведений отчёт неполон: печать не открывается, пока их нет */}
              {observations.error && (
                <Callout tone="caution" title="Отчёт неполон">
                  Не удалось загрузить наблюдения: {observations.error.message}. Обновите страницу.
                </Callout>
              )}
              {dated + undatedCount === 0 ? (
                <p>Кадров пока нет.</p>
              ) : (
                <ul className={styles.facts}>
                  {last && <li>Наблюдаемость: {levelLabels[last.observability].toLowerCase()}</li>}
                  {last && <li>Последнее наблюдение: {formatDate(last.observed_on)}</li>}
                  <li>Дней наблюдений: {list.length}</li>
                  <li>Всего снимков: {dated + undatedCount}</li>
                  {undatedCount > 0 && <li>Без даты: {undatedCount} (в расчёт не идут)</li>}
                </ul>
              )}
            </section>

            <section aria-labelledby="report-limits" className={styles.limits}>
              <h2 id="report-limits">Чего отчёт не утверждает</h2>
              <p>{LIMITS_TEXT}</p>
            </section>
          </article>
        )}
      </SiteQueryState>
    </div>
  )
}
