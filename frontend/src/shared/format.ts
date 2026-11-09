const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export const dlabel = (s: string) => {
  const [m, d] = s.split('-')
  return `${MONTHS[+m - 1]} ${+d}`
}
export const usd = (n: number) => (n < 0 ? '−' : '') + '$' + Math.abs(Math.round(n)).toLocaleString('en-US')
export const kfmt = (n: number) => {
  const a = Math.abs(n),
    s = n < 0 ? '−' : ''
  return a >= 1e6
    ? `${s}$${(a / 1e6).toFixed(2)}M`
    : a >= 1e3
      ? `${s}$${(a / 1e3).toFixed(1)}K`
      : `${s}$${Math.round(a)}`
}
export const tickMoney = (n: number) => {
  const a = Math.abs(n),
    s = n < 0 ? '−' : ''
  return a >= 1e6
    ? `${s}$${+(a / 1e6).toFixed(1)}M`
    : a >= 1e3
      ? `${s}$${Math.round(a / 1e3)}K`
      : `${s}$${Math.round(a)}`
}
export const sum = (a: number[]) => a.reduce((x, y) => x + y, 0)
