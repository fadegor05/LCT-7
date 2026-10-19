import { useState } from 'react'
import { useSearchParams } from 'react-router'
import { useCameras } from '@/api/cameras'
import { useObservation, useObservations, usePhotos, useUndatedPhotos } from '@/api/frames'
import { useSite } from '@/api/sites'
import { SectionHeader } from '@/components/layout/PageHeader'
import { SiteQueryState } from '@/components/layout/SiteQueryState'
import { SiteShell } from '@/components/layout/SiteShell'
import { Button } from '@/components/ui/Button'
import { QueryState } from '@/components/ui/QueryState'
import { AddFramesDialog } from '@/features/observations/AddFramesDialog'
import { CameraStrips } from '@/features/observations/CameraStrips'
import { DayPicker } from '@/features/observations/DayPicker'
import { DetectBacklogSection } from '@/features/observations/DetectBacklogSection'
import { EquipmentList } from '@/features/observations/EquipmentList'
import { NeedsReviewSection } from '@/features/observations/NeedsReviewSection'
import { formatDate, latestObservation } from '@/lib/format'
import { useRequiredParam } from '@/lib/useParam'

const column = { display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' } as const

/** Сколько снимков в последнем дне, чтобы открыть его, а не «Все дни». */
const MIN_PHOTOS_FOR_DAY = 3

/** Экран 6 · Наблюдения (UC-7, UC-3, UC-8): что система увидела на снимках, по дням. */
export function ObservationsPage() {
  const siteId = useRequiredParam('siteId')
  const [params, setParams] = useSearchParams()
  const [adding, setAdding] = useState(false)
  const site = useSite(siteId)
  const days = useObservations(siteId)
  const photos = usePhotos(siteId)
  const undated = useUndatedPhotos(siteId)
  const cameras = useCameras(siteId)

  // В последнем дне меньше трёх снимков (фотоотчёт раз в месяц) — сразу «Все дни»: иначе
  // объект с 15 снимками открывался на одном и казался пустым (как в clean-mvp)
  const last = latestObservation(days.data)
  const lastDay = last && last.photo_count >= MIN_PHOTOS_FOR_DAY ? last.observed_on : null
  const param = params.get('date')
  const date = param === 'all' ? null : (param ?? lastDay)
  const observation = useObservation(siteId, date)

  const selectDay = (value: string | null) => setParams({ date: value ?? 'all' }, { replace: true })

  return (
    <SiteQueryState query={site}>
      {(data) => (
        <SiteShell
          site={data}
          crumb="Наблюдения"
          subtitle="Что система увидела на снимках: по дням. Здесь же загружаются снимки."
          actions={
            <Button icon="plus" onClick={() => setAdding(true)}>
              Добавить снимки
            </Button>
          }
        >
          <QueryState query={days}>
            {(list) => (
              <DayPicker
                days={list}
                value={date}
                onChange={selectDay}
                undated={undated.data?.length ?? 0}
              />
            )}
          </QueryState>

          {date && observation.data && <EquipmentList observation={observation.data} />}

          <section style={column}>
            <SectionHeader
              title={date ? `Снимки за ${formatDate(date)}` : 'Все снимки с датой'}
              description="По камерам. Рамки: найденная техника. Источник даты показан у каждого снимка."
            />
            <QueryState query={photos}>
              {(list) => (
                <CameraStrips
                  siteId={siteId}
                  cameras={cameras.data ?? []}
                  withDate={!date}
                  photos={list
                    .filter((p) => p.captured_on && (!date || p.captured_on === date))
                    .sort((a, b) => a.captured_on!.localeCompare(b.captured_on!))}
                />
              )}
            </QueryState>
          </section>

          <DetectBacklogSection siteId={siteId} />

          <NeedsReviewSection siteId={siteId} />

          {adding && <AddFramesDialog siteId={siteId} onClose={() => setAdding(false)} />}
        </SiteShell>
      )}
    </SiteQueryState>
  )
}
