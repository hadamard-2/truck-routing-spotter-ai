import json
from pathlib import Path

import pytest

from routing import corridor
from routing.services.geo import haversine_mi
from routing.services.routes import parse_feature

CAPTURE = json.loads((Path(__file__).parents[1] / 'fixtures' / 'ors_dallas_denver.json').read_text())
LINES = [parse_feature(CAPTURE['routes'][name]['features'][0]).coords for name in ('direct', 'via_sw', 'via_ne')]


@pytest.fixture(scope='module')
def grid():
    return corridor.build(LINES)


def cell_of(grid, lon, lat):
    col = round((lon - grid.min_lon) / grid.step_deg)
    row = round((lat - grid.min_lat) / grid.step_deg)
    return row * grid.cols + col


def test_build_stays_within_the_point_budget(grid):
    assert 0 < len(grid.cells) <= corridor.MAX_POINTS


def test_build_covers_every_stretch_of_every_route(grid):
    for line in LINES:
        for lon, lat in line[::10]:
            assert cell_of(grid, lon, lat) in grid.cells


def test_build_leaves_out_points_far_from_every_route(grid):
    route_points = [p for line in LINES for p in line[::5]]
    for point in grid.points():
        nearest = min(haversine_mi((point['lon'], point['lat']), p) for p in route_points)
        assert nearest <= corridor.BUFFER_MI + 1


def test_a_corridor_is_finer_than_a_grid_over_the_whole_box(grid):
    # The old even grid over this trip's bounding box spaced points 0.55° apart.
    assert grid.step_deg < 0.55


def test_params_round_trip(grid):
    assert corridor.Grid.from_params(grid.params()) == grid


def test_points_follow_cell_order(grid):
    first = min(grid.cells)
    row, col = divmod(first, grid.cols)
    assert grid.points()[0] == {
        'lat': round(grid.min_lat + row * grid.step_deg, 3),
        'lon': round(grid.min_lon + col * grid.step_deg, 3),
    }


@pytest.mark.parametrize('change, field', [
    ({'cols': 'x'}, 'cols'),
    ({'step_deg': 0.01}, 'step_deg'),
    ({'cols': 1000, 'rows': 1000}, 'cols'),
    ({'cells': 'AAAA'}, 'cells'),
    ({'cells': '!!'}, 'cells'),
    ({'min_lat': 95}, 'min_lat'),
])
def test_from_params_rejects_bad_grids(grid, change, field):
    with pytest.raises(corridor.InvalidGrid) as e:
        corridor.Grid.from_params({**grid.params(), **change})
    assert e.value.field == field


def test_from_params_rejects_more_cells_than_the_budget():
    full = corridor.Grid(min_lon=-100, min_lat=30, step_deg=0.2, cols=20, rows=20, cells=frozenset(range(400)))
    with pytest.raises(corridor.InvalidGrid) as e:
        corridor.Grid.from_params(full.params())
    assert e.value.field == 'cells'
