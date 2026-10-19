import { useState } from 'react'
import { useCameras } from '@/api/cameras'
import { chunkFiles, useUploadPhotos } from '@/api/frames'
import type { Camera, UploadReport } from '@/api/schemas'
import { Button, ButtonLink } from '@/components/ui/Button'
import { Callout } from '@/components/ui/Callout'
import { Dialog } from '@/components/ui/Dialog'
import { FileDrop } from '@/components/ui/FileDrop'
import { QueryState } from '@/components/ui/QueryState'
import { SelectField } from '@/components/ui/SelectField'
import { plural } from '@/lib/labels'

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
  const [sent, setSent] = useState(0)

  const submit = () => {
    setSent(0)
    upload.mutate(
      { files, cameraId, onProgress: setSent },
      {
        onSuccess: (result) => {
          if (result.failed === 0) onClose()
          else setFiles([])
        },
      },
    )
  }

  return (
    <Dialog
      title="Добавить снимки"
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            {report ? 'Готово' : 'Отмена'}
          </Button>
          <Button onClick={submit} disabled={files.length === 0 || !cameraId || upload.isPending}>
            {upload.isPending ? 'Отправка…' : 'Загрузить'}
          </Button>
        </>
      }
    >
      <FileDrop
        title="Перетащите снимки"
        hint="JPEG, PNG или WEBP, сколько угодно снимков. После отправки сервер обработает их в фоне: дата со штампа, из метаданных или имени файла и техника на кадре. Снимки без даты попадут в список «Без даты»."
        accept="image/jpeg,image/png,image/webp"
        multiple
        buttonLabel="Выбрать файлы"
        onFiles={setFiles}
      />
      {files.length > 0 && (
        <p className="sm" role="status">
          {upload.isPending
            ? `Отправлено ${sent} из ${files.length}`
            : files.length > 5
              ? `Выбрано: ${files.length} ${plural(files.length, ['снимок', 'снимка', 'снимков'])}` +
                (chunkFiles(files).length > 1 ? ` — уйдут ${chunkFiles(files).length} пачками` : '')
              : `Выбрано: ${files.map((f) => f.name).join(', ')}`}
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
      {report && report.failed > 0 && <Failed report={report} />}
      {upload.error && (
        <Callout tone="behind" title="Снимки не загружены">
          {upload.error.message}
        </Callout>
      )}
    </Dialog>
  )
}
