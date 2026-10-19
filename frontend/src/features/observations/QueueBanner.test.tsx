import { screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { chunkFiles, MAX_BATCH_BYTES } from '@/api/frames'
import { server } from '@/mocks/server'
import { renderRoute } from '@/test/render'

describe('QueueBanner', () => {
  it('shows background processing and refreshes the site when the queue drains', async () => {
    let left = 3
    let photoLists = 0
    server.use(
      http.get('*/sites/:siteId/photos/progress', () =>
        HttpResponse.json({ queued: Math.max(left - 1, 0), processing: left > 0 ? 1 : 0 }),
      ),
      http.get('*/sites/:siteId/photos', () => {
        photoLists += 1
        return undefined // дальше — обычный мок
      }),
    )
    renderRoute('/sites/site-berezniki/observations')
    expect(await screen.findByText('Обрабатываются снимки: осталось 3')).toBeInTheDocument()
    const before = photoLists
    left = 0
    // Опрос раз в 2 с: очередь опустела — плашка уходит, данные объекта перезапрошены
    await waitFor(() => expect(screen.queryByText(/Обрабатываются снимки/)).toBeNull(), {
      timeout: 4000,
    })
    await waitFor(() => expect(photoLists).toBeGreaterThan(before))
  })

  it('stays hidden when nothing is queued', async () => {
    renderRoute('/sites/site-berezniki/observations')
    await screen.findByRole('group', { name: 'Дни наблюдений' })
    expect(screen.queryByText(/Обрабатываются снимки/)).toBeNull()
  })
})

describe('chunkFiles', () => {
  const file = (mb: number) => {
    const f = new File(['x'], 'f.jpg')
    Object.defineProperty(f, 'size', { value: mb * 1024 * 1024 })
    return f
  }

  it('splits by the batch size limit as well as by count', () => {
    const chunks = chunkFiles([file(150), file(60), file(10), file(190)])
    expect(chunks.map((c) => c.length)).toEqual([1, 2, 1])
    for (const c of chunks)
      expect(c.reduce((s, f) => s + f.size, 0)).toBeLessThanOrEqual(MAX_BATCH_BYTES)
    expect(chunkFiles([])).toEqual([])
  })
})
