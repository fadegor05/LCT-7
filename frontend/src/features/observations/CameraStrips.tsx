import type { Camera, Photo } from '@/api/schemas'
import { plural } from '@/lib/labels'
import styles from './Observations.module.css'
import { PhotoStrip } from './PhotoStrip'

interface CameraStripsProps {
  siteId: string
  photos: readonly Photo[]
  cameras: readonly Camera[]
  /** Показывать дату у снимков (режим «Все дни»). */
  withDate: boolean
}

const count = (n: number) => `${n} ${plural(n, ['снимок', 'снимка', 'снимков'])}`

/**
 * Снимки по камерам (как в clean-mvp): у каждой камеры своя лента, снимки без камеры —
 * отдельной лентой в конце. Одна общая лента смешивала ракурсы, и по ней не понять, что
 * видно с какой камеры.
 */
export function CameraStrips({ siteId, photos, cameras, withDate }: CameraStripsProps) {
  const groups = [
    ...cameras.map((camera) => ({
      key: camera.id,
      name: camera.name,
      own: photos.filter((p) => p.camera_id === camera.id),
    })),
    {
      key: 'none',
      name: 'Без камеры',
      own: photos.filter((p) => !p.camera_id || !cameras.some((c) => c.id === p.camera_id)),
    },
  ].filter((g) => g.own.length > 0)

  // Камер нет — подписывать единственную ленту нечем
  if (groups.length === 0 || (groups.length === 1 && groups[0]!.key === 'none')) {
    return <PhotoStrip siteId={siteId} photos={photos} withDate={withDate} />
  }
  return (
    <>
      {groups.map((g) => (
        <section key={g.key} className={styles.cameraStrip} aria-label={`Снимки: ${g.name}`}>
          <h3 className="lab">
            {g.name} <span className="sm muted">· {count(g.own.length)}</span>
          </h3>
          <PhotoStrip siteId={siteId} photos={g.own} withDate={withDate} />
        </section>
      ))}
    </>
  )
}
