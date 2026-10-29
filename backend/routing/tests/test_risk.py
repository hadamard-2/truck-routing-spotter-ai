import pytest

from routing.risk import Weather, classify, classify_rain, classify_snow, classify_wind


def weather(wind=0.0, rain=0.0, snow=0.0, gust=0.0):
    return Weather(wind_mph=wind, gust_mph=gust, rain_in_hr=rain, snow_in_hr=snow)


@pytest.mark.parametrize('mph, level', [
    (0, 'low'), (24.9, 'low'),
    (25, 'moderate'), (34.9, 'moderate'),
    (35, 'high'), (44.9, 'high'),
    (45, 'severe'), (54.9, 'severe'),
    (55, 'no_travel'), (80, 'no_travel'),
])
def test_wind_bands(mph, level):
    assert classify_wind(mph) == level


@pytest.mark.parametrize('inches, level', [
    (0, 'low'), (0.09, 'low'),
    (0.10, 'moderate'), (0.24, 'moderate'),
    (0.25, 'high'), (0.49, 'high'),
    (0.50, 'severe'), (1.00, 'severe'),
    (1.01, 'no_travel'),
])
def test_rain_bands(inches, level):
    assert classify_rain(inches) == level


@pytest.mark.parametrize('inches, level', [
    (0, 'low'), (0.49, 'low'),
    (0.5, 'moderate'), (0.99, 'moderate'),
    (1.0, 'high'), (1.99, 'high'),
    (2.0, 'severe'), (3.0, 'severe'),
    (3.01, 'no_travel'),
])
def test_snow_bands(inches, level):
    assert classify_snow(inches) == level


def test_worst_condition_wins():
    result = classify(weather(wind=10, rain=0.3, snow=0.6), load_lb=10_000)
    assert result.levels == {'wind': 'low', 'rain': 'high', 'snow': 'moderate'}
    assert result.level == 'high'
    assert result.load_rule is None


def test_gusts_do_not_change_the_level():
    assert classify(weather(wind=20, gust=70), load_lb=10_000).level == 'low'


@pytest.mark.parametrize('wind, load, level, rule', [
    (45, 30_001, 'no_travel', 'wind_45_54_over_30000'),
    (54.9, 45_000, 'no_travel', 'wind_45_54_over_30000'),
    (45, 30_000, 'severe', None),
    (35, 40_001, 'severe', 'wind_35_44_over_40000'),
    (44.9, 40_001, 'severe', 'wind_35_44_over_40000'),
    (35, 40_000, 'high', None),
    (35, 35_000, 'high', None),
    (34.9, 80_000, 'moderate', None),
    (55, 1_000, 'no_travel', None),
])
def test_load_rules(wind, load, level, rule):
    result = classify(weather(wind=wind), load_lb=load)
    assert result.level == level
    assert result.load_rule == rule


def test_load_rule_only_reported_when_it_raises_the_level():
    result = classify(weather(wind=40, rain=0.7), load_lb=50_000)
    assert result.level == 'severe'
    assert result.load_rule is None


def test_load_rule_never_lowers_the_level():
    result = classify(weather(wind=40, snow=3.5), load_lb=50_000)
    assert result.level == 'no_travel'
    assert result.load_rule is None
