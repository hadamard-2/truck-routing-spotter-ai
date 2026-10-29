import type { Checkpoint, RiskLevel } from './api/types'

export const LEVELS: RiskLevel[] = ['low', 'moderate', 'high', 'severe', 'no_travel']

// Literal values for Leaflet; keep in sync with the --risk-* tokens in index.css.
export const LEVEL_COLOR: Record<RiskLevel, string> = {
  low: '#65a30d',
  moderate: '#e5b80b',
  high: '#f27a1a',
  severe: '#dc2626',
  no_travel: '#7c2d92',
}

export const LEVEL_BG: Record<RiskLevel, string> = {
  low: 'bg-risk-low',
  moderate: 'bg-risk-moderate',
  high: 'bg-risk-high',
  severe: 'bg-risk-severe',
  no_travel: 'bg-risk-no-travel',
}

export const MAP_COLORS = {
  route: '#007f7f',
  brand: '#f84a5f',
  otherRoute: '#737373',
}

export const LEVEL_LABEL: Record<RiskLevel, string> = {
  low: 'Low',
  moderate: 'Moderate',
  high: 'High',
  severe: 'Severe',
  no_travel: 'No travel',
}

export const UNKNOWN_COLOR = '#a3a3a3'

export const LOAD_RULE_TEXT: Record<string, string> = {
  wind_45_54_over_30000: 'Raised to no travel: 45–54 mph wind with a load over 30,000 lb',
  wind_35_44_over_40000: 'Raised to severe: 35–44 mph wind with a load over 40,000 lb',
}

/** Where the truck is at `time`, interpolated between checkpoint ETAs. */
export function positionAt(checkpoints: Checkpoint[], time: number): [number, number] | null {
  if (checkpoints.length === 0) return null
  const times = checkpoints.map((c) => Date.parse(c.eta))
  if (time <= times[0]) return [checkpoints[0].lat, checkpoints[0].lon]
  for (let i = 1; i < checkpoints.length; i++) {
    if (time <= times[i]) {
      const t = (time - times[i - 1]) / (times[i] - times[i - 1] || 1)
      const a = checkpoints[i - 1]
      const b = checkpoints[i]
      return [a.lat + t * (b.lat - a.lat), a.lon + t * (b.lon - a.lon)]
    }
  }
  const last = checkpoints[checkpoints.length - 1]
  return [last.lat, last.lon]
}
