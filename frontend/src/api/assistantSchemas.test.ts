import { describe, it, expect } from 'vitest'
import {
  assistantAnswerSchema,
  assistantQuestionSchema,
  assistantStatusSchema,
  assistantStageRefSchema,
} from './schemas'

describe('assistantQuestionSchema', () => {
  it('trims whitespace and validates length', () => {
    const result = assistantQuestionSchema.safeParse('  hello world  ')
    expect(result.success).toBe(true)
    expect(result).toMatchObject({ data: 'hello world' })
  })

  it('rejects questions shorter than 3 chars after trim', () => {
    const result = assistantQuestionSchema.safeParse('  ab  ')
    expect(result.success).toBe(false)
  })

  it('accepts exactly 3 chars', () => {
    const result = assistantQuestionSchema.safeParse('abc')
    expect(result.success).toBe(true)
    expect(result).toMatchObject({ data: 'abc' })
  })

  it('accepts exactly 500 chars', () => {
    const str500 = 'a'.repeat(500)
    const result = assistantQuestionSchema.safeParse(str500)
    expect(result.success).toBe(true)
    expect(result).toMatchObject({ data: str500 })
  })

  it('rejects more than 500 chars', () => {
    const str501 = 'a'.repeat(501)
    const result = assistantQuestionSchema.safeParse(str501)
    expect(result.success).toBe(false)
  })
})

describe('assistantStageRefSchema', () => {
  it('parses valid stage ref', () => {
    const result = assistantStageRefSchema.safeParse({ ref: 'этап 1', stage_id: 'stage-123' })
    expect(result).toMatchObject({
      success: true,
      data: { ref: 'этап 1', stage_id: 'stage-123' },
    })
  })
})

describe('assistantAnswerSchema', () => {
  const validAnswer = {
    answer: 'Sample answer',
    verified: true,
    numbers_not_in_report: [],
    numbers_of_other_site: [],
    limits: 'Some limits text',
    site_label: 'p1',
    stages: [{ ref: 'этап 1', stage_id: 'stage-123' }],
  }

  it('accepts a valid answer', () => {
    const result = assistantAnswerSchema.safeParse(validAnswer)
    expect(result.success).toBe(true)
  })

  it('rejects answer without stages', () => {
    const result = assistantAnswerSchema.safeParse({ ...validAnswer, stages: undefined })
    expect(result.success).toBe(false)
  })

  it('rejects answer with verified as string', () => {
    const result = assistantAnswerSchema.safeParse({
      ...validAnswer,
      verified: 'yes',
    })
    expect(result.success).toBe(false)
  })

  it('rejects answer when numbers_not_in_report is a string', () => {
    const result = assistantAnswerSchema.safeParse({
      ...validAnswer,
      numbers_not_in_report: '1',
    })
    expect(result.success).toBe(false)
  })

  it('rejects answer without limits', () => {
    const result = assistantAnswerSchema.safeParse({ ...validAnswer, limits: undefined })
    expect(result.success).toBe(false)
  })
})

describe('assistantStatusSchema', () => {
  it('accepts enabled: true', () => {
    const result = assistantStatusSchema.safeParse({ enabled: true })
    expect(result.success).toBe(true)
  })

  it('accepts enabled: false', () => {
    const result = assistantStatusSchema.safeParse({ enabled: false })
    expect(result.success).toBe(true)
  })

  it('rejects empty object', () => {
    const result = assistantStatusSchema.safeParse({})
    expect(result.success).toBe(false)
  })
})
