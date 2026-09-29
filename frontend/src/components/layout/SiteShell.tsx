import type { ReactNode } from 'react'
import { NavLink } from 'react-router'
import type { Site } from '@/api/schemas'
import { Breadcrumbs, type Crumb } from '@/components/ui/Breadcrumbs'
import { PageHeader } from './PageHeader'
import styles from './SiteShell.module.css'

interface SiteShellProps {
  site: Site
  /** Последняя крошка («Методика», «Нет нужной техники»); без неё текущая — сама стройка. */
  crumb?: string
  title?: ReactNode
  subtitle?: ReactNode
  actions?: ReactNode
  /** Колонка справа от содержимого (чат ассистента); на узком экране уходит под него. */
  aside?: ReactNode
  children: ReactNode
}

const TABS = [
  { to: '', label: 'Обзор', end: true },
  { to: 'observations', label: 'Наблюдения' },
  { to: 'methodology', label: 'Методика' },
]

/**
 * Каркас экранов объекта: крошки, заголовок и вкладки «Обзор · Наблюдения · Методика».
 * С `aside` содержимое делится на две колонки: основная слева, `aside` — прилипает справа.
 */
export function SiteShell({
  site,
  crumb,
  title,
  subtitle,
  actions,
  aside,
  children,
}: SiteShellProps) {
  const base = `/sites/${site.id}`
  const crumbs: Crumb[] = [{ label: 'Стройки', to: '/sites' }]
  crumbs.push(crumb ? { label: site.name, to: base } : { label: site.name })
  if (crumb) crumbs.push({ label: crumb })

  return (
    <>
      <Breadcrumbs items={crumbs} />
      <PageHeader title={title ?? site.name} subtitle={subtitle} actions={actions} />
      <nav className={styles.tabs} aria-label="Разделы объекта">
        {TABS.map((tab) => (
          <NavLink
            key={tab.label}
            to={tab.to ? `${base}/${tab.to}` : base}
            end={tab.end}
            className={styles.tab}
          >
            {tab.label}
          </NavLink>
        ))}
      </nav>
      {aside ? (
        <div className={styles.withAside} data-layout="with-aside">
          <div className={styles.main}>{children}</div>
          <aside className={styles.aside}>{aside}</aside>
        </div>
      ) : (
        children
      )}
    </>
  )
}
