import { render, screen } from '@testing-library/react'
import { QueryState } from './QueryState'

describe('QueryState', () => {
  it('shows loading', () => {
    render(
      <QueryState query={{ isPending: true, error: null, data: undefined }}>
        {() => 'данные'}
      </QueryState>,
    )
    expect(screen.getByRole('status')).toHaveTextContent('Загрузка…')
  })

  it('shows errors', () => {
    render(
      <QueryState query={{ isPending: false, error: new Error('сломалось'), data: undefined }}>
        {() => 'данные'}
      </QueryState>,
    )
    expect(screen.getByRole('alert')).toHaveTextContent('сломалось')
  })

  it('renders data', () => {
    render(
      <QueryState query={{ isPending: false, error: null, data: 5 }}>
        {(n: number) => `n=${n}`}
      </QueryState>,
    )
    expect(screen.getByText('n=5')).toBeInTheDocument()
  })
})
