import styles from './Button.module.css'

export type ButtonVariant = 'primary' | 'secondary' | 'ghost'
export type ButtonSize = 'sm' | 'md' | 'lg' | 'icon'

/**
 * Классы кнопки дизайн-системы. Нужны и там, где `Button`/`ButtonLink` не подходят: обычная ссылка
 * `<a>` на якорь страницы или `mailto:` выглядит как кнопка и ведёт себя при наведении так же.
 */
export function buttonClassName(
  variant: ButtonVariant = 'primary',
  size: ButtonSize = 'md',
  extra?: string,
): string {
  return [styles.btn, styles[variant], size !== 'md' && styles[size], extra]
    .filter(Boolean)
    .join(' ')
}
