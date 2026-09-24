import type { Severity } from '@/api/schemas'
import { Pill } from '@/components/ui/Pill'
import { severityLabels } from '@/lib/labels'

export function SeverityBadge({ severity }: { severity: Severity }) {
  return severity === 'critical' ? (
    <Pill tone="behind" icon="alert">
      {severityLabels.critical}
    </Pill>
  ) : (
    <Pill tone="caution" icon="info">
      {severityLabels.attention}
    </Pill>
  )
}
