from datetime import UTC, datetime

import pytest

from routing.risk import Weather
from routing.services import weather


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
