import { useState } from 'react'
import { useCameras } from '@/api/cameras'
import { useSite } from '@/api/sites'
import type { Camera, Site } from '@/api/schemas'
import { SectionHeader } from '@/components/layout/PageHeader'
import { SiteQueryState } from '@/components/layout/SiteQueryState'
import { SiteShell } from '@/components/layout/SiteShell'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { QueryState } from '@/components/ui/QueryState'
import { CameraDialog } from '@/features/cameras/CameraDialog'
import { CameraList } from '@/features/cameras/CameraList'
import { camerasWord } from '@/features/cameras/plural'
import { useRequiredParam } from '@/lib/useParam'

/** Вкладка «Камеры»: список камер стройки и настройка стрима и рабочей зоны каждой. */
export function CamerasPage() {
  const siteId = useRequiredParam('siteId')
  const site = useSite(siteId)
  return (
    <SiteQueryState query={site}>
      {(data) => <CamerasContent site={data} siteId={siteId} />}
    </SiteQueryState>
  )
}

function CamerasContent({ site, siteId }: { site: Site; siteId: string }) {
  const cameras = useCameras(siteId)
  // undefined — окно закрыто, null — новая камера
  const [editing, setEditing] = useState<Camera | null | undefined>(undefined)
  const n = cameras.data?.length
  return (
    <SiteShell
      site={site}
      crumb="Камеры"
      subtitle={n !== undefined ? `${n} ${camerasWord(n)}` : undefined}
    >
      <Card aria-labelledby="cameras-title">
        <SectionHeader
          title={<span id="cameras-title">Камеры объекта</span>}
          description="Название, необязательная ссылка на стрим и необязательная рабочая зона. Фотографии привязываются к стройке, зона очерчивает, где работает техника."
          actions={
            <Button icon="plus" onClick={() => setEditing(null)}>
              Добавить камеру
            </Button>
          }
        />
        <QueryState query={cameras}>
          {(data) =>
            data.length === 0 ? (
              <p className="muted">Камер пока нет. Добавьте первую, чтобы настроить стрим.</p>
            ) : (
              <CameraList cameras={data} onEdit={setEditing} />
            )
          }
        </QueryState>
      </Card>
      {editing !== undefined && (
        <CameraDialog siteId={siteId} camera={editing} onClose={() => setEditing(undefined)} />
      )}
    </SiteShell>
  )
}
