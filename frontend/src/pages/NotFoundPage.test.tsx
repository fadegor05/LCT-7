import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server } from '@/mocks/server'
import { renderRoute } from '@/test/render'

describe('NotFoundPage', () => {
  it('renders for unknown routes', async () => {
    renderRoute('/whatever')
    expect(await screen.findByRole('heading', { name: 'Страница не найдена' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'К стройкам' })).toHaveAttribute('href', '/sites')
  })

  // bug-reports/003: кривой id в URL — не текст pydantic, а «не найдена» и путь назад.
  it('shows a missing site with a way back instead of a raw validation error', async () => {
    server.use(
      http.get('/api/sites/:siteId', () =>
        HttpResponse.json(
          { detail: [{ msg: 'Input should be a valid UUID, invalid length' }] },
          { status: 422 },
        ),
      ),
    )
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    renderRoute('/sites/abc')
    expect(await screen.findByText('Стройка не найдена')).toBeInTheDocument()
    expect(screen.queryByText(/Input should be/)).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'К стройкам' })).toHaveAttribute('href', '/sites')
  })
})
