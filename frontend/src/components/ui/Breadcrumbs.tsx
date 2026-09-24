import { Fragment } from 'react'
import { Link } from 'react-router'
import styles from './Breadcrumbs.module.css'

export interface Crumb {
  label: string
  to?: string
}

export function Breadcrumbs({ items }: { items: readonly Crumb[] }) {
  return (
    <nav aria-label="Хлебные крошки" className={styles.crumbs}>
      {items.map((item, index) => (
        <Fragment key={`${item.label}-${index}`}>
          {index > 0 && (
            <span aria-hidden="true" className={styles.sep}>
              /
            </span>
          )}
          {item.to ? (
            <Link to={item.to}>{item.label}</Link>
          ) : (
            <span className={styles.current} aria-current="page">
              {item.label}
            </span>
          )}
        </Fragment>
      ))}
    </nav>
  )
}
