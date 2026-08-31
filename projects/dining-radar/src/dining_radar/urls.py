from django.contrib import admin
from django.urls import include, path

from dining_radar.health import health_check

urlpatterns = [
    path("healthz", health_check, name="health-check"),
    path("admin/", admin.site.urls),
    path("accounts/", include("dining_radar.authentication.urls")),
    path("", include("dining_radar.gathering.urls")),
    path("", include("dining_radar.web.urls")),
]
