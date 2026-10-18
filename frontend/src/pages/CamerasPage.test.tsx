import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '@/mocks/server'
import { env } from '@/lib/env'
import { renderRoute } from '@/test/render'

const URL_CAMERAS = '/sites/site-berezniki/cameras'

/** Область рисования зоны 400×300 px от (0, 0), как в тестах редактора. */
beforeEach(() => {
  vi.spyOn(SVGElement.prototype, 'getBoundingClientRect').mockReturnValue({
    left: 0,
    top: 0,
    width: 400,
    height: 300,
  } as DOMRect)
})

const click = (el: Element, x: number, y: number) => {
  fireEvent.pointerDown(el, { clientX: x, clientY: y })
  fireEvent.pointerUp(el, { clientX: x, clientY: y })
}

async function openNewCamera(user: ReturnType<typeof renderRoute>['user']) {
  await user.click(await screen.findByRole('button', { name: 'Добавить камеру' }))
  return screen.getByRole('dialog', { name: 'Новая камера' })
}

describe('CamerasPage', () => {
  it('opens from the site tabs and shows the empty state', async () => {
    renderRoute('/sites/site-berezniki')
    const tab = await screen.findByRole('link', { name: 'Камеры' })
    expect(tab).toHaveAttribute('href', URL_CAMERAS)
    await userEvent.click(tab)
    expect(await screen.findByRole('heading', { name: 'Камеры объекта' })).toBeInTheDocument()
  })

  it('creates a camera with a stream link, interval and zone', async () => {
    const { user } = renderRoute(URL_CAMERAS)
    expect(
      await screen.findByText('Камер пока нет. Добавьте первую, чтобы настроить стрим.'),
    ).toBeInTheDocument()

    const dialog = await openNewCamera(user)
    await user.type(within(dialog).getByLabelText('Название'), 'Въезд')
    await user.type(
      within(dialog).getByLabelText('Ссылка на стрим (необязательно)'),
      'rtsp://cam/live?seconds=600',
    )
    await user.tab()
    expect(within(dialog).getByLabelText('Ссылка на стрим (необязательно)')).toHaveValue(
      'rtsp://cam/live',
    )
    expect(within(dialog).getByLabelText('Снимать кадр каждые')).toHaveValue(10)

    expect(within(dialog).getByText('Зона не задана')).toBeInTheDocument()
    const area = within(dialog).getByRole('application', { name: 'Рабочая зона' })
    click(area, 40, 30)
    click(area, 360, 30)
    click(area, 200, 270)
    click(within(dialog).getByRole('button', { name: 'Вершина 1' }), 40, 30)
    expect(within(dialog).getByText('Зона задана')).toBeInTheDocument()

    await user.click(within(dialog).getByRole('button', { name: 'Сохранить' }))
    const list = await screen.findByRole('list', { name: 'Камеры' })
    const row = within(list).getByText('Въезд').closest('li')!
    expect(within(row).getByText('Стрим задан')).toBeInTheDocument()
    expect(within(row).getByText('Зона задана')).toBeInTheDocument()
    expect(within(row).getByText('0 кадров')).toBeInTheDocument()
    expect(screen.getByText('1 камера')).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('checks the name, the stream scheme and the interval before saving', async () => {
    const { user } = renderRoute(URL_CAMERAS)
    const dialog = await openNewCamera(user)

    await user.click(within(dialog).getByRole('button', { name: 'Сохранить' }))
    expect(within(dialog).getByText('Укажите название камеры')).toBeInTheDocument()

    await user.type(within(dialog).getByLabelText('Название'), 'Склад')
    await user.type(within(dialog).getByLabelText('Ссылка на стрим (необязательно)'), 'ftp://cam')
    await user.click(within(dialog).getByRole('button', { name: 'Сохранить' }))
    // Схему проверяет бэкенд: его текст об ошибке показывается в окне
    expect(await within(dialog).findByText(/ссылка на стрим — rtsp/)).toBeInTheDocument()

    const every = within(dialog).getByLabelText('Снимать кадр каждые')
    await user.clear(every)
    await user.type(every, '2000')
    await user.click(within(dialog).getByRole('button', { name: 'Сохранить' }))
    expect(within(dialog).getByText('От 1 до 1440 минут')).toBeInTheDocument()
    expect(screen.getByRole('dialog', { name: 'Новая камера' })).toBeInTheDocument()
  })

  it('reports a server refusal inside the dialog', async () => {
    server.use(
      http.post(`${env.apiBaseUrl}/sites/:siteId/cameras`, () =>
        HttpResponse.json({ detail: 'Камера не сохранена на сервере' }, { status: 422 }),
      ),
    )
    const { user } = renderRoute(URL_CAMERAS)
    const dialog = await openNewCamera(user)
    await user.type(within(dialog).getByLabelText('Название'), 'Вход')
    await user.click(within(dialog).getByRole('button', { name: 'Сохранить' }))
    expect(await within(dialog).findByText('Камера не сохранена на сервере')).toBeInTheDocument()
  })

  it('edits a camera, clears its zone and deletes it', async () => {
    const { user } = renderRoute(URL_CAMERAS)
    const dialog0 = await openNewCamera(user)
    await user.type(within(dialog0).getByLabelText('Название'), 'Въезд')
    await user.click(within(dialog0).getByRole('button', { name: 'Сохранить' }))
    await screen.findByRole('list', { name: 'Камеры' })

    await user.click(screen.getByRole('button', { name: 'Настроить камеру Въезд' }))
    const dialog = screen.getByRole('dialog', { name: 'Камера Въезд' })
    expect(within(dialog).getByText('Зона не задана')).toBeInTheDocument()
    await user.clear(within(dialog).getByLabelText('Название'))
    await user.type(within(dialog).getByLabelText('Название'), 'Выезд')
    await user.click(within(dialog).getByRole('button', { name: 'Сохранить' }))
    expect(await screen.findByText('Выезд')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Настроить камеру Выезд' }))
    const again = screen.getByRole('dialog', { name: 'Камера Выезд' })
    const area = within(again).getByRole('application', { name: 'Рабочая зона' })
    click(area, 40, 30)
    click(area, 360, 30)
    click(area, 200, 270)
    click(within(again).getByRole('button', { name: 'Вершина 1' }), 40, 30)
    await user.click(within(again).getByRole('button', { name: 'Очистить зону' }))
    expect(within(again).getByText('Зона не задана')).toBeInTheDocument()

    await user.click(within(again).getByRole('button', { name: 'Удалить' }))
    await user.click(within(again).getByRole('button', { name: 'Удалить камеру' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(
      await screen.findByText('Камер пока нет. Добавьте первую, чтобы настроить стрим.'),
    ).toBeInTheDocument()
  })
})
