"""Acceptance-only candidate-proposal state, guarded like ``LoginThrottle``.

This module implements the ``CandidateProposalAcceptanceState`` seam from
``contracts/test-support-api.yaml``. It is reachable only through
``dining_radar.test_support.views`` and only while ``ACCEPTANCE_TEST_SUPPORT``
is enabled (mirrors the guard on
``dining_radar.authentication.throttle.LoginThrottle.seed_acceptance_limit``).

``NORMAL_WITH_POOL``, ``DEFAULT_EXCLUSION_VISIBLE``,
``CARD_PAYMENT_CAUTION_VISIBLE``, and ``IZAKAYA_BAR_ONLY`` drive the exact
same production ``suggestions.service.propose_candidates`` pipeline with
synthetic candidates, rather than a hand-written fake response, so those
seams exercise real filtering/ordering/pool-sampling logic (adr/0023).
``NO_RESULTS``, ``PROVIDER_UNAVAILABLE``, and ``RATE_LIMITED`` return a fixed
synthetic outcome directly, without calling the pipeline.

Per adr/0023 decision 4 hand-off item 4, this module also owns the seeded
random-source injection this seam needs to make pool sampling deterministic
and reproducible for acceptance testing: a pinned ``randomSeed`` (via
``set_mode``) is read back by ``active_random_source`` and passed straight
into ``suggestions.service.propose_candidates``. It is never exposed on the
public ``candidate-search-api.yaml``.
"""

from __future__ import annotations

import random
from enum import StrEnum

from django.conf import settings
from django.core.cache import cache

from dining_radar.recommendation.pipeline import (
    DEFAULT_EXCLUDED_GENRES,
    CandidateFilters,
    NormalizedCandidate,
    Origin,
)

from .service import ProposalResult, propose_candidates

__all__ = [
    "AcceptanceCandidateProposalMode",
    "AcceptanceProviderUnavailable",
    "AcceptanceRateLimited",
    "active_mode",
    "active_random_source",
    "propose_with_override",
    "reset_mode",
    "set_mode",
]

_CACHE_KEY_MODE = "suggestions.acceptance-candidate-proposal-mode"
_CACHE_KEY_SEED = "suggestions.acceptance-candidate-proposal-random-seed"
_SYNTHETIC_RATE_LIMIT_RETRY_AFTER_SECONDS = 30

# One confirmed member of pipeline.DEFAULT_EXCLUDED_GENRES (adr/0015), reused
# as the synthetic genre for every default-excluded candidate below rather
# than duplicating the exclusion list here. The assertion keeps this seam
# from silently drifting out of sync if that set's confirmed members change.
_DEFAULT_EXCLUDED_SYNTHETIC_GENRE = "居酒屋"
assert _DEFAULT_EXCLUDED_SYNTHETIC_GENRE in DEFAULT_EXCLUDED_GENRES


class AcceptanceCandidateProposalMode(StrEnum):
    NORMAL_WITH_POOL = "NORMAL_WITH_POOL"
    DEFAULT_EXCLUSION_VISIBLE = "DEFAULT_EXCLUSION_VISIBLE"
    CARD_PAYMENT_CAUTION_VISIBLE = "CARD_PAYMENT_CAUTION_VISIBLE"
    IZAKAYA_BAR_ONLY = "IZAKAYA_BAR_ONLY"
    NO_RESULTS = "NO_RESULTS"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
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


def set_mode(mode: AcceptanceCandidateProposalMode, random_seed: int | None = None) -> None:
    """Select the synthetic mode and (optionally) pin the random pool-sampling seed.

    ``random_seed`` mirrors ``CandidateProposalAcceptanceState.randomSeed``
    (adr/0023 decision 4): omitted or ``None`` leaves sampling
    non-deterministic, matching production.
    """
    _require_acceptance_profile()
    cache.set(_CACHE_KEY_MODE, mode.value, timeout=None)
    if random_seed is None:
        cache.delete(_CACHE_KEY_SEED)
    else:
        cache.set(_CACHE_KEY_SEED, random_seed, timeout=None)


def reset_mode() -> None:
    cache.delete(_CACHE_KEY_MODE)
    cache.delete(_CACHE_KEY_SEED)


def active_mode() -> AcceptanceCandidateProposalMode | None:
    if not getattr(settings, "ACCEPTANCE_TEST_SUPPORT", False):
        return None
    raw = cache.get(_CACHE_KEY_MODE)
    return AcceptanceCandidateProposalMode(raw) if raw else None


def active_random_source() -> random.Random:
    """The random source ``propose_with_override`` injects into the pipeline.

    A seeded ``random.Random`` when a ``randomSeed`` is currently pinned
    (``set_mode``); otherwise a fresh, unseeded one (non-deterministic,
    matching production). Outside the acceptance profile this always returns
    an unseeded source, since the seed cache entry is never read there.
    """
    seed = (
        cache.get(_CACHE_KEY_SEED) if getattr(settings, "ACCEPTANCE_TEST_SUPPORT", False) else None
    )
    return random.Random(seed) if seed is not None else random.Random()


def _synthetic_candidate(
    *,
    name: str,
    genre: str,
    provider_page_url: str,
    latitude: float,
    total_seats: int | None = None,
    non_smoking_status: str | None = None,
    card_payment_available: bool | None = None,
    budget_average: float | None = None,
) -> NormalizedCandidate:
    """A deterministic, clearly fictional synthetic shop."""
    return NormalizedCandidate(
        name=name,
        genre=genre,
        description=f"{name}の紹介文（合成データ）です。",
        regular_holiday="日曜・祝日",
        total_seats=total_seats,
        non_smoking_status=non_smoking_status,
        card_payment_available=card_payment_available,
        budget_average=budget_average,
        latitude=latitude,
        longitude=0.0,
        provider_page_url=provider_page_url,
    )


_ORIGIN = Origin(latitude=0.0, longitude=0.0)

# A default-excluded-genre candidate (adr/0015/adr/0023), reused by both
# NORMAL_WITH_POOL (as the sole excluded-genre member of its population) and
# IZAKAYA_BAR_ONLY.
_DEFAULT_EXCLUDED_CANDIDATE = _synthetic_candidate(
    name="合成居酒屋 一号店",
    genre=_DEFAULT_EXCLUDED_SYNTHETIC_GENRE,
    provider_page_url="https://example.invalid/acceptance-shop-izakaya",
    latitude=0.0008,
    total_seats=25,
)

# test-support-api.yaml v1.0.0 (adr/0023): NORMAL_WITH_POOL must supply at
# least 40 lunch-eligible synthetic candidates in the default
# (non-excluded-genre) population -- comfortably exceeding any reasonable
# pool-size implementation choice (decision 4 recommends 20) -- spanning at
# least 3 distinct genres (each with at least 2 members), at least 2 distinct
# nonSmokingStatus values, at least one candidate each with
# cardPaymentAvailable true and false, and at least one candidate each with a
# non-null dinnerBudgetTier and a null value for at least one of
# nonSmokingStatus/cardPaymentAvailable/dinnerBudgetTier (TDR-CS-13's
# ordering rule).
#
# Generated deterministically by cycling five genres, four non-smoking
# references (including the unconfirmed/None bucket), three card-payment
# values (including None), and five budget figures (including None) across
# 40 candidates spaced by latitude (this module's proximity approximation
# with longitude fixed at 0.0, see pipeline._distance) so ranking is
# deterministic and every combination of "confirmed"/"unconfirmed" for every
# soft filter is reachable.
_POOL_GENRES: tuple[str, ...] = ("和食", "洋食", "中華", "エスニック", "カフェ・スイーツ")
_POOL_NON_SMOKING_CYCLE: tuple[str | None, ...] = ("FULL", "PARTIAL", "NONE", None)
_POOL_CARD_PAYMENT_CYCLE: tuple[bool | None, ...] = (True, False, None)
_POOL_BUDGET_CYCLE: tuple[float | None, ...] = (1500.0, 2500.0, 3500.0, 4500.0, None)
_POOL_SIZE = 40


def _pool_candidate(index: int) -> NormalizedCandidate:
    return _synthetic_candidate(
        name=f"合成母集団食堂 {index:02d}号店",
        genre=_POOL_GENRES[index % len(_POOL_GENRES)],
        provider_page_url=f"https://example.invalid/acceptance-pool-shop-{index:02d}",
        latitude=0.0010 + index * 0.0002,
        total_seats=20 + index,
        non_smoking_status=_POOL_NON_SMOKING_CYCLE[index % len(_POOL_NON_SMOKING_CYCLE)],
        card_payment_available=_POOL_CARD_PAYMENT_CYCLE[index % len(_POOL_CARD_PAYMENT_CYCLE)],
        budget_average=_POOL_BUDGET_CYCLE[index % len(_POOL_BUDGET_CYCLE)],
    )


_POOL_CANDIDATES: tuple[NormalizedCandidate, ...] = tuple(
    _pool_candidate(index) for index in range(_POOL_SIZE)
)

_CANDIDATES: tuple[NormalizedCandidate, ...] = (*_POOL_CANDIDATES, _DEFAULT_EXCLUDED_CANDIDATE)

# The two focused TDR-CS Givens intentionally have an eligible population no
# larger than DISPLAY_CAP. Their visible result is therefore independent of a
# random seed, while still running through the production pipeline rather
# than bypassing its filtering, default exclusion, and serialization paths.
_DEFAULT_EXCLUSION_VISIBLE_CANDIDATES: tuple[NormalizedCandidate, ...] = (
    _synthetic_candidate(
        name="Synthetic default-eligible one",
        genre="Synthetic Japanese",
        provider_page_url="https://example.invalid/acceptance-default-visible-one",
        latitude=0.0010,
        card_payment_available=True,
    ),
    _synthetic_candidate(
        name="Synthetic default-eligible two",
        genre="Synthetic Western",
        provider_page_url="https://example.invalid/acceptance-default-visible-two",
        latitude=0.0020,
        card_payment_available=None,
    ),
    _synthetic_candidate(
        name="Synthetic default-excluded",
        genre=_DEFAULT_EXCLUDED_SYNTHETIC_GENRE,
        provider_page_url="https://example.invalid/acceptance-default-visible-excluded",
        latitude=0.0005,
        card_payment_available=False,
    ),
)

_CARD_PAYMENT_CAUTION_VISIBLE_CANDIDATES: tuple[NormalizedCandidate, ...] = (
    _synthetic_candidate(
        name="Synthetic card unavailable",
        genre="Synthetic Card Test",
        provider_page_url="https://example.invalid/acceptance-card-unavailable",
        latitude=0.0010,
        card_payment_available=False,
    ),
    _synthetic_candidate(
        name="Synthetic card available",
        genre="Synthetic Card Test",
        provider_page_url="https://example.invalid/acceptance-card-available",
        latitude=0.0020,
        card_payment_available=True,
    ),
    _synthetic_candidate(
        name="Synthetic card unknown",
        genre="Synthetic Card Test",
        provider_page_url="https://example.invalid/acceptance-card-unknown",
        latitude=0.0030,
        card_payment_available=None,
    ),
)

# Only default-excluded-genre candidates, so the default population (with
# includeIzakayaBar=false) is empty and the response falls through to the
# izakaya-bar-inclusive one instead of a successful no-results outcome
# (TDR-CS-10). Distinct from NO_RESULTS below, which supplies no
# lunch-eligible candidate at all.
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


def _normal_with_pool_source() -> tuple[tuple[NormalizedCandidate, ...], Origin]:
    return _CANDIDATES, _ORIGIN


def _izakaya_bar_only_source() -> tuple[tuple[NormalizedCandidate, ...], Origin]:
    return _IZAKAYA_BAR_ONLY_CANDIDATES, _ORIGIN


def _default_exclusion_visible_source() -> tuple[tuple[NormalizedCandidate, ...], Origin]:
    return _DEFAULT_EXCLUSION_VISIBLE_CANDIDATES, _ORIGIN


def _card_payment_caution_visible_source() -> tuple[tuple[NormalizedCandidate, ...], Origin]:
    return _CARD_PAYMENT_CAUTION_VISIBLE_CANDIDATES, _ORIGIN


def propose_with_override(
    mode: AcceptanceCandidateProposalMode, filters: CandidateFilters
) -> ProposalResult:
    """The deterministic (or seeded-random) synthetic outcome for ``mode``.

    ``filters`` is passed straight through to ``propose_candidates`` for the
    two modes that run the real pipeline; it is otherwise unused, matching
    the other modes' fixed synthetic outcomes.
    """
    if mode is AcceptanceCandidateProposalMode.PROVIDER_UNAVAILABLE:
        raise AcceptanceProviderUnavailable
    if mode is AcceptanceCandidateProposalMode.RATE_LIMITED:
        raise AcceptanceRateLimited(_SYNTHETIC_RATE_LIMIT_RETRY_AFTER_SECONDS)
    if mode is AcceptanceCandidateProposalMode.NO_RESULTS:
        return ProposalResult((), False, ())
    if mode is AcceptanceCandidateProposalMode.IZAKAYA_BAR_ONLY:
        return propose_candidates(
            filters,
            fetch_candidates=_izakaya_bar_only_source,
            random_source=active_random_source(),
        )
    if mode is AcceptanceCandidateProposalMode.DEFAULT_EXCLUSION_VISIBLE:
        return propose_candidates(
            filters,
            fetch_candidates=_default_exclusion_visible_source,
            random_source=active_random_source(),
        )
    if mode is AcceptanceCandidateProposalMode.CARD_PAYMENT_CAUTION_VISIBLE:
        return propose_candidates(
            filters,
            fetch_candidates=_card_payment_caution_visible_source,
            random_source=active_random_source(),
        )

    return propose_candidates(
        filters,
        fetch_candidates=_normal_with_pool_source,
        random_source=active_random_source(),
    )
