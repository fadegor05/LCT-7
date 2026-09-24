import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server } from '@/mocks/server'
import { renderRoute } from '@/test/render'

const editor = () => screen.getByRole('button', { name: 'Сохранить' }).closest('section')!

describe('MethodologyPage', () => {
  it('shows stages with their markers and selects one', async () => {
    const { user } = renderRoute('/sites/site-berezniki/methodology')
    const pit = await screen.findByRole('button', { name: /Разработка котлована/ })
    expect(pit).toHaveTextContent('Комплект 1 · маркер: экскаватор')
    expect(screen.getByRole('button', { name: /Подготовка территории/ })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    await user.click(pit)
    expect(pit).toHaveAttribute('aria-pressed', 'true')
    expect(
      screen.getByRole('heading', { level: 2, name: 'Разработка котлована' }),
    ).toBeInTheDocument()
    expect(within(editor()).getByText('Маркер')).toBeInTheDocument()
    expect(within(editor()).getByText(/Отличает этап от соседних/)).toBeInTheDocument()
  })

  it('edits a kit and the server recomputes markers', async () => {
    const { user } = renderRoute('/sites/site-berezniki/methodology')
    await user.click(await screen.findByRole('button', { name: /Устройство основания/ }))
    const card = editor()
    const save = within(card).getByRole('button', { name: 'Сохранить' })
    expect(save).toBeDisabled()

    await user.click(within(card).getByRole('button', { name: 'Убрать машину: Каток' }))
    expect(within(card).getByText('Есть несохранённые изменения.')).toBeInTheDocument()
    await user.click(within(card).getByRole('button', { name: 'Отмена' }))
    expect(within(card).getByText('Каток')).toBeInTheDocument()

    await user.click(within(card).getByRole('button', { name: 'Добавить машину' }))
    await user.selectOptions(within(card).getByLabelText('Машина'), 'Грузовик')
    await user.selectOptions(within(card).getByLabelText('Вид правила'), 'Вспомогательная')
    await user.click(within(card).getByRole('button', { name: 'Добавить' }))
    const qty = within(card).getByLabelText('Типовое количество: Грузовик')
    await user.type(qty, '3')
    await user.clear(within(card).getByLabelText('Типовое количество: Каток'))
    await user.click(save)
    await vi.waitFor(() =>
      expect(within(editor()).getByLabelText('Типовое количество: Грузовик')).toHaveValue('3'),
    )
    expect(within(editor()).getByText('Вспомогательная')).toBeInTheDocument()
    expect(within(editor()).getByLabelText('Типовое количество: Каток')).toHaveValue('')
  })

  it('turns equipment check off and a stage without machines warns', async () => {
    const { user } = renderRoute('/sites/site-berezniki/methodology')
    await user.click(await screen.findByRole('button', { name: /Разработка котлована/ }))
    const card = editor()
    await user.click(within(card).getByRole('button', { name: 'Убрать машину: Экскаватор' }))
    await user.click(within(card).getByRole('button', { name: 'Убрать машину: Самосвал' }))
    expect(within(card).getByText('В комплекте нет техники')).toBeInTheDocument()
    await user.click(within(card).getByRole('button', { name: 'Добавить машину' }))
    await user.click(within(card).getAllByRole('button', { name: 'Отмена' })[0]!)

    await user.click(within(card).getByRole('button', { name: 'Не проверяется' }))
    expect(within(card).getByText('Этап не проверяется по технике')).toBeInTheDocument()
    await user.click(within(card).getByRole('button', { name: 'Сохранить' }))
    await vi.waitFor(() =>
      expect(screen.getByRole('button', { name: /Разработка котлована/ })).toHaveTextContent(
        'Не проверяется по технике',
      ),
    )
    // Соседи потеряли общего соседа — у подготовки и основания маркеры остались.
    expect(screen.getByRole('button', { name: /Устройство основания/ })).toHaveTextContent(
      'маркер: каток',
    )
  })

  it('shows a stage without markers and save errors', async () => {
    server.use(
      http.put('/api/sites/:siteId/methodology/:stageId', () =>
        HttpResponse.json({ detail: 'Нельзя' }, { status: 409 }),
      ),
    )
    const { user } = renderRoute('/sites/site-berezniki/methodology')
    await user.click(await screen.findByRole('button', { name: /Обратная засыпка/ }))
    await user.click(within(editor()).getByRole('button', { name: 'Добавить машину' }))
    await user.click(within(editor()).getByRole('button', { name: 'Добавить' }))
    await user.click(within(editor()).getByRole('button', { name: 'Сохранить' }))
    expect(await screen.findByText('Нельзя')).toBeInTheDocument()
  })

  it('reports when every class is already in the kit', async () => {
    const { user } = renderRoute('/sites/site-berezniki/methodology')
    await user.click(await screen.findByRole('button', { name: /Бетонирование плиты/ }))
    const card = editor()
    for (let i = 0; i < 6; i++) {
      await user.click(within(card).getByRole('button', { name: 'Добавить машину' }))
      await user.click(within(card).getByRole('button', { name: 'Добавить' }))
    }
    await user.click(within(card).getByRole('button', { name: 'Добавить машину' }))
    expect(within(card).getByText('Все классы техники уже в комплекте.')).toBeInTheDocument()
  })

  it('handles a site without stages', async () => {
    renderRoute('/sites/site-synthetic/methodology')
    expect(await screen.findByText('В графике нет этапов.')).toBeInTheDocument()
  })
})
