import { useState } from 'react'
import { useUploadCameraVideo } from '@/api/cameras'
import type { Camera } from '@/api/schemas'
import { Button } from '@/components/ui/Button'
import { Callout } from '@/components/ui/Callout'
import { Dialog } from '@/components/ui/Dialog'
import { FileDrop } from '@/components/ui/FileDrop'
import { SelectField } from '@/components/ui/SelectField'
import { TextField } from '@/components/ui/TextField'
import { framesWord } from './plural'

// Шаг кадров в секундах: значения уходят на сервер как есть
const STEPS = [
  { value: '10', label: '10 с' },
  { value: '30', label: '30 с' },
  { value: '60', label: '1 мин' },
  { value: '300', label: '5 мин' },
]
const DEFAULT_STEP = '30'

/** Местное время в формате поля datetime-local: «2026-10-20T09:30». */
function localDateTimeValue(ms: number): string {
  const date = new Date(ms)
  const pad = (n: number) => String(n).padStart(2, '0')
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}`
  )
}

interface VideoUploadDialogProps {
  siteId: string
  camera: Camera
  onClose: () => void
}

/**
 * «Загрузить видео» (UC-видео): запись с камеры режется кадрами с выбранным шагом.
 * Начало записи по умолчанию — дата файла, её можно поправить.
 */
export function VideoUploadDialog({ siteId, camera, onClose }: VideoUploadDialogProps) {
  const upload = useUploadCameraVideo(siteId)
  const [file, setFile] = useState<File | null>(null)
  const [recordedAt, setRecordedAt] = useState('')
  const [step, setStep] = useState(DEFAULT_STEP)
  const [fileError, setFileError] = useState<string>()
  const [timeError, setTimeError] = useState<string>()
  const report = upload.data

  const chooseFile = (picked: File) => {
    setFile(picked)
    setFileError(undefined)
    setRecordedAt(localDateTimeValue(picked.lastModified))
  }

  const submit = () => {
    setFileError(file ? undefined : 'Выберите видеофайл')
    setTimeError(recordedAt ? undefined : 'Укажите начало записи')
    if (!file || !recordedAt) return
    upload.mutate({ cameraId: camera.id, file, recordedAt, stepS: Number(step) })
  }

  return (
    <Dialog
      title="Загрузить видео"
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            {report ? 'Готово' : 'Отмена'}
          </Button>
          {!report && (
            <Button onClick={submit} disabled={upload.isPending}>
              {upload.isPending ? 'Отправка…' : 'Загрузить'}
            </Button>
          )}
        </>
      }
    >
      <p className="sm muted">Камера «{camera.name}»</p>
      <FileDrop
        title="Перетащите видео"
        hint="Запись с камеры: MP4, MOV, AVI, MKV или WEBM. Сервер нарежет её кадрами и обработает как снимки."
        accept="video/*"
        buttonLabel="Выбрать видео"
        disabled={upload.isPending}
        onFiles={([picked]) => picked && chooseFile(picked)}
      />
      {file && (
        <p className="sm" role="status">
          Выбрано: {file.name}
        </p>
      )}
      {fileError && <Callout tone="behind" title={fileError} />}
      <TextField
        label="Начало записи"
        type="datetime-local"
        hint="Местное время съёмки. По умолчанию — дата файла."
        error={timeError}
        value={recordedAt}
        onChange={(event) => {
          setRecordedAt(event.target.value)
          setTimeError(undefined)
        }}
      />
      <SelectField
        label="Шаг кадров"
        options={STEPS}
        value={step}
        onChange={(event) => setStep(event.target.value)}
      />
      {report && (
        <Callout
          title={`Принято ${report.uploaded} ${framesWord(report.uploaded)}, они обрабатываются`}
        >
          {report.failed > 0 ? `С ошибкой: ${report.failed}` : undefined}
        </Callout>
      )}
      {upload.error && (
        <Callout tone="behind" title="Видео не загружено">
          {upload.error.message}
        </Callout>
      )}
    </Dialog>
  )
}
