import type { ReactNode } from 'react'
import { Pill } from '@/components/ui/Pill'
import { DEMO_FINDINGS } from './demo/p03'
import { SNAPSHOTS } from './demo/timeline'
import { Shot } from './Shot'
import styles from './Visuals.module.css'

interface RoleShotProps {
  children: ReactNode
  photo: ReactNode
}

/** Фото роли с подсказкой из продукта поверх: картинка связана с тем, что видит человек в сервисе. */
function RoleShot({ photo, children }: RoleShotProps) {
  return (
    <div className={styles.role}>
      {photo}
      <div className={styles.glass}>{children}</div>
    </div>
  )
}

export function InspectorShot() {
  return (
    <RoleShot
      photo={
        <img
          src="/landing/p03/aud-1.jpg"
          alt="Площадка 16 июля: буровые установки и жилой дом рядом"
          loading="lazy"
          width="960"
        />
      }
    >
      <b>Отклонения по стройкам</b>
      <ul>
        {DEMO_FINDINGS.map((f) => (
          <li key={f.id}>
            <Pill tone={f.hypothesis ? 'caution' : 'behind'} icon="alert" size="sm">
              {f.severity}
            </Pill>
          </li>
        ))}
      </ul>
    </RoleShot>
  )
}

export function SupervisorShot() {
  const snap = SNAPSHOTS[1]!
  return (
    <RoleShot photo={<Shot src={snap.src} alt={snap.alt} boxes={snap.boxes} />}>
      <b>Для разговора с подрядчиком</b>
      <span>Этап должен был закончиться 31.07, на кадре от 14.08 работают буровые.</span>
    </RoleShot>
  )
}

export function ItShot() {
  return (
    <RoleShot
      photo={
        <img
          src="/landing/p03/aud-3.jpg"
          alt="Площадка 14 сентября: фура у бытовок и башенный кран"
          loading="lazy"
          width="960"
        />
      }
    >
      <code>$ make deploy</code>
      <span>Распознавание на обычном процессоре, около 0,4 с на снимок.</span>
    </RoleShot>
  )
}
