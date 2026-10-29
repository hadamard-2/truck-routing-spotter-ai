"""Builds the /api/plan and /api/heatmap responses (docs/api-contract.md) from the services."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from routing import corridor, ranking
from routing.risk import SCORE, classify
from routing.services import weather
from routing.services.checkpoints import sample
from routing.services.geocoding import Place, geocode, town_near
from routing.services.routes import RouteOption, distinct_highway, route_options

SAMPLE_INTERVALS = (10, 25, 50)
MAX_DEPARTURE_AHEAD = timedelta(days=14)
MAX_DEPARTURE_BEHIND = timedelta(hours=1)
BBOX_PAD_DEG = 0.5
HEATMAP_HOURS = 48


class InvalidInput(Exception):
    def __init__(self, message: str, field: str | None = None):
        super().__init__(message)
        self.message = message
        self.field = field


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')


def _parse_iso(value, field: str) -> datetime:
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        raise InvalidInput(f'{field} must be an ISO 8601 date and time.', field) from None


def parse_time(value, field: str) -> datetime:
    dt = _parse_iso(value, field)
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
        name = value.get('name')
        return Place(name=name.strip() if isinstance(name, str) and name.strip() else f'{lat:.4f}, {lon:.4f}', lat=lat, lon=lon)
    if not isinstance(value, str) or not value.strip():
        raise InvalidInput(f'{field} is required.', field)
    return geocode(value.strip(), field)


def _validate_plan(data) -> tuple[datetime, int, int]:
    """Departure comes back as given: with its zone, or as a wall-clock time still to be placed at the origin."""
    for field in ('origin', 'destination', 'departure_time'):
        if not data.get(field):
            raise InvalidInput(f'{field} is required.', field)
    departure = _parse_iso(data['departure_time'], 'departure_time')
    load = parse_load(data.get('load_weight_lb'))
    interval = data.get('sample_interval_mi')
    if interval not in SAMPLE_INTERVALS:
        raise InvalidInput('sample_interval_mi must be 10, 25 or 50.', 'sample_interval_mi')
    return departure, load, interval


def _check_departure(departure: datetime, zone: ZoneInfo) -> None:
    now = datetime.now(UTC)
    if departure < now - MAX_DEPARTURE_BEHIND:
        local = now.astimezone(zone)
        clock = f'{local.hour % 12 or 12}:{local:%M %p}'
        raise InvalidInput(f'Departure is in the past: it is now {clock} at the start.', 'departure_time')
    if departure > now + MAX_DEPARTURE_AHEAD:
        raise InvalidInput('Departure must be within the next 14 days, the reach of the weather forecast.', 'departure_time')


def _labels(options: list[RouteOption]) -> list[str]:
    """'Direct', then each alternative named after the highway that sets it apart ('Via US 70').

    Falls back to the town near the middle of the route, then to 'Alternative n'.
    """
    labels = ['Direct']
    taken: set[str] = set()
    for n, option in enumerate(options[1:], start=1):
        others = [o for o in options if o is not option]
        highway = distinct_highway(option, others, taken)
        if highway:
            taken.add(highway)
            labels.append(f'Via {highway}')
            continue
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

    zone = weather.time_zone(origin.lat, origin.lon)
    if departure.tzinfo is None:
        departure = departure.replace(tzinfo=ZoneInfo(zone))
    departure = departure.astimezone(UTC)
    _check_departure(departure, ZoneInfo(zone))

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
            w = weather.at(forecasts[weather.point_key(c.lat, c.lon)], c.eta)
            result = classify(w, load) if w else None
            beyond_forecast |= w is None
            out.append({
                'index': c.index,
                'mile': round(c.mile, 1),
                'segment_mi': round(c.segment_mi, 1),
                'lat': round(c.lat, 5),
                'lon': round(c.lon, 5),
                'eta': iso(c.eta),
                'forecast_time': iso(weather.nearest_hour(c.eta)),
                'precip_hour_ending': iso(weather.precip_hour(c.eta)),
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
        'origin': {'name': origin.name, 'lat': origin.lat, 'lon': origin.lon, 'time_zone': zone},
        'destination': {'name': destination.name, 'lat': destination.lat, 'lon': destination.lon},
        'departure_time': iso(departure),
        'load_weight_lb': load,
        'sample_interval_mi': interval,
        'recommended_route_id': ordered[0]['id'],
        'heatmap_grid': corridor.build([option.coords for option in options]).params(),
        'corridor_bbox': [
            round(min(lons) - BBOX_PAD_DEG, 2),
            round(min(lats) - BBOX_PAD_DEG, 2),
            round(max(lons) + BBOX_PAD_DEG, 2),
            round(max(lats) + BBOX_PAD_DEG, 2),
        ],
        'routes': ordered,
        'warnings': warnings,
    }


def build_heatmap(params) -> dict:
    for field in ('start', 'load_weight_lb'):
        if not params.get(field):
            raise InvalidInput(f'{field} is required.', field)
    try:
        grid = corridor.Grid.from_params(params)
    except corridor.InvalidGrid as e:
        raise InvalidInput(e.message, e.field) from None
    start = parse_time(params['start'], 'start').replace(minute=0, second=0, microsecond=0)
    try:
        load = parse_load(int(params['load_weight_lb']))
    except ValueError:
        raise InvalidInput('load_weight_lb must be a positive whole number of pounds.', 'load_weight_lb') from None

    points = grid.points()
    forecasts = weather.hourly([(p['lat'], p['lon']) for p in points], start, start + timedelta(hours=HEATMAP_HOURS))
    series = [forecasts[weather.point_key(p['lat'], p['lon'])] for p in points]

    frames = []
    for hour in range(HEATMAP_HOURS + 1):
        when = start + timedelta(hours=hour)
        cells = [weather.at(s, when) for s in series]
        frames.append({
            'hour': hour,
            'time': iso(when),
            'score': [SCORE[classify(w, load).level] if w else None for w in cells],
            'wind_mph': [w.wind_mph if w else None for w in cells],
            'rain_in_hr': [w.rain_in_hr if w else None for w in cells],
            'snow_in_hr': [w.snow_in_hr if w else None for w in cells],
        })
    return {'start': iso(start), 'step_deg': grid.step_deg, 'points': points, 'frames': frames}

