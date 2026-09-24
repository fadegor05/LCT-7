import { useState } from 'react'
import { useReferenceFrame, useSaveCamera } from '@/api/cameras'
import { cameraInputSchema, type Camera, type Point } from '@/api/schemas'
import { Button } from '@/components/ui/Button'
import { Callout } from '@/components/ui/Callout'
import { Dialog } from '@/components/ui/Dialog'
import { Pill } from '@/components/ui/Pill'
import { TextField } from '@/components/ui/TextField'
import { ZoneEditor } from './ZoneEditor'
import styles from './Cameras.module.css'

interface CameraDialogProps {
  siteId: string
  /** null — новая камера. */
  camera: Camera | null
  onClose: () => void
}

/** Настройка камеры (UC-6): название, ссылка на стрим, рабочая зона на опорном кадре. */
export function CameraDialog({ siteId, camera, onClose }: CameraDialogProps) {
  const save = useSaveCamera(siteId)
  const frame = useReferenceFrame()
  const [name, setName] = useState(camera?.name ?? '')
  const [streamUrl, setStreamUrl] = useState(camera?.stream_url ?? '')
  const [points, setPoints] = useState<Point[]>(camera?.zone_polygon ?? [])
  const [closed, setClosed] = useState(Boolean(camera?.zone_polygon))
  const [imageUrl, setImageUrl] = useState<string | null>(null)
  const [nameError, setNameError] = useState<string>()

  const submit = () => {
    const parsed = cameraInputSchema.safeParse({
      name,
      stream_url: streamUrl.trim() || null,
      zone_polygon: closed && points.length >= 3 ? points : null,
    })
    if (!parsed.success) {
      setNameError(parsed.error.issues.find((i) => i.path[0] === 'name')?.message)
      return
    }
    setNameError(undefined)
    save.mutate({ cameraId: camera?.id ?? null, data: parsed.data }, { onSuccess: onClose })
  }

  return (
    <Dialog
      wide
      title={camera ? `Камера ${camera.name}` : 'Новая камера'}
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Отмена
          </Button>
          <Button onClick={submit} disabled={save.isPending}>
            Сохранить
          </Button>
        </>
      }
    >
      <div className={styles.formGrid}>
        <TextField
          label="Название"
          placeholder="К-5"
          value={name}
          error={nameError}
          onChange={(event) => setName(event.target.value)}
        />
        <TextField
          label="Ссылка на стрим (необязательно)"
          placeholder="rtsp://[адрес камеры]/stream1"
          hint="Если ссылки нет, кадры загружаются файлами"
          value={streamUrl}
          onChange={(event) => setStreamUrl(event.target.value)}
        />
      </div>

      <div className={styles.zoneHead}>
        <h3>Рабочая зона</h3>
        {closed ? (
          <Pill tone="ontrack" icon="check">
            Зона задана
          </Pill>
        ) : (
          <Pill tone="neutral">Зона не задана</Pill>
        )}
      </div>
      <p className="sm muted">
        Кликайте по кадру, чтобы ставить вершины контура; замкните его на первой точке. Вершины
        перетаскиваются мышью.
      </p>
      <ZoneEditor
        imageUrl={imageUrl}
        points={points}
        closed={closed}
        onChange={(next, isClosed) => {
          setPoints(next)
          setClosed(isClosed)
        }}
      />
      <div className={styles.actions}>
        <Button
          variant="secondary"
          size="sm"
          disabled={!streamUrl.trim() || frame.isPending}
          onClick={() =>
            frame.mutate(streamUrl.trim(), { onSuccess: (data) => setImageUrl(data.image_url) })
          }
        >
          {frame.isPending ? 'Ждём кадр…' : 'Взять кадр со стрима'}
        </Button>
        <label
          className="sm"
          style={{ alignSelf: 'center', cursor: 'pointer', textDecoration: 'underline' }}
        >
          Загрузить свой кадр
          <input
            type="file"
            accept="image/*"
            className="srOnly"
            onChange={(event) => {
              const file = event.target.files?.[0]
              if (file) setImageUrl(URL.createObjectURL(file))
            }}
          />
        </label>
        <Button
          variant="ghost"
          size="sm"
          disabled={points.length === 0}
          onClick={() => {
            setPoints([])
            setClosed(false)
          }}
        >
          Очистить зону
        </Button>
      </div>
      <p className="sm muted">
        Кадр нужен только для рисования контура и не сохраняется: дату и время ему задавать не
        нужно. Кадр со стрима может подгружаться до 10 секунд. Зона одна на камеру и действует на
        все её кадры. После сохранения активность машин пересчитывается по загруженным кадрам.
      </p>
      {frame.error && (
        <Callout tone="caution" title="Кадр со стрима не получен">
          {frame.error.message}
        </Callout>
      )}
      {save.error && (
        <Callout tone="behind" title="Камера не сохранена">
          {save.error.message}
        </Callout>
      )}
    </Dialog>
  )
}
