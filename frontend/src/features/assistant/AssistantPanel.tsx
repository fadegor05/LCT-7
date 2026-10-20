import { useEffect, useRef, useState } from 'react'
import type { AssistantFailureKind } from '@/api/assistant'
import { useAskAssistant, useAssistantStatus } from '@/api/assistant'
import { Button } from '@/components/ui/Button'
import { Callout } from '@/components/ui/Callout'
import { Dialog } from '@/components/ui/Dialog'
import { SectionHeader } from '@/components/layout/PageHeader'
import { AssistantAnswerView } from './AssistantAnswer'
import { AssistantQuestionForm } from './AssistantQuestionForm'
import { useChatHistory, type ChatMessage } from './chatHistory'
import styles from './AssistantPanel.module.css'

interface AssistantPanelProps {
  siteId: string
}

const FAILURE_TITLES: Record<AssistantFailureKind, string> = {
  timeout: 'Модель не ответила',
  rate_limited: 'Слишком часто',
  out_of_scope: 'Вопрос не по теме отчёта',
  too_large: 'Отчёт слишком велик',
  not_found: 'Данных для ответа нет',
  bad_request: 'Площадки нет в отчёте',
  invalid_question: 'Вопрос не принят',
  unavailable: 'Ассистент недоступен',
  cancelled: 'Вопрос отменён',
  unknown: 'Не удалось получить ответ',
}

const timeFormat = new Intl.DateTimeFormat('ru-RU', { hour: '2-digit', minute: '2-digit' })

function formatTime(iso: string): string {
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? '' : timeFormat.format(date)
}

/**
 * Чат с ассистентом по отчёту: колонка справа на экране обзора площадки. Без языковой модели
 * колонка та же, но спросить нельзя — видно, что ассистент есть и почему он молчит.
 * Переписка хранится в localStorage по стройке.
 */
export function AssistantPanel({ siteId }: AssistantPanelProps) {
  const status = useAssistantStatus()
  // Пока статус в пути — пустой блок, а не ничего: колонка справа сразу занимает своё место,
  // и обзор не сужается рывком, когда чат появится (как в clean-mvp)
  if (status.isPending) return <div aria-hidden="true" />
  return <AssistantChat siteId={siteId} disabled={!status.enabled} />
}

function AssistantChat({ siteId, disabled }: AssistantPanelProps & { disabled: boolean }) {
  const { send, cancel, isPending } = useAskAssistant(siteId)
  const { messages, append, remove, clear } = useChatHistory(siteId)
  const logRef = useRef<HTMLDivElement>(null)
  // Переписка в колонке тесная: «Развернуть» показывает тот же чат в широком окне
  const [expanded, setExpanded] = useState(false)
  // Стройка, на которой открыт чат сейчас: ответ, пришедший после смены стройки, в чужую
  // переписку не пишется.
  const siteRef = useRef(siteId)
  useEffect(() => {
    siteRef.current = siteId
  }, [siteId])

  // Новое сообщение или индикатор ожидания — прокручиваем переписку вниз.
  useEffect(() => {
    const log = logRef.current
    if (log) log.scrollTop = log.scrollHeight
  }, [messages.length, isPending, expanded])

  const ask = async (question: string) => {
    const askedFor = siteId
    const result = await send(question)
    if (!result || siteRef.current !== askedFor) return
    if ('answer' in result) {
      append({ role: 'assistant', answer: result.answer })
      return
    }
    const { failure } = result
    append({
      role: 'failure',
      kind: failure.kind,
      title: FAILURE_TITLES[failure.kind],
      text: failure.message,
      question,
      retryable: failure.retryable,
    })
  }

  const handleSubmit = (question: string) => {
    if (isPending || disabled) return
    append({ role: 'user', text: question })
    void ask(question)
  }

  const handleRetry = (message: Extract<ChatMessage, { role: 'failure' }>) => {
    if (isPending) return
    // Отказ заменяется новой попыткой того же вопроса — без дубля вопроса в переписке.
    remove(message.id)
    void ask(message.question)
  }

  const last = messages.at(-1)

  // Один и тот же чат: в колонке или в развёрнутом окне — одновременно виден только один
  const chat = (
    <>
      {disabled && (
        <Callout tone="caution" title="Ассистент не подключён">
          Языковая модель на сервере не настроена или недоступна. Отчёт, отклонения и остальной
          сервис работают без неё.
        </Callout>
      )}

      <div
        ref={logRef}
        className={styles.log}
        role="log"
        aria-live="polite"
        aria-label="Переписка с ассистентом"
      >
        {messages.length === 0 && !isPending && (
          <p className={`sm muted ${styles.empty}`}>
            Задайте вопрос по отчёту — например, где отставание и на сколько. История переписки
            сохраняется в этом браузере.
          </p>
        )}

        {messages.map((message) => (
          <ChatBubble
            key={message.id}
            message={message}
            canRetry={message === last && !isPending}
            onRetry={handleRetry}
          />
        ))}

        {isPending && (
          <div className={`${styles.message} ${styles.assistant}`}>
            <p role="status" className={`sm muted ${styles.typing}`}>
              Ассистент отвечает. Это может занять до двух минут.
            </p>
          </div>
        )}
      </div>

      <div className={styles.composer}>
        <AssistantQuestionForm
          pending={isPending}
          onSubmit={handleSubmit}
          onCancel={cancel}
          showExamples={messages.length === 0}
          disabled={disabled}
        />
      </div>
    </>
  )

  return (
    <section className={styles.section} aria-label="Ассистент по отчёту">
      <SectionHeader
        level={3}
        title="Ассистент по отчёту"
        description="Пересказывает отчёт по запросу. Источник истины — сам отчёт."
        actions={
          <div className={styles.headActions}>
            {!expanded && (
              <Button variant="ghost" size="sm" onClick={() => setExpanded(true)}>
                Развернуть
              </Button>
            )}
            {messages.length > 0 && (
              <Button variant="ghost" size="sm" onClick={clear} disabled={isPending}>
                Очистить
              </Button>
            )}
          </div>
        }
      />

      {expanded ? <p className="sm muted">Чат открыт в отдельном окне</p> : chat}
      {expanded && (
        <Dialog wide title="Ассистент по отчёту" onClose={() => setExpanded(false)}>
          <div className={styles.expanded}>{chat}</div>
        </Dialog>
      )}
    </section>
  )
}

interface ChatBubbleProps {
  message: ChatMessage
  canRetry: boolean
  onRetry(this: void, message: Extract<ChatMessage, { role: 'failure' }>): void
}

function ChatBubble({ message, canRetry, onRetry }: ChatBubbleProps) {
  const time = formatTime(message.at)

  if (message.role === 'user') {
    return (
      <div className={`${styles.message} ${styles.user}`} data-role="user">
        <div className={styles.bubble}>{message.text}</div>
        <span className={styles.meta}>Вы · {time}</span>
      </div>
    )
  }

  if (message.role === 'assistant') {
    return (
      <div className={`${styles.message} ${styles.assistant}`} data-role="assistant">
        <div className={styles.bubble}>
          <AssistantAnswerView answer={message.answer} />
        </div>
        <span className={styles.meta}>Ассистент · {time}</span>
      </div>
    )
  }

  if (message.kind === 'cancelled') {
    return (
      <p className={`sm muted ${styles.note}`} data-role="failure">
        {message.title}
      </p>
    )
  }

  return (
    <div className={`${styles.message} ${styles.assistant}`} data-role="failure">
      <Callout tone="caution" title={message.title}>
        {message.text}
        {message.retryable && canRetry && (
          <div style={{ marginTop: 'var(--space-3)' }}>
            <Button onClick={() => onRetry(message)}>Повторить</Button>
          </div>
        )}
      </Callout>
      <span className={styles.meta}>{time}</span>
    </div>
  )
}
