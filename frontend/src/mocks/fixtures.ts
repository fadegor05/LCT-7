/**
 * Демо-данные моков: «Жилой дом · Березники» на 18.09.2026 и синтетический объект.
 * Формы объектов — контракты backend из src/api/schemas.ts.
 */
import type {
  DeviationDetail,
  EquipmentType,
  ImportIssue,
  Obligation,
  Site,
  StageStatus,
  User,
} from '@/api/schemas'

export const TODAY = '2026-09-18'

export const user: User = {
  id: 'user-1',
  full_name: 'инженер [ФИО]',
  created_at: '2026-09-01T09:00:00Z',
}

/** Часть справочника техники backend (methodology/seed.py). */
export const equipmentTypes: EquipmentType[] = [
  { code: 'excavator_crawler', title: 'Гусеничный экскаватор', is_coarse: false },
  { code: 'excavator_wheeled', title: 'Колёсный экскаватор', is_coarse: false },
  { code: 'bulldozer', title: 'Бульдозер', is_coarse: false },
  { code: 'dump_truck', title: 'Самосвал', is_coarse: false },
  { code: 'concrete_mixer', title: 'Автобетоносмеситель', is_coarse: false },
  { code: 'concrete_pump', title: 'Автобетононасос', is_coarse: false },
  { code: 'truck_crane', title: 'Автокран', is_coarse: false },
].map((eq) => ({
  id: `eq-${eq.code}`,
  code: eq.code,
  title: eq.title,
  synonyms: [],
  is_coarse: eq.is_coarse,
}))

export const equipmentByCode = (code: string) => equipmentTypes.find((e) => e.code === code)!

export const BEREZNIKI = 'site-berezniki'
export const SYNTHETIC = 'site-synthetic'

export const sites: Site[] = [
  {
    id: BEREZNIKI,
    name: 'Жилой дом · Березники',
    address: 'Березники, [адрес объекта]',
    owner_id: user.id,
    created_at: '2026-08-20T05:00:00Z',
    updated_at: '2026-08-20T05:00:00Z',
  },
  {
    id: SYNTHETIC,
    name: 'Синтетический объект (демо)',
    address: null,
    owner_id: user.id,
    created_at: '2026-08-01T07:00:00Z',
    updated_at: '2026-08-01T07:00:00Z',
  },
]

// ---------- График ----------

export interface StageSeed {
  name: string
  start: string | null
  end: string | null
}

/** Шаблон разобранного графика — его же получает стройка при загрузке файла в моках. */
export const STAGE_TEMPLATE: StageSeed[] = [
  { name: 'Подготовка территории', start: '2026-08-24', end: '2026-08-31' },
  { name: 'Разработка котлована', start: '2026-09-01', end: '2026-09-14' },
  { name: 'Устройство фундамента', start: '2026-09-15', end: '2026-09-30' },
  { name: 'Обратная засыпка', start: '2026-10-01', end: '2026-10-10' },
  { name: 'Внутренняя отделка', start: '2026-10-11', end: '2026-11-30' },
  { name: 'Благоустройство', start: null, end: null },
]

export const templateIssues = (prefix: string): ImportIssue[] => [
  { id: `${prefix}-issue-1`, row_number: 9, raw_row: 'ИТОГО;;', reason: 'Нет названия этапа' },
]

// ---------- Методика: базовый набор (как methodology/defaults.py) ----------

type RequirementSeed = [
  code: string,
  obligation: Obligation,
  gesn: string | null,
  note: string | null,
]

export const DEFAULT_RULES: { keywords: string[]; sets: RequirementSeed[][] }[] = [
  {
    keywords: ['котлован'],
    sets: [
      [
        ['excavator_crawler', 'normative', null, 'по смыслу работы (ФСЭМ 91.01.05-087)'],
        ['dump_truck', 'logical', null, 'по смыслу работы: вывоз грунта'],
      ],
    ],
  },
  {
    keywords: ['фундамент', 'бетонир'],
    sets: [
      [
        ['concrete_pump', 'normative', '06-01-001-16', null],
        ['concrete_mixer', 'logical', null, 'по смыслу работы: доставка бетона'],
      ],
      [
        ['truck_crane', 'normative', '06-01-001-16', null],
        ['concrete_mixer', 'logical', null, 'по смыслу работы: доставка бетона'],
      ],
    ],
  },
  {
    keywords: ['засыпк', 'земляные'],
    sets: [
      [
        ['bulldozer', 'normative', null, 'по смыслу работы (ФСЭМ 91.01.01-035)'],
        ['dump_truck', 'logical', null, 'по смыслу работы'],
      ],
      [
        ['excavator_wheeled', 'normative', null, 'по смыслу работы (ФСЭМ 91.01.05-104)'],
        ['dump_truck', 'logical', null, 'по смыслу работы'],
      ],
    ],
  },
]

export const NO_RULE_REASON = 'Нет правила в базовом наборе — задайте комплект'

// ---------- Снимки ----------

/** Снимки Березников: [дата, классы техники на снимке]; дата null — снимок без даты. */
export const PHOTO_SEEDS: [date: string | null, codes: string[]][] = [
  ['2026-09-14', ['excavator_crawler', 'dump_truck']],
  ['2026-09-14', ['excavator_crawler']],
  ['2026-09-15', ['excavator_crawler']],
  ['2026-09-15', []],
  ['2026-09-16', ['excavator_crawler', 'dump_truck']],
  ['2026-09-16', ['excavator_crawler']],
  ['2026-09-17', ['excavator_crawler', 'dump_truck']],
  ['2026-09-17', ['dump_truck']],
  ['2026-09-18', ['excavator_crawler', 'dump_truck']],
  ['2026-09-18', ['excavator_crawler', 'excavator_crawler']],
  ['2026-09-18', ['dump_truck']],
  ['2026-09-18', []],
  [null, ['excavator_crawler']],
  [null, []],
]

// ---------- Выводы движка оценки (Березники) ----------

type StatusSeed = Pick<StageStatus, 'status' | 'delay_days' | 'confidence' | 'confidence_reason'>

/** Статусы по позиции этапа; этапа нет в списке — сервер его ещё не оценивал (status = null). */
export const STATUS_SEEDS: Record<number, StatusSeed> = {
  1: {
    status: 'not_checked',
    delay_days: null,
    confidence: null,
    confidence_reason: NO_RULE_REASON,
  },
  2: {
    status: 'behind',
    delay_days: 4,
    confidence: 'high',
    confidence_reason:
      'Плановый конец 14.09 прошёл, экскаватор наблюдается и 18.09; дата из метаданных снимков',
  },
  3: {
    status: 'not_started',
    delay_days: null,
    confidence: 'medium',
    confidence_reason: 'Маркерной техники нет четыре рабочих дня при высокой наблюдаемости',
  },
  5: {
    status: 'not_checked',
    delay_days: null,
    confidence: null,
    confidence_reason: NO_RULE_REASON,
  },
}

type DeviationSeed = Omit<DeviationDetail, 'stage_id' | 'rule_id'> & { stage: number | null }

export const DEVIATION_SEEDS: DeviationSeed[] = [
  {
    id: 'dev-missing-pump',
    stage: 3,
    type: 'missing_equipment',
    is_hypothesis: false,
    severity: 'critical',
    confidence: 'high',
    period_start: '2026-09-15',
    period_end: '2026-09-18',
    expected:
      'С 15.09 на площадке автобетононасос или автокран (маркеры этапа «Устройство фундамента»).',
    observed: 'С 15.09 по 18.09 на снимках только гусеничный экскаватор и самосвал.',
    limits_text:
      'Не доказывает, что работы по фундаменту не ведутся: техника могла стоять вне кадра.',
    created_at: '2026-09-18T10:00:00Z',
    evidence: [
      { photo_id: 'ph-9', detection_id: 'ph-9-d0' },
      { photo_id: 'ph-10', detection_id: null },
    ],
  },
  {
    id: 'dev-idle-truck',
    stage: 2,
    type: 'idle',
    is_hypothesis: true,
    severity: 'attention',
    confidence: 'medium',
    period_start: '2026-09-17',
    period_end: '2026-09-18',
    expected: 'Самосвал вывозит грунт из котлована.',
    observed: 'Самосвал на одном месте на снимках 17.09 и 18.09.',
    limits_text: 'Гипотеза: по снимкам без камеры и зоны простой не доказывается.',
    created_at: '2026-09-18T09:00:00Z',
    evidence: [{ photo_id: 'ph-11', detection_id: 'ph-11-d0' }],
  },
  {
    id: 'dev-stale',
    stage: null,
    type: 'no_progress',
    is_hypothesis: false,
    severity: 'attention',
    confidence: 'low',
    period_start: '2026-09-16',
    period_end: '2026-09-17',
    expected: 'Сцена меняется между соседними датами.',
    observed: 'Снимки 16.09 и 17.09 почти не отличаются.',
    limits_text: 'Не доказывает остановку работ: изменения могли быть вне кадра.',
    created_at: '2026-09-17T12:00:00Z',
    evidence: [],
  },
]
