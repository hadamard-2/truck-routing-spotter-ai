from django.http import JsonResponse


class HealthCheckMiddleware:
    """Answer health probes before anything validates the Host header.

    Load balancer probes address the container by its private IP, which is not
    a hostname we serve, so letting them reach the view would fail host checks.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == '/api/health':
            return JsonResponse({'status': 'ok'})
        return self.get_response(request)
