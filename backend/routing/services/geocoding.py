"""Address search and reverse lookup through openrouteservice's geocoder (Pelias)."""

from dataclasses import dataclass

import httpx
from django.conf import settings

from .errors import NotFound, UpstreamError

SEARCH_URL = 'https://api.heigit.org/pelias/v1/search'
REVERSE_URL = 'https://api.heigit.org/pelias/v1/reverse'
TIMEOUT_S = 15


@dataclass(frozen=True)
class Place:
    name: str
    lat: float
    lon: float


def _get(url: str, params: dict) -> dict:
    try:
        response = httpx.get(url, params=params, headers={'Authorization': settings.ORS_API_KEY}, timeout=TIMEOUT_S)
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as e:
        raise UpstreamError('geocoding_unavailable', f'Address lookup failed: {e}') from e


def geocode(text: str, field: str) -> Place:
    body = _get(SEARCH_URL, {'text': text, 'size': 1})
    features = body.get('features') or []
    if not features:
        raise NotFound('geocode_not_found', f'Could not find "{text}".', field)
    feature = features[0]
    lon, lat = feature['geometry']['coordinates']
    return Place(name=feature['properties'].get('label', text), lat=lat, lon=lon)


def town_near(lat: float, lon: float) -> str | None:
    """Name of the nearest town or county, for labelling a route; None if the lookup fails."""
    try:
        body = _get(REVERSE_URL, {'point.lat': lat, 'point.lon': lon, 'size': 1, 'layers': 'locality,county'})
    except UpstreamError:
        return None
    features = body.get('features') or []
    return features[0]['properties'].get('name') if features else None
