"""Endpoint tests with the providers stubbed: captured ORS routes and synthetic weather."""

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from routing import corridor, planner
from routing.risk import Weather
from routing.services import weather
from routing.services.errors import NotFound, UpstreamError
from routing.services.geocoding import Place
from routing.services.routes import parse_feature

CAPTURE = json.loads((Path(__file__).parents[1] / 'fixtures' / 'ors_dallas_denver.json').read_text())
LEVELS = {'low', 'moderate', 'high', 'severe', 'no_travel'}
DEPARTURE = (datetime.now(UTC) + timedelta(hours=3)).replace(minute=0, second=0, microsecond=0)
STORMY = Weather(wind_mph=48, gust_mph=60, rain_in_hr=0.0, snow_in_hr=0.0)
CALM = Weather(wind_mph=10, gust_mph=15, rain_in_hr=0.0, snow_in_hr=0.0)


def fake_hourly(points, start, end, horizon_hours=None):
    """Windy west of -101° (the Texas panhandle), calm elsewhere."""
    start = start.replace(minute=0, second=0, microsecond=0)
    hours = int((end - start).total_seconds() // 3600) + 2
    if horizon_hours is not None:
        hours = min(hours, horizon_hours)
    return {
        weather.point_key(lat, lon): {
            start + timedelta(hours=h): STORMY if lon < -101 and lat < 36.5 else CALM for h in range(hours)
        }
        for lat, lon in points
    }


@pytest.fixture
def providers(monkeypatch):
    places = {
        'Dallas, TX': Place('Dallas, TX, USA', 32.7767, -96.797),
        'Denver, CO': Place('Denver, CO, USA', 39.7392, -104.9903),
    }

    def fake_geocode(text, field):
        if text not in places:
            raise NotFound('geocode_not_found', f'Could not find "{text}".', field)
        return places[text]

    options = [parse_feature(CAPTURE['routes'][n]['features'][0]) for n in ('direct', 'via_sw')]
    monkeypatch.setattr(planner, 'geocode', fake_geocode)
    monkeypatch.setattr(planner, 'route_options', lambda o, d: options)
    monkeypatch.setattr(planner, 'town_near', lambda lat, lon: 'Lubbock')
    monkeypatch.setattr(weather, 'hourly', fake_hourly)
    monkeypatch.setattr(weather, 'time_zone', lambda lat, lon: 'America/Chicago')
    return monkeypatch


def body(**overrides):
    return {
        'origin': 'Dallas, TX',
        'destination': 'Denver, CO',
        'departure_time': DEPARTURE.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'load_weight_lb': 42000,
        'sample_interval_mi': 25,
        **overrides,
    }


def post(client, **overrides):
    return client.post('/api/plan', body(**overrides), content_type='application/json')


def test_plan_matches_contract(client, providers):
    response = post(client)
    assert response.status_code == 200
    plan = response.json()

    assert {r['label'] for r in plan['routes']} == {'Direct', 'Via TX 114'}
    assert plan['recommended_route_id'] == plan['routes'][0]['id']
    assert [r['rank'] for r in plan['routes']] == [1, 2]
    assert [w['code'] for w in plan['warnings']] == ['fewer_routes']

    for route in plan['routes']:
        miles = route['summary']['miles_by_level']
        assert sum(miles.values()) == pytest.approx(route['distance_mi'], abs=0.5)
        assert all(c['level'] in LEVELS for c in route['checkpoints'])
        assert route['checkpoints'][0]['eta'] == body()['departure_time']


def test_departure_without_a_zone_is_local_time_at_the_origin(client, providers):
    local = DEPARTURE.astimezone(ZoneInfo('America/Chicago')).strftime('%Y-%m-%dT%H:%M:%S')
    plan = post(client, departure_time=local).json()
    assert plan['departure_time'] == body()['departure_time']
    assert plan['origin']['time_zone'] == 'America/Chicago'


def test_past_departure_says_what_time_it_is_at_the_origin(client, providers):
    message = post(client, departure_time='2020-01-01T00:00:00').json()['error']['message']
    assert re.fullmatch(r'Departure is in the past: it is now \d{1,2}:\d{2} [AP]M at the start\.', message)


def test_heavy_load_in_45_mph_wind_is_no_travel(client, providers):
    plan = post(client).json()
    stormy = [c for r in plan['routes'] for c in r['checkpoints'] if c['weather']['wind_mph'] == 48]
    assert stormy
    assert all(c['level'] == 'no_travel' and c['load_rule'] == 'wind_45_54_over_30000' for c in stormy)

    light = post(client, load_weight_lb=20000).json()
    stormy = [c for r in light['routes'] for c in r['checkpoints'] if c['weather']['wind_mph'] == 48]
    assert all(c['level'] == 'severe' and c['load_rule'] is None for c in stormy)


def rain_in_first_hour(points, start, end):
    """Heavy rain stamped one hour after `start` (it fell during the first hour), dry otherwise."""
    rainy = Weather(wind_mph=10, gust_mph=15, rain_in_hr=0.6, snow_in_hr=0.0)
    series = fake_hourly(points, start, end)
    for s in series.values():
        s[start.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)] = rainy
    return series


def test_checkpoints_read_rain_for_the_hour_they_drive_in(client, providers):
    providers.setattr(weather, 'hourly', rain_in_first_hour)
    first = post(client).json()['routes'][0]['checkpoints'][0]
    assert first['weather']['rain_in_hr'] == 0.6 and first['level'] == 'severe'
    assert first['forecast_time'] == body()['departure_time']
    assert first['precip_hour_ending'] == (DEPARTURE + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%SZ')


def heatmap_params(client, **overrides):
    grid = post(client).json()['heatmap_grid']
    return {**grid, 'start': body()['departure_time'], 'load_weight_lb': 42000, **overrides}


def test_heatmap_frames_read_rain_for_the_hour_that_follows(client, providers):
    params = heatmap_params(client)
    providers.setattr(weather, 'hourly', rain_in_first_hour)
    frames = client.get('/api/heatmap', params).json()['frames']
    assert set(frames[0]['rain_in_hr']) == {0.6}
    assert set(frames[1]['rain_in_hr']) == {0.0}


def test_checkpoints_past_the_forecast_have_no_level(client, providers):
    providers.setattr(weather, 'hourly', lambda p, s, e: fake_hourly(p, s, e, horizon_hours=6))
    plan = post(client).json()
    assert 'beyond_forecast' in [w['code'] for w in plan['warnings']]
    last = plan['routes'][0]['checkpoints'][-1]
    assert last['level'] is None and last['weather'] is None


@pytest.mark.parametrize('field, value', [
    ('origin', ''),
    ('load_weight_lb', 0),
    ('load_weight_lb', '42000'),
    ('sample_interval_mi', 30),
    ('departure_time', 'tomorrow'),
    ('departure_time', '2020-01-01T00:00:00'),
    ('departure_time', '2020-01-01T00:00:00Z'),
])
def test_plan_rejects_bad_input(client, providers, field, value):
    response = post(client, **{field: value})
    assert response.status_code == 400
    error = response.json()['error']
    assert error['code'] == 'invalid_input' and error['field'] == field


def test_unknown_place_names_the_field(client, providers):
    response = post(client, destination='Nowhere, ZZ')
    assert response.status_code == 400
    assert response.json()['error'] == {
        'code': 'geocode_not_found',
        'message': 'Could not find "Nowhere, ZZ".',
        'field': 'destination',
    }


def test_provider_failure_is_a_502(client, providers):
    def down(*args):
        raise UpstreamError('routing_unavailable', 'Route lookup failed: timeout')

    providers.setattr(planner, 'route_options', down)
    response = post(client)
    assert response.status_code == 502
    assert response.json()['error']['code'] == 'routing_unavailable'


def test_heatmap_covers_the_plans_corridor(client, providers):
    params = heatmap_params(client)
    response = client.get('/api/heatmap', params)
    assert response.status_code == 200
    heat = response.json()
    assert heat['step_deg'] == params['step_deg']
    assert heat['points'] == corridor.Grid.from_params(params).points()
    assert [f['hour'] for f in heat['frames']] == list(range(49))
    for frame in heat['frames']:
        assert len(frame['score']) == len(heat['points'])
        assert set(frame['score']) <= {0, 4}


@pytest.mark.parametrize('overrides, field', [
    ({'cells': 'AAAA'}, 'cells'),
    ({'step_deg': 'x'}, 'step_deg'),
    ({'start': 'soon'}, 'start'),
    ({'load_weight_lb': 'x'}, 'load_weight_lb'),
])
def test_heatmap_rejects_bad_input(client, providers, overrides, field):
    response = client.get('/api/heatmap', heatmap_params(client, **overrides))
    assert response.status_code == 400
    assert response.json()['error']['field'] == field


def test_busy_weather_is_a_503_with_retry_after(client, providers):
    def busy(*args):
        raise UpstreamError('weather_busy', 'Try again in a minute.', retry_after_s=60)

    providers.setattr(weather, 'hourly', busy)
    response = post(client)
    assert response.status_code == 503
    assert response['Retry-After'] == '60'
    assert response.json()['error']['code'] == 'weather_busy'


def test_plan_accepts_picked_points_with_names(client, providers):
    plan = post(
        client,
        origin={'lat': 32.7767, 'lon': -96.797, 'name': 'Picked point, Dallas'},
        destination={'lat': 39.7392, 'lon': -104.9903},
    ).json()
    assert plan['origin']['name'] == 'Picked point, Dallas'
    assert plan['destination']['name'] == '39.7392, -104.9903'


def test_places_suggests_and_ignores_short_text(client, monkeypatch):
    from routing.services import geocoding

    monkeypatch.setattr(geocoding, 'suggest', lambda text: [Place('Amarillo, TX, USA', 35.2, -101.8)])
    assert client.get('/api/places', {'text': 'A'}).json() == {'places': []}
    assert client.get('/api/places', {'text': 'Amar'}).json() == {
        'places': [{'name': 'Amarillo, TX, USA', 'lat': 35.2, 'lon': -101.8}]
    }


def test_reverse_place(client, monkeypatch):
    from routing.services import geocoding

    monkeypatch.setattr(geocoding, 'reverse', lambda lat, lon: Place('SE 12th Ave, Amarillo, TX, USA', lat, lon))
    assert client.get('/api/places/reverse', {'lat': 35.2, 'lon': -101.83}).json() == {
        'name': 'SE 12th Ave, Amarillo, TX, USA', 'lat': 35.2, 'lon': -101.83,
    }
    assert client.get('/api/places/reverse', {'lat': 'x', 'lon': 1}).status_code == 400
    assert client.get('/api/places/reverse', {'lat': 95, 'lon': 1}).status_code == 400
