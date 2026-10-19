import type { MarkerPeriod } from '@/api/schemas'
import { Callout } from '@/components/ui/Callout'
import { formatPeriod } from '@/lib/format'

/**
 * «Маркерная техника этапа» (clean-mvp): какие машины отличают этап от идущих одновременно и
 * когда. Только маркеры задают начало и окончание этапа и отставание в днях.
 */
export function MarkerNote({ markers }: { markers: readonly MarkerPeriod[] }) {
  if (markers.length === 0) {
    return (
      <Callout title="Нет отличительной техники">
        Вся нормативная техника этапа есть и у этапов, идущих в это же время, поэтому по ней этап не
        отличить. Статус выводится по полному комплекту в дни, когда этапы не различимы.
      </Callout>
    )
  }
  return (
    <Callout title="Маркерная техника этапа">
      Отличает этап от идущих одновременно:{' '}
      {markers.map((p) => `${p.name.toLowerCase()} (${formatPeriod(p.start, p.end)})`).join(', ')}.
      Только маркеры задают начало и окончание этапа и отставание в днях.
    </Callout>
  )
}
