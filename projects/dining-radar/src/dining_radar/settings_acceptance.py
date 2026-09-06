"""An isolated local HTTP profile used exclusively by acceptance automation."""

import os
import tempfile
from pathlib import Path

from .settings_test import *  # noqa: F403

# fix/intermittent-schedule-question (2026-09-06): this profile is the only
# one whose tests (tests/acceptance/**, StaticLiveServerTestCase) exercise a
# real, threaded HTTP server (Django's ThreadedWSGIServer) driven by a real
# browser that issues genuinely concurrent requests (Playwright's own
# background requests -- e.g. Leaflet tile fetches -- alongside whichever
# request a DSL step is waiting on). settings_test's own ``:memory:`` sqlite
# database is safe for every *other* profile that reuses it (plain
# ``manage.py test tests`` runs single-threaded, one request at a time,
# never touching django.test.testcases.LiveServerTestCase at all), but an
# in-memory sqlite database is not: Django's own
# ``LiveServerTestCase._make_connections_override`` (django/test/testcases.py)
# detects `conn.is_in_memory_db()` and, only in that case, hands the *one*
# already-open connection object to every request-handling thread the
# ThreadedWSGIServer spawns, because a fresh connection to ``:memory:``
# would otherwise be a distinct, empty database. That sharing is exactly
# what breaks under real concurrency: two requests handled on two threads
# at the same moment can each open/release a SAVEPOINT (every
# ``update_or_create``/``get_or_create``/nested ``transaction.atomic()`` in
# this codebase's services.py does) on the *same* underlying sqlite3
# connection object at once, corrupting its savepoint stack. Reproduced
# directly (throwaway script, not committed): 60 concurrent GET
# /participant-links/{token} and PUT .../responses/{id} requests against
# this exact settings module's own live server yielded repeated bare, non-
# JSON HTTP 500s (2-3s each) with this real server-side traceback:
# ``django.db.utils.DatabaseError: not an error`` raised from
# ``connection.savepoint_commit`` inside ``set_schedule_response``'s
# ``ScheduleResponse.objects.update_or_create(...)``. That 500 -- an
# HTML body carrying none of linkError's four recognized codes -- is
# exactly what browserControlSurface.participantAnswer's
# unexpectedLoadFailureOutcome (adr/0047) is contractually required to
# treat as a load failure: participant.js's loadView correctly renders
# only gathering-participant-load-error and never builds
# gathering-schedule-question at all, which is the acceptance suite's own
# observed intermittent symptom (TDR-GTH-05/06/07/10/11/12/15 among
# others -- whichever participant request loses this race on a given run).
# The fix is not in participant.js (browserControlSurface's own
# classification is doing exactly what adr/0047 asked) and not in
# services.py/views.py (every save here is correct under a *real*
# database's own connection-per-thread model -- production already runs
# PostgreSQL, per settings.py, which never hits this at all). It is this
# profile's own choice of sqlite database: a real on-disk file is not
# `is_in_memory_db()`, so LiveServerTestCase never installs
# connections_override for it, and every request-handling thread gets its
# own independent connection the ordinary way (django.db.connections is
# already thread-local) -- eliminating the shared savepoint stack, and
# with it this whole failure mode, rather than papering over one
# particular racing view. A fixed path is not reused across processes:
# this project's own diagnostic runs (several full acceptance suites in
# parallel, one process each) would otherwise collide on one file, so the
# name includes this process's pid; Django's own test runner deletes the
# file at teardown the same way it already discards ``:memory:`` (no
# accumulation across runs, short of a hard crash before teardown).
#
# The path belongs under ``DATABASES["default"]["TEST"]["NAME"]``, not the
# top-level ``NAME`` above it: ``manage.py test`` never opens the
# connection's own configured ``NAME`` at all -- sqlite3's
# ``DatabaseCreation._get_test_db_name`` (django/db/backends/sqlite3/
# creation.py) reads ``self.connection.settings_dict["TEST"]["NAME"]``
# specifically, defaulting to the shared-cache ``:memory:`` URI whenever
# that key is absent, regardless of what the top-level ``NAME`` says. A
# first attempt at this fix that only overrode the top-level key was
# verified (same throwaway concurrency probe) to still race -- confirming
# ``TEST.NAME`` is the key that actually governs this.
_ACCEPTANCE_TEST_DB_PATH = str(
    Path(tempfile.gettempdir()) / f"dining_radar_acceptance_{os.getpid()}.sqlite3"
)
DATABASES = {  # noqa: F405
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
        "TEST": {"NAME": _ACCEPTANCE_TEST_DB_PATH},
        # A real on-disk sqlite file (unlike the shared in-memory connection
        # above) still allows only one writer at a time; sqlite3's own
        # default busy-wait before raising "database is locked" is 5
        # seconds (matching this project's own default Playwright assertion
        # timeout almost exactly, and this suite's own PUT-heavy scenarios
        # already do occasionally overlap in real, unscripted ways -- e.g.
        # a page's other in-flight request finishing just as the next DSL
        # step's own request lands). Raised generously since this is a
        # local, test-only database with no real user waiting on it.
        #
        # ``synchronous=OFF``: measured directly (this branch's own commit
        # history) -- switching off ``:memory:`` alone, without this pragma,
        # made the *whole acceptance suite* run many times slower with the
        # server-handling thread(s) sitting at single-digit-second CPU time
        # for minutes of wall time, i.e. blocked on I/O, not on any other
        # thread's lock: sqlite's default rollback-journal mode calls
        # fsync() on every COMMIT for durability against a real crash, and
        # every request in this suite is its own commit. A test database
        # that is deleted at teardown regardless of outcome (this file
        # already is) has nothing to protect against a crash, so that
        # durability guarantee buys nothing here and only pays its cost.
        "OPTIONS": {"timeout": 30, "init_command": "PRAGMA synchronous=OFF;"},
    }
}
