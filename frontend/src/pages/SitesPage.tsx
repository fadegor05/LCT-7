import { useAllDeviations } from '@/api/deviations'
import { useSites } from '@/api/sites'
import { PageHeader, SectionHeader } from '@/components/layout/PageHeader'
import { ButtonLink } from '@/components/ui/Button'
import { QueryState } from '@/components/ui/QueryState'
import { DeviationList } from '@/features/deviations/DeviationList'
import { SiteTable } from '@/features/sites/SiteTable'
import { formatDate } from '@/lib/format'
import { plural } from '@/lib/labels'

/** Экран 1 · Стройки (UC-9): список строек и сквозной список отклонений. */
export function SitesPage() {
  const sites = useSites()
  const deviations = useAllDeviations()
  const lastFrame = sites.data
    ?.map((s) => s.summary?.last_frame_at)
    .filter((d): d is string => Boolean(d))
    .sort()
    .at(-1)

  return (
    <>
      <PageHeader
        title="Стройки"
        subtitle={
          sites.data &&
          `${sites.data.length} ${plural(sites.data.length, ['объект', 'объекта', 'объектов'])}` +
            (lastFrame ? ` · данные на ${formatDate(lastFrame)}` : '')
        }
        actions={
          <ButtonLink to="/sites/new" icon="plus">
            Новая стройка
          </ButtonLink>
        }
      />
      <QueryState query={sites}>
        {(data) =>
          data.length > 0 ? (
            <SiteTable sites={data} />
          ) : (
            <p className="muted">Строек пока нет. Заведите первую.</p>
          )
        }
      </QueryState>
      <section style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
        <SectionHeader
          title="Отклонения по всем стройкам"
          description="Сначала критичные, внутри уровня свежие. Гипотезы не бывают критичными."
        />
        <QueryState query={deviations}>
          {(data) => <DeviationList items={data} showSite />}
        </QueryState>
      </section>
    </>
  )
}
