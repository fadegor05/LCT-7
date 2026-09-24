import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { Link, type LinkProps } from 'react-router'
import { Icon, type IconName } from './Icon'
import styles from './Button.module.css'

export type ButtonVariant = 'primary' | 'secondary' | 'ghost'
export type ButtonSize = 'sm' | 'md' | 'lg' | 'icon'

interface StyleProps {
  variant?: ButtonVariant
  size?: ButtonSize
  icon?: IconName
  children?: ReactNode
}

function classes(variant: ButtonVariant, size: ButtonSize, extra?: string) {
  return [styles.btn, styles[variant], size !== 'md' && styles[size], extra]
    .filter(Boolean)
    .join(' ')
}

type ButtonProps = StyleProps & ButtonHTMLAttributes<HTMLButtonElement>

export function Button({
  variant = 'primary',
  size = 'md',
  icon,
  className,
  children,
  type = 'button',
  ...rest
}: ButtonProps) {
  return (
    <button type={type} className={classes(variant, size, className)} {...rest}>
      {icon && <Icon name={icon} />}
      {children}
    </button>
  )
}

type ButtonLinkProps = StyleProps & LinkProps

/** Ссылка, оформленная как кнопка (переходы «Далее», «Новая стройка»). */
export function ButtonLink({
  variant = 'primary',
  size = 'md',
  icon,
  className,
  children,
  ...rest
}: ButtonLinkProps) {
  return (
    <Link className={classes(variant, size, className)} {...rest}>
      {icon && <Icon name={icon} />}
      {children}
    </Link>
  )
}
