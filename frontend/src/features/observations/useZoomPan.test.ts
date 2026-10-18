import { act, renderHook } from '@testing-library/react'
import { clampView, useZoomPan, zoomAt } from './useZoomPan'

const box = { width: 400, height: 300 }

describe('clampView', () => {
  it('ограничивает масштаб диапазоном min..max', () => {
    expect(clampView({ scale: 0.2, x: 0, y: 0 }, box).scale).toBe(1)
    expect(clampView({ scale: 50, x: 0, y: 0 }, box).scale).toBe(8)
    expect(clampView({ scale: 3, x: 0, y: 0 }, box, 1, 4).scale).toBe(3)
  })

  it('при scale=1 сдвиг обнуляется', () => {
    expect(clampView({ scale: 1, x: 120, y: -40 }, box)).toEqual({ scale: 1, x: 0, y: 0 })
  })

  it('не даёт контенту уйти левее и выше контейнера', () => {
    // контент шириной 400*2=800: x не ниже 400*(1-2) = -400
    const view = clampView({ scale: 2, x: -999, y: -999 }, box)
    expect(view.x).toBe(-400)
    expect(view.y).toBe(-300)
  })

  it('не даёт сдвинуть контент правее или ниже левого/верхнего края', () => {
    const view = clampView({ scale: 2, x: 50, y: 10 }, box)
    expect(view.x).toBe(0)
    expect(view.y).toBe(0)
  })

  it('оставляет допустимый сдвиг без изменений', () => {
    expect(clampView({ scale: 2, x: -100, y: -50 }, box)).toEqual({ scale: 2, x: -100, y: -50 })
  })
})

describe('zoomAt', () => {
  it('точка под курсором остаётся на месте', () => {
    const view = { scale: 2, x: -100, y: -50 }
    const point = { x: 200, y: 150 }
    // контент под курсором до зума
    const contentX = (point.x - view.x) / view.scale
    const contentY = (point.y - view.y) / view.scale

    const next = zoomAt(view, 1.5, point, box)

    expect(next.scale).toBeCloseTo(3)
    expect(next.x + contentX * next.scale).toBeCloseTo(point.x)
    expect(next.y + contentY * next.scale).toBeCloseTo(point.y)
  })

  it('результат проходит через clampView (масштаб не выше максимума)', () => {
    const next = zoomAt({ scale: 7, x: 0, y: 0 }, 1.5, { x: 0, y: 0 }, box)
    expect(next.scale).toBe(8)
  })

  it('отдаление до scale=1 сбрасывает сдвиг', () => {
    const next = zoomAt({ scale: 1.2, x: -40, y: -20 }, 1 / 1.5, { x: 100, y: 100 }, box)
    expect(next).toEqual({ scale: 1, x: 0, y: 0 })
  })
})

describe('useZoomPan', () => {
  it('начинает с масштаба 1 и не зумлен', () => {
    const { result } = renderHook(() => useZoomPan())
    expect(result.current.view).toEqual({ scale: 1, x: 0, y: 0 })
    expect(result.current.isZoomed).toBe(false)
  })

  it('zoomIn увеличивает масштаб', () => {
    const { result } = renderHook(() => useZoomPan())
    act(() => result.current.zoomIn())
    expect(result.current.view.scale).toBeCloseTo(1.5)
    expect(result.current.isZoomed).toBe(true)
  })

  it('reset возвращает масштаб 1', () => {
    const { result } = renderHook(() => useZoomPan())
    act(() => result.current.zoomIn())
    act(() => result.current.reset())
    expect(result.current.view).toEqual({ scale: 1, x: 0, y: 0 })
    expect(result.current.isZoomed).toBe(false)
  })
})
