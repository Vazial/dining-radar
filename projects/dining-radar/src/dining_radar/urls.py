from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("dining_radar.authentication.urls")),
    path("", include("dining_radar.web.urls")),
]
