import { camerasWord, framesWord } from './plural'

describe('plural forms', () => {
  it('picks the Russian form by the last digits', () => {
    expect([1, 21, 101].map(framesWord)).toEqual(['кадр', 'кадр', 'кадр'])
    expect([2, 3, 24].map(framesWord)).toEqual(['кадра', 'кадра', 'кадра'])
    expect([0, 5, 11, 14, 112].map(framesWord)).toEqual([
      'кадров',
      'кадров',
      'кадров',
      'кадров',
      'кадров',
    ])
    expect([1, 2, 5].map(camerasWord)).toEqual(['камера', 'камеры', 'камер'])
  })
})
