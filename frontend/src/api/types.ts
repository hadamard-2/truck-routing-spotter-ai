// Mirrors docs/api-contract.md.

export type RiskLevel = 'low' | 'moderate' | 'high' | 'severe' | 'no_travel'

export interface Place {
  name: string
  lat: number
  lon: number
}

export interface PlanRequest {
  origin: string
  destination: string
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
  weather: Weather | null
  levels: Record<'wind' | 'rain' | 'snow', RiskLevel> | null
  load_rule: string | null
  level: RiskLevel | null
}

export interface RouteSummary {
  miles_by_level: Record<RiskLevel, number>
  average_risk: number
  worst_level: RiskLevel
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
  origin: Place
  destination: Place
  departure_time: string
  load_weight_lb: number
  sample_interval_mi: number
  recommended_route_id: string
  corridor_bbox: [number, number, number, number]
  routes: Route[]
  warnings: Warning[]
}

export interface HeatmapFrame {
  hour: number
  time: string
  score: number[]
  wind_mph: number[]
  rain_in_hr: number[]
  snow_in_hr: number[]
}

export interface Heatmap {
  start: string
  bbox: [number, number, number, number]
  points: { lat: number; lon: number }[]
  frames: HeatmapFrame[]
}
