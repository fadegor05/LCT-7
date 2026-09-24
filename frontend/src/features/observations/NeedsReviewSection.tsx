import { useState } from 'react'
import { useConfirmFrameTime, useNeedsReview, useSetClipStart } from '@/api/frames'
import type { Frame, NeedsReview } from '@/api/schemas'
import { SectionHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/Button'
import { Callout } from '@/components/ui/Callout'
import { Card } from '@/components/ui/Card'
import { Pill } from '@/components/ui/Pill'
import { QueryState } from '@/components/ui/QueryState'
import { TextField } from '@/components/ui/TextField'
import { parseRuDateTime } from '@/lib/format'
import { plural, pluralFrames, sourceTypeLabels, timeIssueLabels } from '@/lib/labels'
import styles from './Observations.module.css'

const FORMAT_ERROR = 'Формат: дд.мм.гггг чч:мм'

function FrameTimeRow({ frame, siteId }: { frame: Frame; siteId: string }) {
  const [value, setValue] = useState('')
  const [error, setError] = useState<string | null>(null)
  const confirm = useConfirmFrameTime(siteId)
  const submit = () => {
    const parsed = parseRuDateTime(value)
    if (!parsed) return setError(FORMAT_ERROR)
    setError(null)
    confirm.mutate({ frameId: frame.id, capturedAt: parsed })
  }
  return (
    <li className={styles.reviewRow}>
      <span className="sm muted">{frame.camera_name ?? 'Камера не указана'}</span>
      <span className="sm">{sourceTypeLabels[frame.source_type]}</span>
      <span className="sm">{frame.time_issue ? timeIssueLabels[frame.time_issue] : '—'}</span>
      <span>
        <input
          className={styles.input}
          placeholder="дд.мм.гггг чч:мм"
          aria-label={`Дата и время кадра ${frame.id}`}
          aria-invalid={error ? true : undefined}
          value={value}
          onChange={(event) => setValue(event.target.value)}
        />
        {error && (
          <span className="sm" role="alert" style={{ color: 'var(--status-behind)' }}>
            {error}
          </span>
        )}
      </span>
      <Button variant="ghost" size="sm" onClick={submit} disabled={confirm.isPending}>
        Подтвердить
      </Button>
    </li>
  )
}

function ClipStart({ clip, siteId }: { clip: NeedsReview['clips'][number]; siteId: string }) {
  const [value, setValue] = useState('')
  const [error, setError] = useState<string>()
  const setStart = useSetClipStart(siteId)
  return (
    <div className={styles.clipRow}>
      <TextField
        label={`Время начала клипа ${clip.original_name}`}
        placeholder="18.09.2026 08:00"
        value={value}
        error={error}
        onChange={(event) => setValue(event.target.value)}
      />
      <Button
        disabled={setStart.isPending}
        onClick={() => {
          const parsed = parseRuDateTime(value)
          if (!parsed) return setError(FORMAT_ERROR)
          setError(undefined)
          setStart.mutate({ ingestId: clip.ingest_id, clipStartedAt: parsed })
        }}
      >
        Применить ко всем {clip.frames_count}{' '}
        {plural(clip.frames_count, ['кадру', 'кадрам', 'кадрам'])}
      </Button>
    </div>
  )
}

/** «Без даты или времени» (UC-8): такие кадры не участвуют в расчётах, пока время не подтверждено. */
export function NeedsReviewSection({ siteId }: { siteId: string }) {
  const review = useNeedsReview(siteId)
  return (
    <section
      id="no-time"
      style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}
    >
      <QueryState query={review}>
        {({ frames, clips }) => (
          <>
            <SectionHeader
              title="Без даты или времени"
              description={
                frames.length
                  ? `${pluralFrames(frames.length)}. Не участвуют в расчётах, пока время не подтверждено.`
                  : 'Все кадры с известным временем.'
              }
              actions={frames.length > 0 && <Pill tone="caution">Требует проверки</Pill>}
            />
            {clips.map((clip) => (
              <Card key={clip.ingest_id} muted>
                <Callout tone="caution" title="Клип без времени начала">
                  Клип дал {pluralFrames(clip.frames_count)} без времени. Задайте время начала один
                  раз, и все кадры клипа получат его как старт + смещение.
                </Callout>
                <ClipStart clip={clip} siteId={siteId} />
              </Card>
            ))}
            {frames.length > 0 && (
              <ul className={styles.review} aria-label="Кадры без времени">
                {frames.map((frame) => (
                  <FrameTimeRow key={frame.id} frame={frame} siteId={siteId} />
                ))}
              </ul>
            )}
          </>
        )}
      </QueryState>
    </section>
  )
}
