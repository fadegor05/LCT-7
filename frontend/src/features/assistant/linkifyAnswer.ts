import type { AssistantStageRef } from '@/api/schemas'

export type AnswerPart =
  { kind: 'text'; text: string } | { kind: 'stage'; text: string; stageId: string }

/**
 * Разбирает ответ ассистента и выделяет ссылки на этапы.
 *
 * Использует регулярное выражение для поиска "этап N" (без учёта регистра),
 * проверяет наличие этапа в списке и создаёт части текста.
 * Смежные текстовые части объединяются.
 *
 * @param answer Текст ответа
 * @param stages Список доступных этапов с их идентификаторами
 * @returns Массив частей текста и ссылок на этапы
 *
 * @example
 * linkifyAnswer('Этап 3 отстаёт', [{ref: 'этап 3', stage_id: 's3'}])
 * // => [{kind: 'stage', text: 'Этап 3', stageId: 's3'}, {kind: 'text', text: ' отстаёт'}]
 */
export function linkifyAnswer(answer: string, stages: readonly AssistantStageRef[]): AnswerPart[] {
  if (!answer) return []

  // Создаём карту доступных этапов для быстрого поиска
  // Ключ: "этап {number}", значение: stage_id
  const stageMap = new Map<string, string>()
  for (const stage of stages) {
    stageMap.set(stage.ref.toLowerCase(), stage.stage_id)
  }

  // Регулярное выражение для поиска "этап(ов/а/ы) №? N"
  // Использует Unicode-aware границу слова (lookbehind) и захватывает номер в группе
  const regex = /(?<![\p{L}\p{N}_])этап[а-яё]*\s*№?\s*(\d{1,4})(?!\d)/giu
  const parts: AnswerPart[] = []
  let lastIndex = 0
  let match

  // Ищем все совпадения в тексте
  while ((match = regex.exec(answer)) !== null) {
    const matchedText = match[0]
    const stageNumber = match[1]
    const stageRef = `этап ${stageNumber}`.toLowerCase()

    // Добавляем текст перед совпадением (если есть)
    if (match.index > lastIndex) {
      const textBefore = answer.substring(lastIndex, match.index)
      parts.push({ kind: 'text', text: textBefore })
    }

    // Проверяем, есть ли такой этап в списке
    const stageId = stageMap.get(stageRef)
    if (stageId) {
      // Это ссылка на этап — сохраняем исходный текст из документа
      parts.push({
        kind: 'stage',
        text: matchedText,
        stageId,
      })
    } else {
      // Этап не найден — это просто текст
      parts.push({
        kind: 'text',
        text: matchedText,
      })
    }

    lastIndex = regex.lastIndex
  }

  // Добавляем оставшийся текст
  if (lastIndex < answer.length) {
    parts.push({
      kind: 'text',
      text: answer.substring(lastIndex),
    })
  }

  // Объединяем соседние текстовые части
  const mergedParts: AnswerPart[] = []
  for (const part of parts) {
    if (part.kind === 'text' && mergedParts.length > 0) {
      const lastPart = mergedParts[mergedParts.length - 1]
      if (lastPart && lastPart.kind === 'text') {
        // Объединяем соседние текстовые части
        lastPart.text += part.text
        continue
      }
    }
    mergedParts.push(part)
  }

  return mergedParts
}

/**
 * Генерирует идентификатор якоря для строки этапа в таблице.
 *
 * @param stageId Идентификатор этапа
 * @returns Идентификатор якоря для использования в id атрибута и href ссылки
 *
 * @example
 * stageAnchorId('s3') // => 'stage-s3'
 * stageAnchorId('site-berezniki-stage-2') // => 'stage-site-berezniki-stage-2'
 */
export function stageAnchorId(stageId: string): string {
  return `stage-${stageId}`
}
