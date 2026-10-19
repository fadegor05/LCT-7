import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { StatusLegend } from './StatusLegend'

it('explains every stage status', async () => {
  render(<StatusLegend />)
  const legend = screen.getByRole('group', { name: 'Как выбирается статус этапа' })
  await userEvent.click(within(legend).getByText('Как выбирается статус этапа'))
  const rows = within(legend).getAllByRole('listitem')
  expect(rows.map((r) => r.querySelector('[data-part="badge"]')?.textContent)).toEqual([
    'В графике',
    'Опережение',
    'Отставание',
    'Не начата',
    'Не наблюдалось',
    'Не проверяется по технике',
  ])
  expect(rows[2]).toHaveTextContent('после планового конца')
  expect(legend).toHaveTextContent('Маркер — техника, которая отличает этап')
})
