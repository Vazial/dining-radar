"""Per-organizer proposal request throttling.

Mirrors ``dining_radar.authentication.throttle.LoginThrottle``: a generic,
runtime-cache-only limiter that never persists request history and is
separate from the provider's own rate limiting (``ARCHITECTURE.md``
``suggestions`` boundary).
"""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache


@dataclass(frozen=True)
class ProposalThrottle:
    """Counts proposal requests for one authenticated organizer."""

    request: object

    @property
    def max_requests(self) -> int:
        return getattr(settings, "PROPOSAL_RATE_LIMIT_MAX_REQUESTS", 20)

    @property
    def window_seconds(self) -> int:
        return getattr(settings, "PROPOSAL_RATE_LIMIT_WINDOW_SECONDS", 60)

    @property
    def key(self) -> str:
        user_id = getattr(self.request.user, "pk", "anonymous")
        return f"suggestions.proposal-requests.{user_id}"

    def is_limited(self) -> bool:
        return (cache.get(self.key) or 0) >= self.max_requests

    def record_request(self) -> None:
        cache.add(self.key, 0, timeout=self.window_seconds)
        try:
            cache.incr(self.key)
        except ValueError:
            cache.set(self.key, 1, timeout=self.window_seconds)
