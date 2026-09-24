import { screen } from '@testing-library/react'
import { renderWithProviders } from '@/test/render'
import { Button, ButtonLink } from './Button'

describe('Button', () => {
  it('renders a button with icon and calls onClick', async () => {
    const onClick = vi.fn()
    const { user, container } = renderWithProviders(
      <Button icon="plus" onClick={onClick}>
        Добавить
      </Button>,
    )
    const button = screen.getByRole('button', { name: 'Добавить' })
    expect(button).toHaveAttribute('type', 'button')
    expect(button.className).toContain('primary')
    expect(container.querySelector('[data-icon="plus"]')).toBeInTheDocument()
    await user.click(button)
    expect(onClick).toHaveBeenCalledOnce()
  })

  it('applies variant and size classes, respects disabled', async () => {
    const onClick = vi.fn()
    const { user } = renderWithProviders(
      <Button variant="ghost" size="sm" disabled onClick={onClick}>
        Отмена
      </Button>,
    )
    const button = screen.getByRole('button', { name: 'Отмена' })
    expect(button.className).toMatch(/ghost/)
    expect(button.className).toMatch(/sm/)
    await user.click(button)
    expect(onClick).not.toHaveBeenCalled()
  })

  it('ButtonLink navigates', async () => {
    const { user } = renderWithProviders(
      <ButtonLink to="/next" variant="secondary" size="lg" icon="chevronRight">
        Далее
      </ButtonLink>,
    )
    const link = screen.getByRole('link', { name: 'Далее' })
    expect(link.className).toMatch(/secondary/)
    await user.click(link)
    expect(await screen.findByText('другая страница')).toBeInTheDocument()
  })
})
