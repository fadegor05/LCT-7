import type { AssistantStageRef } from '@/api/schemas'
import { linkifyAnswer, stageAnchorId } from './linkifyAnswer'

describe('linkifyAnswer', () => {
  const stages: readonly AssistantStageRef[] = [
    { ref: 'этап 3', stage_id: 's3' },
    { ref: 'этап 4', stage_id: 's4' },
  ]

  describe('case-insensitive stage matching', () => {
    it.each([
      ['Этап 3', 's3'],
      ['этапа 3', 's3'],
      ['этап №3', 's3'],
      ['ЭТАП 3', 's3'],
      ['этап3', 's3'],
    ])('%s → one stage part with preserved text', (text, stageId) => {
      const parts = linkifyAnswer(text, stages)
      expect(parts).toHaveLength(1)
      expect(parts[0]).toEqual({
        kind: 'stage',
        text,
        stageId,
      })
    })
  })

  describe('non-matching references', () => {
    it('этап 30 is text, not stage', () => {
      const parts = linkifyAnswer('этап 30', stages)
      expect(parts).toHaveLength(1)
      expect(parts[0]).toEqual({
        kind: 'text',
        text: 'этап 30',
      })
    })

    it('этап 99 is text, not stage', () => {
      const parts = linkifyAnswer('этап 99', stages)
      expect(parts).toHaveLength(1)
      expect(parts[0]).toEqual({
        kind: 'text',
        text: 'этап 99',
      })
    })

    it('подэтап 3 is text, not stage (word boundary before Cyrillic)', () => {
      const parts = linkifyAnswer('подэтап 3', stages)
      expect(parts).toHaveLength(1)
      expect(parts[0]).toEqual({
        kind: 'text',
        text: 'подэтап 3',
      })
    })
  })

  describe('multiple stages and punctuation', () => {
    it('two different stages and a repeated one → three stage parts in order', () => {
      const parts = linkifyAnswer('Этап 3, этап 4. Этап 3 отстаёт.', stages)
      expect(parts).toHaveLength(6)
      expect(parts.map((p) => p.kind)).toEqual(['stage', 'text', 'stage', 'text', 'stage', 'text'])
      expect(parts[0]).toEqual({
        kind: 'stage',
        text: 'Этап 3',
        stageId: 's3',
      })
      expect(parts[1]).toEqual({
        kind: 'text',
        text: ', ',
      })
      expect(parts[2]).toEqual({
        kind: 'stage',
        text: 'этап 4',
        stageId: 's4',
      })
      expect(parts[3]).toEqual({
        kind: 'text',
        text: '. ',
      })
      expect(parts[4]).toEqual({
        kind: 'stage',
        text: 'Этап 3',
        stageId: 's3',
      })
      expect(parts[5]).toEqual({
        kind: 'text',
        text: ' отстаёт.',
      })
    })

    it('compound word: Этап 3, подэтап 3 → exactly one stage part', () => {
      const parts = linkifyAnswer('Этап 3, подэтап 3', stages)
      expect(parts.filter((p) => p.kind === 'stage')).toHaveLength(1)
      expect(parts[0]).toEqual({
        kind: 'stage',
        text: 'Этап 3',
        stageId: 's3',
      })
    })

    it('decimal number: этап 3.2 → stage part followed by text', () => {
      const parts = linkifyAnswer('этап 3.2', stages)
      expect(parts).toHaveLength(2)
      expect(parts[0]).toEqual({
        kind: 'stage',
        text: 'этап 3',
        stageId: 's3',
      })
      expect(parts[1]).toEqual({
        kind: 'text',
        text: '.2',
      })
    })
  })

  describe('edge cases', () => {
    it('empty stages → single text part', () => {
      const parts = linkifyAnswer('Этап 3 отстаёт', [])
      expect(parts).toHaveLength(1)
      expect(parts[0]).toEqual({
        kind: 'text',
        text: 'Этап 3 отстаёт',
      })
    })

    it('empty answer → empty array', () => {
      const parts = linkifyAnswer('', stages)
      expect(parts).toHaveLength(0)
    })
  })

  describe('join invariant', () => {
    it.each([
      'Этап 3 отстаёт',
      'этап 3, этап 4.',
      'Где этап 3? Вот оно.',
      'ЭТАП №3 и этап 4 вместе',
      'Ничего про этапы',
      'подэтап 3',
      'Этап 3, подэтап 3',
      'этап 3.2',
      '',
    ])('join preserves input: %s', (input) => {
      const parts = linkifyAnswer(input, stages)
      const joined = parts.map((p) => p.text).join('')
      expect(joined).toBe(input)
    })
  })
})

describe('stageAnchorId', () => {
  it('returns stage-{stageId}', () => {
    expect(stageAnchorId('s3')).toBe('stage-s3')
  })

  it('works with long ids', () => {
    expect(stageAnchorId('site-berezniki-stage-2')).toBe('stage-site-berezniki-stage-2')
  })
})
