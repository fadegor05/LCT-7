import { useState } from 'react'
import { useSearchParams } from 'react-router'
import { useCameras } from '@/api/cameras'
import { useFrames, useObservation, useObservationDays } from '@/api/frames'
import type { Frame } from '@/api/schemas'
import { useSite } from '@/api/sites'
import { SectionHeader } from '@/components/layout/PageHeader'
import { SiteShell } from '@/components/layout/SiteShell'
import { Button } from '@/components/ui/Button'
import { QueryState } from '@/components/ui/QueryState'
import { AddFramesDialog } from '@/features/observations/AddFramesDialog'
import { CameraStrip } from '@/features/observations/CameraStrip'
import { DayPicker } from '@/features/observations/DayPicker'
import { EquipmentList } from '@/features/observations/EquipmentList'
import { NeedsReviewSection } from '@/features/observations/NeedsReviewSection'
import { useEquipmentName } from '@/features/observations/useEquipmentName'
import { formatShortDate } from '@/lib/format'
import { useRequiredParam } from '@/lib/useParam'

const column = { display: 'flex', flexDirection: 'column', gap: 'var(--space-8)' } as const

function groupByCamera(frames: readonly Frame[]): Map<string, Frame[]> {
  const groups = new Map<string, Frame[]>()
  for (const f of frames) {
    const key = f.camera_id ?? 'none'
    groups.set(key, [...(groups.get(key) ?? []), f])
  }
  return groups
}

/** Экран 6 · Наблюдения (UC-7, UC-3, UC-8): что система увидела, по дням и камерам. */
export function ObservationsPage() {
  const siteId = useRequiredParam('siteId')
  const [params, setParams] = useSearchParams()
  const [adding, setAdding] = useState(false)
  const site = useSite(siteId)
  const days = useObservationDays(siteId)
  const cameras = useCameras(siteId)
  const name = useEquipmentName()

  const lastDay = days.data?.at(-1)?.obs_date ?? null
  const param = params.get('date')
  const date = param === 'all' ? null : (param ?? lastDay)
  const observation = useObservation(siteId, date)
  const frames = useFrames(siteId, date)

  const selectDay = (value: string | null) => setParams({ date: value ?? 'all' }, { replace: true })

  return (
    <QueryState query={site}>
      {(data) => (
        <SiteShell
          site={data}
          crumb="Наблюдения"
          subtitle="Что система увидела на кадрах: по дням и по камерам. Здесь же загружаются кадры."
          actions={
            <Button icon="plus" onClick={() => setAdding(true)}>
              Добавить кадры
            </Button>
          }
        >
          <QueryState query={days}>
            {(list) => (
              <DayPicker
                days={list}
                value={date}
                onChange={selectDay}
                withoutTime={data.summary?.frames_without_time ?? 0}
              />
            )}
          </QueryState>

          {date && observation.data && (
            <EquipmentList
              siteId={siteId}
              stageName={observation.data.expected_stage_name}
              items={observation.data.equipment}
            />
          )}

          <section style={column}>
            <SectionHeader
              title={date ? `Кадры за ${formatShortDate(date)} по камерам` : 'Все кадры по камерам'}
              description={
                date
                  ? 'Слева направо по времени съёмки. Рамки: найденная техника. Каждая лента прокручивается отдельно.'
                  : 'Слева направо по времени съёмки, справа самые новые. Источник и способ определения времени показаны у каждого кадра.'
              }
            />
            <QueryState query={frames}>
              {(list) => {
                const groups = groupByCamera(list)
                if (groups.size === 0) return <p className="muted">Кадров за этот период нет.</p>
                return [...groups.entries()].map(([cameraId, items]) => (
                  <CameraStrip
                    key={cameraId}
                    name={
                      cameras.data?.find((c) => c.id === cameraId)?.name ??
                      items[0]?.camera_name ??
                      'Без камеры'
                    }
                    frames={items}
                    withDate={!date}
                    classLabel={name}
                  />
                ))
              }}
            </QueryState>
          </section>

          <NeedsReviewSection siteId={siteId} />

          {adding && <AddFramesDialog siteId={siteId} onClose={() => setAdding(false)} />}
        </SiteShell>
      )}
    </QueryState>
  )
}
