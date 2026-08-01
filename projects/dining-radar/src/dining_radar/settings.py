"""Runtime settings for non-test use.

The deployment supplies its own signing secret and host allowlist. Neither a
real origin nor a secret value belongs in this repository.
"""

import os

from .settings_base import *  # noqa: F403

DEBUG = os.environ.get("DJANGO_DEBUG") == "1"

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("DJANGO_SECRET_KEY must be configured at runtime.")

ALLOWED_HOSTS = [
    host.strip() for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if host.strip()
]

# An operator may use a local debug server while developing. Public operation
# keeps this enabled and must terminate TLS before the Django browser boundary.
SECURE_SSL_REDIRECT = not DEBUG
