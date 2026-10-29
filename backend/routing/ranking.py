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


def _fmt(value: float) -> str:
    return f'{value:g}'


def _duration(seconds: float) -> str:
    """'2 h 40 min', '1 h', '40 min'."""
    h, m = divmod(round(abs(seconds) / 60), 60)
    if not h:
        return f'{m} min'
    return f'{h} h {m} min' if m else f'{h} h'


def _risk_difference(route: dict, other: dict) -> tuple[str, bool] | None:
    """('Fewer severe miles than Direct (0 vs 25)', True) for the first risk criterion that differs; True if `route` is safer."""
    mine, theirs = route['summary'], other['summary']
    for level, name in MILE_CRITERIA:
        own, their = mine['miles_by_level'][level], theirs['miles_by_level'][level]
        if own != their:
            return f"{'Fewer' if own < their else 'More'} {name} than {other['label']} ({_fmt(own)} vs {_fmt(their)})", own < their
    own, their = mine['average_risk'], theirs['average_risk']
    if own != their:
        safer = their is None or (own is not None and own < their)
        values = f' ({_fmt(own)} vs {_fmt(their)})' if own is not None and their is not None else ''
        return f"{'Lower' if safer else 'Higher'} average risk than {other['label']}{values}", safer
    return None


def _reason(route: dict, other: dict) -> str:
    """Why `route` sits where it does next to `other`, and what that costs or saves in drive time."""
    delta = route['duration_s'] - other['duration_s']
    pace = f"{_duration(delta)} {'slower' if delta > 0 else 'faster'}" if round(abs(delta) / 60) else ''
    risk = _risk_difference(route, other)
    if risk is None:
        return f"Same risk as {other['label']}, {pace}" if pace else f"Same risk and travel time as {other['label']}"
    text, safer = risk
    if not pace:
        return text
    return f"{text}, {'but' if safer == (delta > 0) else 'and'} {pace}"


def rank(routes: list[dict]) -> list[dict]:
    """Sort best first and set `rank`, `recommended` and `summary.rank_reason` on each route.

    Each route is explained against its neighbour: the winner against the runner-up, every
    later route against the one just above it.
    """
    ordered = sorted(routes, key=_sort_key)
    for pos, route in enumerate(ordered, start=1):
        neighbour = ordered[pos - 2] if pos > 1 else ordered[1] if len(ordered) > 1 else None
        route['rank'] = pos
        route['recommended'] = pos == 1
        route['summary']['rank_reason'] = _reason(route, neighbour) if neighbour else 'Only route found'
    return ordered
