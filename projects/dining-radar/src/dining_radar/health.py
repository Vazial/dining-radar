"""Minimal application readiness probe for the deployment platform."""

from django.db import DatabaseError, connection
from django.http import HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


@never_cache
@require_GET
def health_check(_request):
    """Report readiness without touching the provider or disclosing configuration."""

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        return HttpResponse("unavailable", status=503, content_type="text/plain")
    return HttpResponse("ok", content_type="text/plain")


class HealthCheckMiddleware:
    """Answer ``/healthz`` before Django validates the ``Host`` header.

    Load balancers and container health checks reach the app by IP address or
    ``localhost`` (an ALB sends the target's own IP as ``Host``), which no
    ``ALLOWED_HOSTS`` list can enumerate ahead of time. Without this the probe
    gets a 400 and the platform never sees the app as healthy. Only this exact
    path is answered here; the response is a fixed string that builds no URL
    from the host, so skipping the host check discloses nothing. Every other
    path still goes through the normal middleware chain and host validation.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path_info == "/healthz":
            return health_check(request)
        return self.get_response(request)
