"""Three truck routes between two places, with distance and drive time at every geometry point.

openrouteservice only computes alternative routes up to 100 km, so for real trips we ask for the
direct route plus routes forced through a via point on each side of the straight line (see
docs/problem.md, "Findings").
"""

import math
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import httpx
from django.conf import settings

from .errors import UpstreamError
from .geo import haversine_mi

DIRECTIONS_URL = 'https://api.heigit.org/openrouteservice/v2/directions/driving-hgv/geojson'
TIMEOUT_S = 60

# Via points sit this fraction of the straight-line distance away from the midpoint.
# If the first choice snaps to a dead end, the next one is tried.
VIA_OFFSETS = (0.2, 0.3, 0.12)
# A route that drives the same road both ways for longer than this went out to the via point and back.
MAX_DOUBLED_BACK_MI = 5.0
# A via route sharing more than this share of the direct route's road is not a real alternative.
MAX_SHARED_ROAD = 0.85

# Numbered highways worth naming a route after: interstates, US routes and state routes
# ("I 35", "US 287", "TX 114"). County and farm roads are too local to recognise.
HIGHWAY = re.compile(r'^(I|US|[A-Z]{2})[ -]?\d+[A-Z]?$')
LOCAL_ROAD_PREFIXES = ('CR', 'FM', 'RM')
# A highway names a route only if the route drives at least this much more of it than any other route.
MIN_DISTINCT_HIGHWAY_MI = 20


@dataclass
class RouteOption:
    coords: list[tuple[float, float]]  # (lon, lat)
    cum_mi: list[float]  # miles from the start at each point
    cum_s: list[float]  # driving seconds from the start at each point
    distance_mi: float
    duration_s: float
    via: tuple[float, float] | None = None  # (lon, lat) the route was forced through
    highway_mi: Counter[str] = field(default_factory=Counter)  # miles driven on each numbered highway


def highways_in(step_name: str) -> list[str]:
    """Numbered highways in an ORS step name such as "South Dumas Avenue, US 87, US 287"."""
    refs = (part.strip() for part in step_name.split(','))
    return [r for r in refs if HIGHWAY.match(r) and not r.startswith(LOCAL_ROAD_PREFIXES)]


def parse_feature(feature: dict) -> RouteOption:
    """Turn an ORS GeoJSON feature into per-point cumulative miles and seconds.

    Distances follow the geometry, scaled to ORS's own total. Time is spread within each
    instruction step by distance, so cities are slow and highways fast, as ORS timed them.
    """
    coords = [(lon, lat) for lon, lat in feature['geometry']['coordinates']]
    summary = feature['properties']['summary']
    distance_mi = float(summary['distance'])
    duration_s = float(summary['duration'])

    raw = [0.0]
    for a, b in zip(coords, coords[1:]):
        raw.append(raw[-1] + haversine_mi(a, b))
    scale = distance_mi / raw[-1] if raw[-1] else 0.0
    cum_mi = [d * scale for d in raw]

    cum_s = [0.0] * len(coords)
    elapsed = 0.0
    highway_mi: Counter[str] = Counter()
    for segment in feature['properties']['segments']:
        for step in segment['steps']:
            for ref in highways_in(step.get('name', '')):
                highway_mi[ref] += step['distance']
            start, end = step['way_points']
            span = cum_mi[end] - cum_mi[start]
            for i in range(start, end + 1):
                share = (cum_mi[i] - cum_mi[start]) / span if span else 1.0
                cum_s[i] = elapsed + share * step['duration']
            elapsed += step['duration']
    return RouteOption(coords, cum_mi, cum_s, distance_mi, duration_s, highway_mi=highway_mi)


def doubled_back_mi(option: RouteOption) -> float:
    """Miles of road the route drives in both directions."""
    edges = {}
    for i, (a, b) in enumerate(zip(option.coords, option.coords[1:])):
        key = (round(a[0], 5), round(a[1], 5)), (round(b[0], 5), round(b[1], 5))
        edges[key] = option.cum_mi[i + 1] - option.cum_mi[i]
    return sum(miles for (a, b), miles in edges.items() if (b, a) in edges) / 2


def shared_road(option: RouteOption, other: RouteOption) -> float:
    """Share of `option`'s points that also lie on `other` (to ~100 m)."""
    mine = {(round(x, 3), round(y, 3)) for x, y in option.coords}
    theirs = {(round(x, 3), round(y, 3)) for x, y in other.coords}
    return len(mine & theirs) / len(mine) if mine else 1.0


def _directions(points: list[tuple[float, float]]) -> RouteOption:
    try:
        response = httpx.post(
            DIRECTIONS_URL,
            headers={'Authorization': settings.ORS_API_KEY},
            json={'coordinates': points, 'radiuses': [-1] * len(points), 'units': 'mi'},
            timeout=TIMEOUT_S,
        )
        response.raise_for_status()
        return parse_feature(response.json()['features'][0])
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
        raise UpstreamError('routing_unavailable', f'Route lookup failed: {e}') from e


def via_point(origin: tuple[float, float], destination: tuple[float, float], side: int, offset: float):
    """A point `offset` × straight-line length from the midpoint, left (+1) or right (-1) of travel."""
    (x1, y1), (x2, y2) = origin, destination
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    px, py = -dy / length, dx / length
    return ((x1 + x2) / 2 + side * px * offset * length, (y1 + y2) / 2 + side * py * offset * length)


def _via_route(origin, destination, side: int) -> RouteOption | None:
    for offset in VIA_OFFSETS:
        via = via_point(origin, destination, side, offset)
        try:
            option = _directions([origin, via, destination])
        except UpstreamError:
            continue  # e.g. the via point is in the sea; try a closer one
        if doubled_back_mi(option) <= MAX_DOUBLED_BACK_MI:
            option.via = via
            return option
    return None


def route_options(origin: tuple[float, float], destination: tuple[float, float]) -> list[RouteOption]:
    """The direct route first, then up to two distinct via routes. Points are (lon, lat)."""
    with ThreadPoolExecutor(max_workers=3) as pool:
        direct_job = pool.submit(_directions, [origin, destination])
        via_jobs = [pool.submit(_via_route, origin, destination, side) for side in (1, -1)]
        direct = direct_job.result()
        vias = [job.result() for job in via_jobs]

    options = [direct]
    for option in vias:
        if option and all(shared_road(option, kept) <= MAX_SHARED_ROAD for kept in options):
            options.append(option)
    return options


def _highway_rank(ref: str) -> int:
    return 0 if ref.startswith('I') else 1 if ref.startswith('US') else 2


def distinct_highway(option: RouteOption, others: list[RouteOption], taken: set[str]) -> str | None:
    """The highway this route drives most beyond what any other route drives of it.

    Interstates beat US routes beat state routes when the margin is equal. None when no
    highway sets the route apart by MIN_DISTINCT_HIGHWAY_MI.
    """
    def margin(ref: str) -> float:
        return option.highway_mi[ref] - max((o.highway_mi[ref] for o in others), default=0.0)

    candidates = [ref for ref in option.highway_mi if ref not in taken and margin(ref) >= MIN_DISTINCT_HIGHWAY_MI]
    return max(candidates, key=lambda ref: (margin(ref), -_highway_rank(ref)), default=None)
