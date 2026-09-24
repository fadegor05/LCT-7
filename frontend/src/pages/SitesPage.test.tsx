import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server } from '@/mocks/server'
import { renderRoute } from '@/test/render'

describe('SitesPage', () => {
  it('lists sites with summary and the cross-site deviations', async () => {
    renderRoute('/sites')
    const list = await screen.findByRole('region', { name: 'Список строек' })
    expect(screen.getByText('2 объекта · данные на 18.09.2026')).toBeInTheDocument()
    const berezniki = within(list).getByRole('link', { name: /Жилой дом · Березники/ })
    expect(within(berezniki).getByText('Отставание от 4 дней')).toBeInTheDocument()
    expect(within(berezniki).getByLabelText('Критично')).toHaveTextContent('1')
    expect(within(berezniki).getByLabelText('Внимание')).toHaveTextContent('2')
    expect(within(berezniki).getByText('2 дня назад')).toBeInTheDocument()
    const synthetic = within(list).getByRole('link', { name: /Синтетический/ })
    expect(within(synthetic).getByText('Данные устарели · 35 дн.')).toBeInTheDocument()

    const deviations = await screen.findByRole('list', { name: 'Отклонения' })
    const rows = within(deviations).getAllByRole('link')
    expect(rows).toHaveLength(4)
    expect(rows[0]).toHaveTextContent('Критично')
    expect(rows[0]).toHaveTextContent('Нет нужной техники')
  })

  it('links to site creation', async () => {
    const { user, router } = renderRoute('/sites')
    await user.click(screen.getByRole('link', { name: 'Новая стройка' }))
    expect(router.state.location.pathname).toBe('/sites/new')
  })

  it('shows an empty state and API errors', async () => {
    server.use(
      http.get('/api/sites', () => HttpResponse.json([])),
      http.get('/api/deviations', () => HttpResponse.json({ detail: 'Сбой' }, { status: 500 })),
    )
    renderRoute('/sites')
    expect(await screen.findByText('Строек пока нет. Заведите первую.')).toBeInTheDocument()
    expect(await screen.findByText('Сбой')).toBeInTheDocument()
  })

  it('accepts sites from the current backend without a summary', async () => {
    server.use(
      http.get('/api/sites', () =>
        HttpResponse.json([
          {
            id: 'x',
            name: 'Из API',
            address: null,
            owner_id: 'u',
            created_at: '2026-09-01T00:00:00Z',
            updated_at: '2026-09-01T00:00:00Z',
          },
        ]),
      ),
    )
    renderRoute('/sites')
    const row = await screen.findByRole('link', { name: /Из API/ })
    expect(within(row).getByText('Недостаточно данных')).toBeInTheDocument()
    expect(screen.getByText('1 объект')).toBeInTheDocument()
  })
})
