import { existsSync } from 'node:fs'
import { resolve } from 'node:path'
import { DEMO_FINDINGS } from './p03'

describe('p03 demo data', () => {
  it('keeps the product vocabulary: no signs in delays, no forecast', () => {
    for (const f of DEMO_FINDINGS) {
      expect(`${f.status} ${f.plan} ${f.fact}`).not.toMatch(/[+−]\s?\d/)
      expect(JSON.stringify(f)).not.toMatch(/прогноз|\+104/i)
    }
  })

  it('never calls a hypothesis critical and explains every limit', () => {
    for (const f of DEMO_FINDINGS.filter((x) => x.hypothesis)) {
      expect(f.severity).toBe('Внимание')
    }
    expect(DEMO_FINDINGS.some((f) => f.hypothesis)).toBe(true)
    for (const f of DEMO_FINDINGS) {
      expect(f.cannotClaim.length).toBeGreaterThan(40)
      expect(f.frames.length).toBeGreaterThan(0)
    }
  })

  it('has a real picture and sane boxes for every frame', () => {
    for (const f of DEMO_FINDINGS) {
      for (const frame of f.frames) {
        expect(existsSync(resolve('public', frame.src.slice(1)))).toBe(true)
        expect(frame.alt.length).toBeGreaterThan(20)
        for (const b of frame.boxes) {
          const [x0, y0, x1, y1] = b.box
          expect(x0).toBeGreaterThanOrEqual(0)
          expect(y0).toBeGreaterThanOrEqual(0)
          expect(x1).toBeLessThanOrEqual(1)
          expect(y1).toBeLessThanOrEqual(1)
          expect(x1).toBeGreaterThan(x0)
          expect(y1).toBeGreaterThan(y0)
          expect(b.conf).toBeGreaterThanOrEqual(0.5)
        }
      }
    }
  })
})
