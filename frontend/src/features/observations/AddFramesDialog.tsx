import { useState } from 'react'
import { useCameras } from '@/api/cameras'
import { useCreateIngest, useStopIngest, useStreams } from '@/api/frames'
import type { SourceType } from '@/api/schemas'
import { Button } from '@/components/ui/Button'
import { Callout } from '@/components/ui/Callout'
import { Dialog } from '@/components/ui/Dialog'
import { FileDrop } from '@/components/ui/FileDrop'
import { Pill } from '@/components/ui/Pill'
import { Segmented } from '@/components/ui/Segmented'
import { SelectField } from '@/components/ui/SelectField'
import { TextField } from '@/components/ui/TextField'
import { formatShortDateTime, parseRuDateTime } from '@/lib/format'
import { pluralFrames, sourceTypeLabels } from '@/lib/labels'
import styles from './Observations.module.css'

const sources = (Object.keys(sourceTypeLabels) as SourceType[]).map((value) => ({
  value,
  label: sourceTypeLabels[value],
}))

/** Шаг нарезки видео 60–1800 с и стрима 300–1800 с (DataModel: ingest.slice_step_sec). */
const VIDEO_STEPS = [
  { value: '60', label: '1 кадр в минуту' },
  { value: '300', label: '1 кадр в 5 минут' },
  { value: '1200', label: '1 кадр в 20 минут' },
  { value: '1800', label: '1 кадр в 30 минут' },
]
const STREAM_STEPS = [
  { value: '300', label: 'каждые 5 минут' },
  { value: '1200', label: 'каждые 20 минут' },
  { value: '1800', label: 'каждые 30 минут' },
]

/** «Добавить кадры» (UC-3): фото, видеофайл или стрим. Камеру выбирает инженер. */
export function AddFramesDialog({ siteId, onClose }: { siteId: string; onClose: () => void }) {
  const cameras = useCameras(siteId)
  const streams = useStreams(siteId)
  const create = useCreateIngest(siteId)
  const stop = useStopIngest(siteId)
  const [source, setSource] = useState<SourceType>('photo')
  const [files, setFiles] = useState<File[]>([])
  const [cameraId, setCameraId] = useState('')
  const [videoStep, setVideoStep] = useState('300')
  const [streamStep, setStreamStep] = useState('1200')
  const [clipStart, setClipStart] = useState('')
  const [clipError, setClipError] = useState<string>()

  const allCameras = cameras.data ?? []
  const streamCameras = allCameras.filter((c) => c.stream_url)
  const pool = source === 'stream' ? streamCameras : allCameras
  const camera = pool.find((c) => c.id === cameraId) ?? pool[0]
  const running = (streams.data ?? []).filter((s) => s.state === 'running')

  const canSubmit =
    Boolean(camera) && (source === 'stream' || files.length > 0) && !create.isPending

  const submit = () => {
    if (!camera) return
    let clipStartedAt: string | null = null
    if (source === 'video' && clipStart.trim()) {
      clipStartedAt = parseRuDateTime(clipStart)
      if (!clipStartedAt) return setClipError('Формат: дд.мм.гггг чч:мм')
    }
    create.mutate(
      {
        source_type: source,
        camera_id: camera.id,
        files: source === 'stream' ? [] : files,
        slice_step_sec:
          source === 'photo' ? undefined : Number(source === 'video' ? videoStep : streamStep),
        clip_started_at: clipStartedAt,
      },
      { onSuccess: onClose },
    )
  }

  const cameraSelect = (label: string) => (
    <SelectField
      label={label}
      value={camera?.id ?? ''}
      onChange={(event) => setCameraId(event.target.value)}
      options={pool.map((c) => ({ value: c.id, label: c.name }))}
    />
  )

  return (
    <Dialog
      title="Добавить кадры"
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Отмена
          </Button>
          <Button onClick={submit} disabled={!canSubmit}>
            Добавить
          </Button>
        </>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
        <h3>Источник кадров</h3>
        <Segmented
          label="Источник"
          options={sources}
          value={source}
          onChange={(value) => {
            setSource(value)
            setFiles([])
            setCameraId('')
          }}
        />
      </div>

      {source !== 'stream' && (
        <>
          <FileDrop
            title={source === 'photo' ? 'Перетащите снимки' : 'Перетащите видеофайл'}
            hint={
              source === 'photo'
                ? 'Дата и время берутся из метаданных, затем со штампа в кадре. Нераспознанные попадут в ленту без даты.'
                : 'Видео нарезается на кадры с заданным шагом. Оригинал не хранится: остаются кадры и короткие клипы-доказательства.'
            }
            accept={source === 'photo' ? 'image/*' : 'video/*'}
            multiple={source === 'photo'}
            buttonLabel="Выбрать файлы"
            onFiles={setFiles}
          />
          {files.length > 0 && (
            <p className="sm" role="status">
              Выбрано: {files.map((f) => f.name).join(', ')}
            </p>
          )}
        </>
      )}

      {source === 'photo' && (
        <div className={styles.formGrid}>
          {cameraSelect('Камера')}
          <p className="sm muted" style={{ alignSelf: 'end' }}>
            Камеру выбираете вы: в файлах её идентификатор не гарантирован.
          </p>
        </div>
      )}

      {source === 'video' && (
        <div className={styles.formGrid}>
          {cameraSelect('Камера')}
          <SelectField
            label="Шаг нарезки"
            value={videoStep}
            onChange={(event) => setVideoStep(event.target.value)}
            options={VIDEO_STEPS}
          />
          <TextField
            label="Время начала клипа"
            placeholder="18.09.2026 08:00"
            hint="Если времени нет в файле: кадры получат его как старт + смещение"
            error={clipError}
            value={clipStart}
            onChange={(event) => setClipStart(event.target.value)}
          />
        </div>
      )}

      {source === 'stream' && (
        <>
          <p className="sm muted">
            Ссылка на стрим задаётся в настройках камеры. Здесь выбирается камера со ссылкой и
            периодичность нарезки кадров.
          </p>
          {running.map((s) => (
            <div key={s.id} className={styles.clipRow}>
              <Pill tone="ontrack" icon="check">
                Подключено
              </Pill>
              <span className="sm">
                {allCameras.find((c) => c.id === s.camera_id)?.name} · последний кадр{' '}
                {formatShortDateTime(s.last_frame_at)} · всего {pluralFrames(s.frames_count)}
              </span>
              <Button
                variant="ghost"
                size="sm"
                disabled={stop.isPending}
                onClick={() => stop.mutate(s.id)}
              >
                Остановить
              </Button>
            </div>
          ))}
          {streamCameras.length === 0 ? (
            <Callout tone="caution" title="Нет камер со стримом">
              Добавьте ссылку на стрим в настройках камеры на вкладке «Камеры».
            </Callout>
          ) : (
            <div className={styles.formGrid}>
              {cameraSelect('Камера со стримом')}
              <SelectField
                label="Периодичность нарезки"
                value={streamStep}
                onChange={(event) => setStreamStep(event.target.value)}
                options={STREAM_STEPS}
              />
            </div>
          )}
        </>
      )}

      {create.error && (
        <Callout tone="behind" title="Кадры не добавлены">
          {create.error.message}
        </Callout>
      )}
    </Dialog>
  )
}
