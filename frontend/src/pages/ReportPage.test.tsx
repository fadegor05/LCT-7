import { readFileSync } from 'fs'
import { dirname, resolve } from 'path'
import { fileURLToPath } from 'url'
import { screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server } from '@/mocks/server'
import { BEREZNIKI, SYNTHETIC } from '@/mocks/fixtures'
import { renderRoute } from '@/test/render'

const REPORT = `/sites/${BEREZNIKI}/report`

/** Строки таблицы без заголовка. */
const rowsOf = (name: string) =>
  within(screen.getByRole('table', { name })).getAllByRole('row').slice(1)

describe('ReportPage', () => {
  afterEach(() => {
    document.title = 'Веха'
  })

  it('lays the site out as a document: summary, deviations, stages, data, limits', async () => {
    renderRoute(REPORT)
    const title = await screen.findByRole('heading', {
      level: 1,
      name: 'Отчёт: Жилой дом · Березники',
    })
    // Печатные стили интерфейса прячут шапку приложения: шапка отчёта не внутри <header>
    expect(title.closest('header')).toBeNull()
    expect(screen.getByText('Березники, [адрес объекта]', { exact: false })).toBeInTheDocument()

    const summary = screen.getByRole('region', { name: 'Итог по объекту' })
    expect(summary).toHaveTextContent('Отставание 4 дней')

    const deviations = await waitFor(() => rowsOf('Отклонения'))
    expect(deviations).toHaveLength(3)
    // Первой идёт критичное; под заголовком — тип отклонения (clean-mvp)
    expect(deviations[0]).toHaveTextContent('Критично')
    expect(screen.getByRole('table', { name: 'Отклонения' })).not.toHaveTextContent('Ожидалось')

    const stages = await waitFor(() => rowsOf('Этапы'))
    const pit = stages.find((r) => /Разработка котлована/.test(r.textContent ?? ''))!
    expect(pit).toHaveTextContent('Отставание')
    expect(pit).toHaveTextContent('отставание 4 дн. · уверенность высокая')

    const data = screen.getByRole('region', { name: 'Состояние данных' })
    expect(data).toHaveTextContent('Наблюдаемость: высокая')
    expect(data).toHaveTextContent('Всего снимков: 14')
    expect(data).toHaveTextContent('Без даты: 2 (в расчёт не идут)')

    expect(screen.getByRole('region', { name: 'Чего отчёт не утверждает' })).toHaveTextContent(
      'нижняя граница',
    )
    // Ни вкладок, ни ассистента, ни кнопок интерфейса: только документ
    expect(screen.queryByRole('navigation', { name: 'Разделы объекта' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Печатная версия' })).toBeNull()
  })

  it('says there is nothing to report yet and does not invent facts', async () => {
    renderRoute(`/sites/${SYNTHETIC}/report`)
    expect(await screen.findByText('Недостаточно данных')).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Состояние данных' })).toHaveTextContent(
      'Кадров пока нет',
    )
    expect(screen.getByRole('region', { name: 'Состояние данных' })).not.toHaveTextContent(
      'Всего снимков',
    )
    expect(await screen.findByText('Отклонений нет.')).toBeInTheDocument()
  })

  it('opens the print dialog once the report has loaded when ?print=1 is set', async () => {
    const print = vi.spyOn(window, 'print').mockImplementation(() => {})
    renderRoute(`${REPORT}?print=1`)
    await screen.findByRole('table', { name: 'Этапы' })
    await waitFor(() => expect(print).toHaveBeenCalledTimes(1))
  })

  it('does not open the print dialog without ?print=1', async () => {
    const print = vi.spyOn(window, 'print').mockImplementation(() => {})
    renderRoute(REPORT)
    await screen.findByRole('table', { name: 'Этапы' })
    expect(print).not.toHaveBeenCalled()
  })

  it('offers a save-as-PDF button on screen and hides it from print', async () => {
    const print = vi.spyOn(window, 'print').mockImplementation(() => {})
    const { user } = renderRoute(REPORT)
    await screen.findByRole('table', { name: 'Этапы' })
    await user.click(screen.getByRole('button', { name: 'Сохранить PDF' }))
    expect(print).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('link', { name: '← К обзору' })).toHaveAttribute(
      'href',
      `/sites/${BEREZNIKI}`,
    )
  })

  it('names the document after the site and gives the previous title back', async () => {
    document.title = 'Веха'
    const { unmount } = renderRoute(REPORT)
    await screen.findByRole('table', { name: 'Этапы' })
    // «Сохранить как PDF» берёт имя файла из заголовка страницы
    expect(document.title).toMatch(/^Отчёт — Жилой дом · Березники — \d{2}\.\d{2}\.\d{4}$/)
    unmount()
    expect(document.title).toBe('Веха')
  })

  it('says what is missing and does not print a partial report', async () => {
    server.use(
      http.get('/api/sites/:siteId/observations', () => new HttpResponse(null, { status: 500 })),
    )
    const print = vi.spyOn(window, 'print').mockImplementation(() => {})
    renderRoute(`${REPORT}?print=1`)
    await screen.findByRole('table', { name: 'Этапы' })
    expect(await screen.findByText(/Отчёт неполон/)).toBeInTheDocument()
    expect(print).not.toHaveBeenCalled()
  })

  it('is reached from the overview by «Скачать отчёт PDF» in a new tab', async () => {
    renderRoute(`/sites/${BEREZNIKI}`)
    const link = await screen.findByRole('link', { name: 'Скачать отчёт PDF' })
    expect(link).toHaveAttribute('href', `/sites/${BEREZNIKI}/report?print=1`)
    expect(link).toHaveAttribute('target', '_blank')
  })

  it('keeps the print rules scoped to the report: A4, no bare section rule, no avoid-page', () => {
    const css = readFileSync(
      resolve(dirname(fileURLToPath(import.meta.url)), '../features/report/Report.module.css'),
      'utf-8',
    )
    // Модуль грузится вместе с маршрутами: голый `section` действовал бы на печать любой страницы
    expect(css).not.toMatch(/^\s*section\s*\{/m)
    expect(css).not.toMatch(/break-inside:\s*avoid-page/)
    expect(css).toMatch(/@page\s*\{\s*size:\s*a4/)
  })
})
