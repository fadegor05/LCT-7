/**
 * Контракты API (snake_case, как отдаёт FastAPI/Pydantic).
 *
 * Перечисления и поля повторяют docs/DataModel.md §5. Всё, чего текущий backend ещё не
 * отдаёт (например, сводка в списке строек), объявлено необязательным с default —
 * так фронт работает и на моках, и на частично готовом API.
 */
import { z } from 'zod'

// ---------- Перечисления (DataModel §5.7) ----------

export const objectTypeSchema = z.enum(['housing', 'education', 'health', 'other'])
export const workDaysSchema = z.enum(['mon_fri', 'mon_sat', 'all'])
export const siteStateSchema = z.enum(['draft', 'active'])
export const levelSchema = z.enum(['high', 'medium', 'low'])
export const verdictSchema = z.enum(['behind', 'no_deviations', 'insufficient_data'])
export const stageStatusValueSchema = z.enum([
  'ahead',
  'on_track',
  'behind',
  'not_started',
  'not_observed',
  'not_checked',
  'not_due',
])
export const evidenceStateSchema = z.enum(['marker_confirmed', 'compatible', 'none', 'unknown'])
export const matchKindSchema = z.enum(['exact', 'fuzzy', 'manual', 'none'])
export const datesSourceSchema = z.enum(['works', 'manual'])
export const ruleKindSchema = z.enum(['normative', 'logical', 'auxiliary'])
export const sourceTypeSchema = z.enum(['photo', 'video', 'stream'])
export const dateSourceSchema = z.enum(['exif', 'stamp', 'manual', 'video', 'stream'])
export const timeStateSchema = z.enum(['ok', 'needs_review'])
export const timeIssueSchema = z.enum([
  'stamp_unrecognized',
  'no_metadata',
  'stamp_cropped',
  'stamp_low_conf',
  'clip_no_start',
])
export const activitySchema = z.enum(['working', 'idle', 'unknown'])
export const deviationTypeSchema = z.enum([
  'missing_equipment',
  'stage_mismatch',
  'stale_data',
  'idle',
  'extra_equipment',
  'out_of_zone',
  'no_progress',
])
export const severitySchema = z.enum(['critical', 'attention'])
export const decisionSchema = z.enum(['confirmed', 'rejected'])
export const issueKindSchema = z.enum([
  'row_unparsed',
  'no_dates',
  'fuzzy_match',
  'window_overlap',
  'no_marker',
])
export const ingestStateSchema = z.enum(['queued', 'running', 'done', 'stopped', 'failed'])
export const evidenceRoleSchema = z.enum(['evidence', 'zone'])

/** Дата без времени: YYYY-MM-DD. */
const isoDate = z.string().regex(/^\d{4}-\d{2}-\d{2}$/)
const isoDateTime = z.string()

// ---------- Пользователь ----------

export const userSchema = z.object({
  id: z.string(),
  full_name: z.string(),
  created_at: isoDateTime,
})

// ---------- Стройка ----------

export const siteSummarySchema = z.object({
  verdict: verdictSchema,
  delay_days_min: z.number().nullable(),
  delay_days_max: z.number().nullable(),
  measured_stage_name: z.string().nullable(),
  explanation: z.string().nullable(),
  observability: levelSchema,
  cameras_total: z.number(),
  cameras_reporting: z.number(),
  last_frame_at: isoDateTime.nullable(),
  frames_total: z.number(),
  frames_without_time: z.number(),
  data_age_days: z.number().nullable(),
  critical_count: z.number(),
  attention_count: z.number(),
})

export const siteSchema = z.object({
  id: z.string(),
  name: z.string(),
  address: z.string().nullable(),
  object_type: objectTypeSchema.default('other'),
  work_days: workDaysSchema.default('mon_fri'),
  timezone: z.string().default('Europe/Moscow'),
  state: siteStateSchema.default('active'),
  created_at: isoDateTime,
  summary: siteSummarySchema.nullable().default(null),
})

export const siteCreateSchema = z.object({
  name: z.string().trim().min(1, 'Укажите название').max(255),
  address: z.string().trim().max(500),
  object_type: objectTypeSchema,
  work_days: workDaysSchema,
})

// ---------- График и этапы ----------

export const importIssueSchema = z.object({
  id: z.string(),
  kind: issueKindSchema,
  row_number: z.number().nullable(),
  stage_id: z.string().nullable(),
  message: z.string(),
  blocking: z.boolean(),
  resolved_at: isoDateTime.nullable(),
})

export const scheduleImportSchema = z.object({
  id: z.string(),
  site_id: z.string(),
  file_name: z.string(),
  file_size: z.number(),
  works_total: z.number(),
  rows_failed: z.number(),
  stages_total: z.number(),
  window_overlaps: z.number(),
  checked_stages: z.number(),
  issues: z.array(importIssueSchema),
  uploaded_at: isoDateTime,
})

export const stageSchema = z.object({
  id: z.string(),
  seq_no: z.number(),
  name: z.string(),
  match_kind: matchKindSchema,
  match_score: z.number().nullable(),
  match_confirmed: z.boolean(),
  planned_start: isoDate.nullable(),
  planned_end: isoDate.nullable(),
  dates_source: datesSourceSchema,
  merged_windows: z.number(),
  equipment_check: z.boolean(),
  not_checked_reason: z.string().nullable(),
  has_marker: z.boolean(),
  works: z.array(z.object({ id: z.string(), name: z.string() })),
})

export const stageUpdateSchema = z.object({
  planned_start: isoDate.nullable().optional(),
  planned_end: isoDate.nullable().optional(),
  match_confirmed: z.boolean().optional(),
  equipment_check: z.boolean().optional(),
})

// ---------- Методика ----------

export const equipmentClassSchema = z.object({
  code: z.string(),
  name_ru: z.string(),
  group_code: z.string(),
})

export const kitRuleSchema = z.object({
  id: z.string(),
  equipment_class: z.string().nullable(),
  equipment_group: z.string().nullable(),
  name: z.string(),
  rule_kind: ruleKindSchema,
  source_ref: z.string().nullable(),
  typical_qty: z.number().nullable(),
  is_marker: z.boolean(),
})

export const stageKitSchema = z.object({
  stage_id: z.string(),
  stage_name: z.string(),
  planned_start: isoDate.nullable(),
  planned_end: isoDate.nullable(),
  equipment_check: z.boolean(),
  not_checked_reason: z.string().nullable(),
  rules: z.array(kitRuleSchema),
  marker_explanation: z.string().nullable(),
})

export const kitRuleInputSchema = z.object({
  equipment_class: z.string().nullable(),
  equipment_group: z.string().nullable(),
  rule_kind: ruleKindSchema,
  source_ref: z.string().nullable(),
  typical_qty: z.number().int().min(1).nullable(),
})

export const stageKitUpdateSchema = z.object({
  equipment_check: z.boolean(),
  rules: z.array(kitRuleInputSchema),
})

// ---------- Камеры и кадры ----------

export const pointSchema = z.tuple([z.number(), z.number()])

export const cameraSchema = z.object({
  id: z.string(),
  site_id: z.string(),
  name: z.string(),
  stream_url: z.string().nullable(),
  zone_polygon: z.array(pointSchema).nullable(),
  frames_count: z.number(),
  created_at: isoDateTime,
})

export const cameraInputSchema = z.object({
  name: z.string().trim().min(1, 'Укажите название').max(64),
  stream_url: z.string().trim().nullable(),
  zone_polygon: z.array(pointSchema).min(3).nullable(),
})

export const referenceFrameSchema = z.object({ image_url: z.string() })

export const detectionSchema = z.object({
  id: z.string(),
  equipment_class: z.string(),
  confidence: z.number(),
  bbox_x: z.number(),
  bbox_y: z.number(),
  bbox_w: z.number(),
  bbox_h: z.number(),
})

export const frameSchema = z.object({
  id: z.string(),
  camera_id: z.string().nullable(),
  camera_name: z.string().nullable(),
  ingest_id: z.string().nullable(),
  source_type: sourceTypeSchema,
  captured_at: isoDateTime.nullable(),
  date_source: dateSourceSchema.nullable(),
  time_state: timeStateSchema,
  time_issue: timeIssueSchema.nullable(),
  image_url: z.string().nullable(),
  detections: z.array(detectionSchema),
})

export const needsReviewSchema = z.object({
  frames: z.array(frameSchema),
  clips: z.array(
    z.object({ ingest_id: z.string(), original_name: z.string(), frames_count: z.number() }),
  ),
})

export const ingestSchema = z.object({
  id: z.string(),
  site_id: z.string(),
  camera_id: z.string(),
  source_type: sourceTypeSchema,
  state: ingestStateSchema,
  slice_step_sec: z.number().nullable(),
  clip_started_at: isoDateTime.nullable(),
  frames_count: z.number(),
  last_frame_at: isoDateTime.nullable(),
})

// ---------- Выводы ----------

export const observationDaySchema = z.object({
  obs_date: isoDate,
  frames_total: z.number(),
  observability: levelSchema,
})

export const observationEquipmentSchema = z.object({
  equipment_class: z.string(),
  name: z.string(),
  min_count: z.number(),
  activity: activitySchema,
  activity_hypothesis: z.boolean(),
  basis_text: z.string(),
  deviation_id: z.string().nullable(),
})

export const observationSchema = z.object({
  obs_date: isoDate,
  expected_stage_name: z.string().nullable(),
  frames_total: z.number(),
  observability: levelSchema,
  equipment: z.array(observationEquipmentSchema),
})

export const deviationRefSchema = z.object({ id: z.string(), title: z.string() })

export const stageStatusSchema = z.object({
  stage_id: z.string(),
  stage_name: z.string(),
  planned_start: isoDate.nullable(),
  planned_end: isoDate.nullable(),
  status: stageStatusValueSchema,
  evidence: evidenceStateSchema,
  fact_label: z.string().nullable(),
  delay_days_min: z.number().nullable(),
  delay_days_max: z.number().nullable(),
  confidence: levelSchema.nullable(),
  basis_text: z.string().nullable(),
  deviations: z.array(deviationRefSchema),
})

export const deviationListItemSchema = z.object({
  id: z.string(),
  site_id: z.string(),
  site_name: z.string(),
  type: deviationTypeSchema,
  is_hypothesis: z.boolean(),
  severity: severitySchema,
  confidence: levelSchema,
  stage_name: z.string().nullable(),
  title: z.string(),
  detected_at: isoDateTime,
  decision: decisionSchema.nullable(),
})

export const decisionRecordSchema = z.object({
  decision: decisionSchema,
  comment: z.string().nullable(),
  decided_by_name: z.string(),
  decided_at: isoDateTime,
})

export const deviationSchema = deviationListItemSchema.extend({
  stage_id: z.string().nullable(),
  period_start: isoDate.nullable(),
  period_end: isoDate.nullable(),
  delay_days_min: z.number().nullable(),
  delay_days_max: z.number().nullable(),
  expected_text: z.string(),
  observed_text: z.string(),
  limits_text: z.string(),
  severity_reason: z.string(),
  cause_text: z.string().nullable(),
  confidence_reason: z.string(),
  rule: z
    .object({
      name: z.string(),
      rule_kind: ruleKindSchema,
      source_ref: z.string().nullable(),
    })
    .nullable(),
  camera_id: z.string().nullable(),
  camera_name: z.string().nullable(),
  observation_date: isoDate.nullable(),
  evidence: z.array(
    z.object({ frame: frameSchema, role: evidenceRoleSchema, caption: z.string().nullable() }),
  ),
  zone_polygon: z.array(pointSchema).nullable(),
  decision_record: decisionRecordSchema.nullable(),
})

export const decisionInputSchema = z.object({
  decision: decisionSchema,
  comment: z.string().nullable(),
})

// ---------- Типы ----------

export type ObjectType = z.infer<typeof objectTypeSchema>
export type WorkDays = z.infer<typeof workDaysSchema>
export type Level = z.infer<typeof levelSchema>
export type Verdict = z.infer<typeof verdictSchema>
export type StageStatusValue = z.infer<typeof stageStatusValueSchema>
export type EvidenceState = z.infer<typeof evidenceStateSchema>
export type MatchKind = z.infer<typeof matchKindSchema>
export type RuleKind = z.infer<typeof ruleKindSchema>
export type SourceType = z.infer<typeof sourceTypeSchema>
export type DateSource = z.infer<typeof dateSourceSchema>
export type TimeIssue = z.infer<typeof timeIssueSchema>
export type Activity = z.infer<typeof activitySchema>
export type DeviationType = z.infer<typeof deviationTypeSchema>
export type Severity = z.infer<typeof severitySchema>
export type Decision = z.infer<typeof decisionSchema>
export type IngestState = z.infer<typeof ingestStateSchema>

export type User = z.infer<typeof userSchema>
export type Site = z.infer<typeof siteSchema>
export type SiteSummary = z.infer<typeof siteSummarySchema>
export type SiteCreate = z.infer<typeof siteCreateSchema>
export type ImportIssue = z.infer<typeof importIssueSchema>
export type ScheduleImport = z.infer<typeof scheduleImportSchema>
export type Stage = z.infer<typeof stageSchema>
export type StageUpdate = z.infer<typeof stageUpdateSchema>
export type EquipmentClass = z.infer<typeof equipmentClassSchema>
export type KitRule = z.infer<typeof kitRuleSchema>
export type KitRuleInput = z.infer<typeof kitRuleInputSchema>
export type StageKit = z.infer<typeof stageKitSchema>
export type StageKitUpdate = z.infer<typeof stageKitUpdateSchema>
export type Point = z.infer<typeof pointSchema>
export type Camera = z.infer<typeof cameraSchema>
export type CameraInput = z.infer<typeof cameraInputSchema>
export type Detection = z.infer<typeof detectionSchema>
export type Frame = z.infer<typeof frameSchema>
export type NeedsReview = z.infer<typeof needsReviewSchema>
export type Ingest = z.infer<typeof ingestSchema>
export type ObservationDay = z.infer<typeof observationDaySchema>
export type ObservationEquipment = z.infer<typeof observationEquipmentSchema>
export type Observation = z.infer<typeof observationSchema>
export type StageStatus = z.infer<typeof stageStatusSchema>
export type DeviationListItem = z.infer<typeof deviationListItemSchema>
export type DeviationDetail = z.infer<typeof deviationSchema>
export type DecisionRecord = z.infer<typeof decisionRecordSchema>
export type DecisionInput = z.infer<typeof decisionInputSchema>
