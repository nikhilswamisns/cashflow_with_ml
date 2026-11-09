import { useMemo } from 'react'
import { useTheme } from '../lib/theme'

// Read the CSS variables once per theme change so charts follow light/dark.
export function useChartTokens() {
  const { theme } = useTheme()
  return useMemo(() => {
    const cs = getComputedStyle(document.documentElement)
    const v = (n: string) => cs.getPropertyValue(n).trim()
    return {
      theme,
      surface: v('--surface'), bg: v('--bg'), text: v('--text'), text2: v('--text-2'), border: v('--border'), borderStrong: v('--border-strong'),
      grid: v('--grid'), tick: v('--tick'),
      cash: v('--c-cash'), ml: v('--c-ml'), booked: v('--c-booked'), reseller: v('--c-reseller'), forecast: v('--c-forecast'),
      inC: v('--c-in'), outC: v('--c-out'), floor: v('--c-floor'),
      s1: v('--c-s1'), s2: v('--c-s2'), s3: v('--c-s3'), s4: v('--c-s4'),
    }
  }, [theme])
}
export type Tokens = ReturnType<typeof useChartTokens>

export const alpha = (hex: string, a: number) => {
  const h = hex.replace('#', '')
  const n = parseInt(h.length === 3 ? h.split('').map((c) => c + c).join('') : h, 16)
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`
}
