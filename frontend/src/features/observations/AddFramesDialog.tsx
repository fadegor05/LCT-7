import { useState } from 'react'
import { useCameras } from '@/api/cameras'
import { useUploadPhotos } from '@/api/frames'
import type { Camera, UploadReport } from '@/api/schemas'
import { Button, ButtonLink } from '@/components/ui/Button'
import { Callout } from '@/components/ui/Callout'
import { Dialog } from '@/components/ui/Dialog'
import { FileDrop } from '@/components/ui/FileDrop'
import { QueryState } from '@/components/ui/QueryState'
import { SelectField } from '@/components/ui/SelectField'

// Зеркалит StorageSettings.max_batch_mb на бэкенде
const MAX_BATCH_MB = 200

function Failed({ report }: { report: UploadReport }) {
  return (
    <Callout tone="caution" title={`Загружено ${report.uploaded}, с ошибкой ${report.failed}`}>
      <ul>
        {report.items
          .filter((i) => i.error)
          .map((i) => (
            <li key={i.filename}>
              {i.filename}: {i.error}
            </li>
          ))}
      </ul>
    </Callout>
  )
}

interface DialogProps {
  siteId: string
  onClose: () => void
}

/**
 * «Добавить снимки» (UC-3): пачка фото с одной камеры; ошибка одного файла не прерывает
 * остальные. Камеру выбирает инженер: в файлах её идентификатора нет, а без камеры снимки
 * не разложить по камерам в наблюдениях.
 */
export function AddFramesDialog({ siteId, onClose }: DialogProps) {
  const cameras = useCameras(siteId)
  return (
    <QueryState query={cameras}>
      {(list) =>
        list.length === 0 ? (
          <Dialog title="Добавить снимки" onClose={onClose}>
            <Callout tone="caution" title="Сначала добавьте камеру">
              Снимки привязываются к камере: заведите её на вкладке «Камеры».
            </Callout>
            <ButtonLink to={`/sites/${siteId}/cameras`} variant="secondary">
              Перейти к камерам
            </ButtonLink>
          </Dialog>
        ) : (
          <UploadDialog siteId={siteId} cameras={list} onClose={onClose} />
        )
      }
    </QueryState>
  )
}

function UploadDialog({ siteId, cameras, onClose }: DialogProps & { cameras: readonly Camera[] }) {
  const upload = useUploadPhotos(siteId)
  const [files, setFiles] = useState<File[]>([])
  // Камера одна — она и выбрана: лишний шаг ничего не решает
  const [cameraId, setCameraId] = useState(cameras.length === 1 ? cameras[0]!.id : '')
  const report = upload.data

  const totalBytes = files.reduce((sum, file) => sum + file.size, 0)
  const totalMb = totalBytes / 1024 / 1024
  const isBatchTooLarge = totalBytes > MAX_BATCH_MB * 1024 * 1024

  const submit = () =>
    upload.mutate(
      { files, cameraId },
      {
        onSuccess: (result) => {
          if (result.failed === 0) onClose()
          else setFiles([])
        },
      },
    )

  return (
    <Dialog
      title="Добавить снимки"
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            {report ? 'Готово' : 'Отмена'}
          </Button>
          <Button
            onClick={submit}
            disabled={files.length === 0 || !cameraId || upload.isPending || isBatchTooLarge}
          >
            Загрузить
          </Button>
        </>
      }
    >
      <FileDrop
        title="Перетащите снимки"
        hint="JPEG, PNG или WEBP. Дата берётся из метаданных, затем со штампа в кадре. Снимки без даты попадут в список «Без даты»."
        accept="image/jpeg,image/png,image/webp"
        multiple
        buttonLabel="Выбрать файлы"
        onFiles={setFiles}
      />
      {files.length > 0 && (
        <p className="sm" role="status">
          Выбрано: {files.map((f) => f.name).join(', ')}
        </p>
      )}
      <SelectField
        label="Камера"
        options={[
          { value: '', label: 'Выберите камеру' },
          ...cameras.map((c) => ({ value: c.id, label: c.name })),
        ]}
        value={cameraId}
        onChange={(e) => setCameraId(e.target.value)}
      />
      {isBatchTooLarge && (
        <Callout tone="caution">
          Пачка слишком большая: выбрано {totalMb.toFixed(1)} МБ, максимум {MAX_BATCH_MB} МБ
        </Callout>
      )}
      {report && report.failed > 0 && <Failed report={report} />}
      {upload.error && (
        <Callout tone="behind" title="Снимки не загружены">
          {upload.error.message}
        </Callout>
      )}
    </Dialog>
  )
}
