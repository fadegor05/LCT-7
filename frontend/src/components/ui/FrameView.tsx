import type { ReactNode } from 'react'
import { useAuthorizedImage } from '@/api/images'
import { Icon } from './Icon'
import styles from './FrameView.module.css'

interface FrameViewProps {
  /** Снимок; рамки найденной техники уже нарисованы сервером (`/annotated`). */
  imageUrl: string | null
  caption?: ReactNode
  alt?: string
  /** Открывает снимок крупно; без него изображение не интерактивно. */
  onClick?: () => void
}

/** Снимок с подписью; без изображения — заглушка, пока снимок грузится — пустая подложка. */
export function FrameView({ imageUrl, caption, alt = 'Снимок', onClick }: FrameViewProps) {
  const src = useAuthorizedImage(imageUrl)
  const picture = (
    <span
      className={styles.img}
      role="img"
      aria-label={alt}
      style={src ? { backgroundImage: `url(${src})` } : undefined}
    >
      {!imageUrl && (
        <span className={styles.placeholder} aria-hidden="true">
          <Icon name="camera" size={20} />
          Снимок
        </span>
      )}
    </span>
  )
  return (
    <figure className={styles.frame}>
      {onClick ? (
        <button
          type="button"
          className={styles.open}
          aria-label={`Открыть: ${alt}`}
          onClick={onClick}
        >
          {picture}
        </button>
      ) : (
        picture
      )}
      {caption && <figcaption className={styles.caption}>{caption}</figcaption>}
    </figure>
  )
}
