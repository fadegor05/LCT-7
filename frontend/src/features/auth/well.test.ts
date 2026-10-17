import { Well } from './well'

/** Детерминированный генератор вместо Math.random. */
function seeded(seed = 1) {
  let s = seed
  return () => {
    s = (s * 16807) % 2147483647
    return (s - 1) / 2147483646
  }
}

function fillRow(well: Well, row: number, cols: number[]) {
  for (const c of cols) well.board[row]![c] = { type: 'O', cx: 0, cy: 0 }
}

describe('Well', () => {
  it('drops a piece to the floor of an empty well', () => {
    const well = new Well(10, 8, seeded())
    expect(well.landing('O', 0)).toBe(6)
    expect(well.landing('I', 6)).toBe(7)
  })

  it('stops a piece on top of the stack', () => {
    const well = new Well(4, 6, seeded())
    fillRow(well, 5, [0, 1])
    expect(well.landing('O', 0)).toBe(3)
    expect(well.landing('O', 2)).toBe(4)
  })

  it('deals all seven machines in every seven pieces', () => {
    const well = new Well(40, 30, seeded(7))
    for (let round = 0; round < 3; round++) {
      const dealt = Array.from({ length: 7 }, () => well.drop()?.type)
      expect(new Set(dealt)).toEqual(new Set(['I', 'O', 'T', 'S', 'Z', 'J', 'L']))
    }
  })

  it('locks a falling piece and reports the row it completes', () => {
    const well = new Well(4, 3, seeded())
    well.falling.push({ type: 'I', x: 0, y: -1 })
    expect(well.step()).toEqual([])
    expect(well.step()).toEqual([])
    expect(well.step()).toEqual([])
    expect(well.step()).toEqual([2])
    expect(well.falling).toEqual([])
    well.removeRows([2])
    expect(well.stackHeight()).toBe(0)
  })

  it('shifts the rows above a cleared row down', () => {
    const well = new Well(2, 3, seeded())
    fillRow(well, 1, [0])
    fillRow(well, 2, [0, 1])
    well.removeRows(well.fullRows())
    expect(well.board[2]![0]).not.toBeNull()
    expect(well.board[2]![1]).toBeNull()
    expect(well.stackHeight()).toBe(1)
  })

  it('keeps clear of the columns of a falling piece', () => {
    const well = new Well(8, 6, seeded())
    well.falling.push({ type: 'O', x: 3, y: -2 })
    for (let i = 0; i < 20; i++) {
      const x = well.choose('O')!
      expect(x + 1 < 3 || x > 4).toBe(true)
    }
  })

  it('prefers a place that completes a row', () => {
    const well = new Well(4, 4, seeded())
    fillRow(well, 3, [0, 1])
    fillRow(well, 2, [0, 1])
    expect(well.choose('O')).toBe(2)
  })

  it('refuses a place where the piece would stick out of the top', () => {
    const well = new Well(2, 2, seeded())
    expect(well.choose('O')).toBe(0)
    fillRow(well, 1, [0])
    expect(well.choose('O')).toBeNull()
  })

  it('lets one piece fall per eight columns', () => {
    const wide = new Well(16, 10, seeded())
    expect(wide.spawn()).not.toBeNull()
    expect(wide.spawn()).not.toBeNull()
    expect(wide.spawn()).toBeNull()
    const narrow = new Well(4, 10, seeded())
    expect(narrow.spawn()).not.toBeNull()
    expect(narrow.spawn()).toBeNull()
  })

  it('returns the piece to the bag when there is no room', () => {
    const well = new Well(2, 1, seeded())
    expect(well.spawn()).toBeNull()
    expect(well.falling).toEqual([])
  })

  it('sinks a stack that grows above 60 % of the well', () => {
    const well = new Well(4, 10, seeded())
    for (let r = 3; r < 10; r++) fillRow(well, r, [0])
    expect(well.sinkIfHigh()).toBe(3)
    expect(well.stackHeight()).toBe(4)
    expect(well.sinkIfHigh()).toBe(0)
  })

  it('warms up to about a third of the well without full rows', () => {
    const well = new Well(20, 15, seeded(3))
    well.warmup()
    expect(well.stackHeight()).toBeGreaterThanOrEqual(6)
    expect(well.fullRows()).toEqual([])
    expect(well.falling).toEqual([])
  })

  it('treats an empty well without columns as having no full rows', () => {
    const well = new Well(0, 3, seeded())
    expect(well.fullRows()).toEqual([])
    expect(well.spawn()).toBeNull()
  })
})
