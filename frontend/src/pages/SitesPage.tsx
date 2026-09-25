import { useAllDeviations } from '@/api/deviations'
import type { Site } from '@/api/schemas'
import { useSites } from '@/api/sites'
import { PageHeader, SectionHeader } from '@/components/layout/PageHeader'
import { ButtonLink } from '@/components/ui/Button'
import { QueryState } from '@/components/ui/QueryState'
import { DeviationList } from '@/features/deviations/DeviationList'
import { SiteTable } from '@/features/sites/SiteTable'
import { sortDeviations } from '@/lib/deviations'
import { plural } from '@/lib/labels'

const NO_SITES: Site[] = []

function AllDeviations({ sites }: { sites: readonly Site[] }) {
  const deviations = useAllDeviations(sites)
  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
      <SectionHeader
        title="Отклонения по всем стройкам"
        description="Сначала критичные, внутри уровня свежие. Гипотезы не бывают критичными."
      />
      <QueryState query={deviations}>
        {(data) => <DeviationList items={sortDeviations(data)} showSite />}
      </QueryState>
    </section>
  )
}

/** Экран 1 · Стройки (UC-9): список строек и сквозной список отклонений. */
export function SitesPage() {
  const sites = useSites()

  return (
    <>
      <PageHeader
        title="Стройки"
        subtitle={
          sites.data &&
          `${sites.data.length} ${plural(sites.data.length, ['объект', 'объекта', 'объектов'])}`
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
      <AllDeviations sites={sites.data ?? NO_SITES} />
    </>
  )
}
