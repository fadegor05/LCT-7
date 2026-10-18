import { D, H, PITCH, W, diamond, hull, iso, pts, roofCenter, shade, smoothstep } from './geometry'

describe('iso', () => {
  it('puts the back corner at the origin and the roof one block higher per floor', () => {
    expect(iso(0, 0, 0)).toEqual([450, 520])
    const [x0, y0] = roofCenter(0)
    const [x1, y1] = roofCenter(1)
    expect(x1).toBe(x0)
    expect(y0 - y1).toBe(PITCH)
    expect(y0).toBe(iso(W / 2, D / 2, H)[1])
  })

  it('draws the footprint diamond with a screen offset', () => {
    expect(diamond(0)).toHaveLength(4)
    expect(diamond(0, 10, 5)[0]).toEqual([460, 525])
    expect(pts([[1, 2.55]])).toBe('1.0,2.5')
  })
})

describe('shade', () => {
  it('darkens and lightens a hex colour', () => {
    expect(shade('#808080', 0)).toBe('#000000')
    expect(shade('#808080', 2)).toBe('#ffffff')
    expect(shade('#123456', 1)).toBe('#123456')
  })
})

describe('hull', () => {
  it('keeps only the outline of the point cloud', () => {
    const square: [number, number][] = [
      [0, 0],
      [10, 0],
      [10, 10],
      [0, 10],
    ]
    const outline = hull([...square, [5, 5], [5, 1]])
    expect(outline).toHaveLength(4)
    expect(outline).toEqual(expect.arrayContaining(square))
  })
})

describe('smoothstep', () => {
  it('eases between the edges in either direction', () => {
    expect(smoothstep(0, 10, -5)).toBe(0)
    expect(smoothstep(0, 10, 5)).toBe(0.5)
    expect(smoothstep(10, 0, 0)).toBe(1)
    expect(smoothstep(150, 40, 200)).toBe(0)
  })
})
