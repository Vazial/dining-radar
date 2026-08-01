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


def main() -> None:
    if str(SOURCE_ROOT) not in sys.path:
        sys.path.insert(0, str(SOURCE_ROOT))

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
