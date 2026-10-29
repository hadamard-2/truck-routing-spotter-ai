from rest_framework.decorators import api_view
from rest_framework.response import Response

from routing.planner import InvalidInput, build_heatmap, build_plan
from routing.services.errors import NotFound, UpstreamError


def _error(status, code, message, field=None):
    body = {'code': code, 'message': message}
    if field:
        body['field'] = field
    return Response({'error': body}, status=status)


def _respond(build, data):
    try:
        return Response(build(data))
    except InvalidInput as e:
        return _error(400, 'invalid_input', e.message, e.field)
    except NotFound as e:
        return _error(400, e.code, e.message, e.field)
    except UpstreamError as e:
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
