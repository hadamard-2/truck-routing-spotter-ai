from rest_framework.decorators import api_view
from rest_framework.response import Response

from routing.planner import InvalidInput, build_heatmap, build_plan
from routing.services import geocoding
from routing.services.errors import NotFound, UpstreamError


def _error(status, code, message, field=None, headers=None):
    body = {'code': code, 'message': message}
    if field:
        body['field'] = field
    return Response({'error': body}, status=status, headers=headers)


def _respond(build, data):
    try:
        return Response(build(data))
    except InvalidInput as e:
        return _error(400, 'invalid_input', e.message, e.field)
    except NotFound as e:
        return _error(400, e.code, e.message, e.field)
    except UpstreamError as e:
        if e.retry_after_s:
            return _error(503, e.code, e.message, headers={'Retry-After': str(e.retry_after_s)})
        return _error(502, e.code, e.message)


@api_view(['GET'])
def health(request):
    return Response({'status': 'ok'})


@api_view(['POST'])
def plan(request):
    return _respond(build_plan, request.data)


@api_view(['GET'])
def heatmap(request):
    return _respond(build_heatmap, request.query_params)


MIN_SEARCH_CHARS = 2


def _place_json(place):
    return {'name': place.name, 'lat': place.lat, 'lon': place.lon}


@api_view(['GET'])
def places(request):
    text = request.query_params.get('text', '').strip()
    if len(text) < MIN_SEARCH_CHARS:
        return Response({'places': []})
    try:
        return Response({'places': [_place_json(p) for p in geocoding.suggest(text)]})
    except UpstreamError as e:
        return _error(502, e.code, e.message)


@api_view(['GET'])
def reverse_place(request):
    try:
        lat, lon = float(request.query_params['lat']), float(request.query_params['lon'])
    except (KeyError, ValueError):
        return _error(400, 'invalid_input', 'lat and lon are required numbers.')
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return _error(400, 'invalid_input', 'lat and lon are out of range.')
    try:
        return Response(_place_json(geocoding.reverse(lat, lon)))
    except UpstreamError as e:
        return _error(502, e.code, e.message)
