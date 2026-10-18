/**
 * Интервал снимков, вставленный прямо в ссылку (`?seconds=300` или `&seconds=300`):
 * переносим его в поле интервала, а из ссылки убираем — у части камер в RTSP-ссылке свои
 * параметры, и наш с ними смешивать нельзя (спецификация стрима, §1).
 */
export function takeSeconds(link: string): { url: string; seconds: number | null } {
  const match = /([?&])seconds=(\d+)(?=&|#|$)/.exec(link)
  if (!match) return { url: link, seconds: null }
  const [whole, sep] = match
  const before = link.slice(0, match.index)
  let after = link.slice(match.index + whole.length)
  // «?seconds=1&a=2» → «?a=2»; «?a=1&seconds=2» → «?a=1»
  if (sep === '?' && after.startsWith('&')) after = `?${after.slice(1)}`
  return { url: before + after, seconds: Number(match[2]) }
}
