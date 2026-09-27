import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { TODAY } from '@/mocks/fixtures'
import { server } from '@/mocks/server'
import { renderRoute } from '@/test/render'

describe('SiteOverviewPage', () => {
  afterEach(() => vi.useRealTimers())

  it('shows verdict, data state, deviations, stages and last observation', async () => {
    renderRoute('/sites/site-berezniki')
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Жилой дом · Березники' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Березники, [адрес объекта]')).toBeInTheDocument()
    expect(await screen.findByText('Отставание 4 дней')).toBeInTheDocument()
    expect(await screen.findByText('Наблюдаемость высокая')).toBeInTheDocument()
    expect(screen.getByText('Всего снимков').nextSibling).toHaveTextContent('14')
    expect(await screen.findByText('Без даты')).toBeInTheDocument()
    await vi.waitFor(() => expect(screen.getByText('Без даты').nextSibling).toHaveTextContent('2'))

    expect(await screen.findByRole('heading', { name: 'Отклонения: 3' })).toBeInTheDocument()
    expect(
      screen.getByText('1 критичное, 1 гипотеза: проверьте снимки. Сначала самые важные.'),
    ).toBeInTheDocument()

    const table = await screen.findByRole('table', { name: 'Статусы этапов' })
    const pit = within(table).getByRole('row', { name: /Разработка котлована/ })
    expect(within(pit).getByText('Отставание')).toBeInTheDocument()
    expect(within(pit).getByText('01.09–14.09')).toBeInTheDocument()
    expect(within(pit).getByText('отставание 4 дн. · уверенность высокая')).toBeInTheDocument()
    expect(within(pit).getByRole('link', { name: 'Простой техники (гипотеза)' })).toHaveAttribute(
      'href',
      '/sites/site-berezniki/deviations/dev-idle-truck',
    )
    const backfill = within(table).getByRole('row', { name: /Обратная засыпка/ })
    expect(within(backfill).getByText('Не начата')).toBeInTheDocument()

    expect(
      await screen.findByRole('heading', { name: 'Последнее наблюдение · 18.09' }),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Гусеничный экскаватор 2, самосвал 1 (максимум по снимкам).'),
    ).toBeInTheDocument()
    const photos = await screen.findAllByRole('img', { name: /Снимок IMG_/ })
    expect(photos).toHaveLength(3)
    expect(photos[0]).toHaveStyle({
      backgroundImage: 'url(/api/sites/site-berezniki/photos/ph-9/annotated)',
    })
  })

  it('prints the report', async () => {
    const print = vi.spyOn(window, 'print').mockImplementation(() => {})
    const { user } = renderRoute('/sites/site-berezniki')
    await user.click(await screen.findByRole('button', { name: 'Печатная версия' }))
    expect(print).toHaveBeenCalled()
  })

  it('handles a site without photos or deviations', async () => {
    // Бейдж сравнивает плановое начало с сегодняшним днём — фиксируем «сегодня» моков.
    vi.useFakeTimers({ toFake: ['Date'], now: new Date(`${TODAY}T12:00:00`) })
    renderRoute('/sites/site-synthetic')
    expect(await screen.findByText('Недостаточно данных')).toBeInTheDocument()
    expect(await screen.findByText('Наблюдений пока нет')).toBeInTheDocument()
    // Итог называет настоящую причину, а не все сразу (bug-reports/002).
    expect(screen.getByText(/Нет наблюдений: снимки ещё не загружены/)).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Отклонения: 0' })).toBeInTheDocument()
    // «Отклонений не выявлено.» — один раз, в пустом списке, а не ещё и в подзаголовке.
    expect(screen.getAllByText('Отклонений не выявлено.')).toHaveLength(1)
    const table = await screen.findByRole('table', { name: 'Статусы этапов' })
    // Окно наступило, кадров нет — «не наблюдалось», а не «не начата» (bug-reports/002).
    expect(within(table).getAllByText('Не наблюдалось')).toHaveLength(3)
    expect(within(table).getAllByText('Не начата')).toHaveLength(2)
    expect(within(table).getAllByText('Не оценён')).toHaveLength(1)
    expect(screen.queryByRole('heading', { name: /Последнее наблюдение/ })).not.toBeInTheDocument()
  })

  it('asks for a schedule when there is none', async () => {
    server.use(
      http.get('/api/sites/:siteId/schedule', () =>
        HttpResponse.json({ detail: 'График не загружен' }, { status: 404 }),
      ),
    )
    renderRoute('/sites/site-synthetic')
    expect(await screen.findByText('График не загружен')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Загрузить график' })).toHaveAttribute(
      'href',
      '/sites/site-synthetic/setup',
    )
  })

  it('shows a clear error for unknown sites', async () => {
    renderRoute('/sites/nope')
    expect(await screen.findByText('Стройка не найдена')).toBeInTheDocument()
  })
})
