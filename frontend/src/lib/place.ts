import type { PlacePoint } from '@/api/types'

/** What the user has in a place field: free text, plus the exact point once they pick one. */
export interface PlaceValue {
  text: string
  point?: { lat: number; lon: number }
}

export function toRequestPlace(value: PlaceValue): string | PlacePoint {
  return value.point ? { ...value.point, name: value.text.trim() } : value.text.trim()
}

export function fromRequestPlace(value: string | PlacePoint): PlaceValue {
  if (typeof value === 'string') return { text: value }
  return {
    text: value.name ?? `${value.lat.toFixed(4)}, ${value.lon.toFixed(4)}`,
    point: { lat: value.lat, lon: value.lon },
  }
}
