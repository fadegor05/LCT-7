import type { ReactNode } from 'react'
import { Pill } from '@/components/ui/Pill'
import { DEMO_FINDINGS } from './demo/p03'
import { SNAPSHOTS } from './demo/timeline'
import { Shot } from './Shot'
import styles from './Visuals.module.css'

const FOLDERS = ['backend/', 'frontend/', 'ml/', 'deploy/', 'docs/']

/** «Открытый код»: окно редактора с шапкой лицензии и папками репозитория. */
export function CodeArt() {
  return (
    <div
      className={`${styles.win} ${styles.dark}`}
      role="img"
      aria-label="Окно редактора: лицензия AGPL-3.0 и папки репозитория backend, frontend, ml, deploy, docs"
    >
      <div className={styles.bar} aria-hidden="true">
        <i />
        <i />
        <i />
        <span>LCT-7 / LICENSE</span>
      </div>
      <pre aria-hidden="true">
        <b>GNU AFFERO GENERAL PUBLIC LICENSE</b>
        {'\n'}
        <span>Version 3, 19 November 2007</span>
        {'\n\n'}
        {FOLDERS.map((f) => (
          <em key={f}>{f}</em>
        ))}
      </pre>
    </div>
  )
}

/** «Запуск у вас»: две команды и четыре поднятых сервиса. */
export function RunArt() {
  return (
    <div
      className={`${styles.win} ${styles.dark}`}
      role="img"
      aria-label="Терминал: команды cp .env.dist .env и make deploy-tunnel, сервисы запущены"
    >
      <div className={styles.bar} aria-hidden="true">
        <i />
        <i />
        <i />
        <span>terminal</span>
      </div>
      <pre aria-hidden="true">
        <span>$ cp .env.dist .env</span>
        {'\n'}
        <span>$ make deploy-tunnel</span>
        {'\n\n'}
        <em>✔ postgres</em>
        <em>✔ ml</em>
        {'\n'}
        <em>✔ backend</em>
        <em>✔ frontend</em>
      </pre>
    </div>
  )
}

/** «Без видеокарты»: окно в том же стиле, что соседние, со временем обработки кадра. */
export function CpuArt() {
  return (
    <div
      className={`${styles.win} ${styles.dark}`}
      role="img"
      aria-label="Окно терминала: 364 миллисекунды на кадр на процессоре ноутбука, видеокарта не нужна"
    >
      <div className={styles.bar} aria-hidden="true">
        <i />
        <i />
        <i />
        <span>detector</span>
      </div>
      <pre aria-hidden="true">
        <span>устройство</span>
        <b>процессор ноутбука</b>
        {'\n'}
        <span>на кадр</span>
        <b>364 мс</b>
        {'\n'}
        <span>видеокарта</span>
        <em>не нужна</em>
      </pre>
    </div>
  )
}

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
      <code>$ make deploy-tunnel</code>
      <span>Детектор на процессоре: 364 мс на кадр.</span>
    </RoleShot>
  )
}
