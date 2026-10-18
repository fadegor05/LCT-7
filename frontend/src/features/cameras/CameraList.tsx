import type { Camera } from '@/api/schemas'
import { Button } from '@/components/ui/Button'
import { Pill } from '@/components/ui/Pill'
import { formatDateTime } from '@/lib/format'
import { framesWord } from './plural'
import styles from './Cameras.module.css'

interface CameraListProps {
  cameras: Camera[]
  onEdit: (camera: Camera) => void
}

/** Камеры строками-карточками: стрим, зона и число кадров; «Настроить» открывает окно камеры. */
export function CameraList({ cameras, onEdit }: CameraListProps) {
  return (
    <ul className={styles.list} aria-label="Камеры">
      {cameras.map((camera) => (
        <li key={camera.id} className={styles.row}>
          <span className="lab">{camera.name}</span>
          <span>
            <StreamStatus camera={camera} />
          </span>
          <span>
            {camera.zone ? (
              <Pill tone="ontrack" icon="check" size="sm">
                Зона задана
              </Pill>
            ) : (
              <Pill tone="dashed" size="sm">
                Зона не задана
              </Pill>
            )}
          </span>
          <span className="data">
            {camera.frames_count} {framesWord(camera.frames_count)}
          </span>
          <Button
            variant="secondary"
            size="sm"
            aria-label={`Настроить камеру ${camera.name}`}
            onClick={() => onEdit(camera)}
          >
            Настроить
          </Button>
        </li>
      ))}
    </ul>
  )
}

/** Стрим в строке камеры: идут ли снимки и почему нет. */
function StreamStatus({ camera }: { camera: Camera }) {
  if (!camera.stream_url) return <span className="sm muted">Без стрима, только загрузка</span>
  if (camera.last_capture_error) {
    const text = `Стрим недоступен: ${camera.last_capture_error}`
    return (
      <span className={styles.streamError} title={text}>
        {text}
      </span>
    )
  }
  return (
    <Pill tone="ontrack" icon="check" size="sm">
      {camera.last_capture_at
        ? `Стрим · снимок ${formatDateTime(camera.last_capture_at)}`
        : 'Стрим задан'}
    </Pill>
  )
}
