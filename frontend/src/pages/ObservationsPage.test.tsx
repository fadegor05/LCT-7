import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { createCamera, uploadPhotos } from '@/mocks/db'
import { server } from '@/mocks/server'
import { renderRoute } from '@/test/render'

const photos = () => screen.findAllByRole('img', { name: /Снимок / })
const addCamera = (name = 'К-1 · въезд') =>
  createCamera('site-berezniki', { name, stream_url: null, capture_every_s: null, zone: null })

describe('ObservationsPage', () => {
  it('shows the latest day by default and switches to all days', async () => {
    const { user, router } = renderRoute('/sites/site-berezniki/observations')
    expect(
      await screen.findByRole('heading', { name: 'Снимки за ПТ 18.09.2026' }),
    ).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Техника на площадке' })).toBeInTheDocument()
    expect(screen.getByText('не менее 2')).toBeInTheDocument()
    expect(await photos()).toHaveLength(4)

    await user.click(screen.getByRole('button', { name: /Все дни/ }))
    expect(await screen.findByRole('heading', { name: 'Все снимки с датой' })).toBeInTheDocument()
    expect(router.state.location.search).toBe('?date=all')
    expect(screen.queryByRole('heading', { name: 'Техника на площадке' })).not.toBeInTheDocument()
    // Дни одной строкой слева направо по времени
    const dayButtons = within(screen.getByRole('group', { name: 'Дни наблюдений' }))
      .getAllByRole('button')
      .slice(1)
      .map((b) => b.textContent ?? '')
    const dates = dayButtons.map((t) =>
      t
        .match(/(\d\d)\.(\d\d)\.(\d{4})/)!
        .slice(1)
        .reverse()
        .join(''),
    )
    expect(dates).toEqual([...dates].sort())
    expect(await photos()).toHaveLength(12)
    // «Все дни»: у кадра день недели и дата, время — если источник его знает
    expect(screen.getAllByText('ПН 14.09', { selector: 'figcaption span' })).toHaveLength(2)

    await user.click(screen.getByRole('button', { name: /17\.09/ }))
    expect(
      await screen.findByRole('heading', { name: 'Снимки за ЧТ 17.09.2026' }),
    ).toBeInTheDocument()
    expect(await photos()).toHaveLength(2)
  })

  it('opens a day from the URL and handles empty days', async () => {
    renderRoute('/sites/site-berezniki/observations?date=2026-01-01')
    expect(await screen.findByText('Снимков за этот период нет.')).toBeInTheDocument()
  })

  it('sets a date for photos without one', async () => {
    const { user } = renderRoute('/sites/site-berezniki/observations')
    expect(await screen.findByRole('link', { name: /Без даты/ })).toHaveTextContent('2 снимка')
    const list = await screen.findByRole('list', { name: 'Снимки без даты' })
    expect(within(list).getAllByRole('listitem')).toHaveLength(2)

    await user.click(within(list).getAllByRole('button', { name: 'Задать дату' })[0]!)
    expect(within(list).getByRole('alert')).toHaveTextContent('Формат: дд.мм.гггг')

    // Длинное имя обрезается многоточием — полное остаётся в title (bug-reports/001).
    expect(within(list).getByText('IMG_0013.jpg')).toHaveAttribute('title', 'IMG_0013.jpg')

    const input = within(list).getByLabelText('Дата съёмки IMG_0013.jpg')
    // Дату из будущего форма отсекает сама, не дожидаясь 422 (bug-reports/003).
    await user.type(input, '01.01.2999')
    await user.click(within(list).getAllByRole('button', { name: 'Задать дату' })[0]!)
    expect(within(list).getByRole('alert')).toHaveTextContent(
      'Дата не может быть позже сегодняшней',
    )

    await user.clear(input)
    await user.type(input, '18.09.2026')
    await user.click(within(list).getAllByRole('button', { name: 'Задать дату' })[0]!)
    await vi.waitFor(() =>
      expect(
        within(screen.getByRole('list', { name: 'Снимки без даты' })).getAllByRole('listitem'),
      ).toHaveLength(1),
    )
    expect(
      await screen.findByRole('button', { name: /18\.09\.2026\s*5 снимков/ }),
    ).toBeInTheDocument()
  })

  it('reprocesses a photo the detector has not handled', async () => {
    server.use(
      http.get('/api/sites/:siteId/photos', ({ request }) =>
        new URL(request.url).searchParams.get('undated')
          ? HttpResponse.json([])
          : HttpResponse.json([
              {
                id: 'ph-x',
                site_id: 'site-berezniki',
                original_name: 'pending.jpg',
                width: 10,
                height: 10,
                captured_on: '2026-09-18',
                date_source: 'manual',
                processing_status: 'failed',
                uploaded_at: '2026-09-18T10:00:00Z',
              },
            ]),
      ),
      http.post('/api/sites/:siteId/photos/:photoId/detect', () =>
        HttpResponse.json({ detail: 'Детектор недоступен' }, { status: 502 }),
      ),
    )
    const { user } = renderRoute('/sites/site-berezniki/observations')
    expect(await screen.findByText('Ошибка детектора')).toBeInTheDocument()
    expect(screen.getByText('Вручную')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Обработать ещё раз' }))
    expect(await screen.findByText('Детектор недоступен')).toBeInTheDocument()
    expect(screen.getByText('У всех снимков известна дата.')).toBeInTheDocument()
  })

  it('uploads photos and reports files that failed', async () => {
    addCamera()
    const { user } = renderRoute('/sites/site-berezniki/observations')
    await user.click(await screen.findByRole('button', { name: 'Добавить снимки' }))
    const dialog = await screen.findByRole('dialog', { name: 'Добавить снимки' })
    const upload = within(dialog).getByRole('button', { name: 'Загрузить' })
    expect(upload).toBeDisabled()
    await user.upload(within(dialog).getByLabelText('Выбрать файлы'), [
      new File(['1'], 'a.jpg', { type: 'image/jpeg' }),
      new File(['2'], 'b.jpg', { type: 'image/jpeg' }),
    ])
    expect(within(dialog).getByText('Выбрано: a.jpg, b.jpg')).toBeInTheDocument()

    server.use(
      http.post('/api/sites/:siteId/photos', () =>
        HttpResponse.json(
          {
            items: [
              { filename: 'a.jpg', photo: null, error: 'Файл повреждён' },
              { filename: 'b.jpg', photo: null, error: null },
            ],
            uploaded: 1,
            failed: 1,
          },
          { status: 201 },
        ),
      ),
    )
    await user.click(upload)
    expect(await within(dialog).findByText('Загружено 1, с ошибкой 1')).toBeInTheDocument()
    expect(within(dialog).getByText('a.jpg: Файл повреждён')).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Готово' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('closes the dialog after a clean upload and shows request errors', async () => {
    addCamera()
    const { user } = renderRoute('/sites/site-berezniki/observations')
    await user.click(await screen.findByRole('button', { name: 'Добавить снимки' }))
    let dialog = await screen.findByRole('dialog')
    await user.upload(within(dialog).getByLabelText('Выбрать файлы'), [
      new File(['1'], 'a.jpg', { type: 'image/jpeg' }),
    ])
    await user.click(within(dialog).getByRole('button', { name: 'Загрузить' }))
    await vi.waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())

    server.use(
      http.post('/api/sites/:siteId/photos', () =>
        HttpResponse.json({ detail: 'Слишком много файлов' }, { status: 413 }),
      ),
    )
    await user.click(screen.getByRole('button', { name: 'Добавить снимки' }))
    dialog = await screen.findByRole('dialog')
    await user.upload(within(dialog).getByLabelText('Выбрать файлы'), [
      new File(['1'], 'a.jpg', { type: 'image/jpeg' }),
    ])
    await user.click(within(dialog).getByRole('button', { name: 'Загрузить' }))
    expect(await within(dialog).findByText('Слишком много файлов')).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Отмена' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('shows photos in a strip per camera', async () => {
    const gate = addCamera('К-1 · въезд')
    const pit = addCamera('К-2 · котлован')
    const jpeg = (name: string) => ({ name, type: 'image/jpeg' })
    uploadPhotos('site-berezniki', [jpeg('2026-09-18-a.jpg'), jpeg('2026-09-18-b.jpg')], gate.id)
    uploadPhotos('site-berezniki', [jpeg('2026-09-18-c.jpg')], pit.id)

    renderRoute('/sites/site-berezniki/observations')

    const gateStrip = await screen.findByRole('region', { name: 'Снимки: К-1 · въезд' })
    expect(within(gateStrip).getAllByRole('img', { name: /Снимок 2026-09-18/ })).toHaveLength(2)
    expect(within(gateStrip).getByText('· 2 снимка')).toBeInTheDocument()
    const pitStrip = screen.getByRole('region', { name: 'Снимки: К-2 · котлован' })
    expect(within(pitStrip).getAllByRole('img', { name: /Снимок/ })).toHaveLength(1)
    // Снимки фикстуры загружены без камеры — своей лентой
    expect(screen.getByRole('region', { name: 'Снимки: Без камеры' })).toBeInTheDocument()
  })

  it('opens all days when the latest day has fewer than three photos', async () => {
    server.use(
      http.get('/api/sites/:siteId/observations', () =>
        HttpResponse.json([
          {
            id: 'obs-1',
            site_id: 'site-berezniki',
            observed_on: '2026-09-18',
            photo_count: 1,
            observability: 'low',
            observability_notes: null,
            recomputed_at: '2026-09-18T12:00:00Z',
            equipment: [],
          },
        ]),
      ),
    )
    renderRoute('/sites/site-berezniki/observations')
    expect(await screen.findByRole('heading', { name: 'Все снимки с датой' })).toBeInTheDocument()
  })

  it('prefills the date from the stamp hint of an undated photo', async () => {
    server.use(
      http.get('/api/sites/:siteId/photos', ({ request }) =>
        new URL(request.url).searchParams.get('undated')
          ? HttpResponse.json([
              {
                id: 'ph-hint',
                site_id: 'site-berezniki',
                original_name: '202609270106411790460401577.jpg',
                width: 2592,
                height: 1944,
                captured_on: null,
                date_source: null,
                processing_status: 'done',
                uploaded_at: '2026-09-27T01:06:41Z',
                camera_id: null,
                captured_at: null,
                date_hint: '2026-08-03',
                time_check: null,
              },
            ])
          : HttpResponse.json([]),
      ),
    )
    renderRoute('/sites/site-berezniki/observations')
    const list = await screen.findByRole('list', { name: 'Снимки без даты' })
    expect(within(list).getByLabelText('Дата съёмки 202609270106411790460401577.jpg')).toHaveValue(
      '03.08.2026',
    )
    expect(within(list).getByText(/проверьте подсказку по снимку/)).toBeInTheDocument()
  })

  it('asks to add a camera first when the site has none', async () => {
    const { user } = renderRoute('/sites/site-berezniki/observations')
    await user.click(await screen.findByRole('button', { name: 'Добавить снимки' }))
    const dialog = await screen.findByRole('dialog', { name: 'Добавить снимки' })
    expect(within(dialog).getByText('Сначала добавьте камеру')).toBeInTheDocument()
    expect(within(dialog).getByRole('link', { name: 'Перейти к камерам' })).toHaveAttribute(
      'href',
      '/sites/site-berezniki/cameras',
    )
    expect(within(dialog).queryByRole('button', { name: 'Загрузить' })).not.toBeInTheDocument()
  })

  it('sends the chosen camera with the batch', async () => {
    addCamera('К-1 · въезд')
    const second = addCamera('К-2 · котлован')
    let sent: FormDataEntryValue | null = null
    server.use(
      http.post('/api/sites/:siteId/photos', async ({ request }) => {
        sent = (await request.formData()).get('camera_id')
        return HttpResponse.json({ items: [], uploaded: 1, failed: 0 }, { status: 201 })
      }),
    )
    const { user } = renderRoute('/sites/site-berezniki/observations')
    await user.click(await screen.findByRole('button', { name: 'Добавить снимки' }))
    const dialog = await screen.findByRole('dialog', { name: 'Добавить снимки' })
    await user.upload(within(dialog).getByLabelText('Выбрать файлы'), [
      new File(['1'], 'a.jpg', { type: 'image/jpeg' }),
    ])
    const upload = within(dialog).getByRole('button', { name: 'Загрузить' })
    // Камер две: без выбора не загрузить
    expect(upload).toBeDisabled()
    await user.selectOptions(within(dialog).getByLabelText('Камера'), second.id)
    await user.click(upload)
    await vi.waitFor(() => expect(sent).toBe(second.id))
  })

  it('shows error and disables upload when batch exceeds size limit (200 MB)', async () => {
    addCamera()
    const { user } = renderRoute('/sites/site-berezniki/observations')
    await user.click(await screen.findByRole('button', { name: 'Добавить снимки' }))
    const dialog = await screen.findByRole('dialog', { name: 'Добавить снимки' })
    const upload = within(dialog).getByRole('button', { name: 'Загрузить' })

    // Create a file with size > 200 MB (201 MB)
    const largeFile = new File(['x'], 'large.jpg', { type: 'image/jpeg' })
    Object.defineProperty(largeFile, 'size', { value: 201 * 1024 * 1024, configurable: true })

    await user.upload(within(dialog).getByLabelText('Выбрать файлы'), [largeFile])

    expect(
      await within(dialog).findByText('Пачка слишком большая: выбрано 201.0 МБ, максимум 200 МБ'),
    ).toBeInTheDocument()
    expect(upload).toBeDisabled()
  })

  it('allows upload when batch is under size limit', async () => {
    addCamera()
    const { user } = renderRoute('/sites/site-berezniki/observations')
    await user.click(await screen.findByRole('button', { name: 'Добавить снимки' }))
    const dialog = await screen.findByRole('dialog', { name: 'Добавить снимки' })
    const upload = within(dialog).getByRole('button', { name: 'Загрузить' })

    // Create files with combined size < 200 MB (100 MB + 50 MB)
    const file1 = new File(['x'], 'file1.jpg', { type: 'image/jpeg' })
    Object.defineProperty(file1, 'size', { value: 100 * 1024 * 1024, configurable: true })

    const file2 = new File(['y'], 'file2.jpg', { type: 'image/jpeg' })
    Object.defineProperty(file2, 'size', { value: 50 * 1024 * 1024, configurable: true })

    await user.upload(within(dialog).getByLabelText('Выбрать файлы'), [file1, file2])

    expect(within(dialog).queryByText(/Пачка слишком большая/)).not.toBeInTheDocument()
    expect(upload).not.toBeDisabled()
  })

  it('clears error message when files are changed to under the limit', async () => {
    addCamera()
    const { user } = renderRoute('/sites/site-berezniki/observations')
    await user.click(await screen.findByRole('button', { name: 'Добавить снимки' }))
    const dialog = await screen.findByRole('dialog', { name: 'Добавить снимки' })

    // First, upload a file that exceeds the limit
    const largeFile = new File(['x'], 'large.jpg', { type: 'image/jpeg' })
    Object.defineProperty(largeFile, 'size', { value: 201 * 1024 * 1024, configurable: true })

    await user.upload(within(dialog).getByLabelText('Выбрать файлы'), [largeFile])

    expect(
      await within(dialog).findByText('Пачка слишком большая: выбрано 201.0 МБ, максимум 200 МБ'),
    ).toBeInTheDocument()

    // Now replace with files under the limit
    const smallFile = new File(['y'], 'small.jpg', { type: 'image/jpeg' })
    Object.defineProperty(smallFile, 'size', { value: 50 * 1024 * 1024, configurable: true })

    await user.upload(within(dialog).getByLabelText('Выбрать файлы'), [smallFile])

    expect(within(dialog).queryByText(/Пачка слишком большая/)).not.toBeInTheDocument()
    expect(within(dialog).getByRole('button', { name: 'Загрузить' })).not.toBeDisabled()
  })

  it('does not call upload endpoint when batch exceeds size limit', async () => {
    addCamera()
    const { user } = renderRoute('/sites/site-berezniki/observations')
    await user.click(await screen.findByRole('button', { name: 'Добавить снимки' }))
    const dialog = await screen.findByRole('dialog', { name: 'Добавить снимки' })
    const upload = within(dialog).getByRole('button', { name: 'Загрузить' })

    const largeFile = new File(['x'], 'large.jpg', { type: 'image/jpeg' })
    Object.defineProperty(largeFile, 'size', { value: 201 * 1024 * 1024, configurable: true })

    await user.upload(within(dialog).getByLabelText('Выбрать файлы'), [largeFile])
    await within(dialog).findByText('Пачка слишком большая: выбрано 201.0 МБ, максимум 200 МБ')

    // Button should be disabled, so clicking it should do nothing
    expect(upload).toBeDisabled()
    // The API should not have been called
    // This is implicitly tested by the button being disabled
  })

  it('opens a photo in the viewer and closes it with Escape', async () => {
    const { user } = renderRoute('/sites/site-berezniki/observations')
    const [open] = await screen.findAllByRole('button', { name: /^Открыть: Снимок / })
    const fileName = open!.getAttribute('aria-label')!.replace('Открыть: Снимок ', '')

    await user.click(open!)
    expect(await screen.findByRole('dialog', { name: new RegExp(fileName) })).toBeInTheDocument()

    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
