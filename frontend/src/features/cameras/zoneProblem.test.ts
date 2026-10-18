import { zoneProblem } from './zoneProblem'

test('checks a zone like the backend', () => {
  expect(
    zoneProblem([
      [0, 0],
      [1, 0],
      [0, 1],
    ]),
  ).toBeNull()
  expect(
    zoneProblem([
      [0, 0],
      [1, 0],
    ]),
  ).toBe('Зона — от 3 до 100 вершин')
  const many = Array.from({ length: 101 }, (_, i) => [Math.cos(i), Math.sin(i)] as [number, number])
  expect(zoneProblem(many)).toBe('Зона — от 3 до 100 вершин')
  expect(
    zoneProblem([
      [0.1, 0.1],
      [0.5, 0.1],
      [0.9, 0.1001],
    ]),
  ).toBe('Вершины зоны лежат почти на одной линии')
})
