import { fireEvent, screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server } from '@/mocks/server'
import { renderRoute } from '@/test/render'

describe('CamerasPage', () => {
  it('lists cameras with stream and zone state', async () => {
    renderRoute('/sites/site-berezniki/cameras')
    const list = await screen.findByRole('list', { name: 'Камеры объекта' })
    expect(within(list).getAllByRole('listitem')).toHaveLength(4)
    expect(
      screen.getByText('4 камеры. Настройка стрима и рабочей зоны каждой камеры.'),
    ).toBeInTheDocument()
    const k3 = within(list).getAllByRole('listitem')[2]!
    expect(k3).toHaveTextContent('Стрим подключён')
    expect(k3).toHaveTextContent('Зона не задана')
  })

  it('adds a camera with a drawn zone', async () => {
    const { user } = renderRoute('/sites/site-berezniki/cameras')
    await user.click(await screen.findByRole('button', { name: 'Добавить камеру' }))
    const dialog = screen.getByRole('dialog', { name: 'Новая камера' })
    await user.click(within(dialog).getByRole('button', { name: 'Сохранить' }))
    expect(within(dialog).getByText('Укажите название')).toBeInTheDocument()

    await user.type(within(dialog).getByLabelText('Название'), 'К-5')
    const takeFrame = within(dialog).getByRole('button', { name: 'Взять кадр со стрима' })
    expect(takeFrame).toBeDisabled()
    await user.type(
      within(dialog).getByLabelText('Ссылка на стрим (необязательно)'),
      'rtsp://cam/5',
    )
    await user.click(takeFrame)
    const editor = within(dialog).getByTestId('zone-editor')
    await vi.waitFor(() => expect(editor.style.backgroundImage).toContain('data:image/svg'))

    editor.getBoundingClientRect = () => ({ left: 0, top: 0, width: 100, height: 100 }) as DOMRect
    for (const [x, y] of [
      [10, 10],
      [90, 10],
      [90, 90],
    ])
      fireEvent.pointerDown(editor, { clientX: x, clientY: y })
    fireEvent.pointerDown(within(dialog).getByRole('button', { name: 'Замкнуть контур' }))
    expect(within(dialog).getByText('Зона задана')).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Сохранить' }))

    await vi.waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    const list = screen.getByRole('list', { name: 'Камеры объекта' })
    await vi.waitFor(() => expect(within(list).getAllByRole('listitem')).toHaveLength(5))
    expect(within(list).getAllByRole('listitem')[4]).toHaveTextContent('Зона задана')
  })

  it('edits a camera, clears its zone and reports name conflicts', async () => {
    const { user } = renderRoute('/sites/site-berezniki/cameras')
    await user.click(await screen.findByRole('button', { name: 'Настроить К-2' }))
    const dialog = screen.getByRole('dialog', { name: 'Камера К-2' })
    expect(within(dialog).getByText('Зона задана')).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Очистить зону' }))
    expect(within(dialog).getByText('Зона не задана')).toBeInTheDocument()

    const name = within(dialog).getByLabelText('Название')
    await user.clear(name)
    await user.type(name, 'К-1')
    await user.click(within(dialog).getByRole('button', { name: 'Сохранить' }))
    expect(await within(dialog).findByText('Камера «К-1» уже есть на объекте')).toBeInTheDocument()

    await user.clear(name)
    await user.type(name, 'К-2')
    await user.click(within(dialog).getByRole('button', { name: 'Сохранить' }))
    await vi.waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    const k2 = screen.getAllByRole('listitem')[1]!
    await vi.waitFor(() => expect(k2).toHaveTextContent('Зона не задана'))
  })

  it('loads a custom reference frame and shows stream errors', async () => {
    const createObjectURL = vi.fn(() => 'blob:frame')
    Object.assign(URL, { createObjectURL })
    server.use(
      http.post('/api/reference-frames', () =>
        HttpResponse.json({ detail: 'Стрим не отвечает' }, { status: 504 }),
      ),
    )
    const { user } = renderRoute('/sites/site-berezniki/cameras')
    await user.click(await screen.findByRole('button', { name: 'Настроить К-3' }))
    const dialog = screen.getByRole('dialog')
    await user.upload(
      within(dialog).getByLabelText('Загрузить свой кадр'),
      new File(['i'], 'f.jpg', { type: 'image/jpeg' }),
    )
    expect(within(dialog).getByTestId('zone-editor').style.backgroundImage).toContain('blob:frame')
    await user.click(within(dialog).getByRole('button', { name: 'Взять кадр со стрима' }))
    expect(await within(dialog).findByText('Стрим не отвечает')).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Отмена' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('has an empty state', async () => {
    server.use(http.get('/api/sites/:siteId/cameras', () => HttpResponse.json([])))
    renderRoute('/sites/site-berezniki/cameras')
    expect(await screen.findByText(/Камер пока нет/)).toBeInTheDocument()
  })
})
