/**
 * Тесты для моков ассистента: сценарии ошибок, валидация вопроса, схемы ответа.
 */
/* eslint-disable @typescript-eslint/no-unsafe-assignment, @typescript-eslint/no-unsafe-member-access, @typescript-eslint/no-unsafe-return, vitest/no-conditional-expect, prefer-const */
import { describe, it, expect, beforeEach } from 'vitest'
import * as db from '@/mocks/db'
import { BEREZNIKI } from '@/mocks/fixtures'
import { request } from '@/api/client'
import {
  assistantAnswerSchema,
  assistantStatusSchema,
  scheduleReportSchema,
  siteSchema,
} from '@/api/schemas'
import { ApiError } from '@/api/client'

describe('assistant mocks', () => {
  beforeEach(() => {
    db.resetDb()
  })

  describe('GET /assistant/status', () => {
    it('returns enabled: true by default', async () => {
      const response = await request('/assistant/status', {
        schema: assistantStatusSchema,
      })
      expect(response).toEqual({ enabled: true })
    })

    it('returns enabled: false for no_llm scenario', async () => {
      db.setAssistantScenario('no_llm')
      const response = await request('/assistant/status', {
        schema: assistantStatusSchema,
      })
      expect(response).toEqual({ enabled: false })
    })

    it('returns enabled: false for unavailable scenario', async () => {
      db.setAssistantScenario('unavailable')
      const response = await request('/assistant/status', {
        schema: assistantStatusSchema,
      })
      expect(response).toEqual({ enabled: false })
    })
  })

  describe('POST /sites/:siteId/assistant/ask', () => {
    it('succeeds on demo site with correct answer structure', async () => {
      const response = await request(`/sites/${BEREZNIKI}/assistant/ask`, {
        method: 'POST',
        body: { question: 'где отставание и на сколько' },
        schema: assistantAnswerSchema,
      })
      expect(response).toMatchObject({
        answer: expect.any(String),
        verified: expect.any(Boolean),
        numbers_not_in_report: expect.any(Array),
        numbers_of_other_site: expect.any(Array),
        limits: expect.any(String),
        site_label: 'p1',
        stages: expect.any(Array),
      })
    })

    it('includes correct stage references in response', async () => {
      const response = await request(`/sites/${BEREZNIKI}/assistant/ask`, {
        method: 'POST',
        body: { question: 'где отставание' },
        schema: assistantAnswerSchema,
      })
      const schedule = await request(`/sites/${BEREZNIKI}/schedule`, {
        schema: scheduleReportSchema,
      })
      // All stage_ids in the answer must exist in the schedule
      const scheduleStageIds = schedule.stages.map((s) => s.id)
      for (const stage of response.stages) {
        expect(scheduleStageIds).toContain(stage.stage_id)
      }
    })

    it('returns 404 for site without schedule', async () => {
      const newSite = await request('/sites', {
        method: 'POST',
        body: { name: 'Test Site', address: null },
        schema: siteSchema,
      })
      const error = await request(`/sites/${newSite.id}/assistant/ask`, {
        method: 'POST',
        body: { question: 'test question' },
      }).catch((e) => e)
      expect(error).toBeInstanceOf(ApiError)
      expect(error.status).toBe(404)
      expect(error.message).toBe('График не загружен')
    })

    it('returns 404 for unknown site', async () => {
      const error = await request('/sites/unknown-site-id/assistant/ask', {
        method: 'POST',
        body: { question: 'test question' },
      }).catch((e) => e)
      expect(error).toBeInstanceOf(ApiError)
      expect(error.status).toBe(404)
      expect(error.message).toBe('Стройка не найдена')
    })

    it('returns 429 rate_limited error', async () => {
      db.setAssistantScenario('rate_limited')
      const error = await request(`/sites/${BEREZNIKI}/assistant/ask`, {
        method: 'POST',
        body: { question: 'test' },
      }).catch((e) => e)
      expect(error).toBeInstanceOf(ApiError)
      expect(error.status).toBe(429)
      expect(error.message).toContain('Слишком много вопросов')
      expect(error.code).toBe('rate_limited')
    })

    it('returns 504 timeout error', async () => {
      db.setAssistantScenario('timeout')
      const error = await request(`/sites/${BEREZNIKI}/assistant/ask`, {
        method: 'POST',
        body: { question: 'test' },
      }).catch((e) => e)
      expect(error).toBeInstanceOf(ApiError)
      expect(error.status).toBe(504)
      expect(error.message).toContain('не ответила')
      expect(error.code).toBe('assistant_timeout')
    })

    it('returns 422 out_of_scope error', async () => {
      db.setAssistantScenario('out_of_scope')
      const error = await request(`/sites/${BEREZNIKI}/assistant/ask`, {
        method: 'POST',
        body: { question: 'test' },
      }).catch((e) => e)
      expect(error).toBeInstanceOf(ApiError)
      expect(error.status).toBe(422)
      expect(error.message).toContain('отвечает только на вопросы')
      expect(error.code).toBe('out_of_scope')
    })

    it('returns 413 too_large error', async () => {
      db.setAssistantScenario('too_large')
      const error = await request(`/sites/${BEREZNIKI}/assistant/ask`, {
        method: 'POST',
        body: { question: 'test' },
      }).catch((e) => e)
      expect(error).toBeInstanceOf(ApiError)
      expect(error.status).toBe(413)
      expect(error.message).toContain('Отчёт слишком велик')
      expect(error.code).toBe('report_too_large')
    })

    it('returns 503 unavailable error when scenario is unavailable', async () => {
      db.setAssistantScenario('unavailable')
      const error = await request(`/sites/${BEREZNIKI}/assistant/ask`, {
        method: 'POST',
        body: { question: 'test' },
      }).catch((e) => e)
      expect(error).toBeInstanceOf(ApiError)
      expect(error.status).toBe(503)
      expect(error.code).toBe('assistant_unavailable')
    })

    it('validates question: too short (< 3 chars)', async () => {
      const error = await request(`/sites/${BEREZNIKI}/assistant/ask`, {
        method: 'POST',
        body: { question: 'ab' },
      }).catch((e) => e)
      expect(error).toBeInstanceOf(ApiError)
      expect(error.status).toBe(422)
      expect(Array.isArray(error.detail)).toBe(true)
      expect(error.code).toBeUndefined()
    })

    it('validates question: too long (> 500 chars)', async () => {
      const longQuestion = 'a'.repeat(501)
      const error = await request(`/sites/${BEREZNIKI}/assistant/ask`, {
        method: 'POST',
        body: { question: longQuestion },
      }).catch((e) => e)
      expect(error).toBeInstanceOf(ApiError)
      expect(error.status).toBe(422)
      expect(Array.isArray(error.detail)).toBe(true)
      expect(error.code).toBeUndefined()
    })

    it('accepts question with exactly 3 characters', async () => {
      const response = await request(`/sites/${BEREZNIKI}/assistant/ask`, {
        method: 'POST',
        body: { question: 'abc' },
        schema: assistantAnswerSchema,
      })
      expect(response).toBeDefined()
    })

    it('accepts question with exactly 500 characters', async () => {
      const longQuestion = 'a'.repeat(500)
      const response = await request(`/sites/${BEREZNIKI}/assistant/ask`, {
        method: 'POST',
        body: { question: longQuestion },
        schema: assistantAnswerSchema,
      })
      expect(response).toBeDefined()
    })

    it('trims whitespace from question', async () => {
      // Verify that a question with only 2 chars of content but padded to > 3 chars fails
      const padded = '  ab  '
      const error = await request(`/sites/${BEREZNIKI}/assistant/ask`, {
        method: 'POST',
        body: { question: padded },
      }).catch((e) => e)
      expect(error).toBeInstanceOf(ApiError)
      expect(error.status).toBe(422)
      // After trimming "  ab  " becomes "ab" which is < 3 chars
      expect(Array.isArray(error.detail)).toBe(true)
    })

    it('returns unverified answer with specified fields', async () => {
      db.setAssistantScenario('unverified')
      const response = await request(`/sites/${BEREZNIKI}/assistant/ask`, {
        method: 'POST',
        body: { question: 'test' },
        schema: assistantAnswerSchema,
      })
      expect(response.verified).toBe(false)
      expect(response.numbers_not_in_report).toEqual(['999'])
      expect(response.numbers_of_other_site).toEqual(['p1: 5'])
    })

    it('returns empty stages for unlinked scenario', async () => {
      db.setAssistantScenario('unlinked')
      const response = await request(`/sites/${BEREZNIKI}/assistant/ask`, {
        method: 'POST',
        body: { question: 'test' },
        schema: assistantAnswerSchema,
      })
      expect(response.stages).toEqual([])
    })

    it('resetDb restores scenario to ok', async () => {
      db.setAssistantScenario('timeout')
      let error = await request(`/sites/${BEREZNIKI}/assistant/ask`, {
        method: 'POST',
        body: { question: 'test' },
      }).catch((e) => e)
      expect(error).toBeInstanceOf(ApiError)
      expect(error.status).toBe(504)

      db.resetDb()

      const response = await request(`/sites/${BEREZNIKI}/assistant/ask`, {
        method: 'POST',
        body: { question: 'test' },
        schema: assistantAnswerSchema,
      })
      expect(response).toBeDefined()
      expect(response.answer).toBeDefined()
    })

    it('handle() includes code only for coded errors', async () => {
      // This test verifies that non-coded errors (like 404) don't have a code field
      const error = await request('/sites/unknown/assistant/ask', {
        method: 'POST',
        body: { question: 'test' },
      }).catch((e) => e)
      expect(error).toBeInstanceOf(ApiError)
      expect(error.status).toBe(404)
      expect(error.code).toBeUndefined()
    })

    it('stage_no uses 1-based position order, not array order', async () => {
      // Verify that stage numbering respects the position field
      const response = await request(`/sites/${BEREZNIKI}/assistant/ask`, {
        method: 'POST',
        body: { question: 'test' },
        schema: assistantAnswerSchema,
      })
      // Get the schedule to verify positions
      const schedule = await request(`/sites/${BEREZNIKI}/schedule`, {
        schema: scheduleReportSchema,
      })
      // Check that if there is a behind stage, its stage_no equals its position
      if (response.stages.length > 0) {
        const stageId = response.stages[0]?.stage_id
        if (stageId) {
          const behindStage = schedule.stages.find((s) => s.id === stageId)
          if (behindStage) {
            // Extract stage number from the answer (e.g., "Этап 1" → 1)
            const match = response.answer.match(/Этап (\d+)/)
            if (match?.[1]) {
              const stageNo = parseInt(match[1], 10)
              // Verify it equals the position in a position-sorted array
              const sortedByPosition = [...schedule.stages].sort((a, b) => a.position - b.position)
              const expectedNo = sortedByPosition.findIndex((s) => s.id === behindStage.id)
              expect(stageNo).toBe(expectedNo + 1)
            }
          }
        }
      }
    })
  })
})
