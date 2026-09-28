import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server } from '@/mocks/server'
import { renderRoute } from '@/test/render'

const file = () =>
  new File(['stage;start;end'], 'grafik.xlsx', {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  })

describe('creating a site', () => {
  it('shows recognized column names in the upload hint', () => {
    renderRoute('/sites/new')
    expect(
      screen.getByText(
        'CSV или XLSX до 5 МБ: колонки «Название» (или «Наименование»/«Этап»), «Начало», «Окончание». Техника в файле не нужна.',
      ),
    ).toBeInTheDocument()
  })

  it('walks through both steps', async () => {
    const { user, router } = renderRoute('/sites/new')
    expect(screen.getByRole('heading', { name: 'Новая стройка' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Далее: методика' })).toBeDisabled()

    // Без названия файл не принимаем: форма валидируется до создания стройки.
    await user.upload(screen.getByLabelText('Выбрать файл'), file())
    expect(await screen.findByText('Укажите название')).toBeInTheDocument()

    await user.type(screen.getByLabelText('Название'), 'Школа')
    await user.type(screen.getByLabelText('Адрес или обозначение'), 'Пермь')
    await user.upload(screen.getByLabelText('Выбрать файл'), file())

    expect(await screen.findByText('Заменить файл')).toBeInTheDocument()
    expect(router.state.location.pathname).toMatch(/^\/sites\/site-\d+\/setup$/)
    const callout = screen.getByText('Что проверить в графике').closest('[role="alert"], div')!
    expect(callout).toHaveTextContent('Строка 9 не разобрана: Нет названия этапа.')
    expect(callout).toHaveTextContent('У одного этапа нет дат')

    const table = await screen.findByRole('table', { name: 'Этапы графика' })
    await user.type(within(table).getByLabelText('Дата начала: Благоустройство'), '01.12')
    await user.type(within(table).getByLabelText('Дата окончания: Благоустройство'), '20.12')
    await user.click(within(table).getByRole('button', { name: 'Задать' }))
    expect(await within(table).findByText('задано вручную')).toBeInTheDocument()
    expect(within(table).getByText('ВТ 01.12 — ВС 20.12')).toBeInTheDocument()

    await user.clear(screen.getByLabelText('Адрес или обозначение'))
    await user.click(screen.getByRole('button', { name: 'Далее: методика' }))
    expect(
      await screen.findByRole('heading', { name: 'Методика: этап → техника' }),
    ).toBeInTheDocument()
    expect(router.state.location.pathname).toMatch(/setup\/methodology$/)
    expect(await screen.findByRole('button', { name: /Разработка котлована/ })).toBeInTheDocument()

    await user.click(screen.getByRole('link', { name: 'Готово: к стройке' }))
    await vi.waitFor(() => expect(router.state.location.pathname).toMatch(/^\/sites\/site-\d+$/))
    expect(await screen.findByRole('heading', { level: 1, name: 'Школа' })).toBeInTheDocument()
    expect(screen.queryByText('Пермь')).not.toBeInTheDocument()
  })

  it('goes back from the methodology step to the saved object', async () => {
    const { user } = renderRoute('/sites/new')
    await user.type(screen.getByLabelText('Название'), 'Склад')
    await user.upload(screen.getByLabelText('Выбрать файл'), file())
    await screen.findByText('Заменить файл')
    await user.click(screen.getByRole('button', { name: 'Далее: методика' }))
    await user.click(await screen.findByRole('link', { name: 'Назад' }))
    expect(await screen.findByDisplayValue('Склад')).toBeInTheDocument()
    expect(await screen.findByText(/grafik\.xlsx|blob/)).toBeInTheDocument()
  })

  it('replaces the schedule file and reports upload errors', async () => {
    const { user } = renderRoute('/sites/new')
    await user.type(screen.getByLabelText('Название'), 'Склад')
    await user.upload(screen.getByLabelText('Выбрать файл'), file())
    await screen.findByText('Заменить файл')

    server.use(
      http.post('/api/sites/:siteId/schedule/import', () =>
        HttpResponse.json({ detail: 'Файл не читается' }, { status: 422 }),
      ),
    )
    const replace = screen.getByLabelText('Заменить файл')
    await user.upload(replace, new File(['x'], 'other.csv', { type: 'text/csv' }))
    expect(await screen.findByText('Файл не читается')).toBeInTheDocument()
  })

  it('rejects manual dates the server does not accept', async () => {
    server.use(
      http.patch('/api/sites/:siteId/schedule/stages/:stageId', () =>
        HttpResponse.json({ detail: 'Дата окончания раньше даты начала' }, { status: 422 }),
      ),
    )
    const { user } = renderRoute('/sites/site-synthetic/setup')
    const table = await screen.findByRole('table', { name: 'Этапы графика' })
    expect(await screen.findByDisplayValue('Синтетический объект (демо)')).toBeInTheDocument()
    await user.type(within(table).getByLabelText('Дата начала: Благоустройство'), '01.12')
    await user.type(within(table).getByLabelText('Дата окончания: Благоустройство'), '20.12')
    await user.click(within(table).getByRole('button', { name: 'Задать' }))
    expect(await screen.findByText('Дата окончания раньше даты начала')).toBeInTheDocument()
  })
})
