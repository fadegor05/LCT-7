import { useState } from 'react'
import { useCameras } from '@/api/cameras'
import {
  annotatedThumbUrl,
  useSetPhotoTime,
  useSetTimesBatch,
  useUndatedPhotos,
} from '@/api/frames'
import type { Camera, Photo } from '@/api/schemas'
import { SectionHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/Button'
import { Callout } from '@/components/ui/Callout'
import { Card } from '@/components/ui/Card'
import { FrameView } from '@/components/ui/FrameView'
import { Pill } from '@/components/ui/Pill'
import { QueryState } from '@/components/ui/QueryState'
import { parseRuDateTime } from '@/lib/format'
import { plural } from '@/lib/labels'
import styles from './Observations.module.css'

const FORMAT_ERROR = 'Время в формате дд.мм.гггг чч:мм'

/** 2026-08-05T10:30:15 → 05.08.2026 10:30; только дата — «05.08.2026 » для дописывания времени. */
function toRu(value: string | null | undefined): string {
  if (!value) return ''
  const [d, t] = value.split('T')
  const date = d!.split('-').reverse().join('.')
  return t ? `${date} ${t.slice(0, 5)}` : `${date} `
}

/** Подсказка в поле: выбившееся время, неуверенный штамп или дата-подсказка. */
const suggestion = (p: Photo) =>
  toRu(p.time_check === 'series_outlier' ? p.captured_at : (p.uncertain_at ?? p.date_hint))

/** Почему кадр здесь (clean-mvp, time_issue). */
function reason(p: Photo): string {
  if (p.time_check === 'series_outlier') return 'Время выбивается из серии'
  if (p.uncertain_at || p.date_hint) return 'Штамп читается неуверенно'
  if (p.camera_id) return 'Штамп не распознан, метаданных нет'
  return 'Даты нет ни в метаданных, ни в имени файла, ни у соседних снимков'
}

/** Время вводится по местному времени стройки и не бывает в будущем. */
function checkTime(value: string): { at: string } | { error: string } {
  const at = parseRuDateTime(value)
  if (!at) return { error: FORMAT_ERROR }
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  const local = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}:00`
  if (at > local) return { error: 'Время съёмки не может быть в будущем' }
  return { at }
}

function PhotoTimeRow({ siteId, photo }: { siteId: string; photo: Photo }) {
  // Подсказка — сразу в поле: подтвердить, а не набирать
  const [value, setValue] = useState(suggestion(photo))
  const [error, setError] = useState<string | null>(null)
  const save = useSetPhotoTime(siteId)
  const submit = () => {
    const checked = checkTime(value)
    if ('error' in checked) return setError(checked.error)
    setError(null)
    save.mutate({ photoId: photo.id, capturedAt: checked.at })
  }
  const message = error ?? save.error?.message
  return (
    <li className={styles.undatedRow}>
      <span className={styles.undatedThumb}>
        <FrameView
          imageUrl={annotatedThumbUrl(siteId, photo.id)}
          alt={`Кадр ${photo.original_name}`}
        />
      </span>
      <span className={styles.undatedText}>
        <span className="sm muted" title={photo.original_name}>
          Фото · {photo.original_name}
        </span>
        <span className="sm">{reason(photo)}</span>
      </span>
      <span className={styles.timeForm}>
        <input
          className={styles.input}
          placeholder="дд.мм.гггг чч:мм"
          aria-label={`Время кадра ${photo.original_name}`}
          aria-invalid={message ? true : undefined}
          value={value}
          onChange={(e) => setValue(e.target.value)}
        />
        <Button size="sm" disabled={save.isPending} onClick={submit}>
          Подтвердить
        </Button>
        {message && (
          <span className={`sm ${styles.error}`} role="alert">
            {message}
          </span>
        )}
      </span>
    </li>
  )
}

/** Пакетный ввод для кадров одной камеры: первый кадр и шаг (clean-mvp). */
function BatchTime({
  siteId,
  photos,
  camera,
}: {
  siteId: string
  photos: Photo[]
  camera: string
}) {
  const [first, setFirst] = useState(suggestion(photos[0]!))
  const [step, setStep] = useState('1')
  const [error, setError] = useState<string | null>(null)
  const save = useSetTimesBatch(siteId)
  const submit = () => {
    const checked = checkTime(first)
    if ('error' in checked) return setError(checked.error)
    const minutes = Number(step.replace(',', '.'))
    if (!(minutes > 0) || minutes > 24 * 60)
      return setError('Шаг — минуты, больше нуля и не больше суток')
    setError(null)
    save.mutate({ photoIds: photos.map((p) => p.id), first: checked.at, stepMinutes: minutes })
  }
  const message = error ?? save.error?.message
  return (
    <div
      className={`${styles.timeForm} ${styles.batch}`}
      role="group"
      aria-label={`Пакетный ввод: ${camera}`}
    >
      <label className={styles.field}>
        <span className="sm muted">Время первого кадра</span>
        <input
          className={styles.input}
          placeholder="дд.мм.гггг чч:мм"
          value={first}
          onChange={(e) => setFirst(e.target.value)}
        />
      </label>
      <label className={styles.field}>
        <span className="sm muted">Шаг, мин</span>
        <input
          className={styles.input}
          inputMode="decimal"
          size={5}
          value={step}
          onChange={(e) => setStep(e.target.value)}
        />
      </label>
      <Button size="sm" variant="secondary" disabled={save.isPending} onClick={submit}>
        Применить к {photos.length} {plural(photos.length, ['кадру', 'кадрам', 'кадрам'])}
      </Button>
      {message && (
        <span className={`sm ${styles.error}`} role="alert">
          {message}
        </span>
      )}
    </div>
  )
}

/** Кадры по камерам в порядке выгрузки регистратора (имя файла), как серия штампов. */
function byCamera(photos: readonly Photo[], cameras: readonly Camera[]) {
  const groups = new Map<string, Photo[]>()
  for (const p of [...photos].sort((a, b) => a.original_name.localeCompare(b.original_name)))
    groups.set(p.camera_id ?? '', [...(groups.get(p.camera_id ?? '') ?? []), p])
  return [...groups].map(([id, list]) => ({
    key: id || 'none',
    name: cameras.find((c) => c.id === id)?.name ?? 'Без камеры',
    photos: list,
  }))
}

/**
 * «Без даты или времени» (clean-mvp, §8.7): кадры без даты и кадры, время которых выбилось
 * из серии камеры. Не участвуют в расчётах, пока время не подтверждено. У кадра — причина,
 * поле времени с подсказкой и «Подтвердить»; для нескольких кадров камеры — «первый + шаг».
 */
export function NeedsReviewSection({ siteId }: { siteId: string }) {
  const undated = useUndatedPhotos(siteId)
  const cameras = useCameras(siteId).data ?? []
  return (
    <QueryState query={undated}>
      {(photos) => {
        const n = photos.length
        return (
          <Card id="no-date" className={n ? styles.needsCheck : undefined}>
            <SectionHeader
              title="Без даты или времени"
              description={
                n
                  ? `${n} ${plural(n, ['кадр', 'кадра', 'кадров'])}. Не участвуют в расчётах, пока время не подтверждено.`
                  : 'У всех снимков известны дата и время.'
              }
              actions={
                n > 0 && (
                  <Pill tone="caution" icon="alert" size="sm">
                    Требует проверки
                  </Pill>
                )
              }
            />
            {n > 0 && (
              <Callout>
                Время съёмки не бывает в будущем. После подтверждения кадр попадёт в наблюдение за
                свой день, и выводы по стройке пересчитаются.
              </Callout>
            )}
            {byCamera(photos, cameras).map((g) => (
              <section
                key={g.key}
                className={styles.undatedGroup}
                aria-label={`Без даты: ${g.name}`}
              >
                <h3>{g.name}</h3>
                {g.photos.length > 1 && (
                  <BatchTime siteId={siteId} photos={g.photos} camera={g.name} />
                )}
                <ul className={styles.undated} aria-label="Снимки без даты">
                  {g.photos.map((p) => (
                    <PhotoTimeRow
                      key={`${p.id}-${p.captured_at ?? ''}`}
                      siteId={siteId}
                      photo={p}
                    />
                  ))}
                </ul>
              </section>
            ))}
          </Card>
        )
      }}
    </QueryState>
  )
}
