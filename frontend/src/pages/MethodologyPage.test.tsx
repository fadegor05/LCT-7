import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server } from '@/mocks/server'
import { renderRoute } from '@/test/render'

const kit = (n: number) => screen.getByRole('region', { name: `Комплект ${n}` })
const stageButton = (name: RegExp) => screen.getByRole('button', { name })

describe('MethodologyPage', () => {
  it('shows stages with their kits and markers and selects one', async () => {
    const { user } = renderRoute('/sites/site-berezniki/methodology')
    const pit = await screen.findByRole('button', { name: /Разработка котлована/ })
    expect(pit).toHaveTextContent('1 комплект · маркер: гусеничный экскаватор')
    expect(pit).toHaveAttribute('aria-pressed', 'true')
    expect(stageButton(/Устройство фундамента/)).toHaveTextContent(
      '2 комплекта · маркер: автобетононасос, автокран',
    )
    expect(stageButton(/Подготовка территории/)).toHaveTextContent('Не проверяется по технике')
    expect(screen.getByText('ВТ 01.09 — ПН 14.09')).toBeInTheDocument()
    expect(within(kit(1)).getByText('Маркер')).toBeInTheDocument()
    expect(within(kit(1)).getByText('по смыслу работы: вывоз грунта')).toBeInTheDocument()

    await user.click(stageButton(/Подготовка территории/))
    expect(
      screen.getByRole('heading', { level: 2, name: 'Подготовка территории' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Нет правила в базовом наборе — задайте комплект')).toBeInTheDocument()
  })

  it('edits a kit and saves it to the server', async () => {
    const { user } = renderRoute('/sites/site-berezniki/methodology')
    await screen.findByRole('region', { name: 'Комплект 1' })
    const save = within(kit(1)).getByRole('button', { name: 'Сохранить' })
    expect(save).toBeDisabled()

    await user.click(within(kit(1)).getByRole('button', { name: 'Убрать машину: Самосвал' }))
    expect(within(kit(1)).getByText('Есть несохранённые изменения.')).toBeInTheDocument()
    await user.click(within(kit(1)).getByRole('button', { name: 'Отмена' }))
    expect(within(kit(1)).getByText('Самосвал')).toBeInTheDocument()

    await user.click(within(kit(1)).getByRole('button', { name: 'Добавить машину' }))
    await user.selectOptions(within(kit(1)).getByLabelText('Машина'), 'Бульдозер')
    await user.selectOptions(within(kit(1)).getByLabelText('Обязательность'), 'Вспомогательная')
    await user.click(within(kit(1)).getByRole('button', { name: 'Добавить' }))
    expect(within(kit(1)).getByText('Укажите номер ГЭСН или источник')).toBeInTheDocument()
    await user.type(within(kit(1)).getByLabelText('ГЭСН или источник'), '01-01-036-01')
    await user.click(within(kit(1)).getByRole('button', { name: 'Добавить' }))
    const qty = within(kit(1)).getByLabelText('Минимум машин: Бульдозер')
    await user.tripleClick(qty)
    await user.keyboard('2')
    await user.click(save)

    await vi.waitFor(() =>
      expect(within(kit(1)).getByLabelText('Минимум машин: Бульдозер')).toHaveValue('2'),
    )
    expect(within(kit(1)).getByText('Вспомогательная')).toBeInTheDocument()
    expect(within(kit(1)).getByText('ГЭСН 01-01-036-01')).toBeInTheDocument()
    expect(within(kit(1)).getByRole('button', { name: 'Сохранить' })).toBeDisabled()
  })

  it('does not save a kit without a marker', async () => {
    const { user } = renderRoute('/sites/site-berezniki/methodology')
    await screen.findByRole('region', { name: 'Комплект 1' })
    await user.click(
      within(kit(1)).getByRole('button', { name: 'Убрать машину: Гусеничный экскаватор' }),
    )
    expect(within(kit(1)).getByText('В комплекте нет маркера')).toBeInTheDocument()
    expect(within(kit(1)).getByRole('button', { name: 'Сохранить' })).toBeDisabled()
  })

  it('adds an alternative kit and deletes one', async () => {
    const { user } = renderRoute('/sites/site-berezniki/methodology')
    await screen.findByRole('region', { name: 'Комплект 1' })

    await user.click(screen.getByRole('button', { name: 'Добавить комплект' }))
    await user.click(within(kit(2)).getAllByRole('button', { name: 'Отмена' }).at(-1)!)
    expect(screen.queryByRole('region', { name: 'Комплект 2' })).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Добавить комплект' }))
    await user.selectOptions(within(kit(2)).getByLabelText('Машина'), 'Колёсный экскаватор')
    await user.type(within(kit(2)).getByLabelText('ГЭСН или источник'), 'по смыслу работы')
    await user.click(within(kit(2)).getByRole('button', { name: 'Добавить' }))
    await user.click(within(kit(2)).getByRole('button', { name: 'Сохранить' }))
    await vi.waitFor(() =>
      expect(stageButton(/Разработка котлована/)).toHaveTextContent(
        '2 комплекта · маркер: гусеничный экскаватор, колёсный экскаватор',
      ),
    )

    await user.click(screen.getByRole('button', { name: 'Удалить комплект 1' }))
    await vi.waitFor(() =>
      expect(stageButton(/Разработка котлована/)).toHaveTextContent(
        '1 комплект · маркер: колёсный экскаватор',
      ),
    )
    // Последний комплект проверяемого этапа удалить нельзя — это правило backend.
    await user.click(screen.getByRole('button', { name: 'Удалить комплект 1' }))
    expect(
      await screen.findByText(/Нельзя удалить последний комплект проверяемого этапа/),
    ).toBeInTheDocument()
  })

  it('turns equipment check off with a reason and back on', async () => {
    const { user } = renderRoute('/sites/site-berezniki/methodology')
    await screen.findByRole('region', { name: 'Комплект 1' })
    await user.click(screen.getByRole('button', { name: 'Не проверяется' }))
    await user.click(screen.getAllByRole('button', { name: 'Отмена' })[0]!)
    expect(screen.getByRole('region', { name: 'Комплект 1' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Не проверяется' }))
    await user.click(screen.getByRole('button', { name: 'Сохранить' }))
    expect(screen.getByText('Укажите причину')).toBeInTheDocument()
    await user.type(screen.getByLabelText('Почему этап не проверяется'), 'Работы вне кадра')
    await user.click(screen.getByRole('button', { name: 'Сохранить' }))
    await vi.waitFor(() =>
      expect(stageButton(/Разработка котлована/)).toHaveTextContent('Не проверяется по технике'),
    )
    expect(screen.getByText('Работы вне кадра')).toBeInTheDocument()

    await user.click(stageButton(/Благоустройство/))
    await user.click(screen.getByRole('button', { name: 'Проверяется' }))
    expect(screen.getByText('После сохранения добавьте комплект техники.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Сохранить' }))
    expect(await screen.findByText('Комплектов нет')).toBeInTheDocument()
    expect(stageButton(/Благоустройство/)).toHaveTextContent('0 комплектов · маркеров нет')
  })

  it('shows save errors from the server', async () => {
    server.use(
      http.put('/api/sites/:siteId/methodology/sets/:setId', () =>
        HttpResponse.json({ detail: 'Нельзя' }, { status: 422 }),
      ),
      http.patch('/api/sites/:siteId/methodology/rules/:ruleId', () =>
        HttpResponse.json({ detail: 'Правило не найдено' }, { status: 404 }),
      ),
    )
    const { user } = renderRoute('/sites/site-berezniki/methodology')
    await screen.findByRole('region', { name: 'Комплект 1' })
    await user.click(within(kit(1)).getByRole('button', { name: 'Убрать машину: Самосвал' }))
    await user.click(within(kit(1)).getByRole('button', { name: 'Сохранить' }))
    expect(await within(kit(1)).findByText('Нельзя')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Не проверяется' }))
    await user.type(screen.getByLabelText('Почему этап не проверяется'), 'Причина')
    await user.click(screen.getAllByRole('button', { name: 'Сохранить' })[0]!)
    expect(await screen.findByText('Правило не найдено')).toBeInTheDocument()
  })

  it('reports when every machine is already in the kit', async () => {
    const { user } = renderRoute('/sites/site-berezniki/methodology')
    await screen.findByRole('region', { name: 'Комплект 1' })
    for (let i = 0; i < 5; i++) {
      await user.click(within(kit(1)).getByRole('button', { name: 'Добавить машину' }))
      await user.type(within(kit(1)).getByLabelText('ГЭСН или источник'), 'x')
      await user.click(within(kit(1)).getByRole('button', { name: 'Добавить' }))
    }
    await user.click(within(kit(1)).getByRole('button', { name: 'Добавить машину' }))
    expect(within(kit(1)).getByText('Вся техника справочника уже в комплекте.')).toBeInTheDocument()
  })

  it('handles a site without stages or schedule', async () => {
    server.use(http.get('/api/sites/:siteId/methodology', () => HttpResponse.json([])))
    renderRoute('/sites/site-synthetic/methodology')
    expect(await screen.findByText('В графике нет этапов.')).toBeInTheDocument()

    server.use(
      http.get('/api/sites/:siteId/methodology', () =>
        HttpResponse.json({ detail: 'График не загружен' }, { status: 404 }),
      ),
    )
    renderRoute('/sites/site-synthetic/methodology')
    expect(await screen.findByText('График не загружен')).toBeInTheDocument()
  })
})
