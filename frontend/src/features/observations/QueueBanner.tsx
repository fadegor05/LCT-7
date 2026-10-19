import { usePhotoQueue } from '@/api/frames'
import { Callout } from '@/components/ui/Callout'
import { plural } from '@/lib/labels'

/**
 * Снимки объекта в фоновой обработке: дату со штампа и технику ставит сервер после загрузки.
 * Пока очередь не пуста, итоги объекта — по уже обработанным снимкам; когда она опустеет,
 * экраны обновятся сами.
 */
export function QueueBanner({ siteId }: { siteId: string }) {
  const { left } = usePhotoQueue(siteId)
  if (left === 0) return null
  return (
    <div role="status" aria-live="polite">
      <Callout title={`Обрабатываются снимки: осталось ${left}`}>
        Сервер читает дату со штампа и ищет технику на{' '}
        {plural(left, ['снимке', 'снимках', 'снимках'])}. Итоги пока по уже обработанным снимкам —
        экраны обновятся сами, когда обработка закончится.
      </Callout>
    </div>
  )
}
