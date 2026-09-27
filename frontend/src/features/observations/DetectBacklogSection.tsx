import { useState } from 'react'
import { useDetectBacklog, usePhotos } from '@/api/frames'
import { ApiError } from '@/api/client'
import type { CalloutTone } from '@/components/ui/Callout'
import { Button } from '@/components/ui/Button'
import { Callout } from '@/components/ui/Callout'
import { QueryState } from '@/components/ui/QueryState'
import styles from './Observations.module.css'

interface DetectBacklogSectionProps {
  siteId: string
}

interface Message {
  tone: CalloutTone
  text: string
  title?: string
}

/** Кнопка «Распознать необработанные» и результат операции. */
export function DetectBacklogSection({ siteId }: DetectBacklogSectionProps) {
  const photos = usePhotos(siteId)
  const detectBacklog = useDetectBacklog(siteId)
  const [message, setMessage] = useState<Message | null>(null)

  const hasNonDone = photos.data?.some((p) => p.processing_status !== 'done') ?? false

  const handleDetect = () => {
    setMessage(null)
    detectBacklog.mutate(undefined, {
      onSuccess: (data) => {
        const parts = [
          `Обработано ${data.processed}: готово ${data.done}, с ошибкой ${data.failed}`,
        ]
        if (data.skipped > 0) {
          parts.push(`, пропущено ${data.skipped}`)
        }
        setMessage({
          tone: 'neutral',
          text: parts.join(''),
        })
      },
      onError: (error) => {
        if (error instanceof ApiError && error.status === 409) {
          setMessage({
            tone: 'caution',
            title: 'Детектор не настроен',
            text: '',
          })
        } else if (error instanceof Error) {
          setMessage({
            tone: 'caution',
            text: `Не удалось распознать снимки: ${error.message}`,
          })
        } else {
          setMessage({
            tone: 'caution',
            text: 'Ошибка при распознавании снимков',
          })
        }
      },
    })
  }

  if (!hasNonDone && !message) return null

  return (
    <QueryState query={photos}>
      {() => (
        <section className={styles.detectBacklog}>
          <div className={styles.detectBacklogHeader}>
            <Button onClick={handleDetect} disabled={detectBacklog.isPending}>
              Распознать необработанные
            </Button>
          </div>

          {message && (
            <Callout tone={message.tone} title={message.title}>
              {message.text}
            </Callout>
          )}
        </section>
      )}
    </QueryState>
  )
}
