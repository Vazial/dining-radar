"""Synthetic settings used only by the repository's automated tests."""

import os
import tempfile
from pathlib import Path

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

# 2026-09-06 fix (intermittent tests.acceptance failures -- a bare, non-JSON
# HTTP 500 from getParticipantView, and the "gathering-schedule-question
# not found" symptom that a request failing this way with no recognized
# linkError code produces via unexpectedLoadFailureOutcome, adr/0047):
# `manage.py test` (manage.py's own routing, no explicit --settings flag)
# and `pytest` (pyproject.toml's DJANGO_SETTINGS_MODULE) both select *this*
# module by default -- including for tests/acceptance/**, whose
# StaticLiveServerTestCase-based tests spin up a real, threaded HTTP server
# (Django's ThreadedWSGIServer) driven by a real browser that issues
# genuinely concurrent requests (Playwright's own background requests --
# e.g. Leaflet tile fetches -- alongside whichever request a DSL step is
# waiting on). This module's own `:memory:` sqlite database is safe for
# every *other* test in this project (plain `manage.py test tests`/pytest
# runs are single-threaded, one request at a time, never touching
# django.test.testcases.LiveServerTestCase at all), but is not safe for
# that one: Django's own `LiveServerTestCase._make_connections_override`
# (django/test/testcases.py) detects `conn.is_in_memory_db()` and, only in
# that case, hands the *one* already-open connection object to every
# request-handling thread the ThreadedWSGIServer spawns, because a fresh
# connection to `:memory:` would otherwise be a distinct, empty database.
# That sharing is exactly what breaks under real concurrency: two requests
# handled on two threads at the same moment can each open/release a
# SAVEPOINT (every `update_or_create`/`get_or_create`/nested
# `transaction.atomic()` in this codebase's services.py does) on the *same*
# underlying sqlite3 connection object at once, corrupting its savepoint
# stack. Reproduced directly (throwaway script, not committed): repeated
# concurrent GET /participant-links/{token} and PUT .../responses/{id}
# requests against a real live server using this exact configuration
# yielded a bare, non-JSON HTTP 500 with this real server-side traceback:
# `django.db.utils.DatabaseError: not an error`, raised from
# `connection.savepoint_commit` inside `set_schedule_response`'s
# `ScheduleResponse.objects.update_or_create(...)`.
#
# This exact mechanism, and this exact fix (a real on-disk sqlite file --
# not `is_in_memory_db()`, so LiveServerTestCase never installs
# connections_override for it, and every request-handling thread gets its
# own independent connection the ordinary way -- plus a generous busy-wait
# `timeout` and `synchronous=OFF` since this file is discarded every run
# regardless of outcome), was first diagnosed and applied to a *different*
# settings module, `settings_acceptance.py` (added under
# `fix/intermittent-schedule-question`). That module is never actually
# selected by anything in this repository -- `manage.py test` without an
# explicit `--settings` flag and pytest's own `DJANGO_SETTINGS_MODULE` both
# resolve to *this* module, `settings_test`, not `settings_acceptance` --
# so that first fix, while correctly diagnosed, silently fixed nothing in
# the environment CI and the documented default invocation actually use.
# Confirmed directly: `manage.py test tests --settings=dining_radar.
# settings_test` (this module, unpatched) reproduced the same bare 500 from
# getParticipantView that the original diagnosis described.
# `settings_acceptance.py` now just re-exports this module instead of
# duplicating (and only here, correctly landing) this fix.
_ACCEPTANCE_TEST_DB_PATH = str(
    Path(tempfile.gettempdir()) / f"dining_radar_test_{os.getpid()}.sqlite3"
)
DATABASES = {  # noqa: F405
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
        # DATABASES["default"]["TEST"]["NAME"], not the top-level "NAME"
        # above it: `manage.py test`/pytest never open the connection's own
        # configured "NAME" at all -- sqlite3's own
        # `DatabaseCreation._get_test_db_name` (django/db/backends/sqlite3/
        # creation.py) reads `self.connection.settings_dict["TEST"]["NAME"]`
        # specifically, defaulting to the shared-cache `:memory:` URI
        # whenever that key is absent, regardless of what the top-level
        # "NAME" says. A fixed path is not reused across processes (this
        # project's own diagnostic runs -- several full acceptance suites
        # in parallel, one process each -- would otherwise collide on one
        # file), so the name includes this process's pid; the test runner
        # deletes the file at teardown the same way it already discards
        # `:memory:` (no accumulation across runs, short of a hard crash
        # before teardown).
        "TEST": {"NAME": _ACCEPTANCE_TEST_DB_PATH},
        # A real on-disk sqlite file (unlike the shared in-memory connection
        # above) still allows only one writer at a time; sqlite3's own
        # default busy-wait before raising "database is locked" is 5
        # seconds (matching this project's own default Playwright assertion
        # timeout almost exactly, and tests/acceptance's own PUT-heavy
        # scenarios already do occasionally overlap in real, unscripted
        # ways -- e.g. a page's other in-flight request finishing just as
        # the next DSL step's own request lands). Raised generously since
        # this is a local, test-only database with no real user waiting on
        # it.
        #
        # `synchronous=OFF`: switching off `:memory:` alone, without this
        # pragma, made the *whole acceptance suite* run many times slower
        # with the server-handling thread(s) sitting at single-digit-second
        # CPU time for minutes of wall time, i.e. blocked on I/O, not on
        # any other thread's lock: sqlite's default rollback-journal mode
        # calls fsync() on every COMMIT for durability against a real
        # crash, and every request in that suite is its own commit. A test
        # database that is deleted at teardown regardless of outcome (this
        # file already is) has nothing to protect against a crash, so that
        # durability guarantee buys nothing here and only pays its cost.
        "OPTIONS": {"timeout": 30, "init_command": "PRAGMA synchronous=OFF;"},
    }
}
