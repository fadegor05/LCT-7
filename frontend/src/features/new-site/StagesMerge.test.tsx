import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { Stage } from '@/api/schemas'
import { renderWithProviders } from '@/test/render'
import { StagesTable } from './StagesTable'

const stage = (id: string, name: string, position: number): Stage => ({
  id,
  name,
  position,
  planned_start: '2026-09-01',
  planned_end: '2026-09-10',
  dates_source: 'file',
})

const stages = [stage('a', 'Котлован', 1), stage('b', 'Основание', 2), stage('c', 'Стены', 3)]

describe('StagesTable merge action', () => {
  it('offers merging with the next stage for every row but the last', () => {
    renderWithProviders(
      <StagesTable year={2026} onSetDates={vi.fn()} onMerge={vi.fn()} stages={stages} />,
    )
    expect(
      screen.getByRole('button', { name: 'Объединить «Котлован» со следующим этапом' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Объединить «Основание» со следующим этапом' }),
    ).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /Объединить/ })).toHaveLength(2)
  })

  it('reports the stage and the next one it should be merged with', async () => {
    const onMerge = vi.fn()
    renderWithProviders(
      <StagesTable year={2026} onSetDates={vi.fn()} onMerge={onMerge} stages={stages} />,
    )
    await userEvent.click(
      within(screen.getAllByRole('row')[2]!).getByRole('button', {
        name: /Объединить «Основание»/,
      }),
    )
    expect(onMerge).toHaveBeenCalledWith('b', 'c')
  })

  it('disables merging while a change is pending', () => {
    renderWithProviders(
      <StagesTable year={2026} onSetDates={vi.fn()} onMerge={vi.fn()} pending stages={stages} />,
    )
    expect(
      screen.getByRole('button', { name: 'Объединить «Котлован» со следующим этапом' }),
    ).toBeDisabled()
  })

  it('stays out of the way when no merge handler is given', () => {
    renderWithProviders(<StagesTable year={2026} onSetDates={vi.fn()} stages={stages} />)
    expect(screen.queryByRole('button', { name: /Объединить/ })).not.toBeInTheDocument()
  })
})
