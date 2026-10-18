import { screen, within } from '@testing-library/react'
import type { UserEvent } from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import { server } from '@/mocks/server'
import { env } from '@/lib/env'
import { renderRoute } from '@/test/render'

const URL_CAMERAS = '/sites/site-berezniki/cameras'
const CAPTURE_URL = `${env.apiBaseUrl}/sites/:siteId/cameras/:cameraId/capture`

async function openNewCamera(user: UserEvent) {
  await user.click(await screen.findByRole('button', { name: 'Добавить камеру' }))
  return screen.getByRole('dialog', { name: 'Новая камера' })
}

/** Создаёт камеру с ссылкой на стрим через окно и ждёт её в списке. */
async function createCamera(user: UserEvent, name: string, link: string) {
  const dialog = await openNewCamera(user)
  await user.type(within(dialog).getByLabelText('Название'), name)
  await user.type(within(dialog).getByLabelText('Ссылка на стрим (необязательно)'), link)
  await user.click(within(dialog).getByRole('button', { name: 'Сохранить' }))
  await screen.findByRole('list', { name: 'Камеры' })
}

async function openCamera(user: UserEvent, name: string) {
  await user.click(await screen.findByRole('button', { name: `Настроить камеру ${name}` }))
  return screen.getByRole('dialog', { name: `Камера ${name}` })
}

describe('CamerasPage: «Снять кадр сейчас» и интервал', () => {
  it('takes a frame from the saved stream and shows it in the camera list', async () => {
    const { user } = renderRoute(URL_CAMERAS)
    await createCamera(user, 'Въезд', 'rtsp://cam/live')

    const dialog = await openCamera(user, 'Въезд')
    await user.click(within(dialog).getByRole('button', { name: 'Снять кадр сейчас' }))
    expect(
      await within(dialog).findByText('Кадр со стрима снят и добавлен в ленту камеры'),
    ).toBeInTheDocument()

    await user.click(within(dialog).getByRole('button', { name: 'Отмена' }))
    const list = screen.getByRole('list', { name: 'Камеры' })
    const row = within(list).getByText('Въезд').closest('li')!
    expect(await within(row).findByText(/Стрим · снимок/)).toBeInTheDocument()
    expect(within(row).getByText('1 кадр')).toBeInTheDocument()
  })

  it('keeps the capture button disabled for a camera without a saved stream', async () => {
    const { user } = renderRoute(URL_CAMERAS)
    const dialog = await openNewCamera(user)
    expect(within(dialog).getByRole('button', { name: 'Снять кадр сейчас' })).toBeDisabled()
    expect(
      within(dialog).getByText('Сохраните камеру со ссылкой, чтобы снять кадр'),
    ).toBeInTheDocument()
  })

  it('shows the reason when the grab fails and marks the stream in the list', async () => {
    const { user } = renderRoute(URL_CAMERAS)
    await createCamera(user, 'Склад', 'rtsp://cam/offline')

    const dialog = await openCamera(user, 'Склад')
    await user.click(within(dialog).getByRole('button', { name: 'Снять кадр сейчас' }))
    expect(await within(dialog).findByText('Кадр со стрима не снят')).toBeInTheDocument()
    expect(within(dialog).getByText('Камера не ответила за 15 с')).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Отмена' }))

    const list = screen.getByRole('list', { name: 'Камеры' })
    const row = within(list).getByText('Склад').closest('li')!
    expect(
      within(row).getByText('Стрим недоступен: Камера не ответила за 15 с'),
    ).toBeInTheDocument()
  })

  it('disables the button while the frame is being grabbed', async () => {
    const { user } = renderRoute(URL_CAMERAS)
    await createCamera(user, 'Кран', 'rtsp://cam/live')

    server.use(
      http.post(CAPTURE_URL, async () => {
        await delay(100)
        return HttpResponse.json(
          {
            id: 'ph-stream',
            site_id: 'site-berezniki',
            original_name: 'stream.jpg',
            width: 1920,
            height: 1080,
            captured_on: '2026-09-18',
            date_source: 'channel',
            processing_status: 'pending',
            uploaded_at: '2026-09-18T10:00:00',
            camera_id: 'camera-1',
          },
          { status: 201 },
        )
      }),
    )
    const dialog = await openCamera(user, 'Кран')
    await user.click(within(dialog).getByRole('button', { name: 'Снять кадр сейчас' }))
    expect(within(dialog).getByRole('button', { name: 'Снимаем кадр…' })).toBeDisabled()
    expect(
      await within(dialog).findByText('Кадр со стрима снят и добавлен в ленту камеры'),
    ).toBeInTheDocument()
  })

  it('accepts an empty interval and falls back to the server default of 5 minutes', async () => {
    const { user } = renderRoute(URL_CAMERAS)
    const dialog = await openNewCamera(user)
    await user.type(within(dialog).getByLabelText('Название'), 'Въезд')
    await user.type(
      within(dialog).getByLabelText('Ссылка на стрим (необязательно)'),
      'rtsp://cam/live',
    )
    const every = within(dialog).getByLabelText('Снимать кадр каждые')
    await user.clear(every)
    await user.click(within(dialog).getByRole('button', { name: 'Сохранить' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    const again = await openCamera(user, 'Въезд')
    expect(within(again).getByLabelText('Снимать кадр каждые')).toHaveValue(5)
  })
})
