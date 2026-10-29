// Mirrors docs/api-contract.md.

export type RiskLevel = 'low' | 'moderate' | 'high' | 'severe' | 'no_travel'

export interface Place {
  name: string
  lat: number
  lon: number
}

/** A point the user chose from suggestions or on the map, sent instead of free text. */
export interface PlacePoint {
  lat: number
  lon: number
  name?: string
}

export interface PlanRequest {
  origin: string | PlacePoint
  destination: string | PlacePoint
  /** Wall-clock time at the origin ("2026-10-30T09:00:00"), or a time with its zone ("...Z"). */
  departure_time: string
  load_weight_lb: number
  sample_interval_mi: 10 | 25 | 50
}

export interface Weather {
  wind_mph: number
  gust_mph: number
  rain_in_hr: number
  snow_in_hr: number
}

export interface Checkpoint {
  index: number
  mile: number
  segment_mi: number
  lat: number
  lon: number
  eta: string
  forecast_time: string
  precip_hour_ending: string
  weather: Weather | null
  levels: Record<'wind' | 'rain' | 'snow', RiskLevel> | null
  load_rule: string | null
  level: RiskLevel | null
}

export interface RouteSummary {
  miles_by_level: Record<RiskLevel, number>
  average_risk: number | null
  worst_level: RiskLevel | null
  rank_reason: string
}

export interface Route {
  id: string
  label: string
  rank: number
  recommended: boolean
  distance_mi: number
  duration_s: number
  arrival_time: string
  geometry: { type: 'LineString'; coordinates: [number, number][] }
  summary: RouteSummary
  checkpoints: Checkpoint[]
}

export interface Warning {
  code: string
  message: string
}

export interface Plan {
  /** `time_zone` is the origin's IANA zone; the app shows every trip time in it. */
  origin: Place & { time_zone: string }
  destination: Place
  departure_time: string
  load_weight_lb: number
  sample_interval_mi: number
  recommended_route_id: string
  corridor_bbox: [number, number, number, number]
  /** The heatmap's grid, passed back unchanged as the /api/heatmap query. */
  heatmap_grid: HeatmapGrid
  routes: Route[]
  warnings: Warning[]
}

export interface HeatmapGrid {
  min_lon: number
  min_lat: number
  step_deg: number
  cols: number
  rows: number
  cells: string
}

export interface HeatmapFrame {
  hour: number
  time: string
  score: (number | null)[]
  wind_mph: (number | null)[]
  rain_in_hr: (number | null)[]
  snow_in_hr: (number | null)[]
}

export interface Heatmap {
  start: string
  step_deg: number
  points: { lat: number; lon: number }[]
  frames: HeatmapFrame[]
}
