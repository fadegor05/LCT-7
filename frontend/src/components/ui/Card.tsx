import type { HTMLAttributes, ReactNode } from 'react'
import styles from './Card.module.css'

interface CardProps extends HTMLAttributes<HTMLElement> {
  as?: 'section' | 'div' | 'aside' | 'article'
  muted?: boolean
  children: ReactNode
}

export function Card({ as: Tag = 'section', muted, className, children, ...rest }: CardProps) {
  return (
    <Tag
      className={[styles.card, muted && styles.muted, className].filter(Boolean).join(' ')}
      {...rest}
    >
      {children}
    </Tag>
  )
}
