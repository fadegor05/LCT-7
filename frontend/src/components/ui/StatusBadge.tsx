import type { StageStatusValue } from '@/api/schemas'
import type { IconName } from './Icon'
import { Pill, type PillTone } from './Pill'

const STATUS: Record<StageStatusValue, { label: string; icon: IconName; tone: PillTone }> = {
  ahead: { label: 'Опережение', icon: 'up', tone: 'ahead' },
  on_track: { label: 'В графике', icon: 'check', tone: 'ontrack' },
  behind: { label: 'Отставание', icon: 'clock', tone: 'behind' },
  // not_due и not_started показываются одним бейджем (architecture §7.1).
  not_started: { label: 'Не начата', icon: 'circle', tone: 'outline' },
  not_due: { label: 'Не начата', icon: 'circle', tone: 'outline' },
  not_observed: { label: 'Не наблюдалось', icon: 'dashed', tone: 'unobserved' },
  not_checked: { label: 'Не проверяется по технике', icon: 'minus', tone: 'neutral' },
}

export function StatusBadge({ status }: { status: StageStatusValue }) {
  const s = STATUS[status]
  return (
    <Pill tone={s.tone} icon={s.icon}>
      {s.label}
    </Pill>
  )
}
