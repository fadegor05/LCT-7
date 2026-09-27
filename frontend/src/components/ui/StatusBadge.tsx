import type { StageStatusValue } from '@/api/schemas'
import type { IconName } from './Icon'
import { Pill, type PillTone } from './Pill'

type Status = StageStatusValue | 'not_due'

const STATUS: Record<Status, { label: string; icon: IconName; tone: PillTone }> = {
  ahead: { label: 'Опережение', icon: 'up', tone: 'ahead' },
  on_track: { label: 'В графике', icon: 'check', tone: 'ontrack' },
  behind: { label: 'Отставание', icon: 'clock', tone: 'behind' },
  // Не рассчитанный этап (status = null) и not_started показываются одним бейджем (§7.1).
  not_started: { label: 'Не начата', icon: 'circle', tone: 'outline' },
  not_due: { label: 'Не начата', icon: 'circle', tone: 'outline' },
  not_observed: { label: 'Не наблюдалось', icon: 'dashed', tone: 'unobserved' },
  not_checked: { label: 'Не проверяется по технике', icon: 'minus', tone: 'neutral' },
}

/** `status = null` — сервер ещё не оценивал этап: его плановое окно не наступило. */
export function StatusBadge({ status }: { status: StageStatusValue | null }) {
  const s = STATUS[status ?? 'not_due']
  return (
    <Pill tone={s.tone} icon={s.icon}>
      {s.label}
    </Pill>
  )
}
