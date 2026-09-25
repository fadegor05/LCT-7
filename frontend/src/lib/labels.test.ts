import { plural, pluralPhotos } from './labels'

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

  it('has a ready-made helper for photos', () => {
    expect(pluralPhotos(1)).toBe('1 снимок')
    expect(pluralPhotos(24)).toBe('24 снимка')
    expect(pluralPhotos(9)).toBe('9 снимков')
  })
})
