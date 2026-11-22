export interface RootResponse {
  name: string
  status: string
  version: string
}

export interface HealthResponse {
  status: 'ok' | 'degraded'
  environment: string
  version: string
  checks: Record<string, 'configured' | 'missing'>
  storage: 'durable' | 'in_memory'
}
