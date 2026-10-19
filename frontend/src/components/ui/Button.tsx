import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { Link, type LinkProps } from 'react-router'
import { buttonClassName as classes, type ButtonSize, type ButtonVariant } from './buttonClass'
import { Icon, type IconName } from './Icon'

export type { ButtonSize, ButtonVariant } from './buttonClass'

interface StyleProps {
  variant?: ButtonVariant
  size?: ButtonSize
  icon?: IconName
  children?: ReactNode
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
