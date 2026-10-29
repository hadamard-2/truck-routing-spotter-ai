"""Hourly forecasts from Open-Meteo for many points at once.

Units are requested in mph and inches. Open-Meteo's hourly rain, showers and snowfall are the
amounts over the preceding hour, so they are already in/hr; rain is `rain` + `showers`.
"""

import hashlib
import json
from datetime import UTC, datetime, timedelta

import httpx
from django.core.cache import cache

from routing.risk import Weather

from .errors import UpstreamError

FORECAST_URL = 'https://api.open-meteo.com/v1/forecast'
HOURLY = 'wind_speed_10m,wind_gusts_10m,rain,showers,snowfall'
POINTS_PER_REQUEST = 100
TIMEOUT_S = 30
CACHE_S = 15 * 60
# Open-Meteo forecasts reach 16 days; stay a day inside that.
HORIZON = timedelta(days=15)

Key = tuple[float, float]
Series = dict[datetime, Weather]


def point_key(lat: float, lon: float) -> Key:
    """Points are rounded to ~1 km, which is finer than the forecast grid, so nearby checkpoints share a lookup."""
    return round(lat, 2), round(lon, 2)


def _hour(dt: datetime) -> datetime:
    return dt.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


def nearest_hour(dt: datetime) -> datetime:
    return _hour(dt + timedelta(minutes=30))


def parse_location(location: dict) -> Series:
    h = location['hourly']
    series = {}
    for i, stamp in enumerate(h['time']):
        values = [h['wind_speed_10m'][i], h['wind_gusts_10m'][i], h['rain'][i], h['showers'][i], h['snowfall'][i]]
        if any(v is None for v in values):
            continue
        wind, gust, rain, showers, snow = values
        when = datetime.fromisoformat(stamp).replace(tzinfo=UTC)
        series[when] = Weather(wind_mph=wind, gust_mph=gust, rain_in_hr=round(rain + showers, 3), snow_in_hr=snow)
    return series


def _fetch(keys: list[Key], start: datetime, end: datetime) -> list[Series]:
    params = {
        'latitude': ','.join(str(lat) for lat, _ in keys),
        'longitude': ','.join(str(lon) for _, lon in keys),
        'hourly': HOURLY,
        'wind_speed_unit': 'mph',
        'precipitation_unit': 'inch',
        'timezone': 'GMT',
        'start_hour': start.strftime('%Y-%m-%dT%H:%M'),
        'end_hour': end.strftime('%Y-%m-%dT%H:%M'),
    }
    cache_key = 'om:' + hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()
    body = cache.get(cache_key)
    if body is None:
        try:
            response = httpx.get(FORECAST_URL, params=params, timeout=TIMEOUT_S)
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as e:
            raise UpstreamError('weather_unavailable', f'Weather lookup failed: {e}') from e
        cache.set(cache_key, body, CACHE_S)
    locations = body if isinstance(body, list) else [body]
    if len(locations) != len(keys):
        raise UpstreamError('weather_unavailable', 'Weather lookup returned the wrong number of locations.')
    return [parse_location(loc) for loc in locations]


def hourly(points: list[tuple[float, float]], start: datetime, end: datetime) -> dict[Key, Series]:
    """Hourly weather from `start` to `end` for each (lat, lon), keyed by `point_key`.

    Hours past the forecast horizon are simply absent from each series.
    """
    start = _hour(start)
    end = min(_hour(end) + timedelta(hours=1), _hour(datetime.now(UTC) + HORIZON))
    keys = sorted({point_key(lat, lon) for lat, lon in points})
    result: dict[Key, Series] = {k: {} for k in keys}
    if end < start:
        return result
    for i in range(0, len(keys), POINTS_PER_REQUEST):
        chunk = keys[i : i + POINTS_PER_REQUEST]
        for key, series in zip(chunk, _fetch(chunk, start, end)):
            result[key] = series
    return result
