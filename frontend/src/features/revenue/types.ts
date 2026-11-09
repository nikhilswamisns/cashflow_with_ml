export interface RevenueForecast {
  history: { date: string; revenue: number }[] // date = "YYYY-MM"
  forecast: { date: string; forecast: number; low: number; high: number }[]
  summary: { last12: number; next12: number; growth_pct: number | null; low12: number; high12: number }
  accuracy: { months: number; avg_miss_pct: number; inside_range: number } | null
  model: string
}
