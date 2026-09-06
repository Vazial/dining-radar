"""An isolated local HTTP profile alias for acceptance automation.

2026-09-06: this module used to carry its own copy of the sqlite
concurrency fix (a real on-disk `TEST.NAME` database file plus
`synchronous=OFF`) for `tests/acceptance/**`'s threaded live server. That
fix was correctly diagnosed but wired to the wrong place: nothing in this
repository ever actually selects *this* module by default -- `manage.py
test` without an explicit `--settings` flag, and pytest's own
`DJANGO_SETTINGS_MODULE` (`pyproject.toml`), both resolve to
`settings_test` instead. The fix now lives there (see that module's own
docstring for the full mechanism and the confirmed reproduction), and this
module is kept only as a re-export in case anything still names it
explicitly (`--settings=dining_radar.settings_acceptance`).
"""

from .settings_test import *  # noqa: F401,F403
