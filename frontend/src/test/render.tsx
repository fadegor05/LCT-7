import type { ReactElement } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider, type RouteObject } from 'react-router'
import { routes } from '@/app/routes'

export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false } },
  })
}

/** Рендер всего приложения на нужном URL (интеграционные тесты страниц поверх MSW). */
export function renderRoute(url: string) {
  const client = createTestQueryClient()
  const router = createMemoryRouter(routes, { initialEntries: [url] })
  const user = userEvent.setup()
  const utils = render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return { ...utils, user, router, client }
}

/** Рендер отдельного компонента внутри роутера и QueryClient. */
export function renderWithProviders(
  ui: ReactElement,
  { path = '/', url = '/' }: { path?: string; url?: string } = {},
) {
  const client = createTestQueryClient()
  const extra: RouteObject[] = [{ path: '*', element: <p>другая страница</p> }]
  const router = createMemoryRouter([{ path, element: ui }, ...extra], { initialEntries: [url] })
  const user = userEvent.setup()
  const utils = render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return { ...utils, user, router, client }
}
