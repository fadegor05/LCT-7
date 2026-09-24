/**
 * In-memory «бэкенд» моков. Держит изменяемое состояние (стройки, этапы, камеры, кадры,
 * решения) и повторяет простые правила сервера: пересчёт маркеров, проблемы импорта,
 * сводку по стройке. Тесты вызывают resetDb() перед каждым кейсом.
 */
import type {
  Camera,
  DecisionRecord,
  DeviationDetail,
  DeviationListItem,
  Frame,
  ImportIssue,
  Ingest,
  KitRule,
  Observation,
  ScheduleImport,
  Site,
  Stage,
  StageKit,
  StageStatus,
} from '@/api/schemas'
import { sortDeviations, visibleDeviations } from '@/lib/deviations'
import * as fx from './fixtures'

interface StageRow extends Stage {
  site_id: string
  rules: KitRule[]
}

interface ImportRow extends Omit<
  ScheduleImport,
  'issues' | 'stages_total' | 'window_overlaps' | 'checked_stages'
> {
  unparsedRows: number[]
}

interface State {
  sites: Site[]
  stages: StageRow[]
  imports: ImportRow[]
  cameras: Omit<Camera, 'frames_count'>[]
  frames: Frame[]
  ingests: Ingest[]
  clips: { ingest_id: string; site_id: string; original_name: string; frames_count: number }[]
  decisions: Record<string, DecisionRecord>
  seq: number
}

let state: State

function seedStages(siteId: string, prefix: string): StageRow[] {
  return fx.stageSeeds().map((seed) => ({
    ...seed,
    id: `${prefix}${seed.id}`,
    site_id: siteId,
    works: seed.works.map((name, i) => ({ id: `${prefix}${seed.id}-w${i}`, name })),
    rules: seed.rules.map((r, i) => ({ ...r, id: `${prefix}${seed.id}-r${i}` })),
  }))
}

export function resetDb(): void {
  state = {
    sites: structuredClone(fx.sites),
    stages: seedStages(fx.BEREZNIKI, ''),
    imports: [
      {
        id: 'imp-berezniki',
        site_id: fx.BEREZNIKI,
        file_name: 'grafik_berezniki.xlsx',
        file_size: 24 * 1024,
        works_total: 38,
        rows_failed: 0,
        uploaded_at: '2026-08-20T10:05:00+05:00',
        unparsedRows: [],
      },
    ],
    cameras: structuredClone(fx.cameras),
    frames: fx.buildFrames(),
    ingests: [
      {
        id: 'ing-stream-3',
        site_id: fx.BEREZNIKI,
        camera_id: 'cam-3',
        source_type: 'stream',
        state: 'running',
        slice_step_sec: 1200,
        clip_started_at: null,
        frames_count: 38,
        last_frame_at: '2026-09-18T14:00:00+05:00',
      },
    ],
    clips: [
      {
        ingest_id: 'ing-clip-1',
        site_id: fx.BEREZNIKI,
        original_name: 'k2_morning.mp4',
        frames_count: 24,
      },
    ],
    decisions: {},
    seq: 1,
  }
  recomputeMarkers(fx.BEREZNIKI)
}

export const nextId = (prefix: string) => `${prefix}-${state.seq++}`
export const nowIso = () => `${fx.TODAY}T15:00:00${fx.TZ}`

// ---------- Стройки ----------

export function listSites(): Site[] {
  return state.sites.filter((s) => s.state === 'active').map(withSummary)
}

export function findSite(id: string): Site | undefined {
  const site = state.sites.find((s) => s.id === id)
  return site && withSummary(site)
}

function withSummary(site: Site): Site {
  if (!site.summary) return site
  const devs = visibleDeviations(siteDeviations(site.id))
  const ok = state.frames.filter((f) => frameSite(f) === site.id)
  return {
    ...site,
    summary: {
      ...site.summary,
      frames_total: ok.filter((f) => f.time_state === 'ok').length,
      frames_without_time: ok.filter((f) => f.time_state === 'needs_review').length,
      critical_count: devs.filter((d) => d.severity === 'critical').length,
      attention_count: devs.filter((d) => d.severity === 'attention').length,
    },
  }
}

export function createSite(
  data: Pick<Site, 'name' | 'address' | 'object_type' | 'work_days'>,
): Site {
  const site: Site = {
    ...data,
    id: nextId('site'),
    timezone: 'Europe/Moscow',
    state: 'draft',
    created_at: nowIso(),
    summary: null,
  }
  state.sites.push(site)
  return site
}

export function updateSite(id: string, patch: Partial<Site>): Site | undefined {
  const site = state.sites.find((s) => s.id === id)
  if (!site) return undefined
  Object.assign(site, patch)
  return withSummary(site)
}

/** Активация черновика. Возвращает текст ошибки, если есть блокирующие проблемы импорта. */
export function activateSite(id: string): Site | string {
  const site = state.sites.find((s) => s.id === id)!
  const current = currentImport(id)
  if (!current) return 'Загрузите график работ'
  if (current.issues.some((i) => i.blocking))
    return 'Сначала исправьте блокирующие проблемы графика'
  site.state = 'active'
  site.summary = {
    verdict: 'insufficient_data',
    delay_days_min: null,
    delay_days_max: null,
    measured_stage_name: null,
    explanation: 'Кадров пока нет: загрузите фото на вкладке «Наблюдения».',
    observability: 'low',
    cameras_total: 0,
    cameras_reporting: 0,
    last_frame_at: null,
    frames_total: 0,
    frames_without_time: 0,
    data_age_days: null,
    critical_count: 0,
    attention_count: 0,
  }
  return site
}

// ---------- График ----------

function stagesOf(siteId: string): StageRow[] {
  return state.stages.filter((s) => s.site_id === siteId).sort((a, b) => a.seq_no - b.seq_no)
}

export function listStages(siteId: string): Stage[] {
  return stagesOf(siteId).map(({ site_id: _s, rules: _r, ...stage }) => stage)
}

export function uploadSchedule(siteId: string, fileName: string, fileSize: number): ScheduleImport {
  state.imports = state.imports.filter((i) => i.site_id !== siteId)
  state.stages = state.stages.filter((s) => s.site_id !== siteId)
  const stages = seedStages(siteId, `${siteId}-`)
  // Как в макете: у «Бетонирования плиты» в файле нет дат, «Отделка» сопоставлена нечётко.
  const conc = stages.find((s) => s.name === 'Бетонирование плиты')!
  conc.planned_start = null
  conc.planned_end = null
  const finish = stages.find((s) => s.name === 'Внутренняя отделка')!
  finish.match_kind = 'fuzzy'
  finish.match_score = 0.74
  finish.match_confirmed = false
  state.stages.push(...stages)
  state.imports.push({
    id: nextId('imp'),
    site_id: siteId,
    file_name: fileName,
    file_size: fileSize,
    works_total: 38,
    rows_failed: 2,
    uploaded_at: nowIso(),
    unparsedRows: [14, 27],
  })
  recomputeMarkers(siteId)
  return currentImport(siteId)!
}

function overlaps(a: StageRow, b: StageRow): boolean {
  if (!a.planned_start || !a.planned_end || !b.planned_start || !b.planned_end) return false
  return a.planned_start <= b.planned_end && b.planned_start <= a.planned_end
}

export function currentImport(siteId: string): ScheduleImport | null {
  const row = state.imports.find((i) => i.site_id === siteId)
  if (!row) return null
  const { unparsedRows, ...rest } = row
  const stages = stagesOf(siteId)
  const issues: ImportIssue[] = unparsedRows.map((n) => ({
    id: `${row.id}-row-${n}`,
    kind: 'row_unparsed',
    row_number: n,
    stage_id: null,
    message: `Строка ${n} файла не разобрана: нет названия этапа`,
    blocking: false,
    resolved_at: null,
  }))
  let overlapCount = 0
  stages.forEach((stage, i) => {
    if (!stage.planned_start || !stage.planned_end) {
      issues.push({
        id: `${stage.id}-no-dates`,
        kind: 'no_dates',
        row_number: null,
        stage_id: stage.id,
        message: `У этапа «${stage.name}» нет дат: задайте их вручную`,
        blocking: true,
        resolved_at: null,
      })
    }
    if (!stage.match_confirmed) {
      issues.push({
        id: `${stage.id}-fuzzy`,
        kind: 'fuzzy_match',
        row_number: null,
        stage_id: stage.id,
        message: `Этап «${stage.name}» сопоставлен нечётко: подтвердите`,
        blocking: true,
        resolved_at: null,
      })
    }
    const next = stages[i + 1]
    if (next && overlaps(stage, next)) {
      overlapCount++
      issues.push({
        id: `${stage.id}-overlap`,
        kind: 'window_overlap',
        row_number: null,
        stage_id: stage.id,
        message: `Окна этапов «${stage.name}» и «${next.name}» пересекаются`,
        blocking: true,
        resolved_at: null,
      })
    }
  })
  return {
    ...rest,
    stages_total: stages.length,
    window_overlaps: overlapCount,
    checked_stages: stages.filter((s) => s.equipment_check).length,
    issues,
  }
}

export function updateStage(
  siteId: string,
  stageId: string,
  patch: Partial<Stage>,
): Stage | undefined {
  const stage = stagesOf(siteId).find((s) => s.id === stageId)
  if (!stage) return undefined
  if (patch.planned_start !== undefined || patch.planned_end !== undefined)
    stage.dates_source = 'manual'
  if (patch.match_confirmed)
    stage.match_kind = stage.match_kind === 'fuzzy' ? 'manual' : stage.match_kind
  Object.assign(stage, patch)
  recomputeMarkers(siteId)
  return listStages(siteId).find((s) => s.id === stageId)
}

// ---------- Методика ----------

const classCode = (r: Pick<KitRule, 'equipment_class' | 'equipment_group'>) =>
  r.equipment_class ?? r.equipment_group ?? ''

/**
 * Маркер — нормативная машина этапа, которой нет в комплектах соседних проверяемых этапов
 * (architecture §7.5: логическое требование маркером быть не может).
 */
function recomputeMarkers(siteId: string): void {
  const stages = stagesOf(siteId)
  stages.forEach((stage, i) => {
    const neighbours = [stages[i - 1], stages[i + 1]].filter((s): s is StageRow =>
      Boolean(s?.equipment_check),
    )
    const neighbourCodes = new Set(neighbours.flatMap((s) => s.rules.map(classCode)))
    stage.rules.forEach((r) => {
      r.is_marker =
        stage.equipment_check && r.rule_kind === 'normative' && !neighbourCodes.has(classCode(r))
    })
    stage.has_marker = stage.rules.some((r) => r.is_marker)
  })
}

function markerExplanation(stage: StageRow, stages: StageRow[]): string | null {
  const markers = stage.rules.filter((r) => r.is_marker).map((r) => r.name.toLowerCase())
  if (!stage.equipment_check) return null
  if (markers.length === 0) {
    return 'Маркеров нет: вся техника этапа встречается у соседей. Этап не даст дат и дней отставания, только статус «совместимо».'
  }
  const i = stages.indexOf(stage)
  const neighbours = [stages[i - 1], stages[i + 1]]
    .filter((s): s is StageRow => Boolean(s))
    .map((s) => s.name.toLowerCase())
  const around = neighbours.length ? ` (${neighbours.join(' и ')})` : ''
  return `Отличает этап от соседних${around}: ${markers.join(', ')}. Только маркеры задают начало и окончание этапа и отставание в днях; общая техника даёт лишь статус «совместимо».`
}

export function listMethodology(siteId: string): StageKit[] {
  const stages = stagesOf(siteId)
  return stages.map((stage) => ({
    stage_id: stage.id,
    stage_name: stage.name,
    planned_start: stage.planned_start,
    planned_end: stage.planned_end,
    equipment_check: stage.equipment_check,
    not_checked_reason: stage.not_checked_reason,
    rules: stage.rules,
    marker_explanation: markerExplanation(stage, stages),
  }))
}

export function updateStageKit(
  siteId: string,
  stageId: string,
  data: { equipment_check: boolean; rules: Omit<KitRule, 'id' | 'name' | 'is_marker'>[] },
): StageKit | undefined {
  const stage = stagesOf(siteId).find((s) => s.id === stageId)
  if (!stage) return undefined
  stage.equipment_check = data.equipment_check
  stage.not_checked_reason = data.equipment_check
    ? null
    : (stage.not_checked_reason ?? 'Отключено инженером')
  stage.rules = data.rules.map((r) => ({
    ...r,
    id: nextId('rule'),
    name: fx.className(classCode(r)),
    is_marker: false,
  }))
  recomputeMarkers(siteId)
  return listMethodology(siteId).find((k) => k.stage_id === stageId)
}

// ---------- Камеры ----------

export function listCameras(siteId: string): Camera[] {
  return state.cameras
    .filter((c) => c.site_id === siteId)
    .map((c) => ({ ...c, frames_count: state.frames.filter((f) => f.camera_id === c.id).length }))
}

export function saveCamera(
  siteId: string,
  cameraId: string | null,
  data: Pick<Camera, 'name' | 'stream_url' | 'zone_polygon'>,
): Camera | string {
  const clash = state.cameras.find(
    (c) => c.site_id === siteId && c.name === data.name && c.id !== cameraId,
  )
  if (clash) return `Камера «${data.name}» уже есть на объекте`
  let camera = cameraId ? state.cameras.find((c) => c.id === cameraId) : undefined
  if (camera) {
    Object.assign(camera, data)
  } else {
    camera = { ...data, id: nextId('cam'), site_id: siteId, created_at: nowIso() }
    state.cameras.push(camera)
  }
  return listCameras(siteId).find((c) => c.id === camera.id)!
}

export function cameraSite(cameraId: string): string | undefined {
  return state.cameras.find((c) => c.id === cameraId)?.site_id
}

// ---------- Кадры и наблюдения ----------

function frameSite(frame: Frame): string | undefined {
  return frame.camera_id ? cameraSite(frame.camera_id) : undefined
}

const frameDate = (frame: Frame) => frame.captured_at?.slice(0, 10) ?? null

export function listFrames(siteId: string, date: string | null): Frame[] {
  return state.frames
    .filter((f) => frameSite(f) === siteId && f.time_state === 'ok')
    .filter((f) => !date || frameDate(f) === date)
    .sort((a, b) => (a.captured_at ?? '').localeCompare(b.captured_at ?? ''))
}

export function observationDays(siteId: string) {
  const byDate = new Map<string, number>()
  for (const f of listFrames(siteId, null)) {
    const d = frameDate(f)!
    byDate.set(d, (byDate.get(d) ?? 0) + 1)
  }
  return [...byDate.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([obs_date, frames_total]) => ({
      obs_date,
      frames_total,
      observability: 'high' as const,
    }))
}

/** Наблюдение за дату: число машин — максимум по кадрам, а не сумма (architecture §8.1). */
export function observation(siteId: string, date: string): Observation | undefined {
  const frames = listFrames(siteId, date)
  if (frames.length === 0) return undefined
  const maxByClass = new Map<string, number>()
  for (const frame of frames) {
    const counts = new Map<string, number>()
    frame.detections.forEach((d) =>
      counts.set(d.equipment_class, (counts.get(d.equipment_class) ?? 0) + 1),
    )
    counts.forEach((n, code) => maxByClass.set(code, Math.max(maxByClass.get(code) ?? 0, n)))
  }
  const activity = fx.activityByDay[date] ?? {}
  const expected = stagesOf(siteId).find(
    (s) => s.planned_start && s.planned_end && s.planned_start <= date && date <= s.planned_end,
  )
  return {
    obs_date: date,
    expected_stage_name: expected?.name ?? null,
    frames_total: frames.length,
    observability: 'high',
    equipment: [...maxByClass.entries()].map(([code, min_count]) => {
      const a = activity[code]
      return {
        equipment_class: code,
        name: fx.className(code),
        min_count,
        activity: a?.activity ?? 'unknown',
        activity_hypothesis: a?.hypothesis ?? false,
        basis_text: a?.basis ?? 'Пары кадров для сравнения нет. Оснований для вывода нет.',
        deviation_id: a?.deviation_id ?? null,
      }
    }),
  }
}

export function needsReview(siteId: string) {
  return {
    frames: state.frames.filter((f) => frameSite(f) === siteId && f.time_state === 'needs_review'),
    clips: state.clips.filter((c) => c.site_id === siteId).map(({ site_id: _s, ...clip }) => clip),
  }
}

export function confirmFrameTime(frameId: string, capturedAt: string): Frame | undefined {
  const frame = state.frames.find((f) => f.id === frameId)
  if (!frame) return undefined
  Object.assign(frame, {
    captured_at: capturedAt,
    date_source: 'manual',
    time_state: 'ok',
    time_issue: null,
  } satisfies Partial<Frame>)
  return frame
}

export function setClipStart(ingestId: string, clipStartedAt: string): Ingest | undefined {
  const clip = state.clips.find((c) => c.ingest_id === ingestId)
  if (!clip) return undefined
  state.clips = state.clips.filter((c) => c !== clip)
  state.frames
    .filter((f) => f.ingest_id === ingestId && f.time_state === 'needs_review')
    .forEach((f) =>
      Object.assign(f, {
        captured_at: clipStartedAt,
        date_source: 'video',
        time_state: 'ok',
        time_issue: null,
      }),
    )
  return {
    id: ingestId,
    site_id: clip.site_id,
    camera_id: 'cam-2',
    source_type: 'video',
    state: 'done',
    slice_step_sec: 300,
    clip_started_at: clipStartedAt,
    frames_count: clip.frames_count,
    last_frame_at: null,
  }
}

export function createIngest(
  siteId: string,
  input: {
    source_type: Ingest['source_type']
    camera_id: string
    files: File[]
    slice_step_sec: number | null
    clip_started_at: string | null
  },
): Ingest {
  const camera = state.cameras.find((c) => c.id === input.camera_id)
  const ingest: Ingest = {
    id: nextId('ing'),
    site_id: siteId,
    camera_id: input.camera_id,
    source_type: input.source_type,
    state: input.source_type === 'stream' ? 'running' : 'done',
    slice_step_sec: input.slice_step_sec,
    clip_started_at: input.clip_started_at,
    frames_count: input.files.length,
    last_frame_at: null,
  }
  state.ingests.push(ingest)
  input.files.forEach((_file, i) => {
    // Моки «находят» время в EXIF у фото и берут старт клипа у видео, если он задан.
    const known = input.source_type === 'photo' || Boolean(input.clip_started_at)
    state.frames.push({
      id: nextId('fr'),
      camera_id: input.camera_id,
      camera_name: camera?.name ?? null,
      ingest_id: ingest.id,
      source_type: input.source_type,
      captured_at: known
        ? `${fx.TODAY}T${String(15 + Math.floor(i / 6)).padStart(2, '0')}:${String((i % 6) * 10).padStart(2, '0')}:00${fx.TZ}`
        : null,
      date_source: known ? (input.source_type === 'photo' ? 'exif' : 'video') : null,
      time_state: known ? 'ok' : 'needs_review',
      time_issue: known ? null : 'clip_no_start',
      image_url: null,
      detections: [],
    })
  })
  if (input.source_type === 'video' && !input.clip_started_at) {
    state.clips.push({
      ingest_id: ingest.id,
      site_id: siteId,
      original_name: input.files[0]?.name ?? 'video',
      frames_count: input.files.length,
    })
  }
  return ingest
}

export function listStreams(siteId: string): Ingest[] {
  return state.ingests.filter((i) => i.site_id === siteId && i.source_type === 'stream')
}

export function stopIngest(ingestId: string): Ingest | undefined {
  const ingest = state.ingests.find((i) => i.id === ingestId)
  if (ingest) ingest.state = 'stopped'
  return ingest
}

// ---------- Выводы ----------

export function stageStatuses(siteId: string): StageStatus[] {
  if (fx.stageStatuses[siteId]) return fx.stageStatuses[siteId]
  // Новая стройка: кадров нет — этапы либо не наступили, либо не проверяются.
  return stagesOf(siteId).map((s) => ({
    stage_id: s.id,
    stage_name: s.name,
    planned_start: s.planned_start,
    planned_end: s.planned_end,
    status: s.equipment_check ? (s.has_marker ? 'not_observed' : 'not_checked') : 'not_checked',
    evidence: 'unknown',
    fact_label: null,
    delay_days_min: null,
    delay_days_max: null,
    confidence: null,
    basis_text: s.equipment_check ? 'Кадров пока нет' : 'Нет крупной техники',
    deviations: [],
  }))
}

function frameById(id: string): Frame {
  return state.frames.find((f) => f.id === id)!
}

function toDetail(seed: (typeof fx.deviations)[number]): DeviationDetail {
  const record = state.decisions[seed.id] ?? null
  return {
    ...seed,
    site_name: state.sites.find((s) => s.id === seed.site_id)?.name ?? '',
    decision: record?.decision ?? null,
    decision_record: record,
    evidence: seed.evidence.map((e) => ({
      frame: frameById(e.frame_id),
      role: e.role,
      caption: e.caption,
    })),
  }
}

function toListItem(d: DeviationDetail): DeviationListItem {
  const {
    id,
    site_id,
    site_name,
    type,
    is_hypothesis,
    severity,
    confidence,
    stage_name,
    title,
    detected_at,
    decision,
  } = d
  return {
    id,
    site_id,
    site_name,
    type,
    is_hypothesis,
    severity,
    confidence,
    stage_name,
    title,
    detected_at,
    decision,
  }
}

export function siteDeviations(siteId: string): DeviationListItem[] {
  return sortDeviations(
    fx.deviations.filter((d) => d.site_id === siteId).map((d) => toListItem(toDetail(d))),
  )
}

export function allDeviations(): DeviationListItem[] {
  const active = new Set(listSites().map((s) => s.id))
  return sortDeviations(
    visibleDeviations(
      fx.deviations.filter((d) => active.has(d.site_id)).map((d) => toListItem(toDetail(d))),
    ),
  )
}

export function findDeviation(id: string): DeviationDetail | undefined {
  const seed = fx.deviations.find((d) => d.id === id)
  return seed && toDetail(seed)
}

export function decide(
  id: string,
  decision: DecisionRecord['decision'],
  comment: string | null,
): DecisionRecord {
  const record: DecisionRecord = {
    decision,
    comment: comment?.trim() || null,
    decided_by_name: fx.user.full_name,
    decided_at: `2026-09-21T10:42:00${fx.TZ}`,
  }
  state.decisions[id] = record
  return record
}

export function undoDecision(id: string): void {
  delete state.decisions[id]
}

// Начальное состояние — в конце модуля, когда все хелперы уже объявлены.
resetDb()
