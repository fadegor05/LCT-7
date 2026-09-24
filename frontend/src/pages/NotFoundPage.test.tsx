import { screen } from '@testing-library/react'
import { renderRoute } from '@/test/render'

describe('NotFoundPage', () => {
  it('renders for unknown routes', async () => {
    renderRoute('/whatever')
    expect(await screen.findByRole('heading', { name: 'Страница не найдена' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'К стройкам' })).toHaveAttribute('href', '/sites')
  })
})
