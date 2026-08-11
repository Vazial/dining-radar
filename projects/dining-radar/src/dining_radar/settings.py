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
