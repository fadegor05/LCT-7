import { settled } from './settled'

describe('settled', () => {
  it('waits for every query that is actually loading', () => {
    expect(settled({ isPending: false }, { isPending: false })).toBe(true)
    expect(settled({ isPending: false }, { isPending: true, fetchStatus: 'fetching' })).toBe(false)
  })

  it('treats a disabled query as ready', () => {
    expect(settled({ isPending: true, fetchStatus: 'idle' })).toBe(true)
  })
})
