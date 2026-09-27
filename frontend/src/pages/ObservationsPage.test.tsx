import { screen, within } from '@testing-library/react'
import { renderRoute } from '@/test/render'

describe('ObservationsPage', () => {
  it('shows the latest day by default and switches to all days', async () => {
    const { user, router } = renderRoute('/sites/site-berezniki/observations')
    expect(
      await screen.findByRole('heading', { name: 'Кадры за 18.09 по камерам' }),
    ).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Техника на площадке' })).toBeInTheDocument()
    expect(await screen.findAllByRole('region', { name: /Камера К-/ })).toHaveLength(4)

    await user.click(screen.getByRole('button', { name: /Все дни/ }))
    expect(await screen.findByRole('heading', { name: 'Все кадры по камерам' })).toBeInTheDocument()
    expect(router.state.location.search).toBe('?date=all')
    expect(screen.queryByRole('heading', { name: 'Техника на площадке' })).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /17\.09/ }))
    expect(
      await screen.findByRole('heading', { name: 'Кадры за 17.09 по камерам' }),
    ).toBeInTheDocument()
  })

  it('opens a day from the URL and handles empty days', async () => {
    renderRoute('/sites/site-berezniki/observations?date=2026-01-01')
    expect(await screen.findByText('Кадров за этот период нет.')).toBeInTheDocument()
  })

  it('confirms time for frames and clips', async () => {
    const { user } = renderRoute('/sites/site-berezniki/observations')
    const list = await screen.findByRole('list', { name: 'Кадры без времени' })
    expect(within(list).getAllByRole('listitem')).toHaveLength(5)

    await user.click(within(list).getAllByRole('button', { name: 'Подтвердить' })[0]!)
    expect(within(list).getByRole('alert')).toHaveTextContent('Формат: дд.мм.гггг чч:мм')
    await user.type(within(list).getByLabelText('Дата и время кадра fr-nt-1'), '18.09.2026 09:00')
    await user.click(within(list).getAllByRole('button', { name: 'Подтвердить' })[0]!)
    await vi.waitFor(() =>
      expect(
        within(screen.getByRole('list', { name: 'Кадры без времени' })).getAllByRole('listitem'),
      ).toHaveLength(4),
    )

    const clipInput = screen.getByLabelText('Время начала клипа k2_morning.mp4')
    await user.click(screen.getByRole('button', { name: 'Применить ко всем 24 кадрам' }))
    expect(screen.getByText('Формат: дд.мм.гггг чч:мм')).toBeInTheDocument()
    await user.type(clipInput, '18.09.2026 08:00')
    await user.click(screen.getByRole('button', { name: 'Применить ко всем 24 кадрам' }))
    await vi.waitFor(() =>
      expect(
        screen.queryByText('Клип без времени начала', { selector: 'p' }),
      ).not.toBeInTheDocument(),
    )
    expect(
      within(screen.getByRole('list', { name: 'Кадры без времени' })).getAllByRole('listitem'),
    ).toHaveLength(2)
  })

  it('uploads photos through the add-frames dialog', async () => {
    const { user } = renderRoute('/sites/site-berezniki/observations')
    await user.click(await screen.findByRole('button', { name: 'Добавить кадры' }))
    const dialog = screen.getByRole('dialog', { name: 'Добавить кадры' })
    const add = within(dialog).getByRole('button', { name: 'Добавить' })
    expect(add).toBeDisabled()
    await user.upload(within(dialog).getByLabelText('Выбрать файлы'), [
      new File(['1'], 'a.jpg', { type: 'image/jpeg' }),
      new File(['2'], 'b.jpg', { type: 'image/jpeg' }),
    ])
    expect(within(dialog).getByText('Выбрано: a.jpg, b.jpg')).toBeInTheDocument()
    await user.selectOptions(await within(dialog).findByLabelText('Камера'), 'К-2')
    await user.click(add)
    await vi.waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(await screen.findByRole('button', { name: /18\.09\s*26 кадров/ })).toBeInTheDocument()
  })

  it('uploads a video without start time and it lands in the no-time list', async () => {
    const { user } = renderRoute('/sites/site-berezniki/observations')
    await user.click(await screen.findByRole('button', { name: 'Добавить кадры' }))
    const dialog = screen.getByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Видео' }))
    await user.upload(
      within(dialog).getByLabelText('Выбрать файлы'),
      new File(['v'], 'clip.mp4', { type: 'video/mp4' }),
    )
    await user.selectOptions(within(dialog).getByLabelText('Шаг нарезки'), '1 кадр в минуту')
    await user.type(within(dialog).getByLabelText('Время начала клипа'), 'вчера')
    await user.click(within(dialog).getByRole('button', { name: 'Добавить' }))
    expect(within(dialog).getByText('Формат: дд.мм.гггг чч:мм')).toBeInTheDocument()
    await user.clear(within(dialog).getByLabelText('Время начала клипа'))
    await user.click(within(dialog).getByRole('button', { name: 'Добавить' }))
    await vi.waitFor(() => expect(screen.getAllByLabelText(/Время начала клипа/)).toHaveLength(2))
  })

  it('manages streams in the dialog', async () => {
    const { user } = renderRoute('/sites/site-berezniki/observations')
    await user.click(await screen.findByRole('button', { name: 'Добавить кадры' }))
    const dialog = screen.getByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Стрим' }))
    expect(await within(dialog).findByText('Подключено')).toBeInTheDocument()
    expect(within(dialog).getByLabelText('Камера со стримом')).toHaveValue('cam-3')
    await user.selectOptions(
      within(dialog).getByLabelText('Периодичность нарезки'),
      'каждые 5 минут',
    )
    await user.click(within(dialog).getByRole('button', { name: 'Остановить' }))
    await vi.waitFor(() => expect(within(dialog).queryByText('Подключено')).not.toBeInTheDocument())
    await user.click(within(dialog).getByRole('button', { name: 'Добавить' }))
    await vi.waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('closes the dialog with Cancel', async () => {
    const { user } = renderRoute('/sites/site-berezniki/observations')
    await user.click(await screen.findByRole('button', { name: 'Добавить кадры' }))
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Отмена' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('warns when no camera has a stream', async () => {
    const { user } = renderRoute('/sites/site-synthetic/observations')
    await user.click(await screen.findByRole('button', { name: 'Добавить кадры' }))
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Стрим' }))
    expect(await screen.findByText('Нет камер со стримом')).toBeInTheDocument()
    expect(screen.getByText('Все кадры с известным временем.')).toBeInTheDocument()
  })
})
