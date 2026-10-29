import type { Heatmap, Place, Plan, PlanRequest } from './types'

export class ApiError extends Error {
  code: string
  field?: string
  /** Seconds the server asked us to wait before trying again, when it is busy. */
  retryAfterS?: number

  constructor(code: string, message: string, field?: string, retryAfterS?: number) {
    super(message)
    this.code = code
    this.field = field
    this.retryAfterS = retryAfterS
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(url, init)
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') throw e
    throw new ApiError('network', 'Could not reach the server. Check that the backend is running.')
  }
  const body = await response.json().catch(() => null)
  if (!response.ok) {
    const error = body?.error
    const retryAfter = Number(response.headers.get('Retry-After'))
    throw new ApiError(
      error?.code ?? 'unknown',
      error?.message ?? `The server responded with ${response.status}.`,
      error?.field,
      retryAfter > 0 ? retryAfter : undefined,
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

export async function searchPlaces(text: string, signal?: AbortSignal): Promise<Place[]> {
  const body = await request<{ places: Place[] }>(`/api/places?${new URLSearchParams({ text })}`, { signal })
  return body.places
}

export function reversePlace(lat: number, lon: number): Promise<Place> {
  return request<Place>(`/api/places/reverse?${new URLSearchParams({ lat: String(lat), lon: String(lon) })}`)
}
