"""Shared Django settings that never include a live deployment value."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "dining_radar.authentication",
    "dining_radar.web",
    "dining_radar.gathering",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "dining_radar.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "dining_radar.wsgi.application"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ja"
TIME_ZONE = "Asia/Tokyo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / ".runtime" / "staticfiles"
# This project serves no uploaded/media files (no FileField/ImageField), but
# Django's own default MEDIA_URL == "" (unset) leaves a real, environment-
# specific landmine for LiveServerTestCase-based acceptance tests
# (StaticLiveServerTestCase's own LiveServerThread wraps every request in
# `_MediaFilesHandler(WSGIHandler())`, whose `_should_handle()` -- "path.
# startswith(self.base_url.path)" -- degenerates to "always true" whenever
# MEDIA_URL is the empty string, since every path starts with ""). Real
# measurement, 2026-09-11: gathering-scheduling-api.yaml's own contracted
# `POST /gatherings/{gatheringId}/candidate-dates:batch` path (the literal
# colon is part of the approved contract, not renameable) made Windows'
# `nturl2path.url2pathname` -- which `_MediaFilesHandler.file_path()` calls
# unconditionally on every request once `_should_handle` degenerates this
# way -- misparse the colon as a drive-letter separator and collapse the
# path to a nonsense fragment ("S:batch"), raising an uncaught
# `SuspiciousFileOperation` (not the `Http404` this handler's own code
# expects and catches) as a raw 500 before the request ever reached
# urls.py/views.py. Giving MEDIA_URL its own real, non-empty prefix (the
# same relative-path shape STATIC_URL already uses) restores
# `_should_handle`'s intended behavior -- only requests actually under
# `/media/` take this path-conversion route at all -- closing the landmine
# for every other URL in this project, not just this one contracted path.
MEDIA_URL = "media/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# These are public application invariants. A local debug server may opt out of
# HTTPS redirect only; it does not weaken the production defaults.
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"

# The runtime database is intentionally outside version control. It contains
# Django-managed account and session state, never provider data or fixtures.
RUNTIME_DIR = BASE_DIR / ".runtime"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": RUNTIME_DIR / "dining-radar.sqlite3",
    }
}

# Django's cache interface makes the login limiter replaceable with a shared
# runtime cache during deployment. No request history is committed.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "dining-radar-auth",
    }
}

LOGIN_URL = "authentication:login"
LOGIN_REDIRECT_URL = "web:home"
LOGOUT_REDIRECT_URL = "authentication:login"
