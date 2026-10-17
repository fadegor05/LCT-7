export const LAYERS = [
  'sky',
  'ground',
  'gshadow',
  'props',
  'crane',
  'blocks',
  'fx',
  'front',
  'labels',
  'rig',
] as const

export type LayerName = (typeof LAYERS)[number]

/** Куда рисовать: слои SVG по порядку наложения и ссылки на defs (градиенты, узоры, фильтры). */
export interface Ctx {
  layers: Record<LayerName, SVGGElement>
  /** `url(#…)` на элемент из `<defs>` по короткому имени. */
  ref: (name: string) => string
  /** Только `id` без `url()` — для clip-path и подобного. */
  id: (name: string) => string
}
