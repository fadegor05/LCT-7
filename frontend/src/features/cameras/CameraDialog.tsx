import { useState } from 'react'
import { useDeleteCamera, useSaveCamera } from '@/api/cameras'
import { photoImageUrl, usePhotos } from '@/api/frames'
import type { Camera, Zone } from '@/api/schemas'
import { Button } from '@/components/ui/Button'
import { Callout } from '@/components/ui/Callout'
import { Dialog } from '@/components/ui/Dialog'
import { Pill } from '@/components/ui/Pill'
import { TextField } from '@/components/ui/TextField'
import { useAuthorizedImage } from '@/api/images'
import { newestPhoto } from './newestPhoto'
import { takeSeconds } from './streamLink'
import { ZoneEditor } from './ZoneEditor'
import { zoneProblem } from './zoneProblem'
import styles from './Cameras.module.css'

interface CameraDialogProps {
  siteId: string
  /** `null` — «Новая камера». */
  camera: Camera | null
  onClose: () => void
}

// Интервал снимков в окне — в минутах, как в спецификации: от 1 минуты до суток
const MIN_EVERY_MIN = 1
const MAX_EVERY_MIN = 1440
const DEFAULT_EVERY_MIN = 5

/** «Новая камера» / «Камера {имя}»: название, ссылка на стрим с интервалом и рабочая зона. */
export function CameraDialog({ siteId, camera, onClose }: CameraDialogProps) {
  const [name, setName] = useState(camera?.name ?? '')
  const [stream, setStream] = useState(camera?.stream_url ?? '')
  const [every, setEvery] = useState(
    String(camera?.capture_every_s ? Math.round(camera.capture_every_s / 60) : DEFAULT_EVERY_MIN),
  )
  const [nameError, setNameError] = useState<string>()
  const [everyError, setEveryError] = useState<string>()
  const [zone, setZone] = useState<Zone | null>(camera?.zone ?? null)
  // Начат, но не замкнут контур: сохранять такую зону нельзя
  const [openContour, setOpenContour] = useState(false)
  // Что не так с зоной — показываем после «Сохранить», а не пока контур рисуют
  const [zoneError, setZoneError] = useState<string | null>(null)
  // «Очистить зону» пересоздаёт редактор: сбрасываются и замкнутый, и начатый контур
  const [editorKey, setEditorKey] = useState(0)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [frameFailed, setFrameFailed] = useState(false)

  const save = useSaveCamera(siteId)
  const remove = useDeleteCamera(siteId)
  // Подложка — последний снимок стройки: пока у камеры нет своих кадров, это ориентир для зоны
  const photos = usePhotos(siteId)
  const frame = newestPhoto(photos.data)
  const frameSrc = useAuthorizedImage(
    frame && !frameFailed ? photoImageUrl(siteId, frame.id) : null,
  )
  const aspect = frame && frame.width > 0 && frame.height > 0 ? frame.width / frame.height : 4 / 3

  /** `?seconds=` из ссылки — в поле интервала (при уходе из поля и при сохранении). */
  const splitLink = (value: string) => {
    const { url, seconds } = takeSeconds(value)
    if (seconds !== null) {
      setEvery(String(Math.max(MIN_EVERY_MIN, Math.round(seconds / 60))))
      setEveryError(undefined)
    }
    setStream(url)
    return url
  }

  const onSave = () => {
    if (!name.trim()) return setNameError('Укажите название камеры')
    const link = splitLink(stream).trim()
    const minutes = Number(every)
    const badEvery =
      link !== '' &&
      !(Number.isInteger(minutes) && minutes >= MIN_EVERY_MIN && minutes <= MAX_EVERY_MIN)
    setEveryError(badEvery ? `От ${MIN_EVERY_MIN} до ${MAX_EVERY_MIN} минут` : undefined)
    if (badEvery) return
    const problem = openContour
      ? 'Контур не замкнут: кликните по первой точке'
      : zone && zoneProblem(zone)
    setZoneError(problem || null)
    if (problem) return
    save.mutate(
      {
        cameraId: camera?.id ?? null,
        data: {
          name: name.trim(),
          stream_url: link || null,
          capture_every_s: link ? minutes * 60 : null,
          zone,
        },
      },
      { onSuccess: onClose },
    )
  }

  const onDelete = () => {
    if (!camera) return
    remove.mutate(camera.id, { onSuccess: onClose })
  }

  const failure = save.error ?? remove.error
  return (
    <Dialog
      title={camera ? `Камера ${camera.name}` : 'Новая камера'}
      onClose={onClose}
      wide
      footer={
        <>
          {camera &&
            (confirmDelete ? (
              <>
                <Button variant="ghost" onClick={() => setConfirmDelete(false)}>
                  Не удалять
                </Button>
                <Button variant="secondary" disabled={remove.isPending} onClick={onDelete}>
                  Удалить камеру
                </Button>
              </>
            ) : (
              <Button variant="ghost" onClick={() => setConfirmDelete(true)}>
                Удалить
              </Button>
            ))}
          <span className={styles.spacer} />
          <Button variant="ghost" onClick={onClose}>
            Отмена
          </Button>
          <Button disabled={save.isPending} onClick={onSave}>
            Сохранить
          </Button>
        </>
      }
    >
      <div className={styles.form}>
        {failure && (
          <Callout tone="behind" title="Не получилось сохранить">
            {failure.message}
          </Callout>
        )}
        <div className={styles.fields}>
          <TextField
            label="Название"
            value={name}
            error={nameError}
            onChange={(e) => setName(e.target.value)}
          />
          <TextField
            label="Ссылка на стрим (необязательно)"
            placeholder="rtsp://…"
            value={stream}
            onChange={(e) => setStream(e.target.value)}
            onBlur={(e) => splitLink(e.target.value)}
          />
          <div
            className={[styles.every, !stream.trim() && styles.everyOff].filter(Boolean).join(' ')}
          >
            <label htmlFor="camera-every">Снимать кадр каждые</label>
            <input
              id="camera-every"
              className={[styles.everyInput, everyError && styles.everyInvalid]
                .filter(Boolean)
                .join(' ')}
              aria-invalid={everyError ? true : undefined}
              type="number"
              inputMode="numeric"
              min={MIN_EVERY_MIN}
              max={MAX_EVERY_MIN}
              disabled={!stream.trim()}
              value={every}
              onChange={(e) => setEvery(e.target.value)}
            />
            <span>мин</span>
            {everyError && (
              <p id="camera-every-error" className={styles.everyError}>
                {everyError}
              </p>
            )}
          </div>
        </div>
        <div className={styles.zoneHead}>
          <h3>Рабочая зона</h3>
          {zone ? (
            <Pill tone="ontrack" icon="check" size="sm">
              Зона задана
            </Pill>
          ) : (
            <Pill tone="dashed" size="sm">
              Зона не задана
            </Pill>
          )}
        </div>
        {frameFailed && (
          <Callout tone="caution" title="Снимок не загрузился">
            Зона рисуется на пустом поле: снимок нужен только как ориентир.
          </Callout>
        )}
        <div className={styles.zoneGrid}>
          <ZoneEditor
            key={editorKey}
            imageUrl={frameSrc}
            aspect={aspect}
            value={zone}
            onChange={setZone}
            onOpenContour={(open) => {
              setOpenContour(open)
              setZoneError(null)
            }}
            onImageError={() => setFrameFailed(true)}
          />
          <div className={styles.zoneSide}>
            <p className="sm muted">
              {frame
                ? 'Ориентир — последний снимок стройки. Кликайте по нему, чтобы ставить вершины; замкните контур на первой точке.'
                : 'Снимков стройки пока нет: зона рисуется на пустом поле. Загрузите снимки, чтобы видеть ориентир.'}
            </p>
            <Button
              variant="ghost"
              size="sm"
              disabled={!zone && !openContour}
              onClick={() => {
                setZone(null)
                setOpenContour(false)
                setZoneError(null)
                setEditorKey(editorKey + 1)
              }}
            >
              Очистить зону
            </Button>
            {zoneError && (
              <p className="sm" role="alert">
                {zoneError}
              </p>
            )}
          </div>
        </div>
      </div>
    </Dialog>
  )
}
