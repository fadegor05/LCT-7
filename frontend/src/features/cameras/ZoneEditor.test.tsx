import { fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import type { Zone } from '@/api/schemas'
import { ZoneEditor } from './ZoneEditor'

/** Область рисования 400×300 px от (0, 0): клик в (200, 150) — середина кадра. */
function Harness({ initial = null }: { initial?: Zone | null }) {
  const [zone, setZone] = useState<Zone | null>(initial)
  return (
    <>
      <ZoneEditor imageUrl="/frame.jpg" aspect={4 / 3} value={zone} onChange={setZone} />
      <output data-testid="zone">{JSON.stringify(zone)}</output>
    </>
  )
}

beforeEach(() => {
  vi.spyOn(SVGElement.prototype, 'getBoundingClientRect').mockReturnValue({
    left: 0,
    top: 0,
    width: 400,
    height: 300,
  } as DOMRect)
})

const zone = () => JSON.parse(screen.getByTestId('zone').textContent) as Zone | null
const area = () => screen.getByRole('application', { name: 'Рабочая зона' })
const click = (el: Element, x: number, y: number) => {
  fireEvent.pointerDown(el, { clientX: x, clientY: y })
  fireEvent.pointerUp(el, { clientX: x, clientY: y })
}

describe('ZoneEditor', () => {
  it('places vertices and closes the contour on the first point', () => {
    render(<Harness />)
    click(area(), 40, 30)
    click(area(), 360, 30)
    expect(zone()).toBeNull()
    click(screen.getByRole('button', { name: 'Вершина 1' }), 40, 30)
    expect(zone()).toBeNull() // двух точек мало: контур не замыкается
    click(area(), 200, 270)
    click(screen.getByRole('button', { name: 'Вершина 1' }), 40, 30)
    expect(zone()).toEqual([
      [0.1, 0.1],
      [0.9, 0.1],
      [0.5, 0.9],
    ])
    expect(screen.getByRole('img', { name: 'Кадр для ориентира' })).toHaveAttribute(
      'src',
      '/frame.jpg',
    )
  })

  it('drags vertices, inserts one on an edge and deletes the selected one', () => {
    const square: Zone = [
      [0.1, 0.1],
      [0.9, 0.1],
      [0.9, 0.9],
      [0.1, 0.9],
    ]
    render(<Harness initial={square} />)
    const first = screen.getByRole('button', { name: 'Вершина 1' })
    fireEvent.pointerDown(first, { clientX: 40, clientY: 30 })
    fireEvent.pointerMove(area(), { clientX: 80, clientY: 60, buttons: 1 })
    fireEvent.pointerUp(area(), { clientX: 80, clientY: 60 })
    expect(zone()![0]).toEqual([0.2, 0.2])

    fireEvent.pointerDown(screen.getByTestId('edge-1'), { clientX: 360, clientY: 150 })
    expect(zone()).toHaveLength(5)
    expect(zone()![2]).toEqual([0.9, 0.5])
    expect(screen.getByRole('button', { name: 'Вершина 3' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )

    fireEvent.keyDown(area(), { key: 'Delete' })
    expect(zone()).toHaveLength(4)
    fireEvent.pointerDown(screen.getByRole('button', { name: 'Вершина 1' }))
    fireEvent.keyDown(area(), { key: 'Delete' })
    fireEvent.pointerDown(screen.getByRole('button', { name: 'Вершина 1' }))
    fireEvent.keyDown(area(), { key: 'Delete' })
    expect(zone()).toHaveLength(3) // меньше трёх вершин не бывает
  })

  it('removes a vertex of an open contour and clamps points to the frame', () => {
    render(<Harness />)
    click(area(), -50, 400)
    click(area(), 200, 150)
    fireEvent.pointerDown(screen.getByRole('button', { name: 'Вершина 2' }))
    fireEvent.keyDown(area(), { key: 'Backspace' })
    expect(screen.queryByRole('button', { name: 'Вершина 2' })).toBeNull()
    click(area(), 400, 0)
    click(area(), 200, 300)
    click(screen.getByRole('button', { name: 'Вершина 1' }), 0, 300)
    expect(zone()).toEqual([
      [0, 1],
      [1, 0],
      [0.5, 1],
    ])
  })

  it('ends a drag released outside the frame', () => {
    render(
      <Harness
        initial={[
          [0.1, 0.1],
          [0.9, 0.1],
          [0.5, 0.9],
        ]}
      />,
    )
    fireEvent.pointerDown(screen.getByRole('button', { name: 'Вершина 1' }), {
      clientX: 40,
      clientY: 30,
    })
    fireEvent.pointerMove(area(), { clientX: 80, clientY: 60, buttons: 1 })
    // Кнопку отпустили за пределами кадра: pointerup сюда не пришёл, движение уже без кнопки
    fireEvent.pointerMove(area(), { clientX: 200, clientY: 150, buttons: 0 })
    fireEvent.pointerMove(area(), { clientX: 300, clientY: 200, buttons: 0 })
    expect(zone()![0]).toEqual([0.2, 0.2])
  })

  it('closes the contour on a tap with a little jitter', () => {
    render(<Harness />)
    click(area(), 40, 30)
    click(area(), 360, 30)
    click(area(), 200, 270)
    const first = screen.getByRole('button', { name: 'Вершина 1' })
    fireEvent.pointerDown(first, { clientX: 40, clientY: 30 })
    fireEvent.pointerMove(area(), { clientX: 42, clientY: 31, buttons: 1 })
    fireEvent.pointerUp(first, { clientX: 42, clientY: 31 })
    expect(zone()).toEqual([
      [0.1, 0.1],
      [0.9, 0.1],
      [0.5, 0.9],
    ])
  })

  it('moves and deletes vertices from the keyboard', () => {
    render(
      <Harness
        initial={[
          [0.1, 0.1],
          [0.9, 0.1],
          [0.9, 0.9],
          [0.1, 0.9],
        ]}
      />,
    )
    const first = screen.getByRole('button', { name: 'Вершина 1' })
    first.focus()
    fireEvent.keyDown(first, { key: 'ArrowRight' })
    fireEvent.keyDown(first, { key: 'ArrowDown' })
    expect(zone()![0]).toEqual([0.11, 0.11])
    fireEvent.keyDown(first, { key: 'ArrowLeft' })
    fireEvent.keyDown(first, { key: 'ArrowUp' })
    expect(zone()![0]).toEqual([0.1, 0.1])
    fireEvent.keyDown(first, { key: 'Delete' })
    expect(zone()).toHaveLength(3)
  })

  it('reports an image that failed to load', () => {
    const onImageError = vi.fn()
    render(
      <ZoneEditor
        imageUrl="/broken.jpg"
        aspect={4 / 3}
        value={null}
        onChange={() => {}}
        onImageError={onImageError}
      />,
    )
    fireEvent.error(screen.getByRole('img', { name: 'Кадр для ориентира' }))
    expect(onImageError).toHaveBeenCalled()
  })
})
