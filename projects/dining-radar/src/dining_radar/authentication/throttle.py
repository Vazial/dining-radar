"""Generic-response login throttling without account-state disclosure."""

import hashlib
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache


@dataclass(frozen=True)
class LoginThrottle:
    """Counts failed attempts by an opaque request fingerprint in the runtime cache."""

    request: object
    username: str

    @property
    def max_failures(self) -> int:
        return getattr(settings, "LOGIN_THROTTLE_MAX_FAILURES", 5)

    @property
    def window_seconds(self) -> int:
        return getattr(settings, "LOGIN_THROTTLE_WINDOW_SECONDS", 300)

    @property
    def key(self) -> str:
        remote_address = self.request.META.get("REMOTE_ADDR", "")
        submitted_identity = self.username.casefold().strip()
        fingerprint = hashlib.sha256(
            f"{remote_address}\x00{submitted_identity}".encode()
        ).hexdigest()
        return f"authentication.login-failures.{fingerprint}"

    @property
    def acceptance_seed_key(self) -> str:
        """A test-only key used to make the acceptance Given deterministic."""
        submitted_identity = self.username.casefold().strip()
        fingerprint = hashlib.sha256(submitted_identity.encode("utf-8")).hexdigest()
        return f"authentication.acceptance-login-failures.{fingerprint}"

    def is_limited(self) -> bool:
        request_failures = cache.get(self.key) or 0
        acceptance_failure = (
            cache.get(self.acceptance_seed_key) or 0
            if getattr(settings, "ACCEPTANCE_TEST_SUPPORT", False)
            else 0
        )
        return max(request_failures, acceptance_failure) >= self.max_failures

    def record_failure(self) -> None:
        cache.add(self.key, 0, timeout=self.window_seconds)
        try:
            cache.incr(self.key)
        except ValueError:
            cache.set(self.key, 1, timeout=self.window_seconds)

    def clear(self) -> None:
        cache.delete(self.key)

    def seed_acceptance_limit(self) -> None:
        """Mark the next same-identifier acceptance login as normally throttled."""
        if not getattr(settings, "ACCEPTANCE_TEST_SUPPORT", False):
            raise RuntimeError(
                "Acceptance throttle seeding is unavailable outside the acceptance profile."
            )
        cache.set(self.acceptance_seed_key, self.max_failures, timeout=self.window_seconds)
