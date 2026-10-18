import { takeSeconds } from './streamLink'

describe('takeSeconds', () => {
  it('moves ?seconds= out of the link into the interval', () => {
    expect(takeSeconds('rtsp://cam/live?seconds=300')).toEqual({
      url: 'rtsp://cam/live',
      seconds: 300,
    })
  })

  it('keeps the camera own parameters', () => {
    expect(takeSeconds('rtsp://cam/live?channel=1&seconds=600&subtype=0')).toEqual({
      url: 'rtsp://cam/live?channel=1&subtype=0',
      seconds: 600,
    })
    expect(takeSeconds('http://cam/mjpg?seconds=120#x')).toEqual({
      url: 'http://cam/mjpg#x',
      seconds: 120,
    })
  })

  it('leaves a link without our parameter alone', () => {
    expect(takeSeconds('rtsp://admin:p@ss@10.0.0.5/live?channel=1')).toEqual({
      url: 'rtsp://admin:p@ss@10.0.0.5/live?channel=1',
      seconds: null,
    })
    expect(takeSeconds('  ')).toEqual({ url: '  ', seconds: null })
  })

  it('ignores a value that is not a whole number of seconds', () => {
    expect(takeSeconds('rtsp://cam/live?seconds=abc')).toEqual({
      url: 'rtsp://cam/live?seconds=abc',
      seconds: null,
    })
  })
})
