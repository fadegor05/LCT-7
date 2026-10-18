import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { server } from '@/mocks/server'
import { renderRoute } from '@/test/render'

const MERGE_FIRST_TWO = 'Объединить «Подготовка территории» со следующим этапом'

describe('merging schedule stages on the new-site step', () => {
  it('merges an adjacent pair into the first stage with the joined window', async () => {
    const { user } = renderRoute('/sites/site-synthetic/setup')
    const table = await screen.findByRole('table', { name: 'Этапы графика' })
    const before = within(table).getAllByRole('row').length

    await user.click(within(table).getByRole('button', { name: MERGE_FIRST_TWO }))

    expect(await within(table).findByText(/24\.08\.2026/)).toBeInTheDocument()
    expect(within(table).getByText(/14\.09\.2026/)).toBeInTheDocument()
    expect(within(table).queryByText('Разработка котлована')).not.toBeInTheDocument()
    expect(within(table).getAllByRole('row')).toHaveLength(before - 1)
    expect(screen.queryByText('Не получилось')).not.toBeInTheDocument()
  })

  it('shows the server reason when the merge is refused', async () => {
    server.use(
      http.post('/api/sites/:siteId/schedule/stages/merge', () =>
        HttpResponse.json({ detail: 'Объединять можно только соседние этапы' }, { status: 422 }),
      ),
    )
    const { user } = renderRoute('/sites/site-synthetic/setup')
    const table = await screen.findByRole('table', { name: 'Этапы графика' })

    await user.click(within(table).getByRole('button', { name: MERGE_FIRST_TWO }))

    expect(await screen.findByText('Объединять можно только соседние этапы')).toBeInTheDocument()
    expect(within(table).getByText('Подготовка территории')).toBeInTheDocument()
  })
})
