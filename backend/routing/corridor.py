"""The heatmap grid: evenly spaced points within BUFFER_MI of any route, at most MAX_POINTS of them.

A grid travels between /api/plan and /api/heatmap as its origin, spacing, size and a bitmask of
the cells inside the corridor, so the heatmap needs no copy of the routes.
"""

import base64
import binascii
import math
from dataclasses import dataclass

from routing.services.geo import haversine_mi

BUFFER_MI = 25
# Each point is a weather lookup, and Open-Meteo limits lookups per minute.
MAX_POINTS = 250
MIN_STEP_DEG = 0.2
STEP_INCREMENT_DEG = 0.05
MILES_PER_DEG_LAT = 69.0
# Keeps the bitmask, and so the heatmap URL, a few kilobytes at most.
MAX_GRID_CELLS = 20_000


class InvalidGrid(ValueError):
    def __init__(self, message: str, field: str):
        super().__init__(message)
        self.message = message
        self.field = field


@dataclass(frozen=True)
class Grid:
    min_lon: float
    min_lat: float
    step_deg: float
    cols: int
    rows: int
    cells: frozenset[int]  # row * cols + col of each cell inside the corridor

    def points(self) -> list[dict]:
        """The centre of each corridor cell, in cell order."""
        return [
            {
                'lat': round(self.min_lat + (i // self.cols) * self.step_deg, 3),
                'lon': round(self.min_lon + (i % self.cols) * self.step_deg, 3),
            }
            for i in sorted(self.cells)
        ]

    def params(self) -> dict:
        mask = bytearray((self.cols * self.rows + 7) // 8)
        for i in self.cells:
            mask[i // 8] |= 0x80 >> (i % 8)
        return {
            'min_lon': self.min_lon,
            'min_lat': self.min_lat,
            'step_deg': self.step_deg,
            'cols': self.cols,
            'rows': self.rows,
            'cells': base64.urlsafe_b64encode(mask).decode().rstrip('='),
        }

    @classmethod
    def from_params(cls, params) -> 'Grid':
        def number(field, kind):
            try:
                return kind(params[field])
            except (KeyError, TypeError, ValueError):
                raise InvalidGrid(f'{field} is required and must be a number.', field) from None

        min_lon, min_lat, step = number('min_lon', float), number('min_lat', float), number('step_deg', float)
        cols, rows = number('cols', int), number('rows', int)
        if not (-180 <= min_lon <= 180):
            raise InvalidGrid('min_lon is out of range.', 'min_lon')
        if not (-90 <= min_lat <= 90):
            raise InvalidGrid('min_lat is out of range.', 'min_lat')
        if step < MIN_STEP_DEG:
            raise InvalidGrid(f'step_deg must be at least {MIN_STEP_DEG}.', 'step_deg')
        if cols < 1 or rows < 1 or cols * rows > MAX_GRID_CELLS:
            raise InvalidGrid(f'cols × rows must be between 1 and {MAX_GRID_CELLS}.', 'cols')

        text = str(params.get('cells', ''))
        try:
            mask = base64.urlsafe_b64decode(text + '=' * (-len(text) % 4))
        except (binascii.Error, ValueError):
            raise InvalidGrid('cells is not a valid bitmask.', 'cells') from None
        if len(mask) != (cols * rows + 7) // 8:
            raise InvalidGrid('cells does not match cols × rows.', 'cells')
        cells = frozenset(i for i in range(cols * rows) if mask[i // 8] & (0x80 >> (i % 8)))
        if not cells or len(cells) > MAX_POINTS:
            raise InvalidGrid(f'cells must mark between 1 and {MAX_POINTS} points.', 'cells')
        return cls(min_lon, min_lat, step, cols, rows, cells)


def _lon_deg(miles: float, lat: float) -> float:
    return miles / (MILES_PER_DEG_LAT * max(math.cos(math.radians(lat)), 0.1))


def _thin(line: list[tuple[float, float]], spacing_mi: float) -> list[tuple[float, float]]:
    """The line's points at least `spacing_mi` apart, plus its end."""
    kept = [line[0]]
    for point in line[1:]:
        if haversine_mi(kept[-1], point) >= spacing_mi:
            kept.append(point)
    return kept + [line[-1]]


def _cover(lines, min_lon: float, min_lat: float, cols: int, rows: int, step: float) -> frozenset[int]:
    cells = set()
    reach_rows = math.ceil(BUFFER_MI / MILES_PER_DEG_LAT / step)
    for line in lines:
        for lon, lat in _thin(line, step * MILES_PER_DEG_LAT / 2):
            col0, row0 = round((lon - min_lon) / step), round((lat - min_lat) / step)
            reach_cols = math.ceil(_lon_deg(BUFFER_MI, lat) / step)
            for row in range(max(0, row0 - reach_rows), min(rows, row0 + reach_rows + 1)):
                for col in range(max(0, col0 - reach_cols), min(cols, col0 + reach_cols + 1)):
                    centre = (min_lon + col * step, min_lat + row * step)
                    if haversine_mi(centre, (lon, lat)) <= BUFFER_MI:
                        cells.add(row * cols + col)
    return frozenset(cells)


def build(lines: list[list[tuple[float, float]]]) -> Grid:
    """The finest grid (from MIN_STEP_DEG up) whose corridor around `lines` (each [(lon, lat)]) fits MAX_POINTS."""
    lons = [lon for line in lines for lon, _ in line]
    lats = [lat for line in lines for _, lat in line]
    pad_lat = BUFFER_MI / MILES_PER_DEG_LAT
    pad_lon = _lon_deg(BUFFER_MI, max(abs(min(lats)), abs(max(lats))))
    min_lon, min_lat = round(min(lons) - pad_lon, 2), round(min(lats) - pad_lat, 2)
    span_lon, span_lat = max(lons) + pad_lon - min_lon, max(lats) + pad_lat - min_lat

    step = MIN_STEP_DEG
    while True:
        cols, rows = int(span_lon / step) + 1, int(span_lat / step) + 1
        cells = _cover(lines, min_lon, min_lat, cols, rows, step)
        if len(cells) <= MAX_POINTS and cols * rows <= MAX_GRID_CELLS:
            return Grid(min_lon, min_lat, step, cols, rows, cells)
        step = round(step + STEP_INCREMENT_DEG, 2)
