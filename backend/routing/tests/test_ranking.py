import pytest

from routing.ranking import rank, summarize


def cp(level, segment):
    return {'level': level, 'segment_mi': segment}


def route(rid, label, duration_s, **miles):
    by_level = {'low': 0.0, 'moderate': 0.0, 'high': 0.0, 'severe': 0.0, 'no_travel': 0.0, **miles}
    total = sum(by_level.values()) or 1
    avg = sum(i * by_level[k] for i, k in enumerate(by_level)) / total
    return {
        'id': rid,
        'label': label,
        'duration_s': duration_s,
        'summary': {'miles_by_level': by_level, 'average_risk': round(avg, 2)},
    }


def test_summarize_sums_miles_and_weights_average_by_miles():
    summary = summarize([cp('low', 75), cp('severe', 25), cp('low', 0)])
    assert summary['miles_by_level'] == {'low': 75.0, 'moderate': 0.0, 'high': 0.0, 'severe': 25.0, 'no_travel': 0.0}
    assert summary['average_risk'] == 0.75
    assert summary['worst_level'] == 'severe'


def test_summarize_skips_checkpoints_without_a_forecast():
    summary = summarize([cp('high', 50), cp(None, 50)])
    assert summary['miles_by_level']['high'] == 50
    assert summary['average_risk'] == 2.0
    assert summary['worst_level'] == 'high'


def test_summarize_with_no_forecast_at_all():
    summary = summarize([cp(None, 50)])
    assert summary['average_risk'] is None
    assert summary['worst_level'] is None


def ids(routes):
    return [r['id'] for r in routes]


def test_no_travel_miles_rank_before_severe():
    a = route('a', 'A', 100, low=40, severe=60)
    b = route('b', 'B', 100, low=70, no_travel=30)
    assert ids(rank([b, a])) == ['a', 'b']


def test_severe_then_high_then_average_then_time():
    severe = route('s', 'S', 10, low=90, severe=10)
    high = route('h', 'H', 10, low=80, high=20)
    busier = route('m', 'M', 10, low=50, moderate=50)
    slow = route('q', 'Q', 99, low=100)
    fast = route('f', 'F', 50, low=100)
    assert ids(rank([severe, high, busier, slow, fast])) == ['f', 'q', 'm', 'h', 's']


def test_rank_sets_position_recommendation_and_reasons():
    ranked = rank([
        route('b', 'Direct', 36_000, low=50, no_travel=50),
        route('a', 'Via North', 45_600, low=100),
        route('c', 'Via South', 39_600, low=50, no_travel=50, high=10),
    ])
    assert ids(ranked) == ['a', 'b', 'c']
    assert [r['rank'] for r in ranked] == [1, 2, 3]
    assert [r['recommended'] for r in ranked] == [True, False, False]


def reasons(*routes):
    return [r['summary']['rank_reason'] for r in rank(list(routes))]


def test_each_reason_names_the_neighbour_and_what_the_choice_costs_in_time():
    assert reasons(
        route('b', 'Direct', 36_000, low=50, no_travel=50),
        route('a', 'Via North', 45_600, low=100),
        route('c', 'Via South', 39_600, low=50, no_travel=50, high=10),
    ) == [
        'Fewer no-travel miles than Direct (0 vs 50), but 2 h 40 min slower',
        'More no-travel miles than Via North (50 vs 0), but 2 h 40 min faster',
        'More high miles than Direct (10 vs 0), and 1 h slower',
    ]


def test_winner_is_explained_by_what_separates_it_from_the_runner_up():
    # Tied with B on severe miles, so "fewest severe miles" would not be why A wins.
    assert reasons(
        route('a', 'A', 3600, low=100),
        route('b', 'B', 3600, low=80, moderate=20),
        route('c', 'C', 3600, low=80, severe=20),
    )[0] == 'Lower average risk than B (0 vs 0.2)'


@pytest.mark.parametrize('durations, reason', [
    ((3600, 7200), 'Same risk as B, 1 h faster'),
    ((3600, 3600), 'Same risk and travel time as B'),
])
def test_reason_falls_back_to_time(durations, reason):
    assert reasons(route('a', 'A', durations[0], low=10), route('b', 'B', durations[1], low=10))[0] == reason


def test_a_single_route_has_nothing_to_compare_with():
    assert reasons(route('a', 'A', 3600, low=10)) == ['Only route found']
