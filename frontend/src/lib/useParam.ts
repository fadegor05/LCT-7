import { useParams } from 'react-router'

/** Обязательный параметр маршрута. Маршруты объявлены в app/routes.tsx, так что он всегда есть. */
export function useRequiredParam(name: string): string {
  const value = useParams()[name]
  if (!value) throw new Error(`Нет параметра маршрута «${name}»`)
  return value
}
