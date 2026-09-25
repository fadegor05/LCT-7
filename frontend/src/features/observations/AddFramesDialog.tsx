import { useState } from 'react'
import { useUploadPhotos } from '@/api/frames'
import type { UploadReport } from '@/api/schemas'
import { Button } from '@/components/ui/Button'
import { Callout } from '@/components/ui/Callout'
import { Dialog } from '@/components/ui/Dialog'
import { FileDrop } from '@/components/ui/FileDrop'

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

/** «Добавить снимки» (UC-3): пачка фото; ошибка одного файла не прерывает остальные. */
export function AddFramesDialog({ siteId, onClose }: { siteId: string; onClose: () => void }) {
  const upload = useUploadPhotos(siteId)
  const [files, setFiles] = useState<File[]>([])
  const report = upload.data

  const submit = () =>
    upload.mutate(files, {
      onSuccess: (result) => {
        if (result.failed === 0) onClose()
        else setFiles([])
      },
    })

  return (
    <Dialog
      title="Добавить снимки"
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            {report ? 'Готово' : 'Отмена'}
          </Button>
          <Button onClick={submit} disabled={files.length === 0 || upload.isPending}>
            Загрузить
          </Button>
        </>
      }
    >
      <FileDrop
        title="Перетащите снимки"
        hint="JPEG, PNG или WEBP. Дата берётся из метаданных, затем у соседних снимков пачки. Снимки без даты попадут в список «Без даты»."
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
      {report && report.failed > 0 && <Failed report={report} />}
      {upload.error && (
        <Callout tone="behind" title="Снимки не загружены">
          {upload.error.message}
        </Callout>
      )}
    </Dialog>
  )
}
