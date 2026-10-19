import type { ReactNode } from 'react'

/** Иконки дизайн-системы: сетка 24px, обводка 1.75, currentColor. */
const ICONS = {
  check: <path d="M5 12.5l4.5 4.5L19 7.5" />,
  up: (
    <>
      <path d="M12 19V5" />
      <path d="M6 11l6-6 6 6" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7.5V12l3 2" />
    </>
  ),
  circle: <circle cx="12" cy="12" r="8" />,
  dashed: <circle cx="12" cy="12" r="8" strokeDasharray="3 3.3" />,
  minus: <path d="M6 12h12" />,
  alert: (
    <>
      <path d="M12 4.5l8.5 15H3.5z" />
      <path d="M12 10v4" />
      <path d="M12 16.8h.01" />
    </>
  ),
  info: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 11.5v4.5" />
      <path d="M12 8.2h.01" />
    </>
  ),
  camera: (
    <>
      <path d="M4 8.5h3L8.5 6h7L17 8.5h3V19H4z" />
      <circle cx="12" cy="13.5" r="3" />
    </>
  ),
  pencil: (
    <>
      <path d="M5 19l1-4L16 5l3 3L9 18z" />
      <path d="M14 7l3 3" />
    </>
  ),
  plus: (
    <>
      <path d="M12 5v14" />
      <path d="M5 12h14" />
    </>
  ),
  close: (
    <>
      <path d="M6 6l12 12" />
      <path d="M18 6L6 18" />
    </>
  ),
  chevronRight: <path d="M9 6l6 6-6 6" />,
  chevronLeft: <path d="M15 6l-6 6 6 6" />,
  truck: (
    <>
      <path d="M2.5 16V7h10v9" />
      <path d="M12.5 10h4l3 3v3h-7" />
      <circle cx="7" cy="17.5" r="1.6" />
      <circle cx="16.5" cy="17.5" r="1.6" />
    </>
  ),
  bell: (
    <>
      <path d="M18 15V10a6 6 0 10-12 0v5l-2 3h16l-2-3z" />
      <path d="M10 21h4" />
    </>
  ),
  upload: (
    <>
      <path d="M12 16V4" />
      <path d="M7 9l5-5 5 5" />
      <path d="M4 16v4h16v-4" />
    </>
  ),
} satisfies Record<string, ReactNode>

export type IconName = keyof typeof ICONS

interface IconProps {
  name: IconName
  size?: number
  className?: string
}

export function Icon({ name, size = 20, className }: IconProps) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      data-icon={name}
      style={{ flex: 'none' }}
    >
      {ICONS[name]}
    </svg>
  )
}
