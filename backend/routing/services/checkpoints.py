"""Checkpoints every N miles along a route, each with its position and the truck's ETA."""

from bisect import bisect_left
from dataclasses import dataclass
from datetime import datetime, timedelta

from .routes import RouteOption

# A final stretch shorter than this is folded into the previous checkpoint.
MIN_LAST_STRETCH_MI = 0.5


@dataclass(frozen=True)
class Checkpoint:
    index: int
    mile: float
    segment_mi: float
    lat: float
    lon: float
    eta: datetime


def _at_mile(option: RouteOption, mile: float) -> tuple[float, float, float]:
    """(lon, lat, seconds) at `mile`, interpolated between the surrounding geometry points."""
    j = min(max(bisect_left(option.cum_mi, mile), 1), len(option.cum_mi) - 1)
    m0, m1 = option.cum_mi[j - 1], option.cum_mi[j]
    t = (mile - m0) / (m1 - m0) if m1 > m0 else 0.0
    (x0, y0), (x1, y1) = option.coords[j - 1], option.coords[j]
    s0, s1 = option.cum_s[j - 1], option.cum_s[j]
    return x0 + t * (x1 - x0), y0 + t * (y1 - y0), s0 + t * (s1 - s0)


def sample(option: RouteOption, interval_mi: float, departure: datetime) -> list[Checkpoint]:
    """Checkpoints at mile 0, every `interval_mi`, and the destination.

    Each checkpoint stands for the road from it to the next one (`segment_mi`); the
    destination's is 0, so the segments add up to the route's length.
    """
    marks = [i * interval_mi for i in range(int(option.distance_mi // interval_mi) + 1)]
    if option.distance_mi - marks[-1] >= MIN_LAST_STRETCH_MI or len(marks) == 1:
        marks.append(option.distance_mi)
    else:
        marks[-1] = option.distance_mi

    checkpoints = []
    for i, mile in enumerate(marks):
        lon, lat, seconds = _at_mile(option, mile)
        segment = marks[i + 1] - mile if i + 1 < len(marks) else 0.0
        checkpoints.append(Checkpoint(i, mile, segment, lat, lon, departure + timedelta(seconds=seconds)))
    return checkpoints
