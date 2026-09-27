/**
 * Контракты API (snake_case, как отдаёт FastAPI/Pydantic).
 *
 * Схемы повторяют Pydantic-схемы backend один в один (`backend/app/domains/<домен>/schemas.py`),
 * перечисления — StrEnum из `models.py` доменов. При изменении контракта на бэкенде правится
 * этот файл: Zod-ошибка контракта сразу видна на экране.
 */
import { z } from 'zod'

// ---------- Перечисления ----------

/** observation.models.Observability / Confidence: три уровня, не число (architecture §7.3). */
export const levelSchema = z.enum(['high', 'medium', 'low'])
/** assessment.schemas.SiteSummaryRead.verdict */
export const verdictSchema = z.enum(['behind', 'no_deviations', 'insufficient_data'])
/** assessment.models.StageStatusValue */
export const stageStatusValueSchema = z.enum([
  'ahead',
  'on_track',
  'behind',
  'not_started',
  'not_observed',
  'not_checked',
])
/** schedule.models.DatesSource */
export const datesSourceSchema = z.enum(['file', 'manual'])
/** methodology.models.Obligation */
export const obligationSchema = z.enum(['normative', 'logical', 'auxiliary'])
/** photo.models.DateSource */
export const dateSourceSchema = z.enum(['channel', 'metadata', 'stamp', 'neighbours', 'manual'])
/** photo.models.ProcessingStatus */
export const processingStatusSchema = z.enum(['pending', 'done', 'failed'])
/** observation.models.Activity */
export const activitySchema = z.enum(['works', 'idle', 'unknown'])
/** assessment.models.DeviationType */
export const deviationTypeSchema = z.enum([
  'missing_equipment',
  'missing_logical_equipment',
  'stage_mismatch',
  'stale_data',
  'idle',
  'extra_equipment',
  'out_of_zone',
  'no_progress',
])
/** assessment.models.Severity */
export const severitySchema = z.enum(['critical', 'attention'])

/** Дата без времени: YYYY-MM-DD. */
const isoDate = z.string().regex(/^\d{4}-\d{2}-\d{2}$/)
const isoDateTime = z.string()

// ---------- Пользователь (user) ----------

export const userSchema = z.object({
  id: z.string(),
  full_name: z.string(),
  created_at: isoDateTime,
})

// ---------- Стройка (site) ----------

export const siteSchema = z.object({
  id: z.string(),
  name: z.string(),
  address: z.string().nullable(),
  owner_id: z.string(),
  created_at: isoDateTime,
  updated_at: isoDateTime,
})

/** SiteCreate / SiteUpdate: пустой адрес уходит как null. */
export const siteCreateSchema = z.object({
  name: z.string().trim().min(1, 'Укажите название').max(255),
  address: z.string().trim().max(500),
})

// ---------- График (schedule) ----------

export const stageSchema = z.object({
  id: z.string(),
  name: z.string(),
  position: z.number(),
  planned_start: isoDate.nullable(),
  planned_end: isoDate.nullable(),
  dates_source: datesSourceSchema,
})

export const importIssueSchema = z.object({
  id: z.string(),
  row_number: z.number(),
  raw_row: z.string(),
  reason: z.string(),
})

export const scheduleReportSchema = z.object({
  id: z.string(),
  site_id: z.string(),
  source_filename: z.string(),
  imported_at: isoDateTime,
  rows_total: z.number(),
  rows_parsed: z.number(),
  stages_with_dates: z.number(),
  stages_without_dates: z.number(),
  stages: z.array(stageSchema),
  issues: z.array(importIssueSchema),
})

export const stageDatesUpdateSchema = z.object({
  planned_start: isoDate.nullable().optional(),
  planned_end: isoDate.nullable().optional(),
})

// ---------- Методика (methodology) ----------

export const equipmentTypeSchema = z.object({
  id: z.string(),
  code: z.string(),
  title: z.string(),
  synonyms: z.array(z.string()),
  is_coarse: z.boolean().default(false),
})

export const requirementSchema = z.object({
  id: z.string(),
  equipment_type: equipmentTypeSchema,
  min_count: z.number(),
  obligation: obligationSchema,
  gesn_code: z.string().nullable(),
  source_note: z.string().nullable(),
})

export const equipmentSetSchema = z.object({
  id: z.string(),
  position: z.number(),
  requirements: z.array(requirementSchema),
})

export const ruleSchema = z.object({
  id: z.string(),
  stage_id: z.string().nullable(),
  stage_name: z.string().nullable(),
  is_verifiable: z.boolean(),
  unverifiable_reason: z.string().nullable(),
  updated_at: isoDateTime,
  sets: z.array(equipmentSetSchema),
})

export const ruleUpdateSchema = z.object({
  is_verifiable: z.boolean(),
  unverifiable_reason: z.string().nullable(),
})

export const requirementInputSchema = z.object({
  equipment_type_id: z.string(),
  min_count: z.number().int().min(1),
  obligation: obligationSchema,
  gesn_code: z.string().nullable(),
  source_note: z.string().nullable(),
})

export const setWriteSchema = z.object({
  requirements: z.array(requirementInputSchema).min(1),
})

// ---------- Снимки (photo) ----------

export const detectionSchema = z.object({
  id: z.string(),
  equipment_type_id: z.string(),
  equipment_code: z.string(),
  equipment_title: z.string(),
  /** [x1, y1, x2, y2] в долях кадра 0–1. */
  bbox: z.array(z.number()),
  score: z.number(),
  model_version: z.string(),
})

export const photoSchema = z.object({
  id: z.string(),
  site_id: z.string(),
  original_name: z.string(),
  width: z.number(),
  height: z.number(),
  captured_on: isoDate.nullable(),
  date_source: dateSourceSchema.nullable(),
  processing_status: processingStatusSchema,
  uploaded_at: isoDateTime,
})

export const photoDetailSchema = photoSchema.extend({
  detections: z.array(detectionSchema),
})

export const uploadReportSchema = z.object({
  items: z.array(
    z.object({
      filename: z.string(),
      photo: photoSchema.nullable().optional(),
      error: z.string().nullable().optional(),
    }),
  ),
  uploaded: z.number(),
  failed: z.number(),
})

export const detectBacklogReportSchema = z.object({
  processed: z.number().int(),
  done: z.number().int(),
  failed: z.number().int(),
  skipped: z.number().int(),
})

// ---------- Наблюдения (observation) ----------

export const observedEquipmentSchema = z.object({
  equipment_type_id: z.string(),
  equipment_code: z.string(),
  equipment_title: z.string(),
  count_min: z.number(),
  activity: activitySchema,
  confidence: levelSchema,
})

export const observationSchema = z.object({
  id: z.string(),
  site_id: z.string(),
  observed_on: isoDate,
  photo_count: z.number(),
  observability: levelSchema,
  observability_notes: z.string().nullable(),
  recomputed_at: isoDateTime,
  equipment: z.array(observedEquipmentSchema),
})

// ---------- Оценка (assessment) ----------

export const stageStatusSchema = z.object({
  stage_id: z.string(),
  stage_name: z.string(),
  position: z.number(),
  /** null — статус ещё не рассчитан (этап не наступил или нет данных). */
  status: stageStatusValueSchema.nullable(),
  delay_days: z.number().nullable(),
  confidence: levelSchema.nullable(),
  confidence_reason: z.string().nullable(),
  computed_at: isoDateTime.nullable(),
})

export const deviationSchema = z.object({
  id: z.string(),
  stage_id: z.string().nullable(),
  type: deviationTypeSchema,
  is_hypothesis: z.boolean(),
  severity: severitySchema,
  confidence: levelSchema,
  period_start: isoDate,
  period_end: isoDate,
  expected: z.string(),
  observed: z.string(),
  limits_text: z.string(),
  rule_id: z.string().nullable(),
  created_at: isoDateTime,
})

export const deviationDetailSchema = deviationSchema.extend({
  evidence: z.array(z.object({ photo_id: z.string(), detection_id: z.string().nullable() })),
})

export const siteSummarySchema = z.object({
  verdict: verdictSchema,
  delay_days_min: z.number().nullable(),
  delay_days_max: z.number().nullable(),
  critical_count: z.number(),
  attention_count: z.number(),
})

// ---------- Типы ----------

export type Level = z.infer<typeof levelSchema>
export type Verdict = z.infer<typeof verdictSchema>
export type StageStatusValue = z.infer<typeof stageStatusValueSchema>
export type DatesSource = z.infer<typeof datesSourceSchema>
export type Obligation = z.infer<typeof obligationSchema>
export type DateSource = z.infer<typeof dateSourceSchema>
export type ProcessingStatus = z.infer<typeof processingStatusSchema>
export type Activity = z.infer<typeof activitySchema>
export type DeviationType = z.infer<typeof deviationTypeSchema>
export type Severity = z.infer<typeof severitySchema>

export type User = z.infer<typeof userSchema>
export type Site = z.infer<typeof siteSchema>
export type SiteCreate = z.infer<typeof siteCreateSchema>
export type Stage = z.infer<typeof stageSchema>
export type ImportIssue = z.infer<typeof importIssueSchema>
export type ScheduleReport = z.infer<typeof scheduleReportSchema>
export type StageDatesUpdate = z.infer<typeof stageDatesUpdateSchema>
export type EquipmentType = z.infer<typeof equipmentTypeSchema>
export type Requirement = z.infer<typeof requirementSchema>
export type EquipmentSet = z.infer<typeof equipmentSetSchema>
export type Rule = z.infer<typeof ruleSchema>
export type RuleUpdate = z.infer<typeof ruleUpdateSchema>
export type RequirementInput = z.infer<typeof requirementInputSchema>
export type SetWrite = z.infer<typeof setWriteSchema>
export type Detection = z.infer<typeof detectionSchema>
export type Photo = z.infer<typeof photoSchema>
export type PhotoDetail = z.infer<typeof photoDetailSchema>
export type UploadReport = z.infer<typeof uploadReportSchema>
export type ObservedEquipment = z.infer<typeof observedEquipmentSchema>
export type Observation = z.infer<typeof observationSchema>
export type StageStatus = z.infer<typeof stageStatusSchema>
export type Deviation = z.infer<typeof deviationSchema>
export type DeviationDetail = z.infer<typeof deviationDetailSchema>
export type SiteSummary = z.infer<typeof siteSummarySchema>
export type DetectBacklogReport = z.infer<typeof detectBacklogReportSchema>
