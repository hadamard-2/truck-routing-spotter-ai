"""Route ordering: No Travel miles, then the spec's Severe miles, High miles, average risk, travel time.

Why No Travel comes first is recorded in docs/problem.md ("Decisions").
"""

from routing.risk import LEVELS, SCORE, Level

MILE_CRITERIA = (('no_travel', 'no-travel miles'), ('severe', 'severe miles'), ('high', 'high miles'))


def summarize(checkpoints: list[dict]) -> dict:
    """Miles at each level (each checkpoint owns `segment_mi`), mile-weighted average score, worst level.

    Checkpoints without a forecast (`level` is None) are left out of every figure.
    """
    miles: dict[Level, float] = {level: 0.0 for level in LEVELS}
    for c in checkpoints:
        if c['level'] is not None:
            miles[c['level']] += c['segment_mi']
    known = sum(miles.values())
    average = round(sum(SCORE[k] * m for k, m in miles.items()) / known, 2) if known else None
    levels = [c['level'] for c in checkpoints if c['level'] is not None]
    worst = max(levels, key=SCORE.__getitem__) if levels else None
    return {
        'miles_by_level': {k: round(v, 1) for k, v in miles.items()},
        'average_risk': average,
        'worst_level': worst,
    }


def _sort_key(route: dict) -> tuple:
    s = route['summary']
    m = s['miles_by_level']
    average = s['average_risk'] if s['average_risk'] is not None else float('inf')
    return (m['no_travel'], m['severe'], m['high'], average, route['duration_s'])


def _fmt(miles: float) -> str:
    return f'{miles:g}'


def _reason(route: dict, others: list[dict], first: bool) -> str:
    """The first criterion on which this route differs from the routes it is compared with."""
    mine = route['summary']
    for level, name in MILE_CRITERIA:
        values = [o['summary']['miles_by_level'][level] for o in others]
        own = mine['miles_by_level'][level]
        if any(v != own for v in values):
            if first:
                return f"Fewest {name} ({_fmt(own)} vs {' and '.join(_fmt(v) for v in values)})"
            return f"More {name} than {others[0]['label']} ({_fmt(own)} vs {_fmt(values[0])})"
    if any(o['summary']['average_risk'] != mine['average_risk'] for o in others):
        return 'Lowest average risk' if first else f"Higher average risk than {others[0]['label']}"
    if any(o['duration_s'] != route['duration_s'] for o in others):
        return 'Shortest travel time' if first else f"Longer travel time than {others[0]['label']}"
    return 'Same risk and travel time'


def rank(routes: list[dict]) -> list[dict]:
    """Sort best first and set `rank`, `recommended` and `summary.rank_reason` on each route.

    The winner is explained against every other route; each later route against the one just above it.
    """
    ordered = sorted(routes, key=_sort_key)
    for pos, route in enumerate(ordered, start=1):
        others = ordered[1:] if pos == 1 else [ordered[pos - 2]]
        route['rank'] = pos
        route['recommended'] = pos == 1
        route['summary']['rank_reason'] = _reason(route, others, first=pos == 1) if others else 'Only route found'
    return ordered
