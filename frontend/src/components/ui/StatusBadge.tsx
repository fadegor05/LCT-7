import type { StageStatusValue } from '@/api/schemas'
import { todayIso } from '@/lib/format'
import type { IconName } from './Icon'
import { Pill, type PillTone } from './Pill'

type Status = StageStatusValue | 'not_due' | 'not_assessed'

const STATUS: Record<Status, { label: string; icon: IconName; tone: PillTone }> = {
  ahead: { label: 'Опережение', icon: 'up', tone: 'ahead' },
  on_track: { label: 'В графике', icon: 'check', tone: 'ontrack' },
  behind: { label: 'Отставание', icon: 'clock', tone: 'behind' },
  // Окно этапа не наступило (status = null) и not_started показываются одним бейджем (§7.1).
  not_started: { label: 'Не начата', icon: 'circle', tone: 'outline' },
  not_due: { label: 'Не начата', icon: 'circle', tone: 'outline' },
  not_observed: { label: 'Не наблюдалось', icon: 'dashed', tone: 'unobserved' },
  not_checked: { label: 'Не проверяется по технике', icon: 'minus', tone: 'neutral' },
  // Окно наступило, а оценки нет: сервер ещё не пересчитал этап. Это не «не начата» —
  // о стройке мы тут ничего не утверждаем (§7.1).
  not_assessed: { label: 'Не оценён', icon: 'dashed', tone: 'unobserved' },
}

function resolve(
  status: StageStatusValue | null,
  plannedStart: string | null | undefined,
  asOf: string,
): Status {
  if (status) return status
  // Сервер не оценивает этап, пока его окно не наступило. Если окно уже идёт (или дат нет),
  // null значит «оценки ещё нет», а не «не начата».
  if (plannedStart === undefined) return 'not_due'
  return plannedStart === null || plannedStart <= asOf ? 'not_assessed' : 'not_due'
}

interface StatusBadgeProps {
  status: StageStatusValue | null
  /** Плановое начало этапа (YYYY-MM-DD) — чтобы отличить «окно не наступило» от «не оценён». */
  plannedStart?: string | null
  /** Дата данных объекта (опорная дата расчёта); без неё — сегодня. */
  asOf?: string | null
}

export function StatusBadge({ status, plannedStart, asOf }: StatusBadgeProps) {
  const s = STATUS[resolve(status, plannedStart, asOf ?? todayIso())]
  return (
    <Pill tone={s.tone} icon={s.icon}>
      {s.label}
    </Pill>
  )
}
