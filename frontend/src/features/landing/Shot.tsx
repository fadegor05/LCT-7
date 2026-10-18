import { DETECTOR_THRESHOLD, type DemoBox } from './demo/p03'
import styles from './Shot.module.css'

interface ShotProps {
  src: string
  alt: string
  boxes: readonly DemoBox[]
  /** Первый экран грузим сразу, остальное лениво. */
  eager?: boolean
}

/**
 * Снимок площадки с рамками детектора поверх. Рамки заданы долями кадра и не зависят от размера.
 * Уверенная находка в сплошной рамке, неуверенная (ниже порога, в вывод не идёт) пунктиром.
 */
export function Shot({ src, alt, boxes, eager = false }: ShotProps) {
  return (
    <div className={styles.shot}>
      <img src={src} alt={alt} loading={eager ? 'eager' : 'lazy'} width="960" />
      {boxes.map((b) => (
        <span
          key={`${b.label}-${b.box.join()}`}
          className={b.conf < DETECTOR_THRESHOLD ? `${styles.box} ${styles.unsure}` : styles.box}
          style={{
            left: `${b.box[0] * 100}%`,
            top: `${b.box[1] * 100}%`,
            width: `${(b.box[2] - b.box[0]) * 100}%`,
            height: `${(b.box[3] - b.box[1]) * 100}%`,
          }}
        >
          {/* узкая рамка обрезает подпись, полная остаётся в подсказке */}
          <i title={`${b.label} ${b.conf.toFixed(2)}`}>
            {b.label} {b.conf.toFixed(2)}
          </i>
        </span>
      ))}
    </div>
  )
}
