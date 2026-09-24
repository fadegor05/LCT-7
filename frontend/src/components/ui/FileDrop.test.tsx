import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { FileDrop } from './FileDrop'

const file = new File(['a;b'], 'grafik.csv', { type: 'text/csv' })

describe('FileDrop', () => {
  it('passes chosen files', async () => {
    const onFiles = vi.fn()
    render(<FileDrop title="Перетащите файл" hint="CSV" onFiles={onFiles} />)
    await userEvent.upload(screen.getByLabelText('Выбрать файл'), file)
    expect(onFiles).toHaveBeenCalledWith([file])
  })

  it('opens the picker from the button', async () => {
    render(<FileDrop title="t" hint="h" onFiles={vi.fn()} />)
    const input = screen.getByLabelText<HTMLInputElement>('Выбрать файл')
    const click = vi.spyOn(input, 'click')
    await userEvent.click(screen.getByRole('button', { name: 'Выбрать файл' }))
    expect(click).toHaveBeenCalled()
  })

  it('accepts dropped files and highlights on drag', () => {
    const onFiles = vi.fn()
    render(<FileDrop title="t" hint="h" onFiles={onFiles} />)
    const zone = screen.getByTestId('file-drop')
    fireEvent.dragOver(zone)
    expect(zone.className).toMatch(/active/)
    fireEvent.dragLeave(zone)
    expect(zone.className).not.toMatch(/active/)
    fireEvent.drop(zone, { dataTransfer: { files: [file] } })
    expect(onFiles).toHaveBeenCalledWith([file])
  })

  it('ignores drops when disabled and empty selections', () => {
    const onFiles = vi.fn()
    render(<FileDrop title="t" hint="h" onFiles={onFiles} disabled />)
    fireEvent.drop(screen.getByTestId('file-drop'), { dataTransfer: { files: [file] } })
    fireEvent.change(screen.getByLabelText('Выбрать файл'), { target: { files: [] } })
    expect(onFiles).not.toHaveBeenCalled()
  })
})
