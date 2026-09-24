import { screen } from '@testing-library/react'
import { renderWithProviders } from '@/test/render'
import { Breadcrumbs } from './Breadcrumbs'
import { Stepper } from './Stepper'

describe('Breadcrumbs', () => {
  it('links all but the current crumb', () => {
    renderWithProviders(
      <Breadcrumbs items={[{ label: 'Стройки', to: '/sites' }, { label: 'Камеры' }]} />,
    )
    const nav = screen.getByRole('navigation', { name: 'Хлебные крошки' })
    expect(nav).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Стройки' })).toHaveAttribute('href', '/sites')
    expect(screen.getByText('Камеры')).toHaveAttribute('aria-current', 'page')
  })
})

describe('Stepper', () => {
  it('marks done, current and upcoming steps', () => {
    renderWithProviders(<Stepper steps={['Первый', 'Второй', 'Третий']} current={1} />)
    const items = screen.getAllByRole('listitem').filter((li) => li.textContent)
    expect(items).toHaveLength(3)
    expect(items[1]).toHaveAttribute('aria-current', 'step')
    expect(items[0]!.querySelector('[data-icon="check"]')).toBeInTheDocument()
    expect(items[2]).toHaveTextContent('3Третий')
  })
})
