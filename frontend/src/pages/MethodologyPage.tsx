import { useSite } from '@/api/sites'
import { SiteShell } from '@/components/layout/SiteShell'
import { SectionHeader } from '@/components/layout/PageHeader'
import { QueryState } from '@/components/ui/QueryState'
import { MethodologyEditor } from '@/features/methodology/MethodologyEditor'
import { siteSubtitle } from '@/features/overview/siteSubtitle'
import { useRequiredParam } from '@/lib/useParam'

/** Экран 3а · Методика объекта (вкладка). */
export function MethodologyPage() {
  const siteId = useRequiredParam('siteId')
  const site = useSite(siteId)
  return (
    <QueryState query={site}>
      {(data) => (
        <SiteShell site={data} crumb="Методика" subtitle={siteSubtitle(data)}>
          <SectionHeader
            title="Методика: этап → техника"
            description="Правка комплекта пересчитает статусы и отклонения по уже загруженным кадрам, без повторной обработки изображений."
          />
          <MethodologyEditor siteId={siteId} />
        </SiteShell>
      )}
    </QueryState>
  )
}
