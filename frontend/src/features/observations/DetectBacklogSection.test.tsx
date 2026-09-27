import { screen, waitFor } from '@testing-library/react'
import { renderRoute } from '@/test/render'

describe('DetectBacklogSection', () => {
  it('shows on observations page when photos need processing', async () => {
    renderRoute('/sites/site-berezniki/observations')

    await waitFor(() => {
      const button = screen.getByText('Распознать необработанные')
      expect(button).toBeInTheDocument()
    })
  })

  it('button is enabled on render', async () => {
    renderRoute('/sites/site-berezniki/observations')

    const button = await screen.findByText('Распознать необработанные')
    expect(button).not.toBeDisabled()
  })

  it('success message stays visible after photos refetch when statuses update', async () => {
    const { user } = renderRoute('/sites/site-berezniki/observations')

    const button = await screen.findByText('Распознать необработанные')
    expect(button).toBeInTheDocument()

    // Click button to trigger detect
    await user.click(button)

    // Success message should appear and remain visible even after photos refetch
    // The mock db.detectBacklog updates photos to done status, which triggers refetch
    // but the message should stay because render condition is: hasNonDone || message
    await waitFor(() => {
      expect(screen.getByText(/Обработано \d+:/)).toBeInTheDocument()
    })
  })
})
