import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server } from '@/mocks/server'
import { renderRoute } from '@/test/render'

describe('prefetch', () => {
  it('loads a site tab when the pointer is over it', async () => {
    let cameras = 0
    server.use(
      http.get('/api/sites/:siteId/cameras', () => {
        cameras += 1
        return HttpResponse.json([])
      }),
    )
    const { user } = renderRoute('/sites/site-berezniki/methodology')
    const tab = await screen.findByRole('link', { name: 'Камеры' })
    expect(cameras).toBe(0)

    await user.hover(tab)
    await vi.waitFor(() => expect(cameras).toBe(1))

    // Переход открывает готовый экран: без «Загрузка…»
    await user.click(tab)
    expect(screen.queryByText('Загрузка…')).not.toBeInTheDocument()
  })

  it('loads a site overview when the pointer is over its row', async () => {
    let summary = 0
    server.use(
      http.get('/api/sites/site-berezniki/assessment/deviations', () => {
        summary += 1
        return HttpResponse.json([])
      }),
    )
    const { user } = renderRoute('/sites')
    const row = await screen.findByRole('link', { name: /Жилой дом · Березники/ })
    await user.hover(row)
    await vi.waitFor(() => expect(summary).toBeGreaterThan(0))
  })
})
