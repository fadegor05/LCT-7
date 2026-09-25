/** Знак «Веха» (вариант B — «Засечка»): основание, две засечки и акцентная веха. Сетка 120. */
export function Logo({ size = 28, className }: { size?: number; className?: string }) {
  return (
    <svg
      viewBox="0 0 120 120"
      width={size}
      height={size}
      className={className}
      fill="currentColor"
      aria-hidden="true"
    >
      <rect x="6" y="74" width="108" height="9" />
      <rect x="26" y="50" width="9" height="24" />
      <rect x="55" y="22" width="10" height="52" fill="var(--accent)" />
      <rect x="85" y="50" width="9" height="24" />
    </svg>
  )
}
