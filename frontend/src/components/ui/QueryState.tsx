import type { ReactNode } from 'react'
import type { UseQueryResult } from '@tanstack/react-query'
import { Callout } from './Callout'

interface QueryStateProps<T> {
  query: Pick<UseQueryResult<T>, 'data' | 'error' | 'isPending'>
  children: (data: T) => ReactNode
  loadingText?: string
}

/** Единообразные состояния загрузки и ошибки для данных из TanStack Query. */
export function QueryState<T>({ query, children, loadingText = 'Загрузка…' }: QueryStateProps<T>) {
  if (query.isPending) {
    return (
      <p className="muted" role="status">
        {loadingText}
      </p>
    )
  }
  if (query.error) {
    return (
      <Callout tone="behind" title="Не удалось загрузить данные">
        {query.error.message}
      </Callout>
    )
  }
  return <>{children(query.data as T)}</>
}
