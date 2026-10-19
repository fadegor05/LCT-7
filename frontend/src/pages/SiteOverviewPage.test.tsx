import { screen, waitFor, within } from '@testing-library/react'
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
    // Адрес и дата данных — последнее наблюдение (моки считают as_of как last_observation)
    expect(
      await screen.findByText('Березники, [адрес объекта] · данные на 18.09.2026'),
    ).toBeInTheDocument()
    expect(await screen.findByText('Отставание 4 дней')).toBeInTheDocument()
    // Пояснение итога — про тот же этап, что интервал
    expect(
      screen.getByText(
        'Измерено по этапу «Разработка котлована». Точность не выше частоты съёмки.',
      ),
    ).toBeInTheDocument()
    expect(await screen.findByText('Наблюдаемость высокая')).toBeInTheDocument()
    expect(screen.getByText('Всего снимков').nextSibling).toHaveTextContent('14')
    expect(await screen.findByText('Без даты')).toBeInTheDocument()
    await vi.waitFor(() => expect(screen.getByText('Без даты').nextSibling).toHaveTextContent('2'))

    expect(await screen.findByRole('heading', { name: 'Отклонения: 3' })).toBeInTheDocument()
    expect(
      screen.getByText('1 критичное, 1 гипотеза ждёт вашего решения. Сначала самые важные.'),
    ).toBeInTheDocument()

    const table = await screen.findByRole('table', { name: 'Статусы этапов' })
    const pit = within(table).getByRole('row', { name: /Разработка котлована/ })
    expect(pit).toHaveAttribute('id', 'stage-site-berezniki-stage-2')
    expect(pit).toHaveAttribute('tabindex', '-1')
    expect(within(pit).getByText('Отставание')).toBeInTheDocument()
    expect(within(pit).getByText(/^01\.09–14\.09/)).toBeInTheDocument()
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
    await waitFor(() => expect(photos[0]).toHaveStyle({ backgroundImage: 'url(blob:test)' }))
  })

  it('shows an open-ended delay for a stage that has not started', async () => {
    server.use(
      http.get('/api/sites/:siteId/assessment/summary', () =>
        HttpResponse.json({
          verdict: 'behind',
          delay_days_min: 12,
          delay_days_max: null,
          critical_count: 0,
          attention_count: 0,
          stage_id: 'site-berezniki-stage-2',
          reason: 'Измерено по этапу «Разработка котлована»: это нижняя граница.',
        }),
      ),
      http.get('/api/sites/:siteId/assessment/stages', () =>
        HttpResponse.json([
          {
            stage_id: 'site-berezniki-stage-2',
            stage_name: 'Разработка котлована',
            position: 2,
            status: 'not_started',
            delay_days: 12,
            delay_open: true,
            confidence: 'high',
            confidence_reason: null,
            computed_at: '2026-09-18T12:00:00Z',
          },
        ]),
      ),
    )
    renderRoute('/sites/site-berezniki')
    expect(await screen.findByText('Отставание от 12 дней')).toBeInTheDocument()
    expect(
      screen.getByText('Измерено по этапу «Разработка котлована»: это нижняя граница.'),
    ).toBeInTheDocument()
    const table = await screen.findByRole('table', { name: 'Статусы этапов' })
    expect(
      within(table).getByText('отставание от 12 дн. · уверенность высокая'),
    ).toBeInTheDocument()
  })

  it('offers one report button — the A4 report for PDF', async () => {
    renderRoute('/sites/site-berezniki')
    expect(await screen.findByRole('link', { name: 'Скачать отчёт PDF' })).toHaveAttribute(
      'href',
      '/sites/site-berezniki/report?print=1',
    )
    expect(screen.queryByRole('button', { name: 'Печатная версия' })).not.toBeInTheDocument()
  })

  it('shows the marker fact, markers and the data date', async () => {
    server.use(
      http.get('/api/sites/:siteId/assessment/summary', () =>
        HttpResponse.json({
          verdict: 'behind',
          delay_days_min: 7,
          delay_days_max: 7,
          critical_count: 0,
          attention_count: 0,
          as_of: '2026-09-18',
        }),
      ),
      http.get('/api/sites/:siteId/assessment/stages', () =>
        HttpResponse.json([
          {
            stage_id: 'site-berezniki-stage-2',
            stage_name: 'Разработка котлована',
            position: 2,
            status: 'on_track',
            delay_days: null,
            confidence: 'high',
            confidence_reason: null,
            computed_at: '2026-09-18T12:00:00Z',
            start_fact: '2026-09-09',
            marker_names: ['Бульдозер', 'Гусеничный экскаватор'],
          },
        ]),
      ),
    )
    renderRoute('/sites/site-berezniki')
    const table = await screen.findByRole('table', { name: 'Статусы этапов' })
    // Идущий этап: «с 09.09, идёт», как в clean-mvp
    expect(within(table).getByText(/^с 09\.09/)).toBeInTheDocument()
    expect(within(table).getByText('Маркер: бульдозер, гусеничный экскаватор')).toBeInTheDocument()
    expect(screen.getByText(/данные на 18\.09\.2026/)).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Как выбирается статус этапа' })).toBeInTheDocument()
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
    // Загрузить график предлагают и итог, и раздел «Этапы»
    expect(screen.getAllByRole('link', { name: 'Загрузить график' })[0]).toHaveAttribute(
      'href',
      '/sites/site-synthetic/setup',
    )
  })

  it('shows a clear error for unknown sites', async () => {
    renderRoute('/sites/nope')
    expect(await screen.findByText('Стройка не найдена')).toBeInTheDocument()
  })

  describe('AssistantPanel integration', () => {
    it('shows the assistant column when no_llm', async () => {
      db.setAssistantScenario('no_llm')
      renderRoute('/sites/site-berezniki')
      // Ждём загрузки основного контента
      await screen.findByRole('heading', { level: 1, name: 'Жилой дом · Березники' })
      // Колонка видна и без языковой модели: спросить нельзя, но видно, почему
      await vi.waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Ассистент по отчёту' })).toBeInTheDocument()
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

  it('opens a photo of the last observation and closes it with Escape', async () => {
    const { user } = renderRoute('/sites/site-berezniki')
    const [open] = await screen.findAllByRole('button', { name: /^Открыть: Снимок IMG_/ })
    const fileName = open!.getAttribute('aria-label')!.replace('Открыть: Снимок ', '')

    await user.click(open!)
    expect(await screen.findByRole('dialog', { name: new RegExp(fileName) })).toBeInTheDocument()

    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
