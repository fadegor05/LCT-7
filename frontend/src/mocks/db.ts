/**
 * In-memory «бэкенд» для моков. Повторяет правила backend, которые видны фронту: 404 для
 * чужой стройки и отсутствующего графика, ленивое создание правил методики, валидацию
 * комплектов (422), пересчёт наблюдений по снимкам. Статусы этапов и отклонения — готовые
 * выводы движка для демо-стройки; у новых строек движок ещё ничего не посчитал.
 */
import type {
  Camera,
  Detection,
  DeviationDetail,
  EquipmentSet,
  Level,
  Observation,
  ParseMode,
  Photo,
  Rule,
  RuleUpdate,
  ScheduleReport,
  SetWrite,
  Site,
  Stage,
  StageDatesUpdate,
  StageStatus,
  SiteSummary,
  UploadReport,
  AssistantAnswer,
  Zone,
} from '@/api/schemas'
import {
  BEREZNIKI,
  DEVIATION_SEEDS,
  equipmentByCode,
  equipmentTypes,
  NO_RULE_REASON,
  PHOTO_SEEDS,
  sites as siteFixtures,
  STAGE_TEMPLATE,
  STATUS_SEEDS,
  SYNTHETIC,
  templateIssues,
  TODAY,
  user,
} from './fixtures'

/** Ошибка домена с HTTP-кодом — хендлер превращает её в `{detail, code}`. */
export class MockError extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly code?: string,
  ) {
    super(message)
  }
}

/** Сценарий поведения ассистента в моках. */
export type AssistantScenario =
  | 'ok'
  | 'unverified'
  | 'out_of_scope'
  | 'rate_limited'
  | 'unavailable'
  | 'timeout'
  | 'too_large'
  | 'no_llm'
  | 'slow'
  | 'unlinked'

type StoredPhoto = Photo & { detections: Detection[] }

interface State {
  sites: Site[]
  schedules: Map<string, ScheduleReport>
  rules: Map<string, Rule[]>
  photos: StoredPhoto[]
  observations: Map<string, Observation[]>
  statuses: Map<string, Map<string, Omit<StageStatus, 'stage_id' | 'stage_name' | 'position'>>>
  deviations: Map<string, DeviationDetail[]>
  cameras: Map<string, Camera[]>
  seq: number
  assistantScenario: AssistantScenario
}

let state: State

const now = () => new Date().toISOString()
const nextId = (prefix: string) => `${prefix}-${++state.seq}`

// ---------- Стройки ----------

export function listSites(): Site[] {
  return state.sites
}

export function getSite(siteId: string): Site {
  const site = state.sites.find((s) => s.id === siteId)
  if (!site) throw new MockError(404, 'Стройка не найдена')
  return site
}

export function createSite(data: { name: string; address?: string | null }): Site {
  const site: Site = {
    id: nextId('site'),
    name: data.name,
    address: data.address ?? null,
    owner_id: user.id,
    created_at: now(),
    updated_at: now(),
  }
  state.sites.push(site)
  return site
}

export function updateSite(siteId: string, data: { name?: string; address?: string | null }): Site {
  const site = getSite(siteId)
  if (data.name !== undefined) site.name = data.name
  if (data.address !== undefined) site.address = data.address
  site.updated_at = now()
  return site
}

// ---------- График ----------

function buildSchedule(
  siteId: string,
  filename: string,
  parseMethod: ScheduleReport['parse_method'] = 'builtin',
): ScheduleReport {
  const scheduleId = nextId('schedule')
  const stages: Stage[] = STAGE_TEMPLATE.map((seed, i) => ({
    id: `${siteId}-stage-${i + 1}`,
    name: seed.name,
    position: i + 1,
    planned_start: seed.start,
    planned_end: seed.end,
    dates_source: 'file',
  }))
  const withDates = stages.filter((s) => s.planned_start && s.planned_end).length
  const issues = templateIssues(scheduleId)
  return {
    id: scheduleId,
    site_id: siteId,
    source_filename: filename,
    imported_at: now(),
    rows_total: stages.length + issues.length,
    rows_parsed: stages.length,
    parse_method: parseMethod,
    stages_with_dates: withDates,
    stages_without_dates: stages.length - withDates,
    stages,
    issues,
  }
}

export function getSchedule(siteId: string): ScheduleReport {
  getSite(siteId)
  const schedule = state.schedules.get(siteId)
  if (!schedule) throw new MockError(404, 'График не загружен')
  return schedule
}

export function importSchedule(
  siteId: string,
  filename: string,
  mode: ParseMode = 'auto',
): ScheduleReport {
  getSite(siteId)
  // В тестах имя файла теряется (jsdom → Node FormData): проверяем только явное расширение.
  if (/\.\w+$/.test(filename) && !/\.(csv|xlsx)$/i.test(filename)) {
    throw new MockError(422, 'Неподдерживаемый формат файла: нужен CSV или XLSX')
  }
  // Переимпорт заменяет график целиком: правила и выводы по старым этапам уходят вместе с ним.
  // В моках «авто» всегда справляется встроенным разбором; LLM — только по явному выбору.
  const schedule = buildSchedule(siteId, filename, mode === 'llm' ? 'llm' : 'builtin')
  state.schedules.set(siteId, schedule)
  state.rules.delete(siteId)
  state.statuses.delete(siteId)
  state.deviations.delete(siteId)
  return schedule
}

export function updateStageDates(siteId: string, stageId: string, data: StageDatesUpdate): Stage {
  const stage = getSchedule(siteId).stages.find((s) => s.id === stageId)
  if (!stage) throw new MockError(404, 'Этап не найден')
  const start = data.planned_start !== undefined ? data.planned_start : stage.planned_start
  const end = data.planned_end !== undefined ? data.planned_end : stage.planned_end
  if (start && end && end < start) {
    throw new MockError(422, 'Дата окончания раньше даты начала')
  }
  Object.assign(stage, { planned_start: start, planned_end: end, dates_source: 'manual' })
  return stage
}

/**
 * Объединение соседних этапов: как на бэкенде — первый этап остаётся с названием и правилом,
 * окно — объединение дат, наборы остальных переезжают в его правило (одинаковые не дублируются).
 */
export function mergeStages(siteId: string, stageIds: readonly string[]): ScheduleReport {
  const schedule = getSchedule(siteId)
  const distinct = [...new Set(stageIds)]
  if (distinct.length < 2) throw new MockError(422, 'Выберите хотя бы два разных этапа')
  const chosen = schedule.stages
    .filter((s) => distinct.includes(s.id))
    .sort((a, b) => a.position - b.position)
  if (chosen.length !== distinct.length) throw new MockError(404, 'Этап не найден')
  const positions = chosen.map((s) => s.position)
  if (positions.some((p, i) => p !== positions[0]! + i)) {
    throw new MockError(422, 'Объединять можно только соседние этапы')
  }

  const [target, ...rest] = chosen as [Stage, ...Stage[]]
  const rules = listRules(siteId)
  const targetRule = rules.find((r) => r.stage_id === target.id)!
  const restRules = rules.filter((r) => rest.some((s) => s.id === r.stage_id))

  const signature = (set: EquipmentSet) =>
    set.requirements
      .map((r) =>
        JSON.stringify([
          r.equipment_type.id,
          r.obligation,
          r.min_count,
          r.gesn_code,
          r.source_note,
        ]),
      )
      .sort()
      .join('|')
  const seen = new Set(targetRule.sets.map(signature))
  let position = Math.max(-1, ...targetRule.sets.map((s) => s.position)) + 1
  for (const restRule of restRules) {
    for (const set of restRule.sets) {
      const key = signature(set)
      if (seen.has(key)) continue
      seen.add(key)
      targetRule.sets.push({ ...set, position: position++ })
    }
  }
  if (!targetRule.is_verifiable && restRules.some((r) => r.is_verifiable)) {
    targetRule.is_verifiable = true
    targetRule.unverifiable_reason = null
  }
  state.rules.set(
    siteId,
    rules.filter((r) => !restRules.includes(r)),
  )

  const starts = chosen.map((s) => s.planned_start).filter((d): d is string => Boolean(d))
  const ends = chosen.map((s) => s.planned_end).filter((d): d is string => Boolean(d))
  target.planned_start = starts.sort()[0] ?? null
  target.planned_end = ends.sort().at(-1) ?? null
  if (chosen.some((s) => s.dates_source === 'manual')) target.dates_source = 'manual'

  for (const stage of rest) state.statuses.get(siteId)?.delete(stage.id)
  schedule.stages = schedule.stages.filter((s) => !rest.includes(s))
  schedule.stages.forEach((stage, i) => {
    stage.position = i + 1
  })
  const withDates = schedule.stages.filter((s) => s.planned_start && s.planned_end).length
  schedule.stages_with_dates = withDates
  schedule.stages_without_dates = schedule.stages.length - withDates
  return schedule
}

// ---------- Методика ----------

export function listEquipmentTypes() {
  return equipmentTypes
}

function materializeRules(stages: readonly Stage[]): Rule[] {
  // Комплекты по умолчанию не подставляются: инженер задаёт их сам (как на бэкенде).
  return stages.map((stage) => ({
    id: `${stage.id}-rule`,
    stage_id: stage.id,
    stage_name: stage.name,
    is_verifiable: false,
    unverifiable_reason: NO_RULE_REASON,
    updated_at: now(),
    sets: [],
  }))
}

export function listRules(siteId: string): Rule[] {
  const schedule = getSchedule(siteId)
  if (!state.rules.has(siteId)) state.rules.set(siteId, materializeRules(schedule.stages))
  return state.rules.get(siteId)!
}

function findRule(siteId: string, ruleId: string): Rule {
  const rule = listRules(siteId).find((r) => r.id === ruleId)
  if (!rule) throw new MockError(404, 'Правило не найдено')
  return rule
}

function findSet(siteId: string, setId: string): { rule: Rule; set: EquipmentSet } {
  for (const rule of listRules(siteId)) {
    const set = rule.sets.find((s) => s.id === setId)
    if (set) return { rule, set }
  }
  throw new MockError(404, 'Комплект не найден')
}

export function updateRule(siteId: string, ruleId: string, data: RuleUpdate): Rule {
  const rule = findRule(siteId, ruleId)
  const reason = data.unverifiable_reason?.trim()
  if (!data.is_verifiable && !reason) {
    throw new MockError(422, 'Укажите причину, почему этап не проверяется')
  }
  rule.is_verifiable = data.is_verifiable
  rule.unverifiable_reason = data.is_verifiable ? null : reason!
  rule.updated_at = now()
  return rule
}

function buildSet(id: string, position: number, data: SetWrite): EquipmentSet {
  if (data.requirements.length === 0) throw new MockError(422, 'Комплект пуст')
  if (!data.requirements.some((r) => r.obligation === 'normative')) {
    throw new MockError(
      422,
      'Логическое требование не может быть единственным доказательством этапа: добавьте нормативное требование',
    )
  }
  return {
    id,
    position,
    requirements: data.requirements.map((r, i) => {
      const type = equipmentTypes.find((e) => e.id === r.equipment_type_id)
      if (!type) throw new MockError(422, 'Неизвестный тип техники')
      const gesn = r.gesn_code?.trim() || null
      const note = r.source_note?.trim() || null
      if (!gesn && !note) throw new MockError(422, 'Укажите номер ГЭСН или источник требования')
      return {
        id: `${id}-req-${i + 1}`,
        equipment_type: type,
        min_count: r.min_count,
        obligation: r.obligation,
        gesn_code: gesn,
        source_note: note,
      }
    }),
  }
}

export function createSet(siteId: string, ruleId: string, data: SetWrite): EquipmentSet {
  const rule = findRule(siteId, ruleId)
  const position = Math.max(0, ...rule.sets.map((s) => s.position)) + 1
  const set = buildSet(nextId('set'), position, data)
  rule.sets.push(set)
  rule.updated_at = now()
  return set
}

export function replaceSet(siteId: string, setId: string, data: SetWrite): EquipmentSet {
  const { rule, set } = findSet(siteId, setId)
  const next = buildSet(set.id, set.position, data)
  rule.sets = rule.sets.map((s) => (s.id === setId ? next : s))
  rule.updated_at = now()
  return next
}

export function deleteSet(siteId: string, setId: string): void {
  const { rule } = findSet(siteId, setId)
  if (rule.is_verifiable && rule.sets.length === 1) {
    throw new MockError(
      422,
      'Нельзя удалить последний комплект проверяемого этапа: добавьте другой комплект или пометьте этап непроверяемым',
    )
  }
  rule.sets = rule.sets.filter((s) => s.id !== setId)
  rule.updated_at = now()
}

export function applyDefaultKits(siteId: string): {
  applied: number
  eligible: number
  unmatched: number
} {
  const rules = listRules(siteId)
  let eligible = 0
  let applied = 0

  for (const rule of rules) {
    // Only process rules with empty sets (no kit assigned)
    if (!rule.is_verifiable && rule.sets.length === 0) {
      eligible++
      // Match by stage name: котлован or свай
      const stageName = (rule.stage_name ?? '').toLowerCase()
      if (stageName.includes('котлован') || stageName.includes('свай')) {
        // Create a default kit with excavator
        const excavator = equipmentTypes.find((e) => e.code === 'ЭХ')
        if (excavator) {
          const set = buildSet(nextId('set'), 1, {
            requirements: [
              {
                equipment_type_id: excavator.id,
                min_count: 1,
                obligation: 'normative',
                gesn_code: null,
                source_note: 'Автоматически подставлено',
              },
            ],
          })
          rule.sets.push(set)
          rule.is_verifiable = true
          rule.unverifiable_reason = null
          rule.updated_at = now()
          applied++
        }
      }
    }
  }

  return {
    applied,
    eligible,
    unmatched: eligible - applied,
  }
}

// ---------- Снимки и наблюдения ----------

const toPhoto = ({ detections: _, ...photo }: StoredPhoto): Photo => photo

function detections(photoId: string, codes: readonly string[]): Detection[] {
  return codes.map((code, i) => {
    const type = equipmentByCode(code)
    const x = 0.08 + (i % 2) * 0.46
    return {
      id: `${photoId}-d${i}`,
      equipment_type_id: type.id,
      equipment_code: type.code,
      equipment_title: type.title,
      bbox: [x, 0.35, x + 0.38, 0.75],
      score: 0.82,
      model_version: 'yoloe-mock',
    }
  })
}

function observability(done: number): Level {
  if (done >= 3) return 'high'
  if (done >= 2) return 'medium'
  return 'low'
}

/** Как ObservationService.recompute: максимум по снимкам, а не сумма; без снимков — записи нет. */
function recompute(siteId: string, date: string): void {
  const list = (state.observations.get(siteId) ?? []).filter((o) => o.observed_on !== date)
  const photos = state.photos.filter((p) => p.site_id === siteId && p.captured_on === date)
  if (photos.length > 0) {
    const counts = new Map<string, number>()
    for (const photo of photos) {
      const perPhoto = new Map<string, number>()
      for (const d of photo.detections)
        perPhoto.set(d.equipment_code, (perPhoto.get(d.equipment_code) ?? 0) + 1)
      for (const [code, n] of perPhoto) counts.set(code, Math.max(counts.get(code) ?? 0, n))
    }
    const done = photos.filter((p) => p.processing_status === 'done').length
    list.push({
      id: `obs-${siteId}-${date}`,
      site_id: siteId,
      observed_on: date,
      photo_count: photos.length,
      observability: observability(done),
      observability_notes: done < 3 ? 'Мало обработанных снимков за дату' : null,
      recomputed_at: now(),
      equipment: [...counts].map(([code, count]) => {
        const type = equipmentByCode(code)
        return {
          equipment_type_id: type.id,
          equipment_code: code,
          equipment_title: type.title,
          count_min: count,
          activity: code === 'excavator_crawler' ? 'works' : 'unknown',
          confidence: photos.some((p) => p.date_source === 'manual') ? 'medium' : 'high',
        }
      }),
    })
  }
  state.observations.set(
    siteId,
    list.sort((a, b) => a.observed_on.localeCompare(b.observed_on)),
  )
}

export function listObservations(siteId: string): Observation[] {
  getSite(siteId)
  // Как бэкенд: от новых к старым.
  return [...(state.observations.get(siteId) ?? [])].reverse()
}

export function getObservation(siteId: string, date: string): Observation {
  const observation = listObservations(siteId).find((o) => o.observed_on === date)
  if (!observation) throw new MockError(404, 'Наблюдение не найдено')
  return observation
}

export function listPhotos(siteId: string, undated: boolean): Photo[] {
  getSite(siteId)
  return state.photos
    .filter((p) => p.site_id === siteId && (!undated || p.captured_on === null))
    .map(toPhoto)
}

export function findPhoto(siteId: string, photoId: string): StoredPhoto {
  getSite(siteId)
  const photo = state.photos.find((p) => p.site_id === siteId && p.id === photoId)
  if (!photo) throw new MockError(404, 'Снимок не найден')
  return photo
}

/** Мок распознаёт дату из имени файла вида `…2026-09-18….jpg`, иначе снимок остаётся без даты. */
export function uploadPhotos(
  siteId: string,
  files: readonly { name: string; type: string }[],
): UploadReport {
  getSite(siteId)
  if (files.length === 0) throw new MockError(422, 'Нет файлов')
  const touched = new Set<string>()
  const items = files.map((file) => {
    if (!file.type.startsWith('image/')) {
      return { filename: file.name, photo: null, error: 'Файл не является изображением' }
    }
    const date = /\d{4}-\d{2}-\d{2}/.exec(file.name)?.[0] ?? null
    const id = nextId('ph')
    const photo: StoredPhoto = {
      id,
      site_id: siteId,
      original_name: file.name,
      width: 1920,
      height: 1080,
      captured_on: date,
      date_source: date ? 'metadata' : null,
      processing_status: 'done',
      uploaded_at: now(),
      detections: detections(id, ['dump_truck']),
    }
    state.photos.push(photo)
    if (date) touched.add(date)
    return { filename: file.name, photo: toPhoto(photo), error: null }
  })
  touched.forEach((date) => recompute(siteId, date))
  const failed = items.filter((i) => i.error).length
  return { items, uploaded: items.length - failed, failed }
}

export function setPhotoDate(siteId: string, photoId: string, capturedOn: string): Photo {
  const photo = findPhoto(siteId, photoId)
  if (capturedOn > TODAY) throw new MockError(422, 'Дата съёмки не может быть в будущем')
  const previous = photo.captured_on
  Object.assign(photo, { captured_on: capturedOn, date_source: 'manual' })
  if (previous) recompute(siteId, previous)
  recompute(siteId, capturedOn)
  return toPhoto(photo)
}

export function redetect(siteId: string, photoId: string): StoredPhoto {
  const photo = findPhoto(siteId, photoId)
  photo.processing_status = 'done'
  if (photo.captured_on) recompute(siteId, photo.captured_on)
  return photo
}

/** Распознаёт необработанные снимки. Меток с processing_status в statuses. */
export function detectBacklog(
  siteId: string,
  statuses: ('pending' | 'failed')[],
): { processed: number; done: number; failed: number; skipped: number } {
  getSite(siteId)
  const photos = state.photos.filter(
    (p) => p.site_id === siteId && statuses.includes(p.processing_status as 'pending' | 'failed'),
  )
  const touched = new Set<string>()
  const report = { processed: 0, done: 0, failed: 0, skipped: 0 }

  photos.forEach((photo) => {
    photo.processing_status = 'done'
    report.processed++
    report.done++
    if (photo.captured_on) touched.add(photo.captured_on)
  })

  touched.forEach((date) => recompute(siteId, date))
  return report
}

// ---------- Оценка ----------

export function listStageStatuses(siteId: string): StageStatus[] {
  const statuses = state.statuses.get(siteId)
  return getSchedule(siteId).stages.map((stage) => {
    // Как RecomputeCoordinator после загрузки графика: окно наступило, кадров нет —
    // «не наблюдалось», а не null (bug-reports/002).
    const s =
      statuses?.get(stage.id) ??
      (stage.planned_start && stage.planned_start <= TODAY
        ? {
            status: 'not_observed' as const,
            delay_days: null,
            confidence: 'low' as const,
            confidence_reason: 'отсутствуют наблюдения в окне этапа',
            computed_at: now(),
          }
        : undefined)
    return {
      stage_id: stage.id,
      stage_name: stage.name,
      position: stage.position,
      status: s?.status ?? null,
      delay_days: s?.delay_days ?? null,
      confidence: s?.confidence ?? null,
      confidence_reason: s?.confidence_reason ?? null,
      computed_at: s?.computed_at ?? null,
    }
  })
}

export function listDeviations(siteId: string): Omit<DeviationDetail, 'evidence'>[] {
  getSite(siteId)
  return (state.deviations.get(siteId) ?? []).map(({ evidence: _, ...d }) => d)
}

export function getDeviation(siteId: string, id: string): DeviationDetail {
  getSite(siteId)
  const deviation = state.deviations.get(siteId)?.find((d) => d.id === id)
  if (!deviation) throw new MockError(404, 'Отклонение не найдено')
  return deviation
}

/** Как AssessmentService.get_summary. */
export function getSummary(siteId: string): SiteSummary {
  const deviations = listDeviations(siteId)
  const counts = {
    critical_count: deviations.filter((d) => d.severity === 'critical').length,
    attention_count: deviations.filter((d) => d.severity === 'attention').length,
  }
  const statuses = [...(state.statuses.get(siteId)?.values() ?? [])]
  const insufficient = { verdict: 'insufficient_data', delay_days_min: null, delay_days_max: null }
  if (!state.schedules.has(siteId) || statuses.length === 0)
    return { ...insufficient, ...counts } as SiteSummary
  const meaningful = statuses.filter((s) => !['not_observed', 'not_checked'].includes(s.status!))
  if (meaningful.length === 0) return { ...insufficient, ...counts } as SiteSummary
  const behind = statuses.filter((s) => s.status === 'behind')
  if (behind.length > 0) {
    const delays = behind.map((s) => s.delay_days).filter((d): d is number => d !== null)
    return {
      verdict: 'behind',
      delay_days_min: delays.length ? Math.min(...delays) : null,
      delay_days_max: delays.length ? Math.max(...delays) : null,
      ...counts,
    }
  }
  return { verdict: 'no_deviations', delay_days_min: null, delay_days_max: null, ...counts }
}

// ---------- Ассистент ----------

export function setAssistantScenario(scenario: AssistantScenario): void {
  state.assistantScenario = scenario
}

export function getAssistantScenario(): AssistantScenario {
  return state.assistantScenario
}

export function assistantEnabled(): boolean {
  return state.assistantScenario !== 'no_llm' && state.assistantScenario !== 'unavailable'
}

/** Парсит query string и извлекает значение сценария ассистента. Неизвестные/отсутствующие значения → 'ok'. */
export function parseAssistantScenario(search: string): AssistantScenario {
  const validScenarios: AssistantScenario[] = [
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
  const params = new URLSearchParams(search)
  const value = params.get('assistant')
  if (value && validScenarios.includes(value as AssistantScenario)) {
    return value as AssistantScenario
  }
  return 'ok'
}

/** Задержка ответа (мс) по сценарию: `slow` — 2000, остальные — без задержки. */
export function assistantDelayMs(scenario: AssistantScenario): number {
  return scenario === 'slow' ? 2000 : 0
}

export function assistantAsk(siteId: string): AssistantAnswer {
  const site = getSite(siteId) // Проверяем, что стройка существует (404)

  if (!assistantEnabled()) {
    throw new MockError(503, 'Ассистент недоступен', 'assistant_unavailable')
  }

  const schedule = getSchedule(siteId) // Проверяем, что график есть (404)

  // Проверяем сценарии ошибок
  switch (state.assistantScenario) {
    case 'rate_limited':
      throw new MockError(429, 'Слишком много вопросов. Повторите через 30 с.', 'rate_limited')
    case 'timeout':
      throw new MockError(504, 'Модель не ответила. Повторите вопрос позже.', 'assistant_timeout')
    case 'out_of_scope':
      throw new MockError(
        422,
        'Ассистент отвечает только на вопросы по отчёту об этой площадке: этапы, отставание, отклонения, техника. Например: «где отставание и на сколько», «что с этапом 3».',
        'out_of_scope',
      )
    case 'too_large':
      throw new MockError(413, 'Отчёт слишком велик для ассистента', 'report_too_large')
  }

  // Успешный ответ: ищем первый этап с отставанием
  const statuses = listStageStatuses(siteId)
  const behindStatus = statuses.find((s) => s.status === 'behind')

  let answer: string
  let stages: AssistantAnswer['stages']

  if (behindStatus && behindStatus.stage_id) {
    const stage = schedule.stages.find((s) => s.id === behindStatus.stage_id)
    // stage_no — это 1-based порядковый номер этапа, отсортированного по position
    const sortedByPosition = [...schedule.stages].sort((a, b) => a.position - b.position)
    const stageNo = sortedByPosition.findIndex((s) => s.id === behindStatus.stage_id) + 1
    const stageName = stage?.name || ''
    const delayDays = behindStatus.delay_days || 0
    answer = `Этап ${stageNo} «${stageName}» отстаёт на ${delayDays} дней.`
    stages =
      state.assistantScenario === 'unlinked'
        ? []
        : [{ ref: `этап ${stageNo}`, stage_id: behindStatus.stage_id }]
  } else {
    // Как на бэкенде: служебная метка площадки заменена на название объекта
    answer = `По площадке «${site.name}» отставаний не найдено.`
    stages = []
  }

  const limits =
    'Проверяются числа, а не смысл: верное число может быть отнесено не к тому этапу, и проверка этого не увидит. Источник истины — сам отчёт, ответ лишь пересказывает его.'

  if (state.assistantScenario === 'unverified') {
    return {
      answer,
      verified: false,
      numbers_not_in_report: ['999'],
      numbers_of_other_site: ['p1: 5'],
      limits,
      site_label: 'p1',
      stages,
    }
  }

  return {
    answer,
    verified: true,
    numbers_not_in_report: [],
    numbers_of_other_site: [],
    limits,
    site_label: 'p1',
    stages,
  }
}

// ---------- Начальное состояние ----------

function seedBerezniki(): void {
  const schedule = buildSchedule(BEREZNIKI, 'grafik_berezniki.xlsx')
  state.schedules.set(BEREZNIKI, schedule)
  const stageId = (position: number) => schedule.stages[position - 1]!.id

  PHOTO_SEEDS.forEach(([date, codes], i) => {
    const id = `ph-${i + 1}`
    state.photos.push({
      id,
      site_id: BEREZNIKI,
      original_name: `IMG_${String(i + 1).padStart(4, '0')}.jpg`,
      width: 1920,
      height: 1080,
      captured_on: date,
      date_source: date ? 'metadata' : null,
      processing_status: date ? 'done' : 'pending',
      uploaded_at: '2026-09-18T11:00:00Z',
      detections: detections(id, codes),
    })
  })
  new Set(PHOTO_SEEDS.map(([d]) => d)).forEach((d) => d && recompute(BEREZNIKI, d))

  state.statuses.set(
    BEREZNIKI,
    new Map(
      Object.entries(STATUS_SEEDS).map(([position, s]) => [
        stageId(Number(position)),
        { ...s, computed_at: '2026-09-18T11:00:00Z' },
      ]),
    ),
  )
  const rules = listRules(BEREZNIKI)
  state.deviations.set(
    BEREZNIKI,
    DEVIATION_SEEDS.map(({ stage, ...d }) => ({
      ...d,
      stage_id: stage ? stageId(stage) : null,
      rule_id: stage ? (rules[stage - 1]?.id ?? null) : null,
    })),
  )
}

// ---------- Камеры ----------

/** Как `_stream_url` и `_interval` бэкенда: ссылка — rtsp(s)/http(s), без ссылки снимать нечего. */
const STREAM_SCHEMES = ['rtsp://', 'rtsps://', 'http://', 'https://']
const DEFAULT_CAPTURE_EVERY_S = 300

export interface CameraWrite {
  name: string
  stream_url: string | null
  capture_every_s: number | null
  zone: Zone | null
}

export function listCameras(siteId: string): Camera[] {
  getSite(siteId)
  return state.cameras.get(siteId) ?? []
}

function findCamera(siteId: string, cameraId: string): Camera {
  const camera = listCameras(siteId).find((c) => c.id === cameraId)
  if (!camera) throw new MockError(404, 'Камера не найдена')
  return camera
}

/** Ссылка проверяется отдельно: текст ошибки не повторяет саму ссылку (в ней могут быть пароли). */
function checkStreamUrl(value: string | null | undefined): string | null {
  const url = value?.trim() ?? ''
  if (!url) return null
  if (!STREAM_SCHEMES.some((scheme) => url.toLowerCase().startsWith(scheme))) {
    throw new MockError(422, 'ссылка на стрим — rtsp://, rtsps://, http:// или https://')
  }
  return url
}

const intervalFor = (url: string | null, every: number | null | undefined) =>
  url === null ? null : every || DEFAULT_CAPTURE_EVERY_S

export function createCamera(siteId: string, data: CameraWrite): Camera {
  const url = checkStreamUrl(data.stream_url)
  const camera: Camera = {
    id: nextId('camera'),
    name: data.name,
    stream_url: url,
    capture_every_s: intervalFor(url, data.capture_every_s),
    last_capture_at: null,
    last_capture_error: null,
    last_capture_attempt_at: null,
    capture_failures: 0,
    zone: data.zone ?? null,
    frames_count: 0,
    created_at: now(),
  }
  state.cameras.set(siteId, [...listCameras(siteId), camera])
  return camera
}

/** Частичная правка: поле, которого нет в `data`, не меняется; `null` — очистить. */
export function updateCamera(siteId: string, cameraId: string, data: Partial<CameraWrite>): Camera {
  const camera = findCamera(siteId, cameraId)
  if (data.name !== undefined) camera.name = data.name
  if (data.stream_url !== undefined) camera.stream_url = checkStreamUrl(data.stream_url)
  if (data.zone !== undefined) camera.zone = data.zone
  if (data.stream_url !== undefined || data.capture_every_s !== undefined) {
    camera.capture_every_s = intervalFor(
      camera.stream_url,
      data.capture_every_s ?? camera.capture_every_s,
    )
  }
  return camera
}

/**
 * «Снять кадр сейчас», как `CameraCaptureService`: кадр — в ленту стройки с датой снимка и
 * источником «channel», итог попытки — у камеры. В моках сбой даёт ссылка с «offline», занятый
 * стрим — ссылка с «busy» (это не попытка, поэтому статус камеры не меняется).
 */
export function captureCamera(siteId: string, cameraId: string): Photo {
  const camera = findCamera(siteId, cameraId)
  if (!camera.stream_url) throw new MockError(422, 'У камеры нет ссылки на стрим')
  if (camera.stream_url.includes('busy')) throw new MockError(409, 'Снимок уже идёт, подождите')
  const at = now()
  camera.last_capture_attempt_at = at
  if (camera.stream_url.includes('offline')) {
    camera.last_capture_error = 'Камера не ответила за 15 с'
    camera.capture_failures = (camera.capture_failures ?? 0) + 1
    throw new MockError(422, camera.last_capture_error)
  }
  const date = at.slice(0, 10)
  const photo: StoredPhoto = {
    id: nextId('ph'),
    site_id: siteId,
    original_name: `stream-${at.slice(0, 19).replace(/[-:T]/g, '')}.jpg`,
    width: 1920,
    height: 1080,
    captured_on: date,
    date_source: 'channel',
    processing_status: 'pending',
    uploaded_at: at,
    detections: [],
  }
  state.photos.push(photo)
  camera.last_capture_at = at
  camera.last_capture_error = null
  camera.capture_failures = 0
  camera.frames_count += 1
  recompute(siteId, date)
  return toPhoto(photo)
}

export function deleteCamera(siteId: string, cameraId: string): void {
  findCamera(siteId, cameraId)
  state.cameras.set(
    siteId,
    listCameras(siteId).filter((c) => c.id !== cameraId),
  )
}

export function resetDb(): void {
  // В режиме тестов всегда 'ok'; в браузере может быть задан через ?assistant=
  const initialScenario =
    import.meta.env.MODE === 'test'
      ? 'ok'
      : typeof window !== 'undefined'
        ? parseAssistantScenario(window.location.search)
        : 'ok'

  state = {
    sites: siteFixtures.map((s) => ({ ...s })),
    schedules: new Map(),
    rules: new Map(),
    photos: [],
    observations: new Map(),
    statuses: new Map(),
    deviations: new Map(),
    cameras: new Map(),
    seq: 0,
    assistantScenario: initialScenario,
  }
  seedBerezniki()
  state.schedules.set(SYNTHETIC, buildSchedule(SYNTHETIC, 'synthetic.csv'))
}

resetDb()
