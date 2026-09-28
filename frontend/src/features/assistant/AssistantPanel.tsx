import { useEffect, useRef } from 'react'
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

/**
 * Панель ассистента на экране обзора площадки: форма вопроса, статус загрузки,
 * ответ с проверкой и ссылками, обработка ошибок и повтор.
 */
export function AssistantPanel({ siteId }: AssistantPanelProps) {
  const status = useAssistantStatus()
  const { ask, cancel, isPending, answer, failure } = useAskAssistant(siteId)
  const lastQuestionRef = useRef<string>('')
  const answerContainerRef = useRef<HTMLDivElement>(null)

  // Фокусируем контейнер ответа когда он появляется
  useEffect(() => {
    if (answer && answerContainerRef.current) {
      answerContainerRef.current.focus()
    }
  }, [answer])

  // Если ассистент недоступен, не показываем ничего
  if (!status.enabled) {
    return null
  }

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

        {failure && failure.kind !== 'cancelled' && failure.kind !== 'invalid_question' && (
          <>
            {failure.kind === 'timeout' && (
              <Callout tone="caution" title="Модель не ответила">
                {failure.message}
                {failure.retryable && (
                  <div style={{ marginTop: 'var(--space-3)' }}>
                    <Button onClick={handleRetry}>Повторить</Button>
                  </div>
                )}
              </Callout>
            )}

            {(failure.kind === 'rate_limited' ||
              failure.kind === 'out_of_scope' ||
              failure.kind === 'too_large' ||
              failure.kind === 'not_found' ||
              failure.kind === 'bad_request' ||
              failure.kind === 'unknown') && (
              <Callout tone="caution" title={getFailureTitle(failure.kind)}>
                {failure.message}
              </Callout>
            )}
          </>
        )}
      </div>
    </section>
  )
}

function getFailureTitle(kind: string): string {
  switch (kind) {
    case 'rate_limited':
      return 'Слишком часто'
    case 'out_of_scope':
      return 'Вопрос не по теме отчёта'
    case 'too_large':
      return 'Отчёт слишком велик'
    case 'not_found':
      return 'Данных для ответа нет'
    case 'bad_request':
      return 'Площадки нет в отчёта'
    case 'unknown':
      return 'Не удалось получить ответ'
    default:
      return 'Ошибка'
  }
}
