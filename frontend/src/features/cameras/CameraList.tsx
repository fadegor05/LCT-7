import type { Camera } from '@/api/schemas'
import { Button } from '@/components/ui/Button'
import { Pill } from '@/components/ui/Pill'
import { pluralFrames } from '@/lib/labels'
import styles from './Cameras.module.css'

interface CameraListProps {
  cameras: readonly Camera[]
  onEdit: (camera: Camera) => void
}

export function CameraList({ cameras, onEdit }: CameraListProps) {
  if (cameras.length === 0) {
    return <p className="muted">Камер пока нет. Добавьте первую: кадры привязываются к камере.</p>
  }
  return (
    <ul className={styles.grid} aria-label="Камеры объекта">
      {cameras.map((camera) => (
        <li key={camera.id} className={styles.card}>
          <h3>{camera.name}</h3>
          <div className={styles.tags}>
            {camera.stream_url ? (
              <Pill tone="ontrack">Стрим подключён</Pill>
            ) : (
              <Pill tone="neutral">Только файлы</Pill>
            )}
            {camera.zone_polygon ? (
              <Pill tone="ontrack">Зона задана</Pill>
            ) : (
              <Pill tone="dashed">Зона не задана</Pill>
            )}
          </div>
          <p className="sm muted">{pluralFrames(camera.frames_count)}</p>
          <div>
            <Button
              variant="ghost"
              size="sm"
              icon="pencil"
              onClick={() => onEdit(camera)}
              aria-label={`Настроить ${camera.name}`}
            >
              Настроить
            </Button>
          </div>
        </li>
      ))}
    </ul>
  )
}
