from routing.services import geocoding


def feature(label, lon, lat):
    return {'geometry': {'coordinates': [lon, lat]}, 'properties': {'label': label}}


def test_suggest_drops_repeated_names(monkeypatch):
    monkeypatch.setattr(geocoding, '_get', lambda url, params: {'features': [
        feature('Oklahoma City, OK, USA', -97.6, 35.39),
        feature('City of Oklahoma City, OK, USA', -97.5, 35.47),
        feature('Oklahoma City, OK, USA', -97.52, 35.47),
    ]})
    assert [p.name for p in geocoding.suggest('Oklahoma Ci')] == ['Oklahoma City, OK, USA', 'City of Oklahoma City, OK, USA']
    assert geocoding.suggest('Oklahoma Ci')[0].lon == -97.6
