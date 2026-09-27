import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server } from '@/mocks/server'
import { renderRoute } from '@/test/render'

const photos = () => screen.findAllByRole('img', { name: /Снимок / })

describe('ObservationsPage', () => {
  it('shows the latest day by default and switches to all days', async () => {
    const { user, router } = renderRoute('/sites/site-berezniki/observations')
    expect(await screen.findByRole('heading', { name: 'Снимки за 18.09' })).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Техника на площадке' })).toBeInTheDocument()
    expect(screen.getByText('не менее 2')).toBeInTheDocument()
    expect(await photos()).toHaveLength(4)

    await user.click(screen.getByRole('button', { name: /Все дни/ }))
    expect(await screen.findByRole('heading', { name: 'Все снимки с датой' })).toBeInTheDocument()
    expect(router.state.location.search).toBe('?date=all')
    expect(screen.queryByRole('heading', { name: 'Техника на площадке' })).not.toBeInTheDocument()
    expect(await photos()).toHaveLength(12)
    expect(screen.getAllByText('14.09', { selector: 'figcaption span' })).toHaveLength(2)

    await user.click(screen.getByRole('button', { name: /17\.09/ }))
    expect(await screen.findByRole('heading', { name: 'Снимки за 17.09' })).toBeInTheDocument()
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
    expect(await screen.findByRole('button', { name: /18\.09\s*5 снимков/ })).toBeInTheDocument()
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
    const { user } = renderRoute('/sites/site-berezniki/observations')
    await user.click(await screen.findByRole('button', { name: 'Добавить снимки' }))
    const dialog = screen.getByRole('dialog', { name: 'Добавить снимки' })
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
    const { user } = renderRoute('/sites/site-berezniki/observations')
    await user.click(await screen.findByRole('button', { name: 'Добавить снимки' }))
    let dialog = screen.getByRole('dialog')
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
    dialog = screen.getByRole('dialog')
    await user.upload(within(dialog).getByLabelText('Выбрать файлы'), [
      new File(['1'], 'a.jpg', { type: 'image/jpeg' }),
    ])
    await user.click(within(dialog).getByRole('button', { name: 'Загрузить' }))
    expect(await within(dialog).findByText('Слишком много файлов')).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Отмена' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
