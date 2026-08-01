"""Synthetic settings used only by the repository's automated tests."""

from .settings_base import *  # noqa: F403

DEBUG = False
SECRET_KEY = "test-only-signing-value-not-a-runtime-secret"
ALLOWED_HOSTS = ["testserver", "localhost"]
SECURE_SSL_REDIRECT = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
# Password policy is intentionally deferred by ADR-0006. The isolated
# acceptance profile accepts its contract-supplied synthetic credentials rather
# than making browser behavior depend on a policy selected in a later slice.
AUTH_PASSWORD_VALIDATORS = []

# The repository test runner is an isolated local acceptance environment. Its
# HTTP-only session exception is bounded by ADR-0007 and is never imported by
# the public runtime settings module.
ACCEPTANCE_TEST_SUPPORT = True
ROOT_URLCONF = "dining_radar.acceptance_urls"
SESSION_COOKIE_SECURE = False
# Keep CSRF protection while avoiding a second Secure cookie that a local HTTP
# acceptance browser could not return. The CSRF secret stays server-side in the
# local session and the form/header token remains mandatory.
CSRF_USE_SESSIONS = True

DATABASES = {  # noqa: F405
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
