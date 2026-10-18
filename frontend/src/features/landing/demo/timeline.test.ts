import { existsSync } from 'node:fs'
import { resolve } from 'node:path'
import { AXIS_DAYS, SNAPSHOTS, STEPS, axisPos, dayOf, timelineState } from './timeline'

describe('timeline axis', () => {
  it('puts dates on the axis between 0 and 1', () => {
    expect(dayOf('2023-05-01')).toBe(0)
    expect(AXIS_DAYS).toBe(183)
    expect(axisPos('2023-05-01')).toBe(0)
    expect(axisPos('2023-10-31')).toBe(1)
    expect(axisPos('2023-07-31')).toBeLessThan(axisPos('2023-08-14'))
  })

  it('keeps every snapshot picture on disk and in date order', () => {
    const days = SNAPSHOTS.map((s) => dayOf(s.iso))
    expect([...days].sort((a, b) => a - b)).toEqual(days)
    for (const s of SNAPSHOTS) {
      expect(existsSync(resolve('public', s.src.slice(1)))).toBe(true)
      expect(s.alt.length).toBeGreaterThan(20)
    }
  })
})

describe('timelineState', () => {
  it('starts with the plan only, no cursor and no photos', () => {
    const s = timelineState(0)
    expect(s.cursor).toBeNull()
    expect(s.shown).toEqual([false, false, false])
    expect(s.step).toBe(0)
    expect(s.lag).toBe(0)
  })

  it('shows photos as the cursor passes their dates, never before', () => {
    const early = timelineState(0.35)
    expect(early.shown).toEqual([true, false, false])
    expect(early.step).toBe(1)
    expect(early.piles).toBe(false)

    const mid = timelineState(0.6)
    expect(mid.shown).toEqual([true, true, false])
    expect(mid.piles).toBe(true)
    expect(mid.sheet).toBe(false)
    expect(mid.step).toBe(2)
  })

  it('draws the delay segment only between the plan end and the snapshot with the rig', () => {
    expect(timelineState(0.3).lag).toBe(0)
    const growing = timelineState(0.54).lag
    expect(growing).toBeGreaterThan(0)
    expect(growing).toBeLessThanOrEqual(1)
    expect(timelineState(0.7).lag).toBe(1)
  })

  it('ends with the limits and clamps out-of-range progress', () => {
    const last = timelineState(1)
    expect(last.step).toBe(STEPS.length - 1)
    expect(last.shown).toEqual([true, true, true])
    expect(last.sheet).toBe(true)
    expect(timelineState(-5).cursor).toBeNull()
    expect(timelineState(9).step).toBe(STEPS.length - 1)
  })

  it('never moves a step backwards while scrolling down', () => {
    let prev = 0
    for (let p = 0; p <= 1.0001; p += 0.01) {
      const step = timelineState(p).step
      expect(step).toBeGreaterThanOrEqual(prev)
      prev = step
    }
  })
})
