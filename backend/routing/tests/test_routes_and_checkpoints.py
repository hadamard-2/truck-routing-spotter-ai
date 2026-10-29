import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from routing.services.checkpoints import sample
from routing.services.routes import (
    distinct_highway,
    doubled_back_mi,
    highways_in,
    parse_feature,
    shared_road,
    via_point,
)

CAPTURE = json.loads((Path(__file__).parents[1] / 'fixtures' / 'ors_dallas_denver.json').read_text())
DEPARTURE = datetime(2026, 10, 30, 14, tzinfo=UTC)


def option(name):
    return parse_feature(CAPTURE['routes'][name]['features'][0])


def test_parse_feature_cumulates_to_ors_totals():
    direct = option('direct')
    assert direct.cum_mi[0] == 0 and direct.cum_s[0] == 0
    assert direct.cum_mi[-1] == pytest.approx(direct.distance_mi)
    assert direct.cum_s[-1] == pytest.approx(direct.duration_s, abs=1)
    assert all(b >= a for a, b in zip(direct.cum_s, direct.cum_s[1:]))


def test_doubled_back_flags_the_dead_end_detour_only():
    assert doubled_back_mi(option('direct')) == 0
    assert doubled_back_mi(option('via_sw')) < 5
    assert doubled_back_mi(option('via_ne')) > 5


def test_via_routes_are_distinct_from_direct():
    assert shared_road(option('via_sw'), option('direct')) < 0.85
    assert shared_road(option('direct'), option('direct')) == 1


def test_via_point_sits_either_side_of_the_midpoint():
    left = via_point((0, 0), (10, 0), side=1, offset=0.2)
    right = via_point((0, 0), (10, 0), side=-1, offset=0.2)
    assert left == pytest.approx((5, 2))
    assert right == pytest.approx((5, -2))


@pytest.mark.parametrize('interval', [10, 25, 50])
def test_sample_spacing_segments_and_etas(interval):
    route = option('direct')
    checkpoints = sample(route, interval, DEPARTURE)

    assert checkpoints[0].mile == 0 and checkpoints[0].eta == DEPARTURE
    assert checkpoints[-1].mile == pytest.approx(route.distance_mi)
    assert checkpoints[-1].segment_mi == 0
    assert sum(c.segment_mi for c in checkpoints) == pytest.approx(route.distance_mi)
    assert all(c.segment_mi <= interval + 0.5 for c in checkpoints)
    assert abs((checkpoints[-1].eta - DEPARTURE).total_seconds() - route.duration_s) < 2
    assert [c.eta for c in checkpoints] == sorted(c.eta for c in checkpoints)


def test_etas_follow_road_speed_not_a_constant_average():
    route = option('direct')
    checkpoints = sample(route, 25, DEPARTURE)
    hours = [(b.eta - a.eta).total_seconds() / 3600 for a, b in zip(checkpoints, checkpoints[1:-1])]
    assert max(hours) - min(hours) > 0.05


@pytest.mark.parametrize('name, refs', [
    ('South Dumas Avenue, US 87, US 287', ['US 87', 'US 287']),
    ('I 40;I 27', []),
    ('I 40, Ranch Road', ['I 40']),
    ('South Wansted Street, US 287, CR 40', ['US 287']),
    ('FM 51, TX 114', ['TX 114']),
    ('-', []),
])
def test_highways_in_step_names(name, refs):
    assert highways_in(name) == refs


def test_alternatives_are_named_by_the_highway_only_they_use():
    direct, sw, ne = option('direct'), option('via_sw'), option('via_ne')
    assert distinct_highway(sw, [direct, ne], set()) == 'TX 114'
    assert distinct_highway(ne, [direct, sw], set()) == 'US 183'
    assert distinct_highway(sw, [direct, ne], {'TX 114'}) != 'TX 114'
