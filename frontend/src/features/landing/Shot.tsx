import type { DemoBox } from './demo/p03'
import styles from './Shot.module.css'

interface ShotProps {
  src: string
  alt: string
  boxes: readonly DemoBox[]
  /** Первый экран грузим сразу, остальное лениво. */
  eager?: boolean
}

/** Снимок площадки с рамками детектора поверх. Рамки заданы долями кадра и не зависят от размера. */
export function Shot({ src, alt, boxes, eager = false }: ShotProps) {
  return (
    <div className={styles.shot}>
      <img src={src} alt={alt} loading={eager ? 'eager' : 'lazy'} width="960" />
      {boxes.map((b) => (
        <span
          key={`${b.label}-${b.box.join()}`}
          className={styles.box}
          style={{
            left: `${b.box[0] * 100}%`,
            top: `${b.box[1] * 100}%`,
            width: `${(b.box[2] - b.box[0]) * 100}%`,
            height: `${(b.box[3] - b.box[1]) * 100}%`,
          }}
        >
          <i>
            {b.label} {b.conf.toFixed(2)}
          </i>
        </span>
      ))}
    </div>
  )
}
