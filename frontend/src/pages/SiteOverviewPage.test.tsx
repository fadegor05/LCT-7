import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import * as db from '@/mocks/db'
import { TODAY } from '@/mocks/fixtures'
import { server } from '@/mocks/server'
import { renderRoute } from '@/test/render'

describe('SiteOverviewPage', () => {
  afterEach(() => {
    vi.useRealTimers()
    db.setAssistantScenario('ok') // Reset assistant scenario
  })

  it('shows verdict, data state, deviations, stages and last observation', async () => {
    // Бейдж сравнивает плановое начало с сегодняшним днём — фиксируем «сегодня» моков.
    vi.useFakeTimers({ toFake: ['Date'], now: new Date(`${TODAY}T12:00:00`) })
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
    expect(pit).toHaveAttribute('id', 'stage-site-berezniki-stage-2')
    expect(pit).toHaveAttribute('tabindex', '-1')
    expect(within(pit).getByText('Отставание')).toBeInTheDocument()
    expect(within(pit).getByText('ВТ 01.09.2026–ПН 14.09.2026')).toBeInTheDocument()
    expect(within(pit).getByText('отставание 4 дн. · уверенность высокая')).toBeInTheDocument()
    expect(within(pit).getByRole('link', { name: 'Простой техники (гипотеза)' })).toHaveAttribute(
      'href',
      '/sites/site-berezniki/deviations/dev-idle-truck',
    )
    const backfill = within(table).getByRole('row', { name: /Обратная засыпка/ })
    expect(within(backfill).getByText('Не начата')).toBeInTheDocument()

    expect(
      await screen.findByRole('heading', { name: 'Последнее наблюдение · ПТ 18.09.2026' }),
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

  describe('AssistantPanel integration', () => {
    it('hides the assistant heading when no_llm', async () => {
      db.setAssistantScenario('no_llm')
      renderRoute('/sites/site-berezniki')
      // Ждём загрузки основного контента
      await screen.findByRole('heading', { level: 1, name: 'Жилой дом · Березники' })
      // Проверяем, что заголовка ассистента нет
      await vi.waitFor(() => {
        expect(
          screen.queryByRole('heading', { name: 'Ассистент по отчёту' }),
        ).not.toBeInTheDocument()
      })
    })

    it('shows the assistant heading after "Последнее наблюдение" in document order', async () => {
      renderRoute('/sites/site-berezniki')
      const assistantHeading = await screen.findByRole('heading', { name: 'Ассистент по отчёту' })
      const lastObsHeading = screen.getByRole('heading', { name: /Последнее наблюдение/ })

      // Проверяем, что ассистент идёт ПОСЛЕ "Последнее наблюдение" в документе
      const position = lastObsHeading.compareDocumentPosition(assistantHeading)
      // DOCUMENT_POSITION_FOLLOWING = 4
      expect(position & 4).not.toBe(0)
    })

    it('shows assistant panel with form after page loads', async () => {
      renderRoute('/sites/site-berezniki')

      // Ждём загрузки ассистента
      const heading = await screen.findByRole('heading', { name: 'Ассистент по отчёту' })
      expect(heading).toBeInTheDocument()

      // Проверяем, что форма присутствует
      const textarea = screen.getByRole('textbox', { name: 'Вопрос по отчёту' })
      expect(textarea).toBeInTheDocument()
    })

    it('shows assistant heading after last observation heading in document order', async () => {
      renderRoute('/sites/site-berezniki')

      const assistantHeading = await screen.findByRole('heading', { name: 'Ассистент по отчёту' })
      const lastObsHeading = screen.getByRole('heading', { name: /Последнее наблюдение/ })

      // Проверяем, что ассистент идёт ПОСЛЕ "Последнее наблюдение" в документе
      const position = lastObsHeading.compareDocumentPosition(assistantHeading)
      // DOCUMENT_POSITION_FOLLOWING = 4
      expect(position & 4).not.toBe(0)
    })
  })
})
