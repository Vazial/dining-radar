"""Acceptance-only candidate-proposal state, guarded like ``LoginThrottle``.

This module implements the ``CandidateProposalAcceptanceState`` seam from
``contracts/test-support-api.yaml``. It is reachable only through
``dining_radar.test_support.views`` and only while ``ACCEPTANCE_TEST_SUPPORT``
is enabled (mirrors the guard on
``dining_radar.authentication.throttle.LoginThrottle.seed_acceptance_limit``).

``NORMAL_WITH_REPEAT`` and ``IZAKAYA_BAR_ONLY`` drive the exact same
production ``suggestions.service.propose_candidates`` pipeline with
synthetic candidates, rather than a hand-written fake response, so those
seams exercise real recommendation logic (including the adr/0015 default
genre exclusion and 5-candidate display cap). ``NO_RESULTS``,
``PROVIDER_UNAVAILABLE``, ``RATE_LIMITED``, and ``INVALID_REPROPOSAL_KIND``
return a fixed synthetic outcome directly, without calling the pipeline.
"""

from __future__ import annotations

from enum import StrEnum

from django.conf import settings
from django.core.cache import cache

from dining_radar.recommendation.pipeline import (
    DEFAULT_EXCLUDED_GENRES,
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

# One confirmed member of pipeline.DEFAULT_EXCLUDED_GENRES (adr/0015), reused
# as the synthetic genre for every default-excluded candidate below rather
# than duplicating the exclusion list here. The assertion keeps this seam
# from silently drifting out of sync if that set's confirmed members change.
_DEFAULT_EXCLUDED_SYNTHETIC_GENRE = "居酒屋"
assert _DEFAULT_EXCLUDED_SYNTHETIC_GENRE in DEFAULT_EXCLUDED_GENRES


class AcceptanceCandidateProposalMode(StrEnum):
    NORMAL_WITH_REPEAT = "NORMAL_WITH_REPEAT"
    IZAKAYA_BAR_ONLY = "IZAKAYA_BAR_ONLY"
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

# A default-excluded-genre candidate (adr/0015), reused unchanged across the
# initial and re-proposal candidate sets below -- unlike the plain "repeat"
# candidate, which models fresh-search overlap (ADR-0008 decision 2), this
# one only needs to be present in both fetches so that (a) the initial
# default proposal excludes it, (b) IZAKAYA_BAR_INCLUDED is offered as a
# re-proposal option from the initial response, and (c) selecting that lens
# includes it (TDR-CS-09), all from this one NORMAL_WITH_REPEAT mode.
_DEFAULT_EXCLUDED_CANDIDATE = _synthetic_candidate(
    name="合成居酒屋 一号店",
    genre=_DEFAULT_EXCLUDED_SYNTHETIC_GENRE,
    provider_page_url="https://example.invalid/acceptance-shop-izakaya",
    latitude=0.0025,
    total_seats=25,
)

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
    _DEFAULT_EXCLUDED_CANDIDATE,
)

# One candidate repeats the initial response's providerPageUrl and one is new,
# so a client can observe the repeat-priority display rule after re-proposal.
# The default-excluded candidate is included unchanged (see its own comment).
_REPROPOSAL_CANDIDATES: tuple[NormalizedCandidate, ...] = (
    _INITIAL_CANDIDATES[0],
    _synthetic_candidate(
        name="合成食堂 三号店",
        genre="中華",
        provider_page_url="https://example.invalid/acceptance-shop-c",
        latitude=0.003,
        total_seats=45,
    ),
    _DEFAULT_EXCLUDED_CANDIDATE,
)

# Only default-excluded-genre candidates, so the primary four concept kinds
# are all unbuildable and the response falls through to IZAKAYA_BAR_INCLUDED
# instead of a successful null proposal (TDR-CS-10). Distinct from NO_RESULTS
# below, which supplies no lunch-eligible candidate at all.
_IZAKAYA_BAR_ONLY_CANDIDATES: tuple[NormalizedCandidate, ...] = (
    _DEFAULT_EXCLUDED_CANDIDATE,
    _synthetic_candidate(
        name="合成居酒屋 二号店",
        genre=_DEFAULT_EXCLUDED_SYNTHETIC_GENRE,
        provider_page_url="https://example.invalid/acceptance-shop-izakaya-2",
        latitude=0.0035,
        total_seats=18,
    ),
)


def _normal_with_repeat_source(
    reproposal_kind: str | None,
) -> tuple[tuple[NormalizedCandidate, ...], Origin]:
    candidates = _REPROPOSAL_CANDIDATES if reproposal_kind else _INITIAL_CANDIDATES
    return candidates, _ORIGIN


def _izakaya_bar_only_source(
    reproposal_kind: str | None,
) -> tuple[tuple[NormalizedCandidate, ...], Origin]:
    del reproposal_kind  # Every fetch in this mode returns the same closed set.
    return _IZAKAYA_BAR_ONLY_CANDIDATES, _ORIGIN


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
    if mode is AcceptanceCandidateProposalMode.IZAKAYA_BAR_ONLY:
        return propose_candidates(
            reproposal_kind,
            fetch_candidates=lambda: _izakaya_bar_only_source(reproposal_kind),
        )

    return propose_candidates(
        reproposal_kind,
        fetch_candidates=lambda: _normal_with_repeat_source(reproposal_kind),
    )
