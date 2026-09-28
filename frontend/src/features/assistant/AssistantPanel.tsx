import { useEffect, useRef } from 'react'
import type { AssistantFailureKind } from '@/api/assistant'
import { useAskAssistant, useAssistantStatus } from '@/api/assistant'
import { Button } from '@/components/ui/Button'
import { Callout } from '@/components/ui/Callout'
import { SectionHeader } from '@/components/layout/PageHeader'
import { AssistantAnswerView } from './AssistantAnswer'
import { AssistantQuestionForm } from './AssistantQuestionForm'
import styles from './AssistantPanel.module.css'

interface AssistantPanelProps {
  siteId: string
}

const FAILURE_TITLES: Partial<Record<AssistantFailureKind, string>> = {
  timeout: 'Модель не ответила',
  rate_limited: 'Слишком часто',
  out_of_scope: 'Вопрос не по теме отчёта',
  too_large: 'Отчёт слишком велик',
  not_found: 'Данных для ответа нет',
  bad_request: 'Площадки нет в отчёте',
  unknown: 'Не удалось получить ответ',
}

function shouldRenderFailure(
  failure: ReturnType<typeof useAskAssistant>['failure'],
): failure is Exclude<typeof failure, undefined | null> & {
  kind: Exclude<AssistantFailureKind, 'cancelled' | 'invalid_question' | 'unavailable'>
} {
  return (
    failure !== undefined &&
    failure.kind !== 'cancelled' &&
    failure.kind !== 'invalid_question' &&
    failure.kind !== 'unavailable'
  )
}

/**
 * Панель ассистента на экране обзора площадки: контролирует видимость по статусу.
 * Вложенный компонент AssistantSection отвечает за форму, ответ и обработку ошибок.
 */
export function AssistantPanel({ siteId }: AssistantPanelProps) {
  const status = useAssistantStatus()

  // Показываем раздел только если ассистент включён
  if (!status.enabled) {
    return null
  }

  return <AssistantSection siteId={siteId} />
}

function AssistantSection({ siteId }: AssistantPanelProps) {
  const { ask, cancel, isPending, answer, failure } = useAskAssistant(siteId)
  const lastQuestionRef = useRef<string>('')
  const answerContainerRef = useRef<HTMLDivElement>(null)

  // Фокусируем контейнер ответа когда он появляется
  useEffect(() => {
    if (answer && answerContainerRef.current) {
      answerContainerRef.current.focus()
    }
  }, [answer])

  // Если ассистент недоступен на этапе загрузки вопроса, скрыть весь раздел
  if (failure?.kind === 'unavailable') {
    return null
  }

  const handleSubmit = (question: string) => {
    lastQuestionRef.current = question
    void ask(question)
  }

  const handleRetry = () => {
    if (lastQuestionRef.current) {
      void ask(lastQuestionRef.current)
    }
  }

  const handleCancel = () => {
    cancel()
  }

  // Определяем текст ошибки для поля формы
  const fieldError = failure?.kind === 'invalid_question' ? failure.message : undefined

  // Определяем, показывать ли ошибку в блоке
  const canRenderFailure = shouldRenderFailure(failure)
  const failureTitle = canRenderFailure ? FAILURE_TITLES[failure.kind] : undefined

  return (
    <section className={styles.section} aria-label="Ассистент по отчёту">
      <SectionHeader
        title="Ассистент по отчёту"
        description="Ассистент пересказывает отчёт по запросу — это может помочь найти нужную информацию быстрее. Источник истины — сам отчёт, ответ лишь пересказывает его."
      />

      <AssistantQuestionForm
        pending={isPending}
        error={fieldError}
        onSubmit={handleSubmit}
        onCancel={handleCancel}
      />

      {isPending && <p role="status">Ассистент отвечает. Это может занять до двух минут.</p>}

      <div aria-live="polite">
        {answer && <AssistantAnswerView answer={answer} containerRef={answerContainerRef} />}

        {canRenderFailure && failureTitle && (
          <Callout tone="caution" title={failureTitle}>
            {failure.message}
            {failure.retryable && (
              <div style={{ marginTop: 'var(--space-3)' }}>
                <Button onClick={handleRetry}>Повторить</Button>
              </div>
            )}
          </Callout>
        )}
      </div>
    </section>
  )
}
