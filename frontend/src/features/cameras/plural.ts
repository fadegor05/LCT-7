/** Русская форма слова «кадр» для числа: 1 кадр, 2 кадра, 5 кадров. */
export function framesWord(n: number): string {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return 'кадр'
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return 'кадра'
  return 'кадров'
}

/** Русская форма слова «камера» для числа: 1 камера, 3 камеры, 5 камер. */
export function camerasWord(n: number): string {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return 'камера'
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return 'камеры'
  return 'камер'
}
