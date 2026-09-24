/**
 * Демо-данные моков: «Жилой дом · Березники» на 18.09.2026 и синтетический объект —
 * те же, что на макетах «ЛЦТ — MVP: экраны». Формы объектов — контракты из src/api/schemas.ts.
 */
import type {
  Camera,
  DeviationDetail,
  EquipmentClass,
  Frame,
  KitRule,
  Site,
  Stage,
  StageStatus,
  User,
} from '@/api/schemas'

export const TODAY = '2026-09-18'
export const TZ = '+05:00'

export const user: User = {
  id: 'user-1',
  full_name: 'инженер [ФИО]',
  created_at: '2026-09-01T09:00:00+05:00',
}

export const equipmentClasses: EquipmentClass[] = [
  { code: 'excavator', name_ru: 'Экскаватор', group_code: 'earthmoving' },
  { code: 'bulldozer', name_ru: 'Бульдозер', group_code: 'earthmoving' },
  { code: 'roller', name_ru: 'Каток', group_code: 'earthmoving' },
  { code: 'dump_truck', name_ru: 'Самосвал', group_code: 'transport' },
  { code: 'truck', name_ru: 'Грузовик', group_code: 'transport' },
  { code: 'crane_manipulator', name_ru: 'Кран-манипулятор', group_code: 'lifting' },
  { code: 'truck_crane', name_ru: 'Автокран', group_code: 'lifting' },
  { code: 'concrete_mixer', name_ru: 'Автобетоносмеситель', group_code: 'concrete' },
]

export const equipmentGroups: Record<string, string> = {
  earthmoving: 'Землеройная',
  transport: 'Транспортная',
  lifting: 'Подъёмная',
  concrete: 'Бетонная',
}

export function className(code: string): string {
  return equipmentClasses.find((c) => c.code === code)?.name_ru ?? equipmentGroups[code] ?? code
}

export const BEREZNIKI = 'site-berezniki'
export const SYNTHETIC = 'site-synthetic'

export const sites: Site[] = [
  {
    id: BEREZNIKI,
    name: 'Жилой дом · Березники',
    address: 'Березники, [адрес объекта]',
    object_type: 'housing',
    work_days: 'mon_fri',
    timezone: 'Asia/Yekaterinburg',
    state: 'active',
    created_at: '2026-08-20T10:00:00+05:00',
    summary: {
      verdict: 'behind',
      delay_days_min: 4,
      delay_days_max: null,
      measured_stage_name: 'Разработка котлована',
      explanation:
        'Измерено по этапу «Разработка котлована»: плановый конец 14.09, экскаватор наблюдается и 18.09, смены на технику следующего этапа нет. Точность не выше частоты съёмки.',
      observability: 'high',
      cameras_total: 4,
      cameras_reporting: 4,
      last_frame_at: '2026-09-18T14:20:00+05:00',
      frames_total: 0,
      frames_without_time: 0,
      data_age_days: 2,
      critical_count: 0,
      attention_count: 0,
    },
  },
  {
    id: SYNTHETIC,
    name: 'Синтетический объект (демо)',
    address: 'Открытые датасеты · график задан вручную',
    object_type: 'other',
    work_days: 'mon_sat',
    timezone: 'Europe/Moscow',
    state: 'active',
    created_at: '2026-08-01T10:00:00+03:00',
    summary: {
      verdict: 'insufficient_data',
      delay_days_min: null,
      delay_days_max: null,
      measured_stage_name: null,
      explanation:
        'По объекту давно нет кадров: вывод о ходе работ не делается, пока не придут свежие данные.',
      observability: 'low',
      cameras_total: 2,
      cameras_reporting: 0,
      last_frame_at: '2026-08-16T12:00:00+03:00',
      frames_total: 0,
      frames_without_time: 0,
      data_age_days: 35,
      critical_count: 0,
      attention_count: 0,
    },
  },
]

// ---------- Этапы и методика ----------

const G = 'ГЭСН [номер расценки]'

type StageSeed = Omit<Stage, 'works'> & { works: string[]; rules: Omit<KitRule, 'id'>[] }

function rule(
  equipment_class: string,
  rule_kind: KitRule['rule_kind'],
  typical_qty: number | null,
): Omit<KitRule, 'id'> {
  return {
    equipment_class,
    equipment_group: null,
    name: className(equipment_class),
    rule_kind,
    source_ref: rule_kind === 'normative' ? G : rule_kind === 'logical' ? 'по смыслу работы' : null,
    typical_qty,
    is_marker: false,
  }
}

/** Шаблон разобранного графика — его же получает новая стройка при загрузке файла в моках. */
export function stageSeeds(): StageSeed[] {
  const base = {
    match_score: null,
    match_confirmed: true,
    dates_source: 'works' as const,
    merged_windows: 1,
    not_checked_reason: null,
    has_marker: false,
  }
  return [
    {
      ...base,
      id: 'st-prep',
      seq_no: 1,
      name: 'Подготовка территории',
      match_kind: 'exact',
      planned_start: '2026-08-24',
      planned_end: '2026-08-31',
      merged_windows: 9,
      equipment_check: true,
      works: [
        'Отселение домов',
        'Вынос сетей: теплосеть',
        'Снос домов',
        'Вырубка зелёных насаждений',
        'Вынос сетей: водопровод',
        'Вынос сетей: канализация',
        'Вынос сетей: электроснабжение',
        'Планировка территории',
        'Вывоз строительного мусора',
      ],
      rules: [rule('bulldozer', 'normative', 1), rule('dump_truck', 'logical', 2)],
    },
    {
      ...base,
      id: 'st-site',
      seq_no: 2,
      name: 'Обустройство строительной площадки',
      match_kind: 'exact',
      planned_start: '2026-09-01',
      planned_end: '2026-09-05',
      equipment_check: false,
      not_checked_reason:
        'Ограждение, временные сети и бытовой городок не дают видимых признаков по крупной технике. Этап остаётся в графике, но статус по нему не выводится.',
      works: [
        'Устройство ограждения',
        'Временные инженерные сети',
        'Бытовой городок',
        'Пункт мойки колёс',
        'Временные дороги',
        'Освещение площадки',
      ],
      rules: [],
    },
    {
      ...base,
      id: 'st-pit',
      seq_no: 3,
      name: 'Разработка котлована',
      match_kind: 'exact',
      planned_start: '2026-09-06',
      planned_end: '2026-09-14',
      equipment_check: true,
      works: ['Устройство котлована', 'Ограждающие конструкции', 'Закрепление грунтов'],
      rules: [rule('excavator', 'normative', 2), rule('dump_truck', 'logical', 2)],
    },
    {
      ...base,
      id: 'st-base',
      seq_no: 4,
      name: 'Устройство основания',
      match_kind: 'exact',
      planned_start: '2026-09-15',
      planned_end: '2026-09-22',
      equipment_check: true,
      works: [
        'Песчаная подготовка',
        'Щебёночное основание',
        'Бетонная подготовка',
        'Гидроизоляция',
      ],
      rules: [rule('roller', 'normative', 1), rule('dump_truck', 'logical', 1)],
    },
    {
      ...base,
      id: 'st-conc',
      seq_no: 5,
      name: 'Бетонирование плиты',
      match_kind: 'exact',
      planned_start: '2026-09-23',
      planned_end: '2026-10-05',
      equipment_check: true,
      works: ['Армокаркас', 'Устройство фундаментной плиты'],
      rules: [rule('concrete_mixer', 'normative', 2), rule('truck_crane', 'normative', 1)],
    },
    {
      ...base,
      id: 'st-backfill',
      seq_no: 6,
      name: 'Обратная засыпка',
      match_kind: 'exact',
      planned_start: '2026-10-06',
      planned_end: '2026-10-12',
      equipment_check: true,
      works: ['Обратная засыпка'],
      rules: [rule('bulldozer', 'normative', 1), rule('roller', 'normative', 1)],
    },
    {
      ...base,
      id: 'st-finish',
      seq_no: 7,
      name: 'Внутренняя отделка',
      match_kind: 'exact',
      planned_start: '2026-10-13',
      planned_end: '2026-11-30',
      equipment_check: false,
      not_checked_reason: 'Работы внутри здания: крупная техника на кадрах площадки не видна.',
      works: [
        'Отделочные работы',
        'Внутренние сети',
        'Штукатурные работы',
        'Малярные работы',
        'Устройство полов',
        'Облицовка стен',
        'Установка дверей',
        'Установка окон',
        'Электромонтаж',
        'Сантехнические работы',
        'Вентиляция',
        'Слаботочные сети',
        'Уборка помещений',
      ],
      rules: [],
    },
  ]
}

// ---------- Камеры ----------

export const cameras: Omit<Camera, 'frames_count'>[] = [
  {
    id: 'cam-1',
    site_id: BEREZNIKI,
    name: 'К-1',
    stream_url: null,
    zone_polygon: [
      [0.1, 0.35],
      [0.85, 0.3],
      [0.9, 0.9],
      [0.12, 0.92],
    ],
    created_at: '2026-08-20T10:00:00+05:00',
  },
  {
    id: 'cam-2',
    site_id: BEREZNIKI,
    name: 'К-2',
    stream_url: null,
    zone_polygon: [
      [0.3, 0.3],
      [0.95, 0.3],
      [0.95, 0.95],
      [0.35, 0.95],
    ],
    created_at: '2026-08-20T10:00:00+05:00',
  },
  {
    id: 'cam-3',
    site_id: BEREZNIKI,
    name: 'К-3',
    stream_url: 'rtsp://[адрес камеры]/stream1',
    zone_polygon: null,
    created_at: '2026-08-20T10:00:00+05:00',
  },
  {
    id: 'cam-4',
    site_id: BEREZNIKI,
    name: 'К-4',
    stream_url: null,
    zone_polygon: [
      [0.05, 0.4],
      [0.7, 0.35],
      [0.75, 0.95],
      [0.05, 0.95],
    ],
    created_at: '2026-08-20T10:00:00+05:00',
  },
  {
    id: 'cam-s1',
    site_id: SYNTHETIC,
    name: 'К-1',
    stream_url: null,
    zone_polygon: null,
    created_at: '2026-08-01T10:00:00+03:00',
  },
  {
    id: 'cam-s2',
    site_id: SYNTHETIC,
    name: 'К-2',
    stream_url: null,
    zone_polygon: null,
    created_at: '2026-08-01T10:00:00+03:00',
  },
]

// ---------- Кадры ----------

/** Раскладка ленты: камера → [время, источник кадра, классы техники на кадре]. */
type Shot = [time: string, classes: string[]]

const DAY_SHOTS: Record<string, Record<string, Shot[]>> = {
  '2026-09-18': {
    'cam-1': [
      ['08:10', ['excavator']],
      ['09:30', ['excavator', 'dump_truck']],
      ['10:10', ['excavator']],
      ['11:40', ['excavator', 'dump_truck']],
      ['12:50', ['excavator', 'dump_truck']],
      ['14:20', ['excavator', 'dump_truck']],
    ],
    'cam-2': [
      ['08:20', []],
      ['09:40', ['excavator']],
      ['10:30', []],
      ['11:50', ['excavator']],
      ['12:50', []],
      ['14:20', ['excavator']],
    ],
    'cam-3': [
      ['08:30', ['dump_truck']],
      ['09:50', ['dump_truck']],
      ['10:40', []],
      ['11:30', ['dump_truck']],
      ['12:40', ['bulldozer']],
      ['14:00', ['bulldozer']],
    ],
    'cam-4': [
      ['08:00', []],
      ['09:20', ['excavator']],
      ['10:10', []],
      ['11:20', ['excavator']],
      ['13:00', []],
      ['14:20', ['excavator']],
    ],
  },
}

const EARLIER: Record<string, Shot[]> = {
  'cam-1': [
    ['09:10', ['excavator', 'dump_truck']],
    ['12:30', ['excavator']],
    ['15:30', ['excavator', 'excavator']],
  ],
  'cam-2': [
    ['09:10', ['dump_truck']],
    ['13:10', ['excavator']],
    ['15:30', []],
  ],
  'cam-3': [
    ['10:00', ['bulldozer']],
    ['13:10', []],
    ['16:20', ['dump_truck']],
  ],
  'cam-4': [
    ['09:10', ['excavator', 'bulldozer']],
    ['13:10', ['excavator']],
    ['15:30', []],
  ],
}

const SOURCE: Record<string, Pick<Frame, 'source_type' | 'date_source'>> = {
  'cam-1': { source_type: 'photo', date_source: 'exif' },
  'cam-2': { source_type: 'photo', date_source: 'exif' },
  'cam-3': { source_type: 'stream', date_source: 'stream' },
  'cam-4': { source_type: 'photo', date_source: 'stamp' },
}

/** Рамки раскладываются по кадру детерминированно, чтобы снимки не «прыгали» между рендерами. */
function boxes(frameId: string, classes: string[]): Frame['detections'] {
  return classes.map((code, i) => ({
    id: `${frameId}-d${i}`,
    equipment_class: code,
    confidence: 0.82,
    bbox_x: 0.12 + i * 0.4,
    bbox_y: 0.35 + (i % 2) * 0.12,
    bbox_w: 0.32,
    bbox_h: 0.34,
  }))
}

export function buildFrames(): Frame[] {
  const frames: Frame[] = []
  const days = ['2026-09-14', '2026-09-15', '2026-09-16', '2026-09-17', '2026-09-18']
  for (const day of days) {
    const perCamera = DAY_SHOTS[day] ?? EARLIER
    for (const [cameraId, shots] of Object.entries(perCamera)) {
      const camera = cameras.find((c) => c.id === cameraId)!
      shots.forEach(([time, classes], i) => {
        const id = `fr-${cameraId}-${day}-${i}`
        frames.push({
          id,
          camera_id: cameraId,
          camera_name: camera.name,
          ingest_id: null,
          ...SOURCE[cameraId]!,
          captured_at: `${day}T${time}:00${TZ}`,
          time_state: 'ok',
          time_issue: null,
          image_url: null,
          detections: boxes(id, classes),
        })
      })
    }
  }

  const review: [string, Frame['source_type'], Frame['time_issue'], string | null][] = [
    ['fr-nt-1', 'photo', 'stamp_unrecognized', null],
    ['fr-nt-2', 'photo', 'stamp_cropped', null],
    ['fr-nt-3', 'video', 'clip_no_start', 'ing-clip-1'],
    ['fr-nt-4', 'video', 'clip_no_start', 'ing-clip-1'],
    ['fr-nt-5', 'photo', 'stamp_low_conf', null],
  ]
  for (const [id, source_type, time_issue, ingest_id] of review) {
    frames.push({
      id,
      camera_id: 'cam-2',
      camera_name: 'К-2',
      ingest_id,
      source_type,
      captured_at: null,
      date_source: null,
      time_state: 'needs_review',
      time_issue,
      image_url: null,
      detections: [],
    })
  }
  return frames
}

// ---------- Активность техники за дату (результат движка) ----------

export const activityByDay: Record<
  string,
  Record<
    string,
    {
      activity: 'working' | 'idle' | 'unknown'
      hypothesis: boolean
      basis: string
      deviation_id: string | null
    }
  >
> = {
  '2026-09-18': {
    excavator: {
      activity: 'working',
      hypothesis: false,
      basis:
        'Движение: изображение внутри рамки изменилось между 10:10 и 12:50. Зона: внутри зоны котлована.',
      deviation_id: 'dev-missing-roller',
    },
    dump_truck: {
      activity: 'idle',
      hypothesis: true,
      basis:
        'Гипотеза. Движение: нет на 3 кадрах подряд (11:30–14:20). Зона: вне зоны, у въезда. Оба признака указывают на простой.',
      deviation_id: 'dev-idle-dump',
    },
    bulldozer: {
      activity: 'unknown',
      hypothesis: false,
      basis:
        'Движение: пары кадров для сравнения нет (один кадр). Зона: у К-3 не задана. Оснований для вывода нет.',
      deviation_id: null,
    },
  },
}

// ---------- Статусы этапов (результат движка) ----------

export const stageStatuses: Record<string, StageStatus[]> = {
  [BEREZNIKI]: [
    {
      stage_id: 'st-prep',
      stage_name: 'Подготовка территории',
      planned_start: '2026-08-24',
      planned_end: '2026-08-31',
      status: 'on_track',
      evidence: 'marker_confirmed',
      fact_label: '24.08–31.08',
      delay_days_min: null,
      delay_days_max: null,
      confidence: 'high',
      basis_text: 'Смена техники подтверждена',
      deviations: [],
    },
    {
      stage_id: 'st-site',
      stage_name: 'Обустройство строительной площадки',
      planned_start: '2026-09-01',
      planned_end: '2026-09-05',
      status: 'not_checked',
      evidence: 'unknown',
      fact_label: null,
      delay_days_min: null,
      delay_days_max: null,
      confidence: null,
      basis_text: 'Нет крупной техники',
      deviations: [],
    },
    {
      stage_id: 'st-pit',
      stage_name: 'Разработка котлована',
      planned_start: '2026-09-06',
      planned_end: '2026-09-14',
      status: 'behind',
      evidence: 'marker_confirmed',
      fact_label: 'с 06.09, идёт',
      delay_days_min: 4,
      delay_days_max: null,
      confidence: 'medium',
      basis_text: 'Экскаватор виден после планового конца',
      deviations: [{ id: 'dev-idle-dump', title: 'Самосвал вне зоны' }],
    },
    {
      stage_id: 'st-base',
      stage_name: 'Устройство основания',
      planned_start: '2026-09-15',
      planned_end: '2026-09-22',
      status: 'not_started',
      evidence: 'none',
      fact_label: 'не найден',
      delay_days_min: 3,
      delay_days_max: null,
      confidence: 'high',
      basis_text: 'Каток не найден при высокой наблюдаемости',
      deviations: [
        { id: 'dev-missing-roller', title: 'Каток не найден' },
        { id: 'dev-mismatch', title: 'Техника котлована' },
      ],
    },
    ...(
      [
        ['st-conc', 'Бетонирование плиты', '2026-09-23', '2026-10-05'],
        ['st-backfill', 'Обратная засыпка', '2026-10-06', '2026-10-12'],
      ] as const
    ).map(([stage_id, stage_name, planned_start, planned_end]): StageStatus => ({
      stage_id,
      stage_name,
      planned_start,
      planned_end,
      status: 'not_due',
      evidence: 'unknown',
      fact_label: null,
      delay_days_min: null,
      delay_days_max: null,
      confidence: null,
      basis_text: null,
      deviations: [],
    })),
  ],
  [SYNTHETIC]: [],
}

// ---------- Отклонения ----------

type DeviationSeed = Omit<
  DeviationDetail,
  'decision' | 'decision_record' | 'evidence' | 'site_name'
> & {
  evidence: { frame_id: string; role: 'evidence' | 'zone'; caption: string | null }[]
}

export const deviations: DeviationSeed[] = [
  {
    id: 'dev-missing-roller',
    site_id: BEREZNIKI,
    type: 'missing_equipment',
    is_hypothesis: false,
    severity: 'critical',
    confidence: 'medium',
    stage_id: 'st-base',
    stage_name: 'Устройство основания',
    title: 'Каток не найден',
    detected_at: '2026-09-18T14:20:00+05:00',
    period_start: '2026-09-15',
    period_end: '2026-09-18',
    delay_days_min: 3,
    delay_days_max: null,
    expected_text:
      'Каток — не менее 1 (нормативная). Каток — маркерная техника этапа: он отличает устройство основания от соседних этапов.',
    observed_text:
      'Катков не найдено ни на одном кадре за три даты: 16.09, 17.09 и 18.09. На площадке наблюдаются экскаватор (не менее 2) и самосвал (не менее 1): это комплект разработки котлована.',
    limits_text:
      'Отсутствие катка на снимках не доказывает, что работы не начаты: каток мог работать вне времени съёмки. Срок «от 3 дней» — нижняя граница.',
    severity_reason:
      'Нижняя граница: этап не начат к 18.09, плановое начало 15.09. Измерение, не прогноз; точность не выше частоты съёмки.',
    cause_text:
      'Этап «Разработка котлована» ещё не закончен: экскаватор виден и 18.09 (отставание от 4 дн.), поэтому основание не могло начаться. Отклонение «Техника котлована» вызвано тем же.',
    confidence_reason:
      'Средняя: дата 17.09 прочитана со штампа, а не из метаданных. Наблюдаемость высокая: 12 кадров за три даты, четыре камеры, зона основания видна полностью.',
    rule: {
      name: 'Уплотнение щебёночного основания катком',
      rule_kind: 'normative',
      source_ref: 'ГЭСН',
    },
    camera_id: null,
    camera_name: null,
    observation_date: '2026-09-18',
    zone_polygon: null,
    evidence: [
      { frame_id: 'fr-cam-1-2026-09-16-0', role: 'evidence', caption: 'К-1: катка нет' },
      { frame_id: 'fr-cam-4-2026-09-17-1', role: 'evidence', caption: 'К-4: катка нет' },
      { frame_id: 'fr-cam-2-2026-09-18-0', role: 'evidence', caption: 'К-2: зона пуста' },
    ],
  },
  {
    id: 'dev-idle-dump',
    site_id: BEREZNIKI,
    type: 'idle',
    is_hypothesis: true,
    severity: 'attention',
    confidence: 'low',
    stage_id: 'st-pit',
    stage_name: 'Разработка котлована',
    title: 'Самосвал простаивает у въезда',
    detected_at: '2026-09-18T14:20:00+05:00',
    period_start: '2026-09-17',
    period_end: '2026-09-18',
    delay_days_min: null,
    delay_days_max: null,
    expected_text: 'Самосвал работает в рабочей зоне этапа: возит грунт из котлована.',
    observed_text:
      'Самосвал — не менее 1. На кадрах 17.09 и 18.09 он стоит у въезда на площадку, за пределами рабочей зоны. Признаков движения между соседними кадрами нет.',
    limits_text:
      'Это гипотеза, а не нарушение. Машина могла ждать погрузки или стоять на перерыве. Сервис не утверждает, что вывоз грунта остановлен.',
    severity_reason:
      'Потолок для гипотез: «критично» невозможно при любом сроке. Дней отставания у этого отклонения нет: простой не измеряется по датам.',
    cause_text: null,
    confidence_reason:
      'Низкая: съёмка раз в 30 минут, короткую паузу нельзя отличить от простоя. Годные кадры дали две камеры из четырёх.',
    rule: {
      name: 'Простой: нет движения между соседними кадрами на серии кадров и машина вне рабочей зоны камеры',
      rule_kind: 'auxiliary',
      source_ref: 'методика сервиса',
    },
    camera_id: 'cam-2',
    camera_name: 'К-2',
    observation_date: '2026-09-18',
    zone_polygon: cameras[1]!.zone_polygon,
    evidence: [
      { frame_id: 'fr-cam-2-2026-09-17-0', role: 'evidence', caption: 'К-2: у въезда, вне зоны' },
      { frame_id: 'fr-cam-2-2026-09-18-1', role: 'evidence', caption: 'К-2: то же положение' },
      {
        frame_id: 'fr-cam-2-2026-09-18-1',
        role: 'zone',
        caption: 'Рабочая зона камеры К-2 (зелёным). Машина за её пределами, у въезда.',
      },
    ],
  },
  {
    id: 'dev-mismatch',
    site_id: BEREZNIKI,
    type: 'stage_mismatch',
    is_hypothesis: false,
    severity: 'attention',
    confidence: 'medium',
    stage_id: 'st-base',
    stage_name: 'Устройство основания',
    title: 'Техника котлована',
    detected_at: '2026-09-17T16:20:00+05:00',
    period_start: '2026-09-15',
    period_end: '2026-09-17',
    delay_days_min: null,
    delay_days_max: null,
    expected_text: 'По графику идёт «Устройство основания»: ожидается каток (маркер) и самосвал.',
    observed_text:
      'На кадрах 15.09–17.09 экскаватор (не менее 2) и самосвал (не менее 1): набор техники совпадает с комплектом «Разработки котлована».',
    limits_text:
      'Несоответствие не доказывает, что основание не делается: сервис видит только крупную технику на кадрах.',
    severity_reason:
      'Внимание: уверенность средняя, причина уже учтена в отклонении «Каток не найден».',
    cause_text: 'То же, что у «Каток не найден»: котлован ещё не закончен.',
    confidence_reason: 'Средняя: часть дат прочитана со штампа.',
    rule: {
      name: 'Набор техники этапа «Устройство основания»',
      rule_kind: 'normative',
      source_ref: 'ГЭСН',
    },
    camera_id: null,
    camera_name: null,
    observation_date: '2026-09-17',
    zone_polygon: null,
    evidence: [
      {
        frame_id: 'fr-cam-1-2026-09-15-0',
        role: 'evidence',
        caption: 'К-1: экскаватор и самосвал',
      },
      { frame_id: 'fr-cam-4-2026-09-17-0', role: 'evidence', caption: 'К-4: экскаватор' },
    ],
  },
  {
    id: 'dev-stale',
    site_id: SYNTHETIC,
    type: 'stale_data',
    is_hypothesis: false,
    severity: 'attention',
    confidence: 'high',
    stage_id: null,
    stage_name: null,
    title: 'Данные устарели',
    detected_at: '2026-08-16T12:00:00+03:00',
    period_start: '2026-08-16',
    period_end: null,
    delay_days_min: null,
    delay_days_max: null,
    expected_text: 'Кадры по объекту приходят не реже порога устаревания (7 дней).',
    observed_text: 'Последний кадр — 16.08.2026, 35 дней назад.',
    limits_text:
      'Устаревшие данные не говорят о том, что работы остановлены: говорят только о том, что сервис их не видит.',
    severity_reason: 'Внимание: вывод о ходе работ не делается, пока нет свежих кадров.',
    cause_text: null,
    confidence_reason: 'Высокая: дата последнего кадра известна точно.',
    rule: null,
    camera_id: null,
    camera_name: null,
    observation_date: null,
    zone_polygon: null,
    evidence: [],
  },
]
