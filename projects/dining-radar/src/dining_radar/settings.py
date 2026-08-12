"""Runtime settings for non-test use.

The deployment supplies its own signing secret and host allowlist. Neither a
real origin nor a secret value belongs in this repository.
"""

import os

import dj_database_url

from .settings_base import *  # noqa: F403

MIDDLEWARE = [  # noqa: F405
    MIDDLEWARE[0],  # noqa: F405
    "whitenoise.middleware.WhiteNoiseMiddleware",
    *MIDDLEWARE[1:],  # noqa: F405
]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
WHITENOISE_KEEP_ONLY_HASHED_FILES = True

DEBUG = os.environ.get("DJANGO_DEBUG") == "1"

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("DJANGO_SECRET_KEY must be configured at runtime.")

ALLOWED_HOSTS = [
    host.strip() for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if host.strip()
]
render_hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
if render_hostname and render_hostname not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(render_hostname)

# An operator may use a local debug server while developing. Public operation
# keeps this enabled and must terminate TLS before the Django browser boundary.
SECURE_SSL_REDIRECT = not DEBUG

# Render's health check is sent directly to this service's port, bypassing
# the edge that would otherwise set X-Forwarded-Proto, and it treats a 2xx or
# 3xx response alike as healthy (reconfirmed from Render's own current
# documentation, activeContext.md "Deployment platform terms and
# measurements"). Without this exemption, GET /healthz without that header
# would earn a 301 from SECURE_SSL_REDIRECT above -- a response Render still
# counts as healthy -- so the probe's own SELECT 1 (dining_radar.health)
# would never run and adr/0021 decision 5 / DEPLOYMENT.md section 3.6's
# DB-only readiness probe would silently stop detecting a suspended or broken
# database. SecurityMiddleware matches each pattern here with re.search
# against request.path with its leading slash stripped, so this must match
# only the exact "healthz" path (urls.py's own path("healthz", ...) has no
# trailing slash) -- never as a prefix or substring match against any other
# path, so no other path is exempted from the HTTPS redirect.
SECURE_REDIRECT_EXEMPT = [r"^healthz$"]

render_runtime = os.environ.get("RENDER", "").strip()
if render_runtime:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

database_url = os.environ.get("DATABASE_URL", "").strip()
if render_runtime and not database_url:
    raise RuntimeError("DATABASE_URL must be configured for a Render deployment.")
if database_url:
    DATABASES = {
        "default": dj_database_url.parse(  # noqa: F405
            database_url,
            conn_max_age=600,
            conn_health_checks=True,
            ssl_require=True,
        )
    }

if not DEBUG:
    SECURE_HSTS_SECONDS = 31_536_000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False
