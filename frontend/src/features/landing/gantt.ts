/** Этап графика: начало и конец плана в долях года, отставание и опережение факта в долях года. */
export interface Stage {
  name: string
  start: number
  end: number
  lag: number
  /** Насколько факт опережает «сегодня». Нет — идёт точно по плану. */
  lead?: number
}

/** Условный график жилого дома на год — для фона лендинга. */
export const STAGES: readonly Stage[] = [
  { name: 'Ограждение площадки', start: 0.0, end: 0.06, lag: 0 },
  { name: 'Подготовка территории', start: 0.03, end: 0.12, lag: 0 },
  { name: 'Котлован', start: 0.08, end: 0.22, lag: 0 },
  { name: 'Шпунтовое ограждение', start: 0.1, end: 0.2, lag: 0 },
  { name: 'Фундаментная плита', start: 0.18, end: 0.34, lag: 0.04 },
  { name: 'Гидроизоляция', start: 0.26, end: 0.36, lag: 0 },
  { name: 'Монолитный каркас', start: 0.32, end: 0.68, lag: 0 },
  { name: 'Обратная засыпка', start: 0.36, end: 0.44, lag: 0.05 },
  { name: 'Кладка стен', start: 0.48, end: 0.74, lag: 0, lead: 0.05 },
  { name: 'Наружные сети', start: 0.44, end: 0.62, lag: 0.07 },
  { name: 'Кровля', start: 0.66, end: 0.78, lag: 0, lead: 0.03 },
  { name: 'Внутренние сети', start: 0.6, end: 0.86, lag: 0, lead: 0.04 },
  { name: 'Фасад', start: 0.72, end: 0.92, lag: 0.03 },
  { name: 'Благоустройство', start: 0.86, end: 1.0, lag: 0 },
]

export const MONTHS = [
  'Янв',
  'Фев',
  'Мар',
  'Апр',
  'Май',
  'Июн',
  'Июл',
  'Авг',
  'Сен',
  'Окт',
  'Ноя',
  'Дек',
]

const MONTHS_GEN = [
  'января',
  'февраля',
  'марта',
  'апреля',
  'мая',
  'июня',
  'июля',
  'августа',
  'сентября',
  'октября',
  'ноября',
  'декабря',
]

export type StageState = 'idle' | 'ontrack' | 'behind' | 'ahead' | 'done'

/** Факт этапа на дату `k` (доля года): докуда дошла работа и в каком она статусе. */
export function stageAt(stage: Stage, k: number): { fact: number; state: StageState } {
  if (k < stage.start) return { fact: stage.start, state: 'idle' }
  const lead = stage.lead ?? 0
  const fact = Math.max(stage.start, Math.min(stage.end, k - stage.lag + lead))
  if (fact >= stage.end) return { fact, state: 'done' }
  if (stage.lag && k - stage.start > stage.lag) return { fact, state: 'behind' }
  return { fact, state: lead ? 'ahead' : 'ontrack' }
}

/** Подпись даты для доли года. */
export function dayLabel(k: number): string {
  const month = Math.min(11, Math.floor(k * 12))
  const day = Math.min(28, Math.floor((k * 12 - month) * 28) + 1)
  return `${day} ${MONTHS_GEN[month]}`
}
