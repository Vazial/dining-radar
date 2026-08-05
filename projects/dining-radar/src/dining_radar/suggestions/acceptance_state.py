"""Acceptance-only candidate-proposal state, guarded like ``LoginThrottle``.

This module implements the ``CandidateProposalAcceptanceState`` seam from
``contracts/test-support-api.yaml``. It is reachable only through
``dining_radar.test_support.views`` and only while ``ACCEPTANCE_TEST_SUPPORT``
is enabled (mirrors the guard on
``dining_radar.authentication.throttle.LoginThrottle.seed_acceptance_limit``).

Every synthetic mode except ``NORMAL_WITH_REPEAT`` and ``NO_RESULTS`` drives
the exact same production ``suggestions.service.propose_candidates`` pipeline
with synthetic candidates, rather than a hand-written fake response, so the
acceptance seam exercises real recommendation logic.
"""

from __future__ import annotations

from enum import StrEnum

from django.conf import settings
from django.core.cache import cache

from dining_radar.recommendation.pipeline import (
    NormalizedCandidate,
    Origin,
    ReproposalKindUnavailableError,
)

from .service import ProposalResult, propose_candidates

__all__ = [
    "AcceptanceCandidateProposalMode",
    "AcceptanceProviderUnavailable",
    "AcceptanceRateLimited",
    "active_mode",
    "propose_with_override",
    "reset_mode",
    "set_mode",
]

_CACHE_KEY = "suggestions.acceptance-candidate-proposal-mode"
_SYNTHETIC_RATE_LIMIT_RETRY_AFTER_SECONDS = 30


class AcceptanceCandidateProposalMode(StrEnum):
    NORMAL_WITH_REPEAT = "NORMAL_WITH_REPEAT"
    NO_RESULTS = "NO_RESULTS"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    INVALID_REPROPOSAL_KIND = "INVALID_REPROPOSAL_KIND"
    RATE_LIMITED = "RATE_LIMITED"


class AcceptanceProviderUnavailable(RuntimeError):
    """Mirrors the public 503 PROVIDER_UNAVAILABLE outcome for this seam."""


class AcceptanceRateLimited(RuntimeError):
    """Mirrors the public 429 PROPOSAL_RATE_LIMITED outcome for this seam."""

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("Synthetic acceptance rate limit is active.")
        self.retry_after_seconds = retry_after_seconds


def _require_acceptance_profile() -> None:
    if not getattr(settings, "ACCEPTANCE_TEST_SUPPORT", False):
        raise RuntimeError(
            "The candidate-proposal acceptance seam is unavailable outside the acceptance profile."
        )


def set_mode(mode: AcceptanceCandidateProposalMode) -> None:
    _require_acceptance_profile()
    cache.set(_CACHE_KEY, mode.value, timeout=None)


def reset_mode() -> None:
    cache.delete(_CACHE_KEY)


def active_mode() -> AcceptanceCandidateProposalMode | None:
    if not getattr(settings, "ACCEPTANCE_TEST_SUPPORT", False):
        return None
    raw = cache.get(_CACHE_KEY)
    return AcceptanceCandidateProposalMode(raw) if raw else None


def _synthetic_candidate(
    *,
    name: str,
    genre: str,
    provider_page_url: str,
    latitude: float,
    total_seats: int | None = None,
) -> NormalizedCandidate:
    """A deterministic, clearly fictional synthetic shop.

    Amenity data is intentionally never supplied so ``AMENITY_REFERENCE``
    stays unbuildable, matching the contract's ``NORMAL_WITH_REPEAT``
    requirement that it is excluded from every response's
    ``reProposalOptions``.
    """
    return NormalizedCandidate(
        name=name,
        genre=genre,
        description=f"{name}の紹介文（合成データ）です。",
        business_hours="11:00-14:30",
        regular_holiday="日曜・祝日",
        total_seats=total_seats,
        access="合成アクセス情報",
        latitude=latitude,
        longitude=0.0,
        provider_page_url=provider_page_url,
        amenity_score=0,
    )


_ORIGIN = Origin(latitude=0.0, longitude=0.0)

_INITIAL_CANDIDATES: tuple[NormalizedCandidate, ...] = (
    _synthetic_candidate(
        name="合成食堂 一号店",
        genre="和食",
        provider_page_url="https://example.invalid/acceptance-shop-a",
        latitude=0.001,
        total_seats=30,
    ),
    _synthetic_candidate(
        name="合成食堂 二号店",
        genre="洋食",
        provider_page_url="https://example.invalid/acceptance-shop-b",
        latitude=0.002,
        total_seats=20,
    ),
)

# One candidate repeats the initial response's providerPageUrl and one is new,
# so a client can observe the repeat-priority display rule after re-proposal.
_REPROPOSAL_CANDIDATES: tuple[NormalizedCandidate, ...] = (
    _INITIAL_CANDIDATES[0],
    _synthetic_candidate(
        name="合成食堂 三号店",
        genre="中華",
        provider_page_url="https://example.invalid/acceptance-shop-c",
        latitude=0.003,
        total_seats=45,
    ),
)


def _normal_with_repeat_source(
    reproposal_kind: str | None,
) -> tuple[tuple[NormalizedCandidate, ...], Origin]:
    candidates = _REPROPOSAL_CANDIDATES if reproposal_kind else _INITIAL_CANDIDATES
    return candidates, _ORIGIN


def propose_with_override(
    mode: AcceptanceCandidateProposalMode, reproposal_kind: str | None
) -> ProposalResult:
    """The deterministic synthetic outcome for the currently selected mode."""
    if mode is AcceptanceCandidateProposalMode.PROVIDER_UNAVAILABLE:
        raise AcceptanceProviderUnavailable
    if mode is AcceptanceCandidateProposalMode.RATE_LIMITED:
        raise AcceptanceRateLimited(_SYNTHETIC_RATE_LIMIT_RETRY_AFTER_SECONDS)
    if mode is AcceptanceCandidateProposalMode.INVALID_REPROPOSAL_KIND:
        raise ReproposalKindUnavailableError(reproposal_kind)
    if mode is AcceptanceCandidateProposalMode.NO_RESULTS:
        return ProposalResult(None, [])

    return propose_candidates(
        reproposal_kind,
        fetch_candidates=lambda: _normal_with_repeat_source(reproposal_kind),
    )
