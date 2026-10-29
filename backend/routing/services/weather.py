"""Hourly forecasts from Open-Meteo for many points at once.

Units are requested in mph and inches. Open-Meteo's hourly rain, showers and snowfall are the
amounts over the preceding hour, so they are already in/hr; rain is `rain` + `showers`.
"""

import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import httpx
from django.core.cache import cache

from routing.risk import Weather

from .errors import UpstreamError

FORECAST_URL = 'https://api.open-meteo.com/v1/forecast'
HOURLY = 'wind_speed_10m,wind_gusts_10m,rain,showers,snowfall'
POINTS_PER_REQUEST = 100
# Batches are fetched at the same time, up to this many at once.
MAX_PARALLEL_REQUESTS = 4
TIMEOUT_S = 30
CACHE_S = 15 * 60
# A point's time zone does not change between requests.
TIME_ZONE_CACHE_S = 24 * 60 * 60
# Open-Meteo forecasts reach 16 days; stay a day inside that.
HORIZON = timedelta(days=15)
# Waits before retrying a rate-limited or failed request. Open-Meteo's limits are per minute,
# so short waits only ride out brief spikes; past them we tell the caller when to come back.
RETRY_WAITS_S = (1, 3)
BUSY_RETRY_AFTER_S = 60
RETRYABLE_STATUS = {429, 500, 502, 503, 504}

Key = tuple[float, float]
Series = dict[datetime, Weather]


def point_key(lat: float, lon: float) -> Key:
    """Points are rounded to ~1 km, which is finer than the forecast grid, so nearby checkpoints share a lookup."""
    return round(lat, 2), round(lon, 2)


def _hour(dt: datetime) -> datetime:
    return dt.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


def nearest_hour(dt: datetime) -> datetime:
    return _hour(dt + timedelta(minutes=30))


def precip_hour(dt: datetime) -> datetime:
    """The stamp of the hourly total covering `dt`: Open-Meteo stamps each total with the end of its hour."""
    return _hour(dt) + timedelta(hours=1)


def at(series: Series, when: datetime) -> Weather | None:
    """Weather the truck meets at `when`: wind at the nearest hour, rain and snow for the hour it is driving in."""
    wind, precip = series.get(nearest_hour(when)), series.get(precip_hour(when))
    if wind is None or precip is None:
        return None
    return Weather(wind_mph=wind.wind_mph, gust_mph=wind.gust_mph, rain_in_hr=precip.rain_in_hr, snow_in_hr=precip.snow_in_hr)


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
        body = _request(params)
        cache.set(cache_key, body, CACHE_S)
    locations = body if isinstance(body, list) else [body]
    if len(locations) != len(keys):
        raise UpstreamError('weather_unavailable', 'Weather lookup returned the wrong number of locations.')
    return [parse_location(loc) for loc in locations]


def _request(params: dict):
    """GET with retries on rate limits, server errors and timeouts."""
    for attempt in range(len(RETRY_WAITS_S) + 1):
        last = attempt == len(RETRY_WAITS_S)
        try:
            response = httpx.get(FORECAST_URL, params=params, timeout=TIMEOUT_S)
        except httpx.TransportError as e:
            if last:
                raise UpstreamError('weather_unavailable', f'Weather lookup failed: {e}') from e
        else:
            if response.status_code not in RETRYABLE_STATUS:
                try:
                    response.raise_for_status()
                    return response.json()
                except (httpx.HTTPError, ValueError) as e:
                    raise UpstreamError('weather_unavailable', f'Weather lookup failed: {e}') from e
            if last and response.status_code == 429:
                raise UpstreamError(
                    'weather_busy',
                    'The weather service is getting too many requests. Try again in a minute.',
                    retry_after_s=BUSY_RETRY_AFTER_S,
                )
            if last:
                raise UpstreamError('weather_unavailable', f'Weather lookup failed with HTTP {response.status_code}.')
        time.sleep(RETRY_WAITS_S[attempt])
    raise AssertionError('unreachable')


def time_zone(lat: float, lon: float) -> str:
    """The IANA time zone at a point, e.g. 'America/Chicago', as Open-Meteo resolves it."""
    lat, lon = point_key(lat, lon)
    cache_key = f'om:tz:{lat},{lon}'
    zone = cache.get(cache_key)
    if zone is None:
        body = _request({'latitude': lat, 'longitude': lon, 'timezone': 'auto', 'forecast_days': 1})
        zone = body.get('timezone') if isinstance(body, dict) else None
        if not zone:
            raise UpstreamError('weather_unavailable', 'Time zone lookup returned no zone.')
        cache.set(cache_key, zone, TIME_ZONE_CACHE_S)
    return zone


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
    chunks = [keys[i : i + POINTS_PER_REQUEST] for i in range(0, len(keys), POINTS_PER_REQUEST)]
    if not chunks:
        return result
    with ThreadPoolExecutor(max_workers=min(len(chunks), MAX_PARALLEL_REQUESTS)) as pool:
        for chunk, fetched in zip(chunks, pool.map(lambda chunk: _fetch(chunk, start, end), chunks)):
            result.update(zip(chunk, fetched))
    return result
