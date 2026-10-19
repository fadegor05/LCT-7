import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { Photo } from '@/api/schemas'
import { renderWithProviders } from '@/test/render'
import { byShotTime } from './photoOrder'
import { PhotoStrip } from './PhotoStrip'

const base: Photo = {
  id: 'p',
  site_id: 's',
  original_name: 'x.jpg',
  width: 2592,
  height: 1944,
  captured_on: '2026-08-03',
  date_source: 'stamp',
  processing_status: 'done',
  uploaded_at: '2026-08-03T12:00:00Z',
}

const late = {
  ...base,
  id: 'late',
  original_name: '202608031000.jpg',
  captured_at: '2026-08-03T10:00:00',
  machines: ['Автокран', 'Самосвал'],
  out_of_zone: true,
  evidence: true,
}
const early = { ...base, id: 'early', captured_at: '2026-08-03T08:00:02', machines: [] }

const renderStrip = (withDate = false) =>
  renderWithProviders(
    <PhotoStrip
      siteId="s"
      photos={[late, early]}
      withDate={withDate}
      zone={[
        [0, 0],
        [1, 0],
        [1, 1],
      ]}
      title={<h3>Север</h3>}
    />,
    { path: '/strip', url: '/strip' },
  )

describe('PhotoStrip', () => {
  it('orders frames by shot time and captions them like clean-mvp', () => {
    renderStrip()
    const figures = within(screen.getByTestId('strip')).getAllByRole('figure')
    // Слева направо по времени съёмки, а не по порядку загрузки
    expect(figures[0]).toHaveTextContent('08:00')
    expect(figures[0]).toHaveTextContent('нет техники')
    expect(figures[1]).toHaveTextContent('10:00')
    // Подпись — время и техника, а не имя файла
    expect(figures[1]).toHaveTextContent('Автокран, самосвал')
    expect(figures[1]).not.toHaveTextContent('202608031000.jpg')
    expect(within(figures[1]!).getByText('Вне зоны')).toBeInTheDocument()
    expect(within(figures[1]!).getByText('Доказательство')).toBeInTheDocument()
    expect(within(figures[0]!).queryByText('Доказательство')).toBeNull()
    // Контур зоны камеры поверх каждой миниатюры
    expect(screen.getAllByRole('img', { name: 'Рабочая зона камеры' })).toHaveLength(2)
  })

  it('shows the day in the all-days mode and scrolls with the arrows', async () => {
    renderStrip(true)
    expect(screen.getByText('ПН 03.08 10:00')).toBeInTheDocument()
    const strip = screen.getByTestId('strip')
    const scrollBy = vi.fn<(options?: ScrollToOptions) => void>()
    strip.scrollBy = scrollBy as typeof strip.scrollBy
    await userEvent.click(screen.getByRole('button', { name: 'Вперёд по времени' }))
    await userEvent.click(screen.getByRole('button', { name: 'Назад по времени' }))
    expect(scrollBy.mock.calls.map(([arg]) => Math.sign(arg?.left ?? 0))).toEqual([1, -1])
    expect(screen.getByRole('heading', { name: 'Север' })).toBeInTheDocument()
  })

  it('puts frames without time at the start of their day', () => {
    const undated = { ...base, id: 'u', captured_at: null }
    expect([late, undated].sort(byShotTime).map((p) => p.id)).toEqual(['u', 'late'])
  })
})
