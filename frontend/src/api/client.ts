import type { Heatmap, Plan, PlanRequest } from './types'

export class ApiError extends Error {
  code: string
  field?: string

  constructor(code: string, message: string, field?: string) {
    super(message)
    this.code = code
    this.field = field
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(url, init)
  } catch {
    throw new ApiError('network', 'Could not reach the server. Check that the backend is running.')
  }
  const body = await response.json().catch(() => null)
  if (!response.ok) {
    const error = body?.error
    throw new ApiError(
      error?.code ?? 'unknown',
      error?.message ?? `The server responded with ${response.status}.`,
      error?.field,
    )
  }
  return body as T
}

export function planTrip(payload: PlanRequest): Promise<Plan> {
  return request<Plan>('/api/plan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function getHeatmap(plan: Plan): Promise<Heatmap> {
  const params = new URLSearchParams({
    bbox: plan.corridor_bbox.join(','),
    start: plan.departure_time,
    load_weight_lb: String(plan.load_weight_lb),
  })
  return request<Heatmap>(`/api/heatmap?${params}`)
}
