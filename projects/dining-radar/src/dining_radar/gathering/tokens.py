"""Participant-link token generation (adr/0035 decision 4).

Kept in its own module so ``dining_radar.gathering.services`` reads as
business logic rather than credential-generation mechanics, and so a future
change to the generation scheme touches exactly one place.
"""

from __future__ import annotations

import secrets

# adr/0035 decision 4: "128bitエントロピー". ``secrets.token_urlsafe`` takes a
# byte count, not a bit count -- 16 bytes is exactly 128 bits. The resulting
# string is URL-safe base64 (no padding), roughly 22 characters, so it can be
# embedded directly in a path segment with no additional encoding.
_TOKEN_ENTROPY_BYTES = 16


def generate_participant_token() -> str:
    """A new, unguessable, URL-safe participant-link token.

    Never predictable, never derived from the gathering or participant slot
    it will be assigned to -- adr/0037 decision 4 requires acceptance testing
    to read this same production generator's real output rather than a
    test-only substitute.
    """
    return secrets.token_urlsafe(_TOKEN_ENTROPY_BYTES)
