import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server } from '@/mocks/server'
import { renderRoute } from '@/test/render'

describe('SitesPage', () => {
  it('lists sites with their summary and the cross-site deviations', async () => {
    renderRoute('/sites')
    const list = await screen.findByRole('region', { name: 'Список строек' })
    // Как в clean-mvp: число объектов и дата данных — последняя среди объектов
    expect(await screen.findByText(/^2 объекта · данные на \d\d\.\d\d\.\d{4}$/)).toBeInTheDocument()
    const berezniki = within(list).getByRole('link', { name: /Жилой дом · Березники/ })
    expect(await within(berezniki).findByText('Отставание 4 дней')).toBeInTheDocument()
    expect(within(berezniki).getByLabelText('Критично')).toHaveTextContent('1')
    expect(within(berezniki).getByLabelText('Внимание')).toHaveTextContent('2')
    expect(await within(berezniki).findByText('ПТ 18.09.2026')).toBeInTheDocument()
    expect(within(berezniki).getByText('Высокая')).toBeInTheDocument()
    const synthetic = within(list).getByRole('link', { name: /Синтетический/ })
    expect(within(synthetic).getByText('Недостаточно данных')).toBeInTheDocument()

    const deviations = await screen.findByRole('list', { name: 'Отклонения' })
    const rows = within(deviations).getAllByRole('link')
    expect(rows).toHaveLength(3)
    expect(rows[0]).toHaveTextContent('Критично')
    expect(rows[0]).toHaveTextContent('Нет нужной техники')
    expect(rows[0]).toHaveTextContent('Жилой дом · Березники')
    expect(rows[0]).toHaveAttribute('href', '/sites/site-berezniki/deviations/dev-missing-pump')
  })

  it('links to site creation', async () => {
    const { user, router } = renderRoute('/sites')
    await user.click(screen.getByRole('link', { name: 'Новая стройка' }))
    expect(router.state.location.pathname).toBe('/sites/new')
  })

  it('shows an empty state', async () => {
    server.use(http.get('/api/sites', () => HttpResponse.json([])))
    renderRoute('/sites')
    expect(await screen.findByText('Строек пока нет. Заведите первую.')).toBeInTheDocument()
    expect(await screen.findByText('Отклонений не выявлено.')).toBeInTheDocument()
  })

  it('shows deviation errors of any site', async () => {
    server.use(
      http.get('/api/sites/:siteId/assessment/deviations', () =>
        HttpResponse.json({ detail: 'Сбой' }, { status: 500 }),
      ),
    )
    renderRoute('/sites')
    expect(await screen.findByText('Сбой')).toBeInTheDocument()
  })
})
