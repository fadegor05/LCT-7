import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server } from '@/mocks/server'
import { renderRoute } from '@/test/render'

describe('SiteOverviewPage', () => {
  it('shows verdict, data state, deviations, stages and last observation', async () => {
    renderRoute('/sites/site-berezniki')
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Жилой дом · Березники' }),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Березники, [адрес объекта] · данные на 18.09.2026'),
    ).toBeInTheDocument()
    expect(screen.getByText('Отставание от 4 дней')).toBeInTheDocument()
    expect(screen.getByText('4 из 4 присылают кадры')).toBeInTheDocument()

    expect(await screen.findByRole('heading', { name: 'Отклонения: 3' })).toBeInTheDocument()
    expect(
      screen.getByText('1 критичное, 1 гипотеза ждёт вашего решения. Сначала самые важные.'),
    ).toBeInTheDocument()

    const table = await screen.findByRole('table', { name: 'Статусы этапов' })
    const pit = within(table).getByRole('row', { name: /Разработка котлована/ })
    expect(within(pit).getByText('Отставание')).toBeInTheDocument()
    expect(within(pit).getByText('от 4 дн. · уверенность средняя')).toBeInTheDocument()
    expect(within(pit).getByRole('link', { name: 'Самосвал вне зоны' })).toHaveAttribute(
      'href',
      '/sites/site-berezniki/deviations/dev-idle-dump',
    )

    expect(
      await screen.findByRole('heading', { name: 'Последнее наблюдение · 18.09' }),
    ).toBeInTheDocument()
    expect(
      await screen.findByText(/максимум по кадрам\)\. Простаивает: самосвал \(гипотеза\)/),
    ).toBeInTheDocument()
    expect(await screen.findAllByRole('img', { name: /Кадр К-/ })).toHaveLength(3)
  })

  it('prints the report', async () => {
    const print = vi.spyOn(window, 'print').mockImplementation(() => {})
    const { user } = renderRoute('/sites/site-berezniki')
    await user.click(await screen.findByRole('button', { name: 'Печатная версия' }))
    expect(print).toHaveBeenCalled()
  })

  it('handles a site without frames or deviations', async () => {
    renderRoute('/sites/site-synthetic')
    expect(await screen.findByText('Недостаточно данных')).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Отклонения: 1' })).toBeInTheDocument()
    expect(screen.getByText('Сначала самые важные.')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: /Последнее наблюдение/ })).not.toBeInTheDocument()
  })

  it('shows a clear error for unknown sites', async () => {
    renderRoute('/sites/nope')
    expect(await screen.findByText('Стройка не найдена')).toBeInTheDocument()
  })

  it('describes an empty deviation list', async () => {
    server.use(http.get('/api/sites/:siteId/deviations', () => HttpResponse.json([])))
    renderRoute('/sites/site-berezniki')
    expect(
      await screen.findByText('Отклонений не выявлено.', { selector: 'p.sm' }),
    ).toBeInTheDocument()
  })
})
