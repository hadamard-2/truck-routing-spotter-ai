# API contract

The frontend talks only to the endpoints below. Geocoding, routing and weather providers stay behind them. Times in responses are ISO 8601 in UTC (`2026-10-30T14:00:00Z`); the plan carries the origin's time zone so a client can show them in the trip's local time. Coordinates in GeoJSON geometry are `[lon, lat]`; everywhere else they are `{ "lat": ..., "lon": ... }`. Distances are miles, durations are seconds.

## Risk levels

Every risk value uses one string enum, with a fixed numeric score used for averaging and for the heatmap:

| Level | Score |
|---|---|
| `low` | 0 |
| `moderate` | 1 |
| `high` | 2 |
| `severe` | 3 |
| `no_travel` | 4 |

## `POST /api/plan`

### Request

```json
{
  "origin": "Dallas, TX",
  "destination": "Denver, CO",
  "departure_time": "2026-10-30T09:00:00",
  "load_weight_lb": 42000,
  "sample_interval_mi": 25
}
```

- `departure_time`: wall-clock time at the origin when it has no zone (`2026-10-30T09:00:00` is 9 AM in Dallas), or an exact instant when it has one (`2026-10-30T14:00:00Z`). It must be from 1 hour ago to 14 days ahead.
- `origin`, `destination`: free text, geocoded by the backend, or an exact point `{ "lat": ..., "lon": ..., "name": "..." }` (from a suggestion or a point picked on the map). `name` is optional and is echoed back as the place name; without it the name is the coordinates.
- `sample_interval_mi`: one of `10`, `25`, `50`.
- `load_weight_lb`: integer, > 0.

### Response `200`

```json
{
  "origin": { "name": "Dallas, Texas, USA", "lat": 32.7767, "lon": -96.797, "time_zone": "America/Chicago" },
  "destination": { "name": "Denver, Colorado, USA", "lat": 39.7392, "lon": -104.9903 },
  "departure_time": "2026-10-30T14:00:00Z",
  "load_weight_lb": 42000,
  "sample_interval_mi": 25,
  "recommended_route_id": "r1",
  "corridor_bbox": [-106.1, 32.2, -95.9, 40.3],
  "heatmap_grid": { "min_lon": -105.93, "min_lat": 31.97, "step_deg": 0.3, "cols": 35, "rows": 28, "cells": "AAAAHgAA..." },
  "routes": [
    {
      "id": "r1",
      "label": "Direct",
      "rank": 1,
      "recommended": true,
      "distance_mi": 782.4,
      "duration_s": 68040,
      "arrival_time": "2026-10-31T08:54:00Z",
      "geometry": { "type": "LineString", "coordinates": [[-96.797, 32.7767], "..."] },
      "summary": {
        "miles_by_level": { "low": 610.0, "moderate": 97.4, "high": 50.0, "severe": 25.0, "no_travel": 0.0 },
        "average_risk": 0.38,
        "worst_level": "severe",
        "rank_reason": "Fewer severe miles than Via US 287 (25 vs 50), but 1 h 10 min slower"
      },
      "checkpoints": [
        {
          "index": 0,
          "mile": 0.0,
          "segment_mi": 25.0,
          "lat": 32.7767,
          "lon": -96.797,
          "eta": "2026-10-30T14:00:00Z",
          "forecast_time": "2026-10-30T14:00:00Z",
          "precip_hour_ending": "2026-10-30T15:00:00Z",
          "weather": { "wind_mph": 12.0, "gust_mph": 21.0, "rain_in_hr": 0.0, "snow_in_hr": 0.0 },
          "levels": { "wind": "low", "rain": "low", "snow": "low" },
          "load_rule": null,
          "level": "low"
        }
      ]
    }
  ],
  "warnings": []
}
```

Field notes:

- `routes` holds up to 3 entries, ordered by `rank` (1 = recommended).
- `checkpoints[i].segment_mi` is the stretch of road this checkpoint stands for; summing `segment_mi` by `level` gives `miles_by_level`, so the UI never re-derives it.
- `origin.time_zone` is the origin's IANA time zone.
- `forecast_time` is the hour wind is read at (the hour nearest `eta`). `precip_hour_ending` is the end of the hour whose rain and snow totals are used: the hour the truck is driving in at `eta`.
- `levels` is the per-condition classification before load rules; `level` is the final checkpoint level. `load_rule` is `null`, `"wind_45_54_over_30000"` or `"wind_35_44_over_40000"` when a load rule raised the level.
- `rank_reason` is a one-line, human-readable reason for the route's position, compared with its neighbour (the recommended route with the runner-up, every other route with the one above it), including the drive-time difference.
- `average_risk` and `worst_level` cover only checkpoints with a forecast; both are `null` when no checkpoint has one.
- `warnings` carries non-fatal notes as `{ "code": "...", "message": "..." }`, e.g. `fewer_routes` (fewer than 3 distinct routes found) or `beyond_forecast` (some checkpoints fall past the forecast horizon; their `level` is `null` and their `weather` is `null`).

## `GET /api/heatmap`

Weather risk over the trip corridor, hour by hour, for the slider.

### Request

`GET /api/heatmap?min_lon=-105.93&min_lat=31.97&step_deg=0.3&cols=35&rows=28&cells=AAAAHgAA...&start=2026-10-30T14:00:00Z&load_weight_lb=42000`

- `min_lon`, `min_lat`, `step_deg`, `cols`, `rows`, `cells`: the plan's `heatmap_grid`, passed back unchanged. The grid's cell at row `r`, column `c` is centred on `(min_lat + r × step_deg, min_lon + c × step_deg)`; `cells` is a base64url bitmask (no padding) over `rows × cols` cells, row by row, most significant bit first, marking the cells inside the corridor. At most 250 cells may be marked.
- `start`: hour 0 of the slider.
- `load_weight_lb`: so cell levels apply the same load rules as checkpoints.

### Response `200`

```json
{
  "start": "2026-10-30T14:00:00Z",
  "step_deg": 0.3,
  "points": [{ "lat": 32.2, "lon": -106.1 }, "..."],
  "frames": [
    {
      "hour": 0,
      "time": "2026-10-30T14:00:00Z",
      "score": [0, 0, 1, 2, "..."],
      "wind_mph": [12.0, 14.5, "..."],
      "rain_in_hr": [0.0, 0.02, "..."],
      "snow_in_hr": [0.0, 0.0, "..."]
    }
  ]
}
```

- `frames` has 49 entries, hours 0 to 48. Each frame reads wind at its `time` and rain and snow for the hour that starts at its `time`, the same rule as checkpoints.
- Every array in a frame is aligned by index with `points`. `score` is the 0–4 risk score; the raw arrays let the UI switch the heatmap to a single condition. Values are `null` where the forecast has no data for that hour.
- `points` are the centres of the marked cells, in row-major order: an even grid of at most 250 points within 25 miles of any route, so the response stays small and within the weather provider's per-minute limits. `step_deg` is the cell size.

## `GET /api/places`

Address suggestions while typing. `GET /api/places?text=Oklahoma%20Ci` returns up to 6 places, best first, with no repeated names:

```json
{ "places": [{ "name": "Oklahoma City, OK, USA", "lat": 35.393761, "lon": -97.602513 }] }
```

Text shorter than 2 characters returns an empty list.

## `GET /api/places/reverse`

The address nearest a point. `GET /api/places/reverse?lat=35.2&lon=-101.83` returns `{ "name": "Southeast 12th Avenue, Amarillo, TX, USA", "lat": 35.2, "lon": -101.83 }`. The returned position is the point asked about, not the address's own position.

## Errors

Any non-2xx response has this body:

```json
{ "error": { "code": "geocode_not_found", "message": "Could not find \"Dallsa, TX\".", "field": "origin" } }
```

| Status | Codes |
|---|---|
| `400` | `invalid_input`, `geocode_not_found` |
| `502` | `geocoding_unavailable`, `routing_unavailable`, `weather_unavailable` |
| `503` | `weather_busy` (the weather provider's rate limit; the response carries `Retry-After` in seconds) |

`field` is present only when the error belongs to one request field.

## What this contract does not decide

The shape carries the results of the open decisions in [problem.md](problem.md) without fixing them: band edges, sustained wind vs. gusts, how `no_travel` miles rank, and how `average_risk` is weighted are backend rules. The UI only displays what it receives.
