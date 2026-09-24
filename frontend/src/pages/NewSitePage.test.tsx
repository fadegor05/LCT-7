import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server } from '@/mocks/server'
import { renderRoute } from '@/test/render'

const file = () => new File(['work;start;end'], 'grafik.xlsx', { type: 'application/vnd.ms-excel' })

describe('creating a site', () => {
  it('walks through both steps and activates the site', async () => {
    const { user, router } = renderRoute('/sites/new')
    expect(screen.getByRole('heading', { name: 'Новая стройка' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Далее: методика' })).toBeDisabled()

    // Без названия файл не принимаем: форма валидируется до создания черновика.
    await user.upload(screen.getByLabelText('Выбрать файл'), file())
    expect(await screen.findByText('Укажите название')).toBeInTheDocument()

    await user.type(screen.getByLabelText('Название'), 'Школа')
    await user.type(screen.getByLabelText('Адрес или обозначение'), 'Пермь')
    await user.click(screen.getByRole('button', { name: 'Образование' }))
    await user.click(screen.getByRole('button', { name: 'Пн–Сб' }))
    await user.upload(screen.getByLabelText('Выбрать файл'), file())

    // Имя файла в тестах теряется (jsdom → Node FormData), поэтому ждём саму сводку импорта.
    expect(await screen.findByText('Заменить файл')).toBeInTheDocument()
    expect(router.state.location.pathname).toMatch(/^\/sites\/site-\d+\/setup$/)
    const callout = screen.getByRole('alert')
    expect(callout).toHaveTextContent('2 строки не разобраны')
    expect(callout).toHaveTextContent('У одного этапа нет дат')

    const table = await screen.findByRole('table', { name: 'Крупные этапы графика' })
    await user.type(within(table).getByLabelText('Дата начала: Бетонирование плиты'), '23.09')
    await user.type(within(table).getByLabelText('Дата окончания: Бетонирование плиты'), '05.10')
    await user.click(within(table).getByRole('button', { name: 'Задать' }))
    await user.click(
      await within(table).findByRole('button', { name: 'Подтвердить сопоставление' }),
    )
    await screen.findByText(/2 строки не разобраны/)
    await vi.waitFor(() => expect(screen.getByRole('alert')).not.toHaveTextContent('нет дат'))

    await user.click(screen.getByRole('button', { name: 'Далее: методика' }))
    expect(
      await screen.findByRole('heading', { name: 'Методика: этап → техника' }),
    ).toBeInTheDocument()
    expect(router.state.location.pathname).toMatch(/setup\/methodology$/)

    await user.click(await screen.findByRole('button', { name: 'Создать стройку' }))
    await vi.waitFor(() => expect(router.state.location.pathname).toMatch(/^\/sites\/site-\d+$/))
    expect(await screen.findByRole('heading', { level: 1, name: 'Школа' })).toBeInTheDocument()
  })

  it('blocks activation while blocking issues remain', async () => {
    const { user } = renderRoute('/sites/new')
    await user.type(screen.getByLabelText('Название'), 'Склад')
    await user.upload(screen.getByLabelText('Выбрать файл'), file())
    await screen.findByText('Заменить файл')
    await user.click(screen.getByRole('button', { name: 'Далее: методика' }))
    await user.click(await screen.findByRole('button', { name: 'Создать стройку' }))
    expect(
      await screen.findByText('Сначала исправьте блокирующие проблемы графика'),
    ).toBeInTheDocument()
    await user.click(screen.getByRole('link', { name: 'Назад' }))
    expect(await screen.findByDisplayValue('Склад')).toBeInTheDocument()
  })

  it('replaces the schedule file and reports upload errors', async () => {
    const { user } = renderRoute('/sites/new')
    await user.type(screen.getByLabelText('Название'), 'Склад')
    await user.upload(screen.getByLabelText('Выбрать файл'), file())
    await screen.findByText('Заменить файл')

    server.use(
      http.post('/api/sites/:siteId/schedule-imports', () =>
        HttpResponse.json({ detail: 'Файл не читается' }, { status: 422 }),
      ),
    )
    const replace = screen.getByLabelText('Заменить файл')
    await user.upload(replace, new File(['x'], 'other.csv', { type: 'text/csv' }))
    expect(await screen.findByText('Файл не читается')).toBeInTheDocument()
  })

  it('blocks the next step when stage windows overlap', async () => {
    const { user } = renderRoute('/sites/new')
    await user.type(screen.getByLabelText('Название'), 'Склад')
    await user.upload(screen.getByLabelText('Выбрать файл'), file())
    const table = await screen.findByRole('table', { name: 'Крупные этапы графика' })
    await user.type(within(table).getByLabelText('Дата начала: Бетонирование плиты'), '20.09')
    await user.type(within(table).getByLabelText('Дата окончания: Бетонирование плиты'), '05.10')
    await user.click(within(table).getByRole('button', { name: 'Задать' }))
    expect(await screen.findByText(/пересекаются/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Далее: методика' })).toBeDisabled()
  })
})
