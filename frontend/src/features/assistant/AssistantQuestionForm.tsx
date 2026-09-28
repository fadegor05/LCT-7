import { useRef, useState, type FormEvent } from 'react'
import { Button } from '@/components/ui/Button'
import { TextAreaField } from '@/components/ui/TextAreaField'
import { ASSISTANT_QUESTION_MAX, assistantQuestionSchema } from '@/api/schemas'
import styles from './AssistantQuestionForm.module.css'

interface AssistantQuestionFormProps {
  pending: boolean
  error?: string
  onSubmit(this: void, question: string): void
  onCancel(this: void): void
}

const EXAMPLES = ['где отставание и на сколько', 'что с этой площадкой']

/** Форма для вопроса ассистенту по отчёту. */
export function AssistantQuestionForm({
  pending,
  error,
  onSubmit,
  onCancel,
}: AssistantQuestionFormProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const [fieldValue, setFieldValue] = useState('')
  const [fieldError, setFieldError] = useState<string>()

  const trimmedLength = fieldValue.trim().length
  const isOverLimit = trimmedLength > ASSISTANT_QUESTION_MAX
  const counterText = `${trimmedLength} / ${ASSISTANT_QUESTION_MAX}`
  const counterErrorText = `${trimmedLength} / ${ASSISTANT_QUESTION_MAX} — слишком длинный вопрос`

  const submit = () => {
    const result = assistantQuestionSchema.safeParse(fieldValue)
    if (!result.success) {
      setFieldError('Вопрос должен быть от 3 до 500 символов')
      return
    }
    onSubmit(result.data)
  }

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    submit()
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (pending) {
      return
    }
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      submit()
    }
  }

  const handleExampleClick = (example: string) => {
    setFieldValue(example)
    setFieldError(undefined)
    textareaRef.current?.focus()
  }

  const displayError = error || fieldError || (isOverLimit ? counterErrorText : undefined)

  return (
    <form onSubmit={handleSubmit} className={styles.form}>
      <TextAreaField
        ref={textareaRef}
        label="Вопрос по отчёту"
        value={fieldValue}
        onChange={(e) => {
          setFieldValue(e.currentTarget.value)
          if (fieldError) {
            setFieldError(undefined)
          }
        }}
        onKeyDown={handleKeyDown}
        error={displayError}
        hint={!displayError ? <span className={styles.counter}>{counterText}</span> : undefined}
        readOnly={pending}
      />

      <div className={styles.examples}>
        {EXAMPLES.map((example) => (
          <Button
            key={example}
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => handleExampleClick(example)}
          >
            {example}
          </Button>
        ))}
      </div>

      <div className={styles.actions}>
        <Button type="submit" disabled={pending}>
          Спросить
        </Button>
        {pending && (
          <Button type="button" variant="ghost" onClick={onCancel}>
            Отменить
          </Button>
        )}
      </div>
    </form>
  )
}
