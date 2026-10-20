import { screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import type { Camera } from '@/api/schemas'
import { server } from '@/mocks/server'
import { env } from '@/lib/env'
import { renderRoute } from '@/test/render'

const URL_CAMERAS = '/sites/site-berezniki/cameras'
const VIDEO_PATH = `${env.apiBaseUrl}/sites/:siteId/cameras/:cameraId/video`

const camera: Camera = {
  id: 'camera-1',
  name: 'Въезд',
  stream_url: null,
  capture_every_s: null,
  last_capture_at: null,
  last_capture_error: null,
  zone: null,
  frames_count: 0,
  created_at: '2026-09-01T10:00:00',
}

/** Видео, записанное 20 октября 2026 в 09:30 по местному времени. */
const recordedAt = new Date(2026, 9, 20, 9, 30).getTime()
const videoFile = () =>
  new File(['video-bytes'], 'vyezd.mp4', { type: 'video/mp4', lastModified: recordedAt })

beforeEach(() => {
  server.use(http.get(`${env.apiBaseUrl}/sites/:siteId/cameras`, () => HttpResponse.json([camera])))
})

afterEach(() => {
  server.events.removeAllListeners()
})

async function openVideoDialog(user: ReturnType<typeof renderRoute>['user']) {
  await user.click(await screen.findByRole('button', { name: 'Загрузить видео камеры Въезд' }))
  return screen.getByRole('dialog', { name: 'Загрузить видео' })
}

describe('VideoUploadDialog', () => {
  it('opens for the camera from its row', async () => {
    const { user } = renderRoute(URL_CAMERAS)
    const dialog = await openVideoDialog(user)
    expect(within(dialog).getByText('Камера «Въезд»')).toBeInTheDocument()
  })

  it('starts with step 30 seconds and fills the start from the file date', async () => {
    const { user } = renderRoute(URL_CAMERAS)
    const dialog = await openVideoDialog(user)

    expect(within(dialog).getByRole('combobox', { name: 'Шаг кадров' })).toHaveValue('30')
    expect(within(dialog).getByLabelText('Начало записи')).toHaveValue('')

    await user.upload(within(dialog).getByLabelText('Видео'), videoFile())
    expect(within(dialog).getByLabelText('Начало записи')).toHaveValue('2026-10-20T09:30')
  })

  it('asks for a file and a start before sending', async () => {
    const posts = vi.fn()
    server.use(
      http.post(VIDEO_PATH, () => {
        posts()
        return HttpResponse.json({}, { status: 201 })
      }),
    )
    const { user } = renderRoute(URL_CAMERAS)
    const dialog = await openVideoDialog(user)

    await user.click(within(dialog).getByRole('button', { name: 'Загрузить' }))
    expect(within(dialog).getByText('Выберите видеофайл')).toBeInTheDocument()

    await user.upload(within(dialog).getByLabelText('Видео'), videoFile())
    await user.clear(within(dialog).getByLabelText('Начало записи'))
    await user.click(within(dialog).getByRole('button', { name: 'Загрузить' }))
    expect(within(dialog).getByText('Укажите начало записи')).toBeInTheDocument()
    expect(posts).not.toHaveBeenCalled()
  })

  it('reports how many frames were accepted and closes', async () => {
    const { user } = renderRoute(URL_CAMERAS)
    const dialog = await openVideoDialog(user)

    await user.upload(within(dialog).getByLabelText('Видео'), videoFile())
    await user.click(within(dialog).getByRole('button', { name: 'Загрузить' }))
    expect(
      await within(dialog).findByText('Принято 3 кадра, они обрабатываются'),
    ).toBeInTheDocument()

    await user.click(within(dialog).getByRole('button', { name: 'Готово' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('sends the file, the start and the step as multipart fields', async () => {
    const bodies: FormData[] = []
    server.events.on('request:start', async ({ request }) => {
      if (request.method === 'POST' && request.url.includes('/video')) {
        bodies.push(await request.clone().formData())
      }
    })
    const { user } = renderRoute(URL_CAMERAS)
    const dialog = await openVideoDialog(user)

    await user.upload(within(dialog).getByLabelText('Видео'), videoFile())
    await user.selectOptions(within(dialog).getByRole('combobox', { name: 'Шаг кадров' }), '60')
    await user.click(within(dialog).getByRole('button', { name: 'Загрузить' }))
    await within(dialog).findByText('Принято 3 кадра, они обрабатываются')

    expect(bodies).toHaveLength(1)
    const form = bodies[0]!
    // Имя файла в тестах теряется (jsdom → Node FormData), проверяем содержимое части
    expect((form.get('file') as Blob).size).toBe('video-bytes'.length)
    expect(form.get('recorded_at')).toBe('2026-10-20T09:30:00')
    expect(form.get('step_s')).toBe('60')
  })

  it('shows the server refusal inside the dialog', async () => {
    server.use(
      http.post(VIDEO_PATH, () =>
        HttpResponse.json({ detail: 'Видео не удалось прочитать' }, { status: 422 }),
      ),
    )
    const { user } = renderRoute(URL_CAMERAS)
    const dialog = await openVideoDialog(user)

    await user.upload(within(dialog).getByLabelText('Видео'), videoFile())
    await user.click(within(dialog).getByRole('button', { name: 'Загрузить' }))
    expect(await within(dialog).findByText('Видео не удалось прочитать')).toBeInTheDocument()
  })
})
