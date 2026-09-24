import { plural, pluralFrames, pluralMachines, pluralWorks } from './labels'

describe('plural', () => {
  it.each([
    [1, 'кадр'],
    [2, 'кадра'],
    [5, 'кадров'],
    [11, 'кадров'],
    [12, 'кадров'],
    [21, 'кадр'],
    [24, 'кадра'],
    [111, 'кадров'],
  ])('%i → %s', (n, word) => {
    expect(plural(n, ['кадр', 'кадра', 'кадров'])).toBe(word)
  })

  it('has ready-made helpers', () => {
    expect(pluralFrames(24)).toBe('24 кадра')
    expect(pluralMachines(1)).toBe('1 машина')
    expect(pluralWorks(9)).toBe('9 работ')
  })
})
