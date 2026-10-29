import pytest

LEVELS = {'low', 'moderate', 'high', 'severe', 'no_travel'}
VALID = {
    'origin': 'Dallas, TX',
    'destination': 'Denver, CO',
    'departure_time': '2026-10-30T14:00:00Z',
    'load_weight_lb': 42000,
    'sample_interval_mi': 25,
}


def post_plan(client, **overrides):
    return client.post('/api/plan', {**VALID, **overrides}, content_type='application/json')


@pytest.mark.parametrize('interval', [10, 25, 50])
def test_plan_matches_contract(client, interval):
    response = post_plan(client, sample_interval_mi=interval)
    assert response.status_code == 200
    body = response.json()

    routes = body['routes']
    assert len(routes) == 3
    assert [r['rank'] for r in routes] == [1, 2, 3]
    assert body['recommended_route_id'] == routes[0]['id']
    assert [r['recommended'] for r in routes] == [True, False, False]
    assert body['sample_interval_mi'] == interval
    assert any(w['code'] == 'sample_data' for w in body['warnings'])

    for route in routes:
        miles = route['summary']['miles_by_level']
        assert set(miles) == LEVELS
        assert sum(miles.values()) == pytest.approx(route['distance_mi'], abs=0.5)
        checkpoints = route['checkpoints']
        assert checkpoints[0]['mile'] == 0
        assert all(c['level'] in LEVELS for c in checkpoints)
        assert all(b['mile'] - a['mile'] <= interval + 0.01 for a, b in zip(checkpoints, checkpoints[1:]))
        assert [c['eta'] for c in checkpoints] == sorted(c['eta'] for c in checkpoints)


@pytest.mark.parametrize('field, value', [
    ('origin', ''),
    ('load_weight_lb', 0),
    ('load_weight_lb', '42000'),
    ('sample_interval_mi', 30),
])
def test_plan_rejects_bad_input(client, field, value):
    response = post_plan(client, **{field: value})
    assert response.status_code == 400
    assert response.json()['error'] == {
        'code': 'invalid_input',
        'message': response.json()['error']['message'],
        'field': field,
    }


def test_heatmap_frames_align_with_points(client):
    response = client.get('/api/heatmap')
    assert response.status_code == 200
    body = response.json()
    assert [f['hour'] for f in body['frames']] == list(range(49))
    n = len(body['points'])
    for frame in body['frames']:
        for key in ('score', 'wind_mph', 'rain_in_hr', 'snow_in_hr'):
            assert len(frame[key]) == n
        assert set(frame['score']) <= {0, 1, 2, 3, 4}
