"""Weather risk classification per checkpoint: risk table plus load rules.

The bands and the reasoning behind every edge case are in docs/problem.md ("Decisions").
"""

from dataclasses import dataclass
from typing import Literal

Level = Literal['low', 'moderate', 'high', 'severe', 'no_travel']

LEVELS: tuple[Level, ...] = ('low', 'moderate', 'high', 'severe', 'no_travel')
SCORE: dict[Level, int] = {level: i for i, level in enumerate(LEVELS)}

# Upper bounds for low, moderate, high and severe. Wind bands exclude their upper bound
# (No Travel is ">= 55"); rain and snow include the Severe upper bound (No Travel is "> 1.00", "> 3.0").
WIND_BOUNDS = (25, 35, 45, 55)
RAIN_BOUNDS = (0.10, 0.25, 0.50, 1.00)
SNOW_BOUNDS = (0.5, 1.0, 2.0, 3.0)

HEAVY_LOAD_45_54_LB = 30_000
HEAVY_LOAD_35_44_LB = 40_000


@dataclass(frozen=True)
class Weather:
    wind_mph: float
    gust_mph: float
    rain_in_hr: float
    snow_in_hr: float


@dataclass(frozen=True)
class Classification:
    levels: dict[str, Level]
    load_rule: str | None
    level: Level


def _band(value: float, bounds: tuple[float, ...], severe_includes_top: bool) -> Level:
    for i, upper in enumerate(bounds):
        is_top = i == len(bounds) - 1
        if value < upper or (is_top and severe_includes_top and value == upper):
            return LEVELS[i]
    return 'no_travel'


def classify_wind(mph: float) -> Level:
    return _band(mph, WIND_BOUNDS, severe_includes_top=False)


def classify_rain(in_hr: float) -> Level:
    return _band(in_hr, RAIN_BOUNDS, severe_includes_top=True)


def classify_snow(in_hr: float) -> Level:
    return _band(in_hr, SNOW_BOUNDS, severe_includes_top=True)


def _load_rule(wind_mph: float, load_lb: int) -> tuple[Level, str] | None:
    if 45 <= wind_mph < 55 and load_lb > HEAVY_LOAD_45_54_LB:
        return 'no_travel', 'wind_45_54_over_30000'
    if 35 <= wind_mph < 45 and load_lb > HEAVY_LOAD_35_44_LB:
        return 'severe', 'wind_35_44_over_40000'
    return None


def classify(weather: Weather, load_lb: int) -> Classification:
    """Worst of wind, rain and snow (sustained wind only), then raised by any load rule."""
    levels: dict[str, Level] = {
        'wind': classify_wind(weather.wind_mph),
        'rain': classify_rain(weather.rain_in_hr),
        'snow': classify_snow(weather.snow_in_hr),
    }
    level = max(levels.values(), key=SCORE.__getitem__)
    load_rule = None
    raised = _load_rule(weather.wind_mph, load_lb)
    if raised and SCORE[raised[0]] > SCORE[level]:
        level, load_rule = raised
    return Classification(levels=levels, load_rule=load_rule, level=level)
