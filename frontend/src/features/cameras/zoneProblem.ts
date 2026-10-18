import type { Zone } from '@/api/schemas'

/** Как `MAX_ZONE_POINTS` и `MIN_ZONE_AREA` бэкенда (`camera/schemas.py`). */
export const MAX_ZONE_POINTS = 100
const MIN_ZONE_AREA = 1e-4

/** Площадь многоугольника в долях кадра (формула шнурования). */
function area(zone: Zone): number {
  let total = 0
  zone.forEach(([x1, y1], i) => {
    const [x2, y2] = zone[(i + 1) % zone.length]!
    total += x1 * y2 - x2 * y1
  })
  return Math.abs(total) / 2
}

/**
 * Почему бэкенд не примет зону, текстом для инженера; `null` — зона годится. Ответ 422
 * бэкенда — список ошибок pydantic, из него интерфейс показывает только общий текст.
 */
export function zoneProblem(zone: Zone): string | null {
  if (zone.length < 3 || zone.length > MAX_ZONE_POINTS) {
    return `Зона — от 3 до ${MAX_ZONE_POINTS} вершин`
  }
  if (area(zone) < MIN_ZONE_AREA) return 'Вершины зоны лежат почти на одной линии'
  return null
}
