import { useState } from 'react'
import { useSearchParams } from 'react-router'
import { useObservation, useObservations, usePhotos, useUndatedPhotos } from '@/api/frames'
import { useSite } from '@/api/sites'
import { SectionHeader } from '@/components/layout/PageHeader'
import { SiteShell } from '@/components/layout/SiteShell'
import { Button } from '@/components/ui/Button'
import { QueryState } from '@/components/ui/QueryState'
import { AddFramesDialog } from '@/features/observations/AddFramesDialog'
import { DayPicker } from '@/features/observations/DayPicker'
import { EquipmentList } from '@/features/observations/EquipmentList'
import { NeedsReviewSection } from '@/features/observations/NeedsReviewSection'
import { PhotoStrip } from '@/features/observations/PhotoStrip'
import { formatShortDate } from '@/lib/format'
import { useRequiredParam } from '@/lib/useParam'

const column = { display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' } as const

/** Экран 6 · Наблюдения (UC-7, UC-3, UC-8): что система увидела на снимках, по дням. */
export function ObservationsPage() {
  const siteId = useRequiredParam('siteId')
  const [params, setParams] = useSearchParams()
  const [adding, setAdding] = useState(false)
  const site = useSite(siteId)
  const days = useObservations(siteId)
  const photos = usePhotos(siteId)
  const undated = useUndatedPhotos(siteId)

  const lastDay = days.data?.at(-1)?.observed_on ?? null
  const param = params.get('date')
  const date = param === 'all' ? null : (param ?? lastDay)
  const observation = useObservation(siteId, date)

  const selectDay = (value: string | null) => setParams({ date: value ?? 'all' }, { replace: true })

  return (
    <QueryState query={site}>
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
              title={date ? `Снимки за ${formatShortDate(date)}` : 'Все снимки с датой'}
              description="Рамки: найденная техника. Источник даты показан у каждого снимка."
            />
            <QueryState query={photos}>
              {(list) => (
                <PhotoStrip
                  siteId={siteId}
                  withDate={!date}
                  photos={list
                    .filter((p) => p.captured_on && (!date || p.captured_on === date))
                    .sort((a, b) => a.captured_on!.localeCompare(b.captured_on!))}
                />
              )}
            </QueryState>
          </section>

          <NeedsReviewSection siteId={siteId} />

          {adding && <AddFramesDialog siteId={siteId} onClose={() => setAdding(false)} />}
        </SiteShell>
      )}
    </QueryState>
  )
}
