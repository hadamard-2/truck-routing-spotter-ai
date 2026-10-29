"""Builds the /api/plan and /api/heatmap responses (docs/api-contract.md) from the services."""

import math
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

from routing import ranking
from routing.risk import SCORE, classify
from routing.services import weather
from routing.services.checkpoints import sample
from routing.services.geocoding import Place, geocode, town_near
from routing.services.routes import RouteOption, route_options

SAMPLE_INTERVALS = (10, 25, 50)
MAX_DEPARTURE_AHEAD = timedelta(days=14)
MAX_DEPARTURE_BEHIND = timedelta(hours=1)
BBOX_PAD_DEG = 0.5
HEATMAP_HOURS = 48
HEATMAP_MAX_POINTS = 250
HEATMAP_MIN_STEP_DEG = 0.25
HEATMAP_MAX_SPAN_DEG = 30


class InvalidInput(Exception):
    def __init__(self, message: str, field: str | None = None):
        super().__init__(message)
        self.message = message
        self.field = field


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')


def parse_time(value, field: str) -> datetime:
    try:
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        raise InvalidInput(f'{field} must be an ISO 8601 date and time.', field) from None
    if dt.tzinfo is None:
        raise InvalidInput(f'{field} must include a time zone, e.g. "2026-10-30T14:00:00Z".', field)
    return dt.astimezone(UTC)


def parse_load(value, field: str = 'load_weight_lb') -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise InvalidInput('load_weight_lb must be a positive whole number of pounds.', field)
    return value


def _place(value, field: str) -> Place:
    if isinstance(value, dict):
        try:
            lat, lon = float(value['lat']), float(value['lon'])
        except (KeyError, TypeError, ValueError):
            raise InvalidInput(f'{field} needs numeric "lat" and "lon".', field) from None
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise InvalidInput(f'{field} is not a valid coordinate.', field)
        return Place(name=f'{lat:.4f}, {lon:.4f}', lat=lat, lon=lon)
    if not isinstance(value, str) or not value.strip():
        raise InvalidInput(f'{field} is required.', field)
    return geocode(value.strip(), field)


def _validate_plan(data) -> tuple[datetime, int, int]:
    for field in ('origin', 'destination', 'departure_time'):
        if not data.get(field):
            raise InvalidInput(f'{field} is required.', field)
    departure = parse_time(data['departure_time'], 'departure_time')
    now = datetime.now(UTC)
    if departure < now - MAX_DEPARTURE_BEHIND:
        raise InvalidInput('Departure is in the past. Pick a time from now on.', 'departure_time')
    if departure > now + MAX_DEPARTURE_AHEAD:
        raise InvalidInput('Departure must be within the next 14 days, the reach of the weather forecast.', 'departure_time')
    load = parse_load(data.get('load_weight_lb'))
    interval = data.get('sample_interval_mi')
    if interval not in SAMPLE_INTERVALS:
        raise InvalidInput('sample_interval_mi must be 10, 25 or 50.', 'sample_interval_mi')
    return departure, load, interval


def _labels(options: list[RouteOption]) -> list[str]:
    """'Direct', then 'Via <town near the middle of the route>' for each alternative."""
    labels = ['Direct']
    for n, option in enumerate(options[1:], start=1):
        mid = min(range(len(option.cum_mi)), key=lambda i: abs(option.cum_mi[i] - option.distance_mi / 2))
        lon, lat = option.coords[mid]
        town = town_near(lat, lon)
        label = f'Via {town}' if town else f'Alternative {n}'
        labels.append(label if label not in labels else f'{label} ({n})')
    return labels


def build_plan(data) -> dict:
    departure, load, interval = _validate_plan(data)

    with ThreadPoolExecutor(max_workers=2) as pool:
        origin_job = pool.submit(_place, data['origin'], 'origin')
        destination_job = pool.submit(_place, data['destination'], 'destination')
        origin, destination = origin_job.result(), destination_job.result()
    if (round(origin.lat, 3), round(origin.lon, 3)) == (round(destination.lat, 3), round(destination.lon, 3)):
        raise InvalidInput('Origin and destination are the same place.', 'destination')

    options = route_options((origin.lon, origin.lat), (destination.lon, destination.lat))
    labels = _labels(options)
    sampled = [sample(option, interval, departure) for option in options]

    points = [(c.lat, c.lon) for checkpoints in sampled for c in checkpoints]
    last_eta = max(c.eta for checkpoints in sampled for c in checkpoints)
    forecasts = weather.hourly(points, departure, last_eta)

    beyond_forecast = False
    routes = []
    for i, (option, checkpoints) in enumerate(zip(options, sampled), start=1):
        out = []
        for c in checkpoints:
            hour = weather.nearest_hour(c.eta)
            w = forecasts[weather.point_key(c.lat, c.lon)].get(hour)
            result = classify(w, load) if w else None
            beyond_forecast |= w is None
            out.append({
                'index': c.index,
                'mile': round(c.mile, 1),
                'segment_mi': round(c.segment_mi, 1),
                'lat': round(c.lat, 5),
                'lon': round(c.lon, 5),
                'eta': iso(c.eta),
                'forecast_time': iso(hour),
                'weather': w and {
                    'wind_mph': w.wind_mph,
                    'gust_mph': w.gust_mph,
                    'rain_in_hr': w.rain_in_hr,
                    'snow_in_hr': w.snow_in_hr,
                },
                'levels': result and result.levels,
                'load_rule': result and result.load_rule,
                'level': result and result.level,
            })
        routes.append({
            'id': f'r{i}',
            'label': labels[i - 1],
            'distance_mi': round(option.distance_mi, 1),
            'duration_s': round(option.duration_s),
            'arrival_time': iso(departure + timedelta(seconds=option.duration_s)),
            'geometry': {'type': 'LineString', 'coordinates': [[round(x, 5), round(y, 5)] for x, y in option.coords]},
            'summary': ranking.summarize(out),
            'checkpoints': out,
        })

    warnings = []
    if len(routes) < 3:
        warnings.append({
            'code': 'fewer_routes',
            'message': f'Only {len(routes)} distinct route{"s" if len(routes) > 1 else ""} found for this trip.',
        })
    if beyond_forecast:
        warnings.append({
            'code': 'beyond_forecast',
            'message': 'Part of the trip is past the end of the weather forecast; those checkpoints have no risk level.',
        })

    ordered = ranking.rank(routes)
    lons = [x for option in options for x, _ in option.coords]
    lats = [y for option in options for _, y in option.coords]
    return {
        'origin': {'name': origin.name, 'lat': origin.lat, 'lon': origin.lon},
        'destination': {'name': destination.name, 'lat': destination.lat, 'lon': destination.lon},
        'departure_time': iso(departure),
        'load_weight_lb': load,
        'sample_interval_mi': interval,
        'recommended_route_id': ordered[0]['id'],
        'corridor_bbox': [
            round(min(lons) - BBOX_PAD_DEG, 2),
            round(min(lats) - BBOX_PAD_DEG, 2),
            round(max(lons) + BBOX_PAD_DEG, 2),
            round(max(lats) + BBOX_PAD_DEG, 2),
        ],
        'routes': ordered,
        'warnings': warnings,
    }


def parse_bbox(value) -> tuple[float, float, float, float]:
    try:
        min_lon, min_lat, max_lon, max_lat = (float(v) for v in str(value).split(','))
    except ValueError:
        raise InvalidInput('bbox must be "minLon,minLat,maxLon,maxLat".', 'bbox') from None
    if not (-180 <= min_lon < max_lon <= 180 and -90 <= min_lat < max_lat <= 90):
        raise InvalidInput('bbox corners are out of order or out of range.', 'bbox')
    if max_lon - min_lon > HEATMAP_MAX_SPAN_DEG or max_lat - min_lat > HEATMAP_MAX_SPAN_DEG:
        raise InvalidInput(f'bbox can span at most {HEATMAP_MAX_SPAN_DEG} degrees each way.', 'bbox')
    return min_lon, min_lat, max_lon, max_lat


def grid(bbox: tuple[float, float, float, float]) -> list[dict]:
    """Evenly spaced points covering the box, at most about HEATMAP_MAX_POINTS of them."""
    min_lon, min_lat, max_lon, max_lat = bbox
    area = (max_lon - min_lon) * (max_lat - min_lat)
    step = max(HEATMAP_MIN_STEP_DEG, math.ceil(math.sqrt(area / HEATMAP_MAX_POINTS) * 20) / 20)
    cols = int((max_lon - min_lon) // step) + 1
    rows = int((max_lat - min_lat) // step) + 1
    return [
        {'lat': round(min_lat + r * step, 3), 'lon': round(min_lon + c * step, 3)}
        for r in range(rows)
        for c in range(cols)
    ]


def build_heatmap(params) -> dict:
    for field in ('bbox', 'start', 'load_weight_lb'):
        if not params.get(field):
            raise InvalidInput(f'{field} is required.', field)
    bbox = parse_bbox(params['bbox'])
    start = parse_time(params['start'], 'start').replace(minute=0, second=0, microsecond=0)
    try:
        load = parse_load(int(params['load_weight_lb']))
    except ValueError:
        raise InvalidInput('load_weight_lb must be a positive whole number of pounds.', 'load_weight_lb') from None

    points = grid(bbox)
    forecasts = weather.hourly([(p['lat'], p['lon']) for p in points], start, start + timedelta(hours=HEATMAP_HOURS))
    series = [forecasts[weather.point_key(p['lat'], p['lon'])] for p in points]

    frames = []
    for hour in range(HEATMAP_HOURS + 1):
        when = start + timedelta(hours=hour)
        cells = [s.get(when) for s in series]
        frames.append({
            'hour': hour,
            'time': iso(when),
            'score': [SCORE[classify(w, load).level] if w else None for w in cells],
            'wind_mph': [w.wind_mph if w else None for w in cells],
            'rain_in_hr': [w.rain_in_hr if w else None for w in cells],
            'snow_in_hr': [w.snow_in_hr if w else None for w in cells],
        })
    return {'start': iso(start), 'bbox': list(bbox), 'points': points, 'frames': frames}

