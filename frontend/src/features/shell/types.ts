export interface HealthCheck {
  name: string
  ok: boolean
  required: boolean
  detail: string
  fix: string
}

export interface Health {
  status: 'ok' | 'degraded' | 'broken' | string
  checks: HealthCheck[]
}
