/**
 * Тесты моков ассистента: сценарии ошибок, валидация вопроса, схемы ответа, выбор сценария.
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { ApiError, request } from '@/api/client'
import {
  assistantAnswerSchema,
  assistantStatusSchema,
  scheduleReportSchema,
  siteSchema,
} from '@/api/schemas'
import * as db from '@/mocks/db'
import { BEREZNIKI } from '@/mocks/fixtures'

const SCENARIOS: db.AssistantScenario[] = [
  'ok',
  'unverified',
  'out_of_scope',
  'rate_limited',
  'unavailable',
  'timeout',
  'too_large',
  'no_llm',
  'slow',
  'unlinked',
]

/** Ждёт отказа запроса и возвращает ApiError; если запрос прошёл — тест падает. */
async function rejection(promise: Promise<unknown>): Promise<ApiError> {
  let result: unknown
  try {
    result = await promise
  } catch (error) {
    if (error instanceof ApiError) return error
    throw error
  }
  throw new Error(`Ожидался отказ запроса, получен ответ: ${JSON.stringify(result)}`)
}

const ask = (siteId: string, question: string) =>
  request(`/sites/${siteId}/assistant/ask`, { method: 'POST', body: { question } })

describe('моки ассистента', () => {
  beforeEach(() => {
    db.resetDb()
  })

  describe('GET /assistant/status', () => {
    it('по умолчанию ассистент включён', async () => {
      const status = await request('/assistant/status', { schema: assistantStatusSchema })
      expect(status).toEqual({ enabled: true })
    })

    it.each(['no_llm', 'unavailable'] as const)('сценарий %s выключает ассистента', async (s) => {
      db.setAssistantScenario(s)
      const status = await request('/assistant/status', { schema: assistantStatusSchema })
      expect(status).toEqual({ enabled: false })
    })
  })

  describe('POST /sites/:siteId/assistant/ask', () => {
    it('на демо-стройке отдаёт ответ по контракту', async () => {
      const answer = await request(`/sites/${BEREZNIKI}/assistant/ask`, {
        method: 'POST',
        body: { question: 'где отставание и на сколько' },
        schema: assistantAnswerSchema,
      })
      expect(answer.site_label).toBe('p1')
      expect(answer.verified).toBe(true)
      expect(answer.numbers_not_in_report).toEqual([])
      expect(answer.numbers_of_other_site).toEqual([])
      expect(answer.limits).toContain('Проверяются числа')
    })

    it('ссылки на этапы указывают на этапы графика', async () => {
      const answer = await request(`/sites/${BEREZNIKI}/assistant/ask`, {
        method: 'POST',
        body: { question: 'где отставание' },
        schema: assistantAnswerSchema,
      })
      const schedule = await request(`/sites/${BEREZNIKI}/schedule`, {
        schema: scheduleReportSchema,
      })
      const scheduleStageIds = schedule.stages.map((s) => s.id)
      expect(answer.stages.length).toBeGreaterThan(0)
      for (const stage of answer.stages) {
        expect(scheduleStageIds).toContain(stage.stage_id)
      }
    })

    it('номер этапа — порядок по position, ссылка совпадает с текстом ответа', async () => {
      const answer = await request(`/sites/${BEREZNIKI}/assistant/ask`, {
        method: 'POST',
        body: { question: 'где отставание' },
        schema: assistantAnswerSchema,
      })
      const schedule = await request(`/sites/${BEREZNIKI}/schedule`, {
        schema: scheduleReportSchema,
      })
      expect(answer.stages).toHaveLength(1)
      const ref = answer.stages[0]!
      const inAnswer = /Этап (\d+)/.exec(answer.answer)
      expect(inAnswer).not.toBeNull()
      const stageNo = Number(inAnswer![1])
      const byPosition = [...schedule.stages].sort((a, b) => a.position - b.position)
      expect(byPosition.findIndex((s) => s.id === ref.stage_id) + 1).toBe(stageNo)
      expect(ref.ref).toBe(`этап ${stageNo}`)
    })

    it('стройка без графика — 404 без кода', async () => {
      const site = await request('/sites', {
        method: 'POST',
        body: { name: 'Новая', address: null },
        schema: siteSchema,
      })
      const error = await rejection(ask(site.id, 'что с этапами'))
      expect(error).toMatchObject({ status: 404, message: 'График не загружен' })
      expect(error.code).toBeUndefined()
    })

    it('неизвестная стройка — 404 без кода', async () => {
      const error = await rejection(ask('unknown-site-id', 'что с этапами'))
      expect(error).toMatchObject({ status: 404, message: 'Стройка не найдена' })
      expect(error.code).toBeUndefined()
    })

    it.each([
      ['rate_limited', 429, 'Слишком много вопросов. Повторите через 30 с.', 'rate_limited'],
      ['timeout', 504, 'Модель не ответила. Повторите вопрос позже.', 'assistant_timeout'],
      ['too_large', 413, 'Отчёт слишком велик для ассистента', 'report_too_large'],
      ['unavailable', 503, 'Ассистент недоступен', 'assistant_unavailable'],
    ] as const)('сценарий %s → %i', async (scenario, status, message, code) => {
      db.setAssistantScenario(scenario)
      const error = await rejection(ask(BEREZNIKI, 'что с этапами'))
      expect(error).toMatchObject({ status, message, code })
    })

    it('сценарий out_of_scope → 422 с кодом и текстом ассистента', async () => {
      db.setAssistantScenario('out_of_scope')
      const error = await rejection(ask(BEREZNIKI, 'что с этапами'))
      expect(error.status).toBe(422)
      expect(error.code).toBe('out_of_scope')
      expect(error.message).toContain('отвечает только на вопросы по отчёту')
    })

    it.each([
      ['слишком короткий', 'ab'],
      ['слишком длинный', 'a'.repeat(501)],
      ['короткий после trim', '  ab  '],
    ])('вопрос %s → 422 со списком detail и без кода', async (_name, question) => {
      const error = await rejection(ask(BEREZNIKI, question))
      expect(error.status).toBe(422)
      expect(Array.isArray(error.detail)).toBe(true)
      expect(error.code).toBeUndefined()
    })

    it.each([
      ['3 символа', 'abc'],
      ['500 символов', 'a'.repeat(500)],
    ])('вопрос из %s принимается', async (_name, question) => {
      const answer = await request(`/sites/${BEREZNIKI}/assistant/ask`, {
        method: 'POST',
        body: { question },
        schema: assistantAnswerSchema,
      })
      expect(answer.answer.length).toBeGreaterThan(0)
    })

    it('сценарий unverified отдаёт непроверенный ответ с числами', async () => {
      db.setAssistantScenario('unverified')
      const answer = await request(`/sites/${BEREZNIKI}/assistant/ask`, {
        method: 'POST',
        body: { question: 'что с этапами' },
        schema: assistantAnswerSchema,
      })
      expect(answer.verified).toBe(false)
      expect(answer.numbers_not_in_report).toEqual(['999'])
      expect(answer.numbers_of_other_site).toEqual(['p1: 5'])
    })

    it('сценарий unlinked не отдаёт ссылок на этапы', async () => {
      db.setAssistantScenario('unlinked')
      const answer = await request(`/sites/${BEREZNIKI}/assistant/ask`, {
        method: 'POST',
        body: { question: 'что с этапами' },
        schema: assistantAnswerSchema,
      })
      expect(answer.stages).toEqual([])
    })

    it('resetDb возвращает сценарий ok', async () => {
      db.setAssistantScenario('timeout')
      const error = await rejection(ask(BEREZNIKI, 'что с этапами'))
      expect(error.status).toBe(504)

      db.resetDb()

      expect(db.getAssistantScenario()).toBe('ok')
      const answer = await request(`/sites/${BEREZNIKI}/assistant/ask`, {
        method: 'POST',
        body: { question: 'что с этапами' },
        schema: assistantAnswerSchema,
      })
      expect(answer.verified).toBe(true)
    })
  })

  describe('выбор сценария', () => {
    it.each(SCENARIOS)('parseAssistantScenario распознаёт %s', (scenario) => {
      expect(db.parseAssistantScenario(`?assistant=${scenario}`)).toBe(scenario)
    })

    it.each([
      ['неизвестное имя', '?assistant=nope'],
      ['пустая строка', ''],
      ['другой параметр', '?other=1'],
      ['пустое значение', '?assistant='],
    ])('parseAssistantScenario: %s → ok', (_name, search) => {
      expect(db.parseAssistantScenario(search)).toBe('ok')
    })

    it('parseAssistantScenario находит параметр среди других', () => {
      expect(db.parseAssistantScenario('?x=1&assistant=timeout&y=2')).toBe('timeout')
    })

    it('задержку даёт только сценарий slow', () => {
      expect(db.assistantDelayMs('slow')).toBe(2000)
      for (const scenario of SCENARIOS.filter((s) => s !== 'slow')) {
        expect(db.assistantDelayMs(scenario)).toBe(0)
      }
    })
  })
})
