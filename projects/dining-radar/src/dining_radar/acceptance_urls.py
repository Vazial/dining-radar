"""Routes available only in the isolated local acceptance configuration."""

from django.conf import settings
from django.urls import include, path

from .urls import urlpatterns as application_urlpatterns

urlpatterns = [*application_urlpatterns]

if getattr(settings, "ACCEPTANCE_TEST_SUPPORT", False):
    urlpatterns.append(path("test-support/", include("dining_radar.test_support.urls")))
