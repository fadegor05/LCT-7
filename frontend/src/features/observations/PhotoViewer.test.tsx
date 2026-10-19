import { fireEvent, screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { setToken } from '@/lib/authStorage'
import { formatDate } from '@/lib/format'
import type { Photo } from '@/api/schemas'
import { server } from '@/mocks/server'
import { renderWithProviders } from '@/test/render'
import { PhotoViewer } from './PhotoViewer'

// Снимок ph-1 из моков Березников: две рамки (экскаватор и самосвал), оба по 82%.
const photo: Photo = {
  id: 'ph-1',
  site_id: 'site-berezniki',
  original_name: 'IMG_0001.jpg',
  width: 1920,
  height: 1080,
  captured_on: '2026-09-14',
  date_source: 'metadata',
  processing_status: 'done',
  uploaded_at: '2026-09-18T11:00:00Z',
}

const renderViewer = (onClose = vi.fn()) =>
  renderWithProviders(<PhotoViewer siteId="site-berezniki" photo={photo} onClose={onClose} />, {
    path: '/viewer',
    url: '/viewer',
  })

/** Слой с изображением и рамками: его transform меняется при зуме. */
async function zoomLayer() {
  const image = await screen.findByRole('img', { name: 'Снимок IMG_0001.jpg' })
  return image.parentElement as HTMLElement
}

describe('PhotoViewer', () => {
  beforeEach(() => setToken('mock-token'))

  it('показывает диалог с названием и датой, снимок и рамки техники', async () => {
    renderViewer()

    const dialog = screen.getByRole('dialog', {
      name: `IMG_0001.jpg · ${formatDate('2026-09-14')}`,
    })
    expect(
      await within(dialog).findByRole('img', { name: 'Снимок IMG_0001.jpg' }),
    ).toBeInTheDocument()
    expect(await screen.findByLabelText('Гусеничный экскаватор, 82%')).toBeInTheDocument()
    expect(screen.getByLabelText('Самосвал, 82%')).toBeInTheDocument()
  })

  it('кнопка «Увеличить» меняет масштаб слоя, «Сбросить масштаб» возвращает 1', async () => {
    const { user } = renderViewer()
    const layer = await zoomLayer()
    const reset = screen.getByRole('button', { name: 'Сбросить масштаб' })
    expect(reset).toBeDisabled()

    await user.click(screen.getByRole('button', { name: 'Увеличить' }))
    expect(layer.style.transform).toContain('scale(1.5)')
    expect(layer.style.getPropertyValue('--zoom')).toBe('1.5')
    expect(reset).toBeEnabled()

    await user.click(reset)
    expect(layer.style.transform).toContain('scale(1)')
    expect(reset).toBeDisabled()
  })

  it('«Уменьшить» не опускает масштаб ниже 1', async () => {
    const { user } = renderViewer()
    const layer = await zoomLayer()

    await user.click(screen.getByRole('button', { name: 'Уменьшить' }))
    expect(layer.style.transform).toContain('scale(1)')
  })

  it('наведение на рамку показывает подпись с названием и уверенностью', async () => {
    const { user } = renderViewer()

    await user.hover(await screen.findByLabelText('Самосвал, 82%'))

    expect(screen.getByText('Самосвал · 82%')).toBeInTheDocument()
  })

  it('колесо мыши не прокручивает страницу', async () => {
    renderViewer()
    const layer = await zoomLayer()

    const notCancelled = fireEvent.wheel(layer.parentElement as HTMLElement, { deltaY: -100 })

    expect(notCancelled).toBe(false)
  })

  it('показывает ошибку, если рамки не загрузились, а снимок остаётся', async () => {
    server.use(
      http.get('/api/sites/:siteId/photos/:photoId', () =>
        HttpResponse.json({ detail: 'Сбой' }, { status: 500 }),
      ),
    )
    renderViewer()

    expect(await screen.findByText('Не удалось загрузить рамки')).toBeInTheDocument()
    expect(await screen.findByRole('img', { name: 'Снимок IMG_0001.jpg' })).toBeInTheDocument()
  })

  it('Escape закрывает диалог', async () => {
    const onClose = vi.fn()
    const { user } = renderViewer(onClose)
    await screen.findByRole('img', { name: 'Снимок IMG_0001.jpg' })

    await user.keyboard('{Escape}')

    expect(onClose).toHaveBeenCalled()
  })
})
