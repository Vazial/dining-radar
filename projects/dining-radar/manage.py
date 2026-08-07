#!/usr/bin/env python
"""Django command entry point for the Toyama Dining Radar application."""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = PROJECT_ROOT / "src"


def _has_explicit_settings_argument(arguments: list[str]) -> bool:
    return any(
        argument == "--settings" or argument.startswith("--settings=") for argument in arguments
    )


def _load_local_env_file(path: Path) -> None:
    """Populate ``os.environ`` from an optional developer-local file.

    ``env.example`` (ADR-0040) documents every variable `src/dining_radar`
    reads and tells a developer to copy it to ``.env.local`` next to this
    script; the repository root `.gitignore`'s unanchored `.env*` pattern
    keeps that copy out of git at any depth. This is the loader that makes
    that copy take effect.

    Deliberately scoped to this entry point rather than to
    `dining_radar.settings`: `settings.py`'s docstring already states "The
    deployment supplies its own signing secret and host allowlist", and a
    real deployment runs the WSGI application (`wsgi.py`), not this script,
    so production is unaffected either way. Keeping the read here also
    leaves `dining_radar.settings` byte-for-byte what
    `tests/test_structure.py` and `tests/test_bootstrap.py` already exercise
    directly with `os.environ` cleared or patched.

    A variable already present in the real process environment always wins
    (`os.environ.setdefault`), so CI and any deployment that sets these
    variables directly behave identically whether or not this file exists.
    A missing file is a silent no-op.
    """
    if not path.is_file():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]

        if key:
            os.environ.setdefault(key, value)


def main() -> None:
    if str(SOURCE_ROOT) not in sys.path:
        sys.path.insert(0, str(SOURCE_ROOT))

    _load_local_env_file(PROJECT_ROOT / ".env.local")

    command_arguments = sys.argv[1:]
    if command_arguments[:1] == ["test"] and not _has_explicit_settings_argument(command_arguments):
        # `manage.py test` is the documented local acceptance runner. It must
        # not accidentally select public HTTPS settings or expose test support
        # in a normal runtime command.
        os.environ["DJANGO_SETTINGS_MODULE"] = "dining_radar.settings_test"
    else:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dining_radar.settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
