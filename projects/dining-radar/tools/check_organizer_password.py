"""Report which password validator rejects a candidate organizer password.

``provision_organizer`` deliberately reports only "not acceptable", so a
failing build never discloses anything about the configured secret. That is
correct for a build log and useless for choosing a password, so this local
helper applies the very same validators and prints their own messages.

Run it on your own machine, never in CI or a deploy log:

    python tools/check_organizer_password.py

It prompts for the username and password without echoing the password and
without taking either from argv, so neither reaches your shell history. The
value is never written to disk, sent anywhere, or logged.
"""

import getpass
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
# settings_test sets AUTH_PASSWORD_VALIDATORS = [] so the suite can use short
# fixtures; asking it would approve anything. settings_base holds the list the
# production module inherits unchanged, which is the list the build applies.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dining_radar.settings_base")

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.contrib.auth.password_validation import validate_password  # noqa: E402
from django.core.exceptions import ValidationError  # noqa: E402


def main() -> int:
    # Django renders these messages in LANGUAGE_CODE (ja), which a cp932
    # console mangles. Force UTF-8 so the reason stays readable.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")

    username = input("DJANGO_BOOTSTRAP_ORGANIZER_USERNAME: ").strip()
    password = getpass.getpass("DJANGO_BOOTSTRAP_ORGANIZER_PASSWORD (echo off): ")

    user = get_user_model()(username=username)
    try:
        validate_password(password, user=user)
    except ValidationError as error:
        print("\nNG - this password would fail the build:")
        for message in error.messages:
            print(f"  - {message}")
        return 1
    print("\nOK - this password passes every validator provision_organizer applies.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
