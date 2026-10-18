import { PITCH, roofCenter } from './geometry'
import { TOWER_STAGES, buildTimeline, valueAt } from './timeline'

describe('valueAt', () => {
  const keys = [
    { t: 0, v: 0, e: 'lin' as const },
    { t: 10, v: 100, e: 'lin' as const },
    { t: 20, v: 100, e: 'out' as const },
    { t: 30, v: 0, e: 'io' as const },
  ]

  it('interpolates, holds and clamps after the last key', () => {
    expect(valueAt(keys, 5)).toBe(50)
    expect(valueAt(keys, 15)).toBe(100)
    expect(valueAt(keys, 99)).toBe(0)
  })

  it('applies easing curves between keys', () => {
    const slowStart = valueAt(keys, 21)
    expect(slowStart).toBeLessThan(100)
    expect(slowStart).toBeGreaterThan(50)
    expect(valueAt(keys, 25)).toBeCloseTo(50, 5)
  })
})

describe('buildTimeline', () => {
  const tl = buildTimeline()

  it('places one block per stage, one after another', () => {
    expect(tl.events).toHaveLength(TOWER_STAGES.length)
    tl.events.forEach((ev) => {
      expect(ev.appear).toBeLessThan(ev.attach)
      expect(ev.attach).toBeLessThan(ev.release)
    })
    tl.events.slice(1).forEach((ev, i) => {
      expect(ev.appear).toBeCloseTo(tl.events[i]!.release, 6)
    })
    expect(tl.cycle).toBeGreaterThan(tl.end)
  })

  it('brings the trolley over the tower and the hook down onto the roof for every block', () => {
    tl.events.forEach((ev, i) => {
      const [topX, topY] = roofCenter(i)
      expect(valueAt(tl.tx, ev.release)).toBeCloseTo(topX, 3)
      expect(valueAt(tl.hy, ev.release)).toBeCloseTo(topY - 26, 3)
    })
  })

  it('lifts the load clear of the stack before carrying it', () => {
    tl.events.forEach((ev, i) => {
      const [, topY] = roofCenter(i)
      const carry = valueAt(tl.hy, ev.attach + (ev.release - ev.attach) * 0.4)
      expect(carry).toBeLessThan(topY - 26 - PITCH)
    })
  })
})
