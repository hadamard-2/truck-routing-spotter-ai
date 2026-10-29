import json
from functools import cache
from pathlib import Path

from rest_framework.decorators import api_view
from rest_framework.response import Response

FIXTURES = Path(__file__).parent / 'fixtures'
SAMPLE_INTERVALS = (10, 25, 50)
SAMPLE_WARNING = {
    'code': 'sample_data',
    'message': 'Showing sample data: Dallas to Denver with synthetic weather.',
}


@cache
def _fixture(name):
    return json.loads((FIXTURES / name).read_text())


def _error(status, code, message, field=None):
    body = {'code': code, 'message': message}
    if field:
        body['field'] = field
    return Response({'error': body}, status=status)


@api_view(['GET'])
def health(request):
    return Response({'status': 'ok'})


@api_view(['POST'])
def plan(request):
    data = request.data
    for field in ('origin', 'destination', 'departure_time'):
        if not data.get(field):
            return _error(400, 'invalid_input', f'{field} is required.', field)
    weight = data.get('load_weight_lb')
    if not isinstance(weight, int) or isinstance(weight, bool) or weight <= 0:
        return _error(400, 'invalid_input', 'load_weight_lb must be a positive integer.', 'load_weight_lb')
    interval = data.get('sample_interval_mi')
    if interval not in SAMPLE_INTERVALS:
        return _error(400, 'invalid_input', 'sample_interval_mi must be 10, 25 or 50.', 'sample_interval_mi')

    body = dict(_fixture(f'plan_{interval}.json'))
    body['warnings'] = [*body['warnings'], SAMPLE_WARNING]
    return Response(body)


@api_view(['GET'])
def heatmap(request):
    return Response(_fixture('heatmap.json'))
