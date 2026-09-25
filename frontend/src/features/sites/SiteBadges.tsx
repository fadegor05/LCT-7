import type { Level, SiteSummary } from '@/api/schemas'
import { Pill } from '@/components/ui/Pill'
import { levelLabels } from '@/lib/labels'
import { verdictText } from './verdict'

export function VerdictBadge({ summary }: { summary: SiteSummary | undefined }) {
  if (!summary || summary.verdict === 'insufficient_data') {
    return <Pill tone="dashed">Недостаточно данных</Pill>
  }
  return summary.verdict === 'behind' ? (
    <Pill tone="behind" icon="alert">
      {verdictText(summary)}
    </Pill>
  ) : (
    <Pill tone="ontrack" icon="check">
      {verdictText(summary)}
    </Pill>
  )
}

export function ObservabilityBadge({ level }: { level: Level }) {
  if (level === 'high') {
    return (
      <Pill tone="ontrack" icon="check">
        {levelLabels.high}
      </Pill>
    )
  }
  return (
    <Pill tone="caution" icon="alert">
      {levelLabels[level]}
    </Pill>
  )
}
