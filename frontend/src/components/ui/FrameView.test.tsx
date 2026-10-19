import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setToken } from '@/lib/authStorage'
import { server } from '@/mocks/server'
import { FrameView } from './FrameView'

const imageUrl = '/api/sites/s/photos/p/annotated'

describe('FrameView', () => {
  it('shows a placeholder and a caption without an image', () => {
    render(<FrameView imageUrl={null} caption="IMG_0001.jpg" alt="Снимок IMG_0001" />)
    expect(screen.getByRole('img', { name: 'Снимок IMG_0001' })).toBeInTheDocument()
    expect(screen.getByText('Снимок')).toBeInTheDocument()
    expect(screen.getByText('IMG_0001.jpg').tagName).toBe('FIGCAPTION')
  })

  it('loads the server-annotated image with the auth token', async () => {
    setToken('token-1')
    let auth: string | null = null
    server.use(
      http.get(imageUrl, ({ request }) => {
        auth = request.headers.get('Authorization')
        return new HttpResponse(new Blob(['png']), { headers: { 'Content-Type': 'image/png' } })
      }),
    )
    render(<FrameView imageUrl={imageUrl} />)
    const frame = screen.getByRole('img', { name: 'Снимок' })
    await waitFor(() => expect(frame).toHaveStyle({ backgroundImage: 'url(blob:test)' }))
    expect(auth).toBe('Bearer token-1')
    expect(screen.queryByText('Снимок')).not.toBeInTheDocument()
  })

  it('keeps an empty frame when the image cannot be loaded', async () => {
    let requested = false
    server.use(
      http.get(imageUrl, () => {
        requested = true
        return new HttpResponse(null, { status: 401 })
      }),
    )
    const revoke = vi.spyOn(URL, 'revokeObjectURL')
    const { unmount } = render(<FrameView imageUrl={imageUrl} />)
    await waitFor(() => expect(requested).toBe(true))
    expect(screen.getByRole('img', { name: 'Снимок' }).style.backgroundImage).toBe('')
    unmount()
    expect(revoke).not.toHaveBeenCalled()
  })

  it('releases the image when the frame goes away', async () => {
    server.use(http.get(imageUrl, () => new HttpResponse(new Blob(['png']))))
    const revoke = vi.spyOn(URL, 'revokeObjectURL')
    const { unmount } = render(<FrameView imageUrl={imageUrl} />)
    await waitFor(() =>
      expect(screen.getByRole('img', { name: 'Снимок' })).toHaveStyle({
        backgroundImage: 'url(blob:test)',
      }),
    )
    unmount()
    expect(revoke).toHaveBeenCalledWith('blob:test')
  })

  it('без onClick кнопки нет', () => {
    render(<FrameView imageUrl={null} alt="Снимок IMG_0002" />)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('с onClick снимок открывается мышью и с клавиатуры', async () => {
    const onClick = vi.fn()
    const user = userEvent.setup()
    render(<FrameView imageUrl={null} alt="Снимок IMG_0003" onClick={onClick} />)
    const open = screen.getByRole('button', { name: 'Открыть: Снимок IMG_0003' })

    await user.click(open)
    expect(onClick).toHaveBeenCalledTimes(1)

    open.focus()
    await user.keyboard('{Enter}')
    expect(onClick).toHaveBeenCalledTimes(2)
  })
})
