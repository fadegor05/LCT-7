import { useState } from 'react'
import { useCameras } from '@/api/cameras'
import type { Camera } from '@/api/schemas'
import { useSite } from '@/api/sites'
import { SectionHeader } from '@/components/layout/PageHeader'
import { SiteShell } from '@/components/layout/SiteShell'
import { Button } from '@/components/ui/Button'
import { QueryState } from '@/components/ui/QueryState'
import { CameraDialog } from '@/features/cameras/CameraDialog'
import { CameraList } from '@/features/cameras/CameraList'
import { plural } from '@/lib/labels'
import { useRequiredParam } from '@/lib/useParam'

/** Экран 4 · Камеры объекта (UC-6). */
export function CamerasPage() {
  const siteId = useRequiredParam('siteId')
  const site = useSite(siteId)
  const cameras = useCameras(siteId)
  const [editing, setEditing] = useState<Camera | 'new' | null>(null)
  const count = cameras.data?.length ?? 0

  return (
    <QueryState query={site}>
      {(data) => (
        <SiteShell
          site={data}
          crumb="Камеры"
          subtitle={
            cameras.data &&
            `${count} ${plural(count, ['камера', 'камеры', 'камер'])}. Настройка стрима и рабочей зоны каждой камеры.`
          }
        >
          <SectionHeader
            title="Камеры объекта"
            description="Камера: название, необязательная ссылка на стрим и необязательная рабочая зона. Кадры привязываются к выбранной камере."
            actions={
              <Button icon="plus" onClick={() => setEditing('new')}>
                Добавить камеру
              </Button>
            }
          />
          <QueryState query={cameras}>
            {(list) => <CameraList cameras={list} onEdit={setEditing} />}
          </QueryState>
          {editing && (
            <CameraDialog
              siteId={siteId}
              camera={editing === 'new' ? null : editing}
              onClose={() => setEditing(null)}
            />
          )}
        </SiteShell>
      )}
    </QueryState>
  )
}
