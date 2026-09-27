import type { Deviation } from '@/api/schemas'
import { deviationTitle, sortDeviations, withStages } from './deviations'

describe('deviation ordering', () => {
  it('puts critical first, then the freshest within a level', () => {
    const items = [
      { id: 'a', severity: 'attention' as const, created_at: '2026-09-18' },
      { id: 'b', severity: 'critical' as const, created_at: '2026-09-10' },
      { id: 'c', severity: 'attention' as const, created_at: '2026-09-19' },
    ]
    expect(sortDeviations(items).map((d) => d.id)).toEqual(['b', 'c', 'a'])
    expect(items[0]!.id).toBe('a')
  })
})

describe('deviationTitle', () => {
  it('builds the title from the type, hypothesis mark and stage', () => {
    expect(deviationTitle({ type: 'idle', is_hypothesis: true }, 'Котлован')).toBe(
      'Простой техники (гипотеза) · Котлован',
    )
    expect(deviationTitle({ type: 'stale_data', is_hypothesis: false })).toBe('Данные устарели')
  })
})

describe('withStages', () => {
  it('adds the site and the stage name from the schedule', () => {
    const base = { stage_id: null } as Deviation
    const stage = {
      id: 'st',
      name: 'Котлован',
      position: 1,
      planned_start: null,
      planned_end: null,
      dates_source: 'file' as const,
    }
    const [staged, unknown, general] = withStages(
      's1',
      [
        { ...base, id: 'a', stage_id: 'st' },
        { ...base, id: 'b', stage_id: 'gone' },
        { ...base, id: 'c' },
      ],
      [stage],
    )
    expect(staged).toMatchObject({ site_id: 's1', stage_name: 'Котлован' })
    expect(unknown!.stage_name).toBeNull()
    expect(general!.stage_name).toBeNull()
  })
})
