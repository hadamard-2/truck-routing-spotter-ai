# API contract

The frontend talks only to these two endpoints. Geocoding, routing and weather providers stay behind them. All times are ISO 8601 in UTC (`2026-10-30T14:00:00Z`); the frontend converts to local time for display. Coordinates in GeoJSON geometry are `[lon, lat]`; everywhere else they are `{ "lat": ..., "lon": ... }`. Distances are miles, durations are seconds.

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
  "departure_time": "2026-10-30T14:00:00Z",
  "load_weight_lb": 42000,
  "sample_interval_mi": 25
}
```

- `origin`, `destination`: free text, geocoded by the backend. A `{ "lat": ..., "lon": ... }` object is also accepted (for "use my location").
- `sample_interval_mi`: one of `10`, `25`, `50`.
- `load_weight_lb`: integer, > 0.

### Response `200`

```json
{
  "origin": { "name": "Dallas, Texas, USA", "lat": 32.7767, "lon": -96.797 },
  "destination": { "name": "Denver, Colorado, USA", "lat": 39.7392, "lon": -104.9903 },
  "departure_time": "2026-10-30T14:00:00Z",
  "load_weight_lb": 42000,
  "sample_interval_mi": 25,
  "recommended_route_id": "r1",
  "corridor_bbox": [-106.1, 32.2, -95.9, 40.3],
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
        "rank_reason": "Fewest severe miles (25.0 vs 50.0 and 75.0)"
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
- `forecast_time` is the forecast hour actually used for `eta` (the hour nearest the ETA), so the UI can show both.
- `levels` is the per-condition classification before load rules; `level` is the final checkpoint level. `load_rule` is `null`, `"wind_45_54_over_30000"` or `"wind_35_44_over_40000"` when a load rule raised the level.
- `rank_reason` is a one-line, human-readable reason for the route's position.
- `average_risk` and `worst_level` cover only checkpoints with a forecast; both are `null` when no checkpoint has one.
- `warnings` carries non-fatal notes as `{ "code": "...", "message": "..." }`, e.g. `fewer_routes` (fewer than 3 distinct routes found) or `beyond_forecast` (some checkpoints fall past the forecast horizon; their `level` is `null` and their `weather` is `null`).

## `GET /api/heatmap`

Weather risk over the trip corridor, hour by hour, for the slider.

### Request

`GET /api/heatmap?bbox=-106.1,32.2,-95.9,40.3&start=2026-10-30T14:00:00Z&load_weight_lb=42000`

- `bbox`: `minLon,minLat,maxLon,maxLat`, normally the plan's `corridor_bbox`.
- `start`: hour 0 of the slider.
- `load_weight_lb`: so cell levels apply the same load rules as checkpoints.

### Response `200`

```json
{
  "start": "2026-10-30T14:00:00Z",
  "bbox": [-106.1, 32.2, -95.9, 40.3],
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

- `frames` has 49 entries, hours 0 to 48.
- Every array in a frame is aligned by index with `points`. `score` is the 0–4 risk score; the raw arrays let the UI switch the heatmap to a single condition. Values are `null` where the forecast has no data for that hour.
- `points` is an even grid over `bbox` of at most about 250 points, so the response stays small and within the weather provider's per-minute limits.

## Errors

Any non-2xx response has this body:

```json
{ "error": { "code": "geocode_not_found", "message": "Could not find \"Dallsa, TX\".", "field": "origin" } }
```

| Status | Codes |
|---|---|
| `400` | `invalid_input`, `geocode_not_found` |
| `502` | `geocoding_unavailable`, `routing_unavailable`, `weather_unavailable` |

`field` is present only when the error belongs to one request field.

## What this contract does not decide

The shape carries the results of the open decisions in [problem.md](problem.md) without fixing them: band edges, sustained wind vs. gusts, how `no_travel` miles rank, and how `average_risk` is weighted are backend rules. The UI only displays what it receives.
