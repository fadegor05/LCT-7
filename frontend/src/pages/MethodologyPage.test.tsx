import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server } from '@/mocks/server'
import { renderRoute } from '@/test/render'

const kit = (n: number) => screen.getByRole('region', { name: `Комплект ${n}` })
const stageButton = (name: RegExp) => screen.getByRole('button', { name })

type User = ReturnType<typeof renderRoute>['user']

/** Комплекты по умолчанию не подставляются: этап включают в проверку и наполняют вручную. */
async function createPitKit(user: User) {
  await user.click(await screen.findByRole('button', { name: /Разработка котлована/ }))
  await user.click(screen.getByRole('button', { name: 'Проверяется' }))
  await user.click(screen.getByRole('button', { name: 'Сохранить' }))
  await screen.findByText('Комплекта нет')

  await user.selectOptions(within(kit(1)).getByLabelText('Машина'), 'Гусеничный экскаватор')
  await user.type(within(kit(1)).getByLabelText('ГЭСН или источник'), 'по смыслу работы')
  await user.click(within(kit(1)).getByRole('button', { name: 'Добавить' }))
  await user.click(within(kit(1)).getByRole('button', { name: 'Добавить машину' }))
  await user.selectOptions(within(kit(1)).getByLabelText('Машина'), 'Самосвал')
  await user.selectOptions(within(kit(1)).getByLabelText('Обязательность'), 'Логическая')
  await user.type(
    within(kit(1)).getByLabelText('ГЭСН или источник'),
    'по смыслу работы: вывоз грунта',
  )
  await user.click(within(kit(1)).getByRole('button', { name: 'Добавить' }))
  await user.click(within(kit(1)).getByRole('button', { name: 'Сохранить' }))
  await vi.waitFor(() =>
    expect(stageButton(/Разработка котлована/)).toHaveTextContent(
      '1 комплект · маркер: гусеничный экскаватор',
    ),
  )
}

describe('MethodologyPage', () => {
  it('starts without default kits and lets the engineer fill a stage', async () => {
    const { user } = renderRoute('/sites/site-berezniki/methodology')
    const pit = await screen.findByRole('button', { name: /Разработка котлована/ })
    expect(pit).toHaveTextContent('Не проверяется по технике')
    expect(stageButton(/Устройство фундамента/)).toHaveTextContent('Не проверяется по технике')
    expect(screen.queryByRole('region', { name: /Комплект/ })).not.toBeInTheDocument()
    expect(screen.getByText('Комплект не задан — добавьте технику для этапа')).toBeInTheDocument()

    await createPitKit(user)
    expect(pit).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText('ВТ 01.09.2026 — ПН 14.09.2026')).toBeInTheDocument()
    expect(within(kit(1)).getByText('Маркер')).toBeInTheDocument()
    expect(within(kit(1)).getByText('по смыслу работы: вывоз грунта')).toBeInTheDocument()
  })

  it('edits a kit and saves it to the server', async () => {
    const { user } = renderRoute('/sites/site-berezniki/methodology')
    await createPitKit(user)
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
    await createPitKit(user)
    await user.click(
      within(kit(1)).getByRole('button', { name: 'Убрать машину: Гусеничный экскаватор' }),
    )
    expect(within(kit(1)).getByText('В комплекте нет маркера')).toBeInTheDocument()
    expect(within(kit(1)).getByRole('button', { name: 'Сохранить' })).toBeDisabled()
  })

  it('keeps a single kit: no adding or deleting kits', async () => {
    const { user } = renderRoute('/sites/site-berezniki/methodology')
    await createPitKit(user)
    expect(screen.queryByRole('button', { name: 'Добавить комплект' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Удалить комплект/ })).not.toBeInTheDocument()
  })

  it('turns equipment check off with a reason and back on', async () => {
    const { user } = renderRoute('/sites/site-berezniki/methodology')
    await createPitKit(user)
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
    expect(await screen.findByText('Комплекта нет')).toBeInTheDocument()
    expect(stageButton(/Благоустройство/)).toHaveTextContent('0 комплектов · маркеров нет')

    // У этапа без комплекта пустой комплект открыт сразу: машину добавляют и сохраняют.
    await user.selectOptions(within(kit(1)).getByLabelText('Машина'), 'Колёсный экскаватор')
    await user.type(within(kit(1)).getByLabelText('ГЭСН или источник'), 'по смыслу работы')
    await user.click(within(kit(1)).getByRole('button', { name: 'Добавить' }))
    await user.click(within(kit(1)).getByRole('button', { name: 'Сохранить' }))
    await vi.waitFor(() =>
      expect(stageButton(/Благоустройство/)).toHaveTextContent(
        '1 комплект · маркер: колёсный экскаватор',
      ),
    )
  })

  it('shows save errors from the server', async () => {
    const { user } = renderRoute('/sites/site-berezniki/methodology')
    await createPitKit(user)
    server.use(
      http.put('/api/sites/:siteId/methodology/sets/:setId', () =>
        HttpResponse.json({ detail: 'Нельзя' }, { status: 422 }),
      ),
      http.patch('/api/sites/:siteId/methodology/rules/:ruleId', () =>
        HttpResponse.json({ detail: 'Правило не найдено' }, { status: 404 }),
      ),
    )
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
    await createPitKit(user)
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

  it('shows the apply defaults button', async () => {
    renderRoute('/sites/site-berezniki/methodology')
    const button = await screen.findByRole('button', { name: 'Подставить базовые комплекты' })
    expect(button).toBeInTheDocument()
  })

  it('opens and closes the apply defaults dialog', async () => {
    const { user } = renderRoute('/sites/site-berezniki/methodology')
    const button = await screen.findByRole('button', { name: 'Подставить базовые комплекты' })
    await user.click(button)
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
    expect(
      screen.getByText('Подставить базовые комплекты для этапов без комплектов?'),
    ).toBeInTheDocument()

    const cancelButton = screen.getByRole('button', { name: 'Отмена' })
    await user.click(cancelButton)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('applies defaults and shows success message with counts', async () => {
    const { user } = renderRoute('/sites/site-berezniki/methodology')
    const button = await screen.findByRole('button', { name: 'Подставить базовые комплекты' })
    await user.click(button)
    const applyButton = screen.getByRole('button', { name: 'Применить' })
    await user.click(applyButton)
    expect(
      await screen.findByText((content) => content.includes('Комплекты подставлены для')),
    ).toBeInTheDocument()
  })

  it('shows message when no eligible stages', async () => {
    server.use(
      http.post('/api/sites/:siteId/methodology/apply-defaults', () =>
        HttpResponse.json({ applied: 0, eligible: 0, unmatched: 0 }, { status: 200 }),
      ),
    )
    const { user } = renderRoute('/sites/site-berezniki/methodology')
    const button = await screen.findByRole('button', { name: 'Подставить базовые комплекты' })
    await user.click(button)
    const applyButton = screen.getByRole('button', { name: 'Применить' })
    await user.click(applyButton)
    expect(
      await screen.findByText('Нет этапов без комплекта — подставлять нечего.'),
    ).toBeInTheDocument()
  })

  it('shows unmatched stages message with correct grammar for unmatched=1', async () => {
    server.use(
      http.post('/api/sites/:siteId/methodology/apply-defaults', () =>
        HttpResponse.json({ applied: 2, eligible: 3, unmatched: 1 }, { status: 200 }),
      ),
    )
    const { user } = renderRoute('/sites/site-berezniki/methodology')
    const button = await screen.findByRole('button', { name: 'Подставить базовые комплекты' })
    await user.click(button)
    const applyButton = screen.getByRole('button', { name: 'Применить' })
    await user.click(applyButton)
    expect(
      await screen.findByText((content) => content.includes('Комплекты подставлены для 2 из 3')),
    ).toBeInTheDocument()
    expect(
      screen.getByText((content) =>
        content.includes('1 этап не подошёл ни под одно правило — задайте вручную'),
      ),
    ).toBeInTheDocument()
  })

  it('shows error when apply defaults fails', async () => {
    server.use(
      http.post('/api/sites/:siteId/methodology/apply-defaults', () =>
        HttpResponse.json({ detail: 'Ошибка сервера' }, { status: 500 }),
      ),
    )
    const { user } = renderRoute('/sites/site-berezniki/methodology')
    const button = await screen.findByRole('button', { name: 'Подставить базовые комплекты' })
    await user.click(button)
    const applyButton = screen.getByRole('button', { name: 'Применить' })
    await user.click(applyButton)
    expect(await screen.findByText('Ошибка сервера')).toBeInTheDocument()
  })
})

describe('MethodologyPage: маркеры этапа', () => {
  it('shows the real markers with their periods after a recompute', async () => {
    const { equipmentByCode } = await import('@/mocks/fixtures')
    const excavator = equipmentByCode('excavator_crawler')
    const { user, client } = renderRoute('/sites/site-berezniki/methodology')
    await createPitKit(user)
    server.use(
      http.get('*/sites/:siteId/assessment/stages', () =>
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
            marker_names: ['Гусеничный экскаватор'],
            marker_periods: [
              {
                equipment_type_id: excavator.id,
                name: 'Гусеничный экскаватор',
                start: '2026-08-21',
                end: '2026-09-17',
              },
            ],
          },
        ]),
      ),
    )
    // Пересчёт после правки комплекта: статусы этапов перезапрошены
    await client.invalidateQueries({ queryKey: ['site', 'site-berezniki'] })
    expect(
      await screen.findByRole('button', { name: /маркер: гусеничный экскаватор/ }),
    ).toBeInTheDocument()
    expect(within(kit(1)).getByText('21.08–17.09', { exact: false })).toBeInTheDocument()
    expect(screen.getByText('Маркерная техника этапа')).toBeInTheDocument()
  })
})
