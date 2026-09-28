import type { ParseMode } from '@/api/schemas'
import { Segmented, type SegmentedOption } from '@/components/ui/Segmented'
import styles from './NewSite.module.css'
import { PARSE_MODE_HINTS } from './parseModeHints'

const OPTIONS: readonly SegmentedOption<ParseMode>[] = [
  { value: 'auto', label: 'Авто' },
  { value: 'builtin', label: 'Встроенный' },
  { value: 'llm', label: 'LLM' },
]

interface ParseModeSwitchProps {
  value: ParseMode
  onChange: (mode: ParseMode) => void
  disabled?: boolean
}

/** Выбор режима разбора графика: авто / встроенный / LLM, с пояснением выбранного. */
export function ParseModeSwitch({ value, onChange, disabled }: ParseModeSwitchProps) {
  return (
    <div className={styles.parseMode}>
      <span className="sm muted">Режим разбора файла</span>
      <Segmented
        label="Режим разбора файла"
        options={OPTIONS}
        value={value}
        onChange={onChange}
        disabled={disabled}
      />
      <p className="sm muted" data-testid="parse-mode-hint">
        {PARSE_MODE_HINTS[value]}
      </p>
    </div>
  )
}
