import { sortDeviations, visibleDeviations } from './deviations'

describe('deviation ordering', () => {
  it('puts critical first, then the freshest within a level', () => {
    const items = [
      { id: 'a', severity: 'attention' as const, detected_at: '2026-09-18' },
      { id: 'b', severity: 'critical' as const, detected_at: '2026-09-10' },
      { id: 'c', severity: 'attention' as const, detected_at: '2026-09-19' },
    ]
    expect(sortDeviations(items).map((d) => d.id)).toEqual(['b', 'c', 'a'])
    expect(items[0]!.id).toBe('a')
  })

  it('hides rejected hypotheses', () => {
    const items = [
      { id: 'a', decision: null },
      { id: 'b', decision: 'rejected' as const },
      { id: 'c', decision: 'confirmed' as const },
    ]
    expect(visibleDeviations(items).map((d) => d.id)).toEqual(['a', 'c'])
  })
})
