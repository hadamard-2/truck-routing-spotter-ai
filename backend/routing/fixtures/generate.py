"""Build the sample /api/plan and /api/heatmap responses served while the UI is built.

Routes are real (captured from openrouteservice). Weather is synthetic: one storm
that drifts north-east over time, tuned so every risk level shows up. Risk and
ranking here are a stand-in until routing/risk.py and routing/ranking.py exist.

Run from backend/:  uv run python -m routing.fixtures.generate
"""

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).parent
DEPARTURE = datetime(2026, 10, 30, 14, 0, tzinfo=timezone.utc)
LOAD_WEIGHT_LB = 42000
INTERVALS = (10, 25, 50)
HEATMAP_STEP_DEG = 0.4
HEATMAP_HOURS = 48

LEVELS = ['low', 'moderate', 'high', 'severe', 'no_travel']
ROUTE_LABELS = {'direct': 'Direct', 'via_left': 'Via Lubbock', 'via_right': 'Via Dodge City'}

# (upper bound exclusive, level index); lower bound inclusive.
WIND_BANDS = [(25, 0), (35, 1), (45, 2), (55, 3)]
RAIN_BANDS = [(0.10, 0), (0.25, 1), (0.50, 2), (1.00, 3)]
SNOW_BANDS = [(0.5, 0), (1.0, 1), (2.0, 2), (3.0, 3)]


def iso(dt):
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')


def haversine_mi(a, b):
    lon1, lat1, lon2, lat2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(h))


def band(value, bands, top_inclusive=False):
    for upper, level in bands:
        if value < upper or (top_inclusive and value == upper and upper == bands[-1][0]):
            return level
    return 4


def weather_at(lat, lon, when):
    """Synthetic storm: centre starts near Amarillo and drifts north-east at ~25 mph."""
    hours = (when - DEPARTURE).total_seconds() / 3600
    c_lat, c_lon = 34.6 + 0.12 * hours, -102.6 + 0.10 * hours
    d = haversine_mi((lon, lat), (c_lon, c_lat))
    core = math.exp(-((d / 110) ** 2))
    wind = 10 + 52 * core + 4 * math.sin(lat * 3 + lon * 2)
    precip = 1.3 * core ** 1.5
    cold = lat > 37.0
    return {
        'wind_mph': round(max(wind, 0), 1),
        'gust_mph': round(max(wind * 1.4, 0), 1),
        'rain_in_hr': 0.0 if cold else round(precip, 2),
        'snow_in_hr': round(precip * 3.2, 2) if cold else 0.0,
    }


def classify(weather, load_lb):
    levels = {
        'wind': band(weather['wind_mph'], WIND_BANDS),
        'rain': band(weather['rain_in_hr'], RAIN_BANDS, top_inclusive=True),
        'snow': band(weather['snow_in_hr'], SNOW_BANDS, top_inclusive=True),
    }
    level, load_rule = max(levels.values()), None
    wind = weather['wind_mph']
    if 45 <= wind < 55 and load_lb > 30000 and level < 4:
        level, load_rule = 4, 'wind_45_54_over_30000'
    elif 35 <= wind < 45 and load_lb > 40000 and level < 3:
        level, load_rule = 3, 'wind_35_44_over_40000'
    return {k: LEVELS[v] for k, v in levels.items()}, load_rule, level


def checkpoints_for(coords, distance_mi, duration_s, interval):
    cum = [0.0]
    for a, b in zip(coords, coords[1:]):
        cum.append(cum[-1] + haversine_mi(a, b))
    scale = distance_mi / cum[-1]
    cum = [c * scale for c in cum]

    marks = [m * interval for m in range(int(distance_mi // interval) + 1)]
    if distance_mi - marks[-1] > 0.5:
        marks.append(distance_mi)
    points, j = [], 0
    for mile in marks:
        while j < len(cum) - 2 and cum[j + 1] < mile:
            j += 1
        span = cum[j + 1] - cum[j] or 1
        t = min(max((mile - cum[j]) / span, 0), 1)
        lon = coords[j][0] + t * (coords[j + 1][0] - coords[j][0])
        lat = coords[j][1] + t * (coords[j + 1][1] - coords[j][1])
        points.append((mile, lat, lon))

    out = []
    for i, (mile, lat, lon) in enumerate(points):
        segment = (points[i + 1][0] - mile) if i + 1 < len(points) else 0.0
        eta = DEPARTURE + timedelta(seconds=duration_s * mile / distance_mi)
        forecast_time = eta.replace(minute=0, second=0, microsecond=0)
        weather = weather_at(lat, lon, forecast_time)
        levels, load_rule, level = classify(weather, LOAD_WEIGHT_LB)
        out.append({
            'index': i,
            'mile': round(mile, 1),
            'segment_mi': round(segment, 1),
            'lat': round(lat, 5),
            'lon': round(lon, 5),
            'eta': iso(eta),
            'forecast_time': iso(forecast_time),
            'weather': weather,
            'levels': levels,
            'load_rule': load_rule,
            'level': LEVELS[level],
        })
    return out


def summarize(checkpoints):
    miles = {lvl: 0.0 for lvl in LEVELS}
    for c in checkpoints:
        miles[c['level']] += c['segment_mi']
    total = sum(miles.values()) or 1
    avg = sum(LEVELS.index(lvl) * m for lvl, m in miles.items()) / total
    worst = max((c['level'] for c in checkpoints), key=LEVELS.index)
    return {'miles_by_level': {k: round(v, 1) for k, v in miles.items()}, 'average_risk': round(avg, 2), 'worst_level': worst}


def rank(routes):
    def key(r):
        m = r['summary']['miles_by_level']
        return (m['no_travel'], m['severe'], m['high'], r['summary']['average_risk'], r['duration_s'])

    ordered = sorted(routes, key=key)
    criteria = [('no_travel', 'no-travel miles'), ('severe', 'severe miles'), ('high', 'high miles')]
    for pos, r in enumerate(ordered, start=1):
        r['rank'], r['recommended'] = pos, pos == 1
        # The winner is compared with everyone else; the rest with the route just above them.
        others = ordered[1:] if pos == 1 else [ordered[pos - 2]]
        reason = 'Shorter travel time' if pos == 1 else f"Longer travel time than {others[0]['label']}"
        for lvl, name in criteria:
            values = [o['summary']['miles_by_level'][lvl] for o in others]
            mine = r['summary']['miles_by_level'][lvl]
            if any(v != mine for v in values):
                if pos == 1:
                    reason = f"Fewest {name} ({mine} vs {' and '.join(str(v) for v in values)})"
                else:
                    reason = f"More {name} than {others[0]['label']} ({mine} vs {values[0]})"
                break
        else:
            if any(o['summary']['average_risk'] != r['summary']['average_risk'] for o in others):
                reason = 'Lowest average risk' if pos == 1 else f"Higher average risk than {others[0]['label']}"
        r['summary']['rank_reason'] = reason
    return ordered


def build_plan(raw, interval):
    routes, all_coords = [], []
    for i, (name, fc) in enumerate(raw['routes'].items(), start=1):
        feature = fc['features'][0]
        coords = feature['geometry']['coordinates']
        all_coords += coords
        s = feature['properties']['summary']
        distance, duration = round(s['distance'], 1), round(s['duration'])
        cps = checkpoints_for(coords, distance, duration, interval)
        routes.append({
            'id': f'r{i}',
            'label': ROUTE_LABELS[name],
            'distance_mi': distance,
            'duration_s': duration,
            'arrival_time': iso(DEPARTURE + timedelta(seconds=duration)),
            'geometry': {'type': 'LineString', 'coordinates': [[round(x, 5), round(y, 5)] for x, y in coords]},
            'summary': summarize(cps),
            'checkpoints': cps,
        })
    ordered = rank(routes)
    lons, lats = [c[0] for c in all_coords], [c[1] for c in all_coords]
    pad = 0.5
    bbox = [round(min(lons) - pad, 2), round(min(lats) - pad, 2), round(max(lons) + pad, 2), round(max(lats) + pad, 2)]
    return {
        'origin': {'name': 'Dallas, Texas, USA', 'lat': raw['origin']['lat'], 'lon': raw['origin']['lon']},
        'destination': {'name': 'Denver, Colorado, USA', 'lat': raw['destination']['lat'], 'lon': raw['destination']['lon']},
        'departure_time': iso(DEPARTURE),
        'load_weight_lb': LOAD_WEIGHT_LB,
        'sample_interval_mi': interval,
        'recommended_route_id': ordered[0]['id'],
        'corridor_bbox': bbox,
        'routes': ordered,
        'warnings': [],
    }


def build_heatmap(bbox):
    min_lon, min_lat, max_lon, max_lat = bbox
    points = []
    lat = min_lat
    while lat <= max_lat:
        lon = min_lon
        while lon <= max_lon:
            points.append({'lat': round(lat, 2), 'lon': round(lon, 2)})
            lon += HEATMAP_STEP_DEG
        lat += HEATMAP_STEP_DEG
    frames = []
    for hour in range(HEATMAP_HOURS + 1):
        when = DEPARTURE + timedelta(hours=hour)
        cells = [weather_at(p['lat'], p['lon'], when) for p in points]
        frames.append({
            'hour': hour,
            'time': iso(when),
            'score': [classify(w, LOAD_WEIGHT_LB)[2] for w in cells],
            'wind_mph': [w['wind_mph'] for w in cells],
            'rain_in_hr': [w['rain_in_hr'] for w in cells],
            'snow_in_hr': [w['snow_in_hr'] for w in cells],
        })
    return {'start': iso(DEPARTURE), 'bbox': bbox, 'points': points, 'frames': frames}


def main():
    raw = json.loads((HERE / 'ors_dallas_denver.json').read_text())
    for interval in INTERVALS:
        plan = build_plan(raw, interval)
        (HERE / f'plan_{interval}.json').write_text(json.dumps(plan, separators=(',', ':')))
        print(f'plan_{interval}:', ', '.join(
            f"{r['rank']}. {r['label']} {r['summary']['miles_by_level']} avg={r['summary']['average_risk']}"
            for r in plan['routes']))
    heatmap = build_heatmap(build_plan(raw, INTERVALS[0])['corridor_bbox'])
    (HERE / 'heatmap.json').write_text(json.dumps(heatmap, separators=(',', ':')))
    print('heatmap:', len(heatmap['points']), 'points x', len(heatmap['frames']), 'frames')


if __name__ == '__main__':
    main()
