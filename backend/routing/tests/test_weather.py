import threading
from datetime import UTC, datetime

import pytest

import httpx

from routing.risk import Weather
from routing.services import weather
from routing.services.errors import UpstreamError


def location(times, wind, gust, rain, showers, snow):
    return {
        'hourly': {
            'time': times,
            'wind_speed_10m': wind,
            'wind_gusts_10m': gust,
            'rain': rain,
            'showers': showers,
            'snowfall': snow,
        }
    }


def test_parse_location_adds_showers_to_rain_and_skips_gaps():
    series = weather.parse_location(location(
        ['2026-10-30T14:00', '2026-10-30T15:00'],
        [12.0, None], [20.0, 25.0], [0.1, 0.0], [0.05, 0.0], [0.0, 0.0],
    ))
    assert series == {
        datetime(2026, 10, 30, 14, tzinfo=UTC): Weather(wind_mph=12.0, gust_mph=20.0, rain_in_hr=0.15, snow_in_hr=0.0),
    }


@pytest.mark.parametrize('minute, hour', [(0, 14), (29, 14), (30, 15), (59, 15)])
def test_nearest_hour(minute, hour):
    assert weather.nearest_hour(datetime(2026, 10, 30, 14, minute, tzinfo=UTC)).hour == hour


def hour_series(**rain_by_hour):
    """Each hour's wind equals the hour, so the hour wind was read from shows in the result."""
    return {
        datetime(2026, 10, 30, h, tzinfo=UTC): Weather(wind_mph=h, gust_mph=h, rain_in_hr=rain_by_hour.get(f'h{h}', 0.0), snow_in_hr=0.0)
        for h in range(13, 17)
    }


@pytest.mark.parametrize('minute, wind_hour', [(0, 14), (20, 14), (40, 15)])
def test_at_reads_wind_at_the_nearest_hour_and_rain_for_the_hour_the_truck_is_in(minute, wind_hour):
    series = hour_series(h14=0.2, h15=0.6)
    w = weather.at(series, datetime(2026, 10, 30, 14, minute, tzinfo=UTC))
    assert w.wind_mph == wind_hour
    # Open-Meteo stamps rain with the end of the hour it fell in; 14:00–15:00 is stamped 15:00.
    assert w.rain_in_hr == 0.6


def test_at_is_none_when_the_hour_the_truck_is_in_has_no_forecast():
    series = hour_series()
    assert weather.at(series, datetime(2026, 10, 30, 16, 10, tzinfo=UTC)) is None


def test_hourly_batches_points_and_rounds_keys(monkeypatch):
    calls = []

    def fake_fetch(keys, start, end):
        calls.append(len(keys))
        return [{} for _ in keys]

    monkeypatch.setattr(weather, '_fetch', fake_fetch)
    monkeypatch.setattr(weather, 'POINTS_PER_REQUEST', 2)
    now = datetime.now(UTC)
    result = weather.hourly([(35.001, -101.0), (35.004, -101.0), (36.0, -101.0), (37.0, -101.0)], now, now)
    assert sorted(result) == [(35.0, -101.0), (36.0, -101.0), (37.0, -101.0)]
    assert calls == [2, 1]


class FakeResponse:
    def __init__(self, status, body=None):
        self.status_code = status
        self._body = body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError('error', request=None, response=None)

    def json(self):
        return self._body


@pytest.fixture
def no_sleep(monkeypatch):
    waits = []
    monkeypatch.setattr(weather.time, 'sleep', waits.append)
    return waits


def replay(monkeypatch, *responses):
    queue = list(responses)

    def fake_get(*args, **kwargs):
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(weather.httpx, 'get', fake_get)
    return queue


def test_request_retries_a_rate_limit_then_succeeds(monkeypatch, no_sleep):
    replay(monkeypatch, FakeResponse(429), FakeResponse(200, {'ok': True}))
    assert weather._request({}) == {'ok': True}
    assert no_sleep == [1]


def test_request_retries_timeouts(monkeypatch, no_sleep):
    replay(monkeypatch, httpx.ReadTimeout('slow'), FakeResponse(503), FakeResponse(200, {'ok': True}))
    assert weather._request({}) == {'ok': True}
    assert no_sleep == [1, 3]


def test_request_reports_busy_after_repeated_rate_limits(monkeypatch, no_sleep):
    replay(monkeypatch, FakeResponse(429), FakeResponse(429), FakeResponse(429))
    with pytest.raises(UpstreamError) as e:
        weather._request({})
    assert e.value.code == 'weather_busy' and e.value.retry_after_s == 60


def test_request_does_not_retry_client_errors(monkeypatch, no_sleep):
    replay(monkeypatch, FakeResponse(400))
    with pytest.raises(UpstreamError) as e:
        weather._request({})
    assert e.value.code == 'weather_unavailable' and no_sleep == []


def test_time_zone_reads_the_zone_open_meteo_resolves_for_the_point(monkeypatch, no_sleep):
    replay(monkeypatch, FakeResponse(200, {'timezone': 'America/Chicago', 'utc_offset_seconds': -18000}))
    assert weather.time_zone(32.7767, -96.797) == 'America/Chicago'


def test_hourly_fetches_batches_at_the_same_time(monkeypatch):
    # Each fake fetch waits for the other; run one after another, they would time out.
    both_started = threading.Barrier(2, timeout=2)

    def fake_fetch(keys, start, end):
        both_started.wait()
        return [{} for _ in keys]

    monkeypatch.setattr(weather, '_fetch', fake_fetch)
    monkeypatch.setattr(weather, 'POINTS_PER_REQUEST', 1)
    now = datetime.now(UTC)
    assert len(weather.hourly([(35.0, -101.0), (36.0, -101.0)], now, now)) == 2
