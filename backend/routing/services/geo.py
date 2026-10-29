import math

EARTH_RADIUS_MI = 3958.8


def haversine_mi(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance between two (lon, lat) points, in miles."""
    lon1, lat1, lon2, lat2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return EARTH_RADIUS_MI * 2 * math.asin(math.sqrt(h))
