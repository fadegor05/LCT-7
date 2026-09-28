import type { Ref } from 'react'
import type { AssistantAnswer } from '@/api/schemas'
import { Callout } from '@/components/ui/Callout'
import { linkifyAnswer, stageAnchorId } from './linkifyAnswer'
import styles from './AssistantAnswer.module.css'

interface AssistantAnswerViewProps {
  answer: AssistantAnswer
  containerRef?: Ref<HTMLDivElement>
}

/** Компонент для отображения ответа ассистента с проверкой и ссылками на этапы. */
export function AssistantAnswerView({ answer, containerRef }: AssistantAnswerViewProps) {
  const parts = linkifyAnswer(answer.answer, answer.stages)

  return (
    <div ref={containerRef} tabIndex={-1} className={styles.container}>
      {!answer.verified && (
        <Callout tone="caution" title="Ответ не прошёл проверку">
          <p>Сверьтесь с отчётом: эти числа в нём не найдены.</p>
          {answer.numbers_not_in_report.length > 0 && (
            <div>
              <p>Чисел нет в отчёте:</p>
              <ul>
                {answer.numbers_not_in_report.map((num) => (
                  <li key={num}>{num}</li>
                ))}
              </ul>
            </div>
          )}
          {answer.numbers_of_other_site.length > 0 && (
            <div>
              <p>Числа относятся к другой площадке:</p>
              <ul>
                {answer.numbers_of_other_site.map((num) => (
                  <li key={num}>{num}</li>
                ))}
              </ul>
            </div>
          )}
        </Callout>
      )}

      <div className={styles.answer}>
        {parts.map((part, idx) => {
          if (part.kind === 'text') {
            return part.text
          }
          return (
            <a key={idx} href={'#' + stageAnchorId(part.stageId)}>
              {part.text}
            </a>
          )
        })}
      </div>

      {answer.limits && <p className="sm muted">{answer.limits}</p>}
    </div>
  )
}
