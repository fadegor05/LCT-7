import type { ReactNode } from 'react'
import type { UseQueryResult } from '@tanstack/react-query'
import type { Site } from '@/api/schemas'
import { ButtonLink } from '@/components/ui/Button'
import { QueryState } from '@/components/ui/QueryState'

interface SiteQueryStateProps {
  query: Pick<UseQueryResult<Site>, 'data' | 'error' | 'isPending'>
  children: (site: Site) => ReactNode
}

/** Стройка из URL: если её нет (или адрес кривой), из ошибки есть путь назад к списку. */
export function SiteQueryState({ query, children }: SiteQueryStateProps) {
  return (
    <QueryState
      query={query}
      errorAction={
        <ButtonLink to="/sites" variant="ghost">
          К стройкам
        </ButtonLink>
      }
    >
      {children}
    </QueryState>
  )
}
