"""Acceptance-only candidate-proposal state, guarded like ``LoginThrottle``.

This module implements the ``CandidateProposalAcceptanceState`` seam from
``contracts/test-support-api.yaml``. It is reachable only through
``dining_radar.test_support.views`` and only while ``ACCEPTANCE_TEST_SUPPORT``
is enabled (mirrors the guard on
``dining_radar.authentication.throttle.LoginThrottle.seed_acceptance_limit``).

``NORMAL_WITH_WEIGHTED_SAMPLING`` (renamed from ``NORMAL_WITH_POOL``,
adr/0024 decision 3 -- the fixed near-distance pool it was named for no
longer exists), ``DEFAULT_EXCLUSION_VISIBLE``,
``CARD_PAYMENT_CAUTION_VISIBLE``, ``ZERO_PENDING_MATCH``,
``FALLBACK_PRESERVES_FILTERS``, ``GENRE_ORDER_BY_COUNT``,
``SHOWN_POOL_PRIORITY`` (adr/0024 decisions 1 and 4),
``WALKING_TIME_LIMIT_EXCLUDES`` (adr/0025 decision 3), and
``IZAKAYA_BAR_ONLY`` drive the exact same production
``suggestions.service.propose_candidates`` pipeline with synthetic
candidates, rather than a hand-written fake response, so those seams exercise
real filtering/ordering/selection logic (adr/0023, adr/0024, adr/0025).
``NO_RESULTS``, ``PROVIDER_UNAVAILABLE``, and ``RATE_LIMITED`` return a
fixed synthetic outcome directly, without calling the pipeline.
``RATE_LIMITED_AFTER_INITIAL_SUCCESS`` (human decision 2026-08-23, TDR-CS-16)
is the one mode that does both: its first call runs the real pipeline and
every later call under the same acceptance state raises the same fixed
outcome ``RATE_LIMITED`` does (see its own handling in
``propose_with_override``).

Per adr/0023 decision 4 hand-off item 4, this module also owns the seeded
random-source injection this seam needs to make selection deterministic and
reproducible for acceptance testing: a pinned ``randomSeed`` (via
``set_mode``) is read back by ``active_random_source`` and passed straight
into ``suggestions.service.propose_candidates``. It is never exposed on the
public ``candidate-search-api.yaml``. ``propose_with_override`` also forwards
the caller's ``shown_provider_page_urls`` (adr/0024 decision 4) straight
through to the same pipeline call, for the same reason: this seam must
exercise the real not-yet-shown-priority logic, not a hand-rolled copy of it.

A pinned ``searchOrigin`` (via ``set_mode``, test-support-api.yaml 1.4.0,
independent-audit finding F1) is read back by ``active_search_origin`` and
reported as every mode's ``ProposalResult.search_origin``, independently of
which mode is selected; omitted or ``None`` falls back to this module's own
default ``_ORIGIN``, unchanged from before this property existed. Every
``_..._source`` function's synthetic candidates are translated by the same
delta the origin itself moves by (``_origin_shifted``), so a pinned origin
never changes any distance-, walking-time-, or ordering-dependent property
those populations were authored to prove -- only the response's absolute
``searchOrigin`` (and the never-serialized absolute candidate coordinates)
move.
"""

from __future__ import annotations

import random
from collections.abc import Collection
from dataclasses import replace
from enum import StrEnum

from django.conf import settings
from django.core.cache import cache

from dining_radar.recommendation.pipeline import (
    DEFAULT_EXCLUDED_GENRES,
    METERS_PER_DEGREE_LATITUDE,
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
    "active_search_origin",
    "propose_with_override",
    "reset_mode",
    "set_mode",
]

_CACHE_KEY_MODE = "suggestions.acceptance-candidate-proposal-mode"
_CACHE_KEY_SEED = "suggestions.acceptance-candidate-proposal-random-seed"
# CandidateProposalAcceptanceState.searchOrigin (test-support-api.yaml
# 1.4.0, independent-audit finding F1 / adr/0027 2026-08-24 addendum 2):
# stored as a plain (latitude, longitude) tuple, not an Origin instance, so
# this key stays trivially picklable across whichever CACHES backend the
# deployed profile configures (mirrors _CACHE_KEY_SEED storing a plain int
# rather than a richer object).
_CACHE_KEY_SEARCH_ORIGIN = "suggestions.acceptance-candidate-proposal-search-origin"
# TDR-CS-16 (human decision 2026-08-23): RATE_LIMITED_AFTER_INITIAL_SUCCESS's
# own call counter -- the only mode whose synthetic outcome differs between
# the first and every later /candidate-proposals request within the same
# acceptance scenario (see its own handling in propose_with_override for why
# a second set_mode call was deliberately not used for this). Reset whenever
# a mode is (re)selected or the seam is reset, so re-selecting this mode
# (or any other) always starts its count fresh.
_CACHE_KEY_RATE_LIMITED_AFTER_INITIAL_SUCCESS_CALLS = (
    "suggestions.acceptance-rate-limited-after-initial-success-calls"
)
_SYNTHETIC_RATE_LIMIT_RETRY_AFTER_SECONDS = 30

# One confirmed member of pipeline.DEFAULT_EXCLUDED_GENRES (adr/0015), reused
# as the synthetic genre for every default-excluded candidate below rather
# than duplicating the exclusion list here. The assertion keeps this seam
# from silently drifting out of sync if that set's confirmed members change.
_DEFAULT_EXCLUDED_SYNTHETIC_GENRE = "居酒屋"
assert _DEFAULT_EXCLUDED_SYNTHETIC_GENRE in DEFAULT_EXCLUDED_GENRES


class AcceptanceCandidateProposalMode(StrEnum):
    NORMAL_WITH_WEIGHTED_SAMPLING = "NORMAL_WITH_WEIGHTED_SAMPLING"
    DEFAULT_EXCLUSION_VISIBLE = "DEFAULT_EXCLUSION_VISIBLE"
    CARD_PAYMENT_CAUTION_VISIBLE = "CARD_PAYMENT_CAUTION_VISIBLE"
    ZERO_PENDING_MATCH = "ZERO_PENDING_MATCH"
    FALLBACK_PRESERVES_FILTERS = "FALLBACK_PRESERVES_FILTERS"
    GENRE_ORDER_BY_COUNT = "GENRE_ORDER_BY_COUNT"
    SHOWN_POOL_PRIORITY = "SHOWN_POOL_PRIORITY"
    WALKING_TIME_LIMIT_EXCLUDES = "WALKING_TIME_LIMIT_EXCLUDES"
    IZAKAYA_BAR_ONLY = "IZAKAYA_BAR_ONLY"
    NO_RESULTS = "NO_RESULTS"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    RATE_LIMITED = "RATE_LIMITED"
    RATE_LIMITED_AFTER_INITIAL_SUCCESS = "RATE_LIMITED_AFTER_INITIAL_SUCCESS"


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


def set_mode(
    mode: AcceptanceCandidateProposalMode,
    random_seed: int | None = None,
    search_origin: Origin | None = None,
) -> None:
    """Select the synthetic mode and (optionally) pin the seed and/or origin.

    ``random_seed`` mirrors ``CandidateProposalAcceptanceState.randomSeed``
    (adr/0023 decision 4): omitted or ``None`` leaves sampling
    non-deterministic, matching production.

    ``search_origin`` mirrors ``CandidateProposalAcceptanceState.searchOrigin``
    (test-support-api.yaml 1.4.0, independent-audit finding F1): omitted or
    ``None`` leaves every ``_..._source`` reporting this module's own default
    ``_ORIGIN``, exactly matching every scenario's behavior from before this
    property existed. A pinned value is read back by
    ``active_search_origin`` and reported as ``ProposalResult.search_origin``
    for every mode's response, independently of which mode is selected.
    """
    _require_acceptance_profile()
    cache.set(_CACHE_KEY_MODE, mode.value, timeout=None)
    if random_seed is None:
        cache.delete(_CACHE_KEY_SEED)
    else:
        cache.set(_CACHE_KEY_SEED, random_seed, timeout=None)
    if search_origin is None:
        cache.delete(_CACHE_KEY_SEARCH_ORIGIN)
    else:
        cache.set(
            _CACHE_KEY_SEARCH_ORIGIN,
            (search_origin.latitude, search_origin.longitude),
            timeout=None,
        )
    cache.delete(_CACHE_KEY_RATE_LIMITED_AFTER_INITIAL_SUCCESS_CALLS)


def reset_mode() -> None:
    cache.delete(_CACHE_KEY_MODE)
    cache.delete(_CACHE_KEY_SEED)
    cache.delete(_CACHE_KEY_SEARCH_ORIGIN)
    cache.delete(_CACHE_KEY_RATE_LIMITED_AFTER_INITIAL_SUCCESS_CALLS)


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


def active_search_origin() -> Origin:
    """The origin every ``_..._source`` function reports for the active state.

    ``CandidateProposalAcceptanceState.searchOrigin`` (test-support-api.yaml
    1.4.0, independent-audit finding F1,
    ``reviews/audit-tdr-cs-origin-marker-position.md``) lets a Given pin a
    non-default origin so a scenario can prove the map marker's position
    derives from the response rather than from an independently known
    constant -- a self-consistency check against a single origin every mode
    always returned cannot distinguish a correctly wired implementation from
    one that hardcodes that same fixed value (adr/0027 2026-08-24 addendum
    2). Falls back to ``_ORIGIN`` when unset or outside the acceptance
    profile, exactly matching every scenario's behavior from before this
    property existed.
    """
    if not getattr(settings, "ACCEPTANCE_TEST_SUPPORT", False):
        return _ORIGIN
    raw = cache.get(_CACHE_KEY_SEARCH_ORIGIN)
    if raw is None:
        return _ORIGIN
    latitude, longitude = raw
    return Origin(latitude=latitude, longitude=longitude)


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


def _latitude_degrees_for_meters(meters: float) -> float:
    """The latitude delta from ``_ORIGIN`` that places a candidate at exactly ``meters``.

    Every synthetic candidate in this module fixes ``longitude=0.0`` (see
    ``_synthetic_candidate``) and ``_ORIGIN`` is ``(0.0, 0.0)``, so
    ``pipeline._distance`` reduces to ``abs(latitude) *
    METERS_PER_DEGREE_LATITUDE``. Sharing that constant (rather than
    duplicating its numeric value here) guarantees a candidate built this
    way lands at exactly the intended walking-time distance -- needed for
    WALKING_TIME_LIMIT_EXCLUDES's deterministic TDR-CS-15 boundary case
    below -- regardless of any future change to the constant's value.
    """
    return meters / METERS_PER_DEGREE_LATITUDE


def _origin_shifted(
    candidates: tuple[NormalizedCandidate, ...],
) -> tuple[tuple[NormalizedCandidate, ...], Origin]:
    """Report ``candidates`` against ``active_search_origin()``, translated.

    Every synthetic population in this module is authored as absolute
    latitude/longitude values that are, in effect, fixed deltas from
    ``_ORIGIN`` (see e.g. ``_latitude_degrees_for_meters`` and the module's
    other distance-dependent Given comments) -- every distance-, walking-
    time-, radius-ring-, and nearest-first-ordering-dependent scenario this
    module's populations were built to prove depends on those exact deltas
    holding. When ``active_search_origin()`` pins a different origin
    (``CandidateProposalAcceptanceState.searchOrigin``, independent-audit
    finding F1), every candidate here is translated by the same delta the
    origin itself moved by, so ``pipeline._distance(origin, candidate)`` --
    and therefore every property derived from it -- returns exactly the
    values each population was authored to produce; only the absolute
    coordinates (never observable to the browser, ADR-0004/0005/0008) move.
    Returns the untranslated ``candidates`` tuple unchanged when the active
    origin is still the default ``_ORIGIN``, matching every scenario's
    behavior from before this property existed.
    """
    origin = active_search_origin()
    if origin == _ORIGIN:
        return candidates, origin
    delta_latitude = origin.latitude - _ORIGIN.latitude
    delta_longitude = origin.longitude - _ORIGIN.longitude
    shifted = tuple(
        replace(
            candidate,
            latitude=candidate.latitude + delta_latitude,
            longitude=candidate.longitude + delta_longitude,
        )
        for candidate in candidates
    )
    return shifted, origin


# A default-excluded-genre candidate (adr/0015/adr/0023), reused by both
# NORMAL_WITH_WEIGHTED_SAMPLING (as the sole excluded-genre member of its
# population) and IZAKAYA_BAR_ONLY.
_DEFAULT_EXCLUDED_CANDIDATE = _synthetic_candidate(
    name="合成居酒屋 一号店",
    genre=_DEFAULT_EXCLUDED_SYNTHETIC_GENRE,
    provider_page_url="https://example.invalid/acceptance-shop-izakaya",
    latitude=0.0008,
    total_seats=25,
)

# test-support-api.yaml v1.1.0 (adr/0023, renamed by adr/0024 decision 3):
# NORMAL_WITH_WEIGHTED_SAMPLING must supply at least 40 lunch-eligible
# synthetic candidates in the default (non-excluded-genre) population --
# comfortably exceeding the five-candidate display cap, so distance-weighted
# selection and its reproducibility under a pinned randomSeed are both
# observable -- spanning at least 3 distinct genres (each with at least 2
# members), at least 2 distinct nonSmokingStatus values, at least one
# candidate each with cardPaymentAvailable true and false, and at least one
# candidate each with a non-null dinnerBudgetTier and a null value for at
# least one of nonSmokingStatus/cardPaymentAvailable/dinnerBudgetTier
# (TDR-CS-13's ordering rule).
#
# Generated deterministically by cycling five genres, four non-smoking
# references (including the unconfirmed/None bucket), three card-payment
# values (including None), and five budget figures (including None) across
# 40 candidates spaced by latitude (this module's proximity approximation
# with longitude fixed at 0.0, see pipeline._distance) so ranking is
# deterministic and every combination of "confirmed"/"unconfirmed" for every
# soft filter is reachable.
_WEIGHTED_SAMPLING_GENRES: tuple[str, ...] = (
    "和食",
    "洋食",
    "中華",
    "エスニック",
    "カフェ・スイーツ",
)
_WEIGHTED_SAMPLING_NON_SMOKING_CYCLE: tuple[str | None, ...] = ("FULL", "PARTIAL", "NONE", None)
_WEIGHTED_SAMPLING_CARD_PAYMENT_CYCLE: tuple[bool | None, ...] = (True, False, None)
_WEIGHTED_SAMPLING_BUDGET_CYCLE: tuple[float | None, ...] = (1500.0, 2500.0, 3500.0, 4500.0, None)
_WEIGHTED_SAMPLING_POPULATION_SIZE = 40

# Real-device report (2026-08-28): the card's trailing walk-time chip was
# hidden under the map column for real, long shop names ("ドラゴンレッド
# リバー DRAGON RED RIVER", "福寿林 ホテルグランテラス富山") -- a layout bug
# this local demo's own synthetic population never exercised because every
# generated name here was short (`合成母集団食堂 NN号店`) and near-identical
# in length. This module's own docstring (adr/0023/adr/0024/adr/0025) is
# explicit that this population exists to run real production logic against
# synthetic data, and TDR-CS-13's ordering assertions (see test_suggestions.py)
# read genre/nonSmokingStatus/cardPaymentAvailable/dinnerBudgetTier -- never
# `name` -- so substituting one candidate's display name below changes no
# scenario's observable outcome. Only the string changes: index 0 keeps its
# own latitude/genre/seats/nonSmokingStatus/cardPaymentAvailable/budget
# exactly as the cycle below would already assign them, so every
# distance-, ordering-, and boundary-dependent assertion this population was
# authored to prove is untouched.
_WEIGHTED_SAMPLING_LONG_NAME_INDEX = 0
_WEIGHTED_SAMPLING_LONG_NAME = "ドラゴンレッドリバー DRAGON RED RIVER 総本店（合成データ）"


def _weighted_sampling_candidate(index: int) -> NormalizedCandidate:
    name = (
        _WEIGHTED_SAMPLING_LONG_NAME
        if index == _WEIGHTED_SAMPLING_LONG_NAME_INDEX
        else f"合成母集団食堂 {index:02d}号店"
    )
    return _synthetic_candidate(
        name=name,
        genre=_WEIGHTED_SAMPLING_GENRES[index % len(_WEIGHTED_SAMPLING_GENRES)],
        provider_page_url=f"https://example.invalid/acceptance-pool-shop-{index:02d}",
        latitude=0.0010 + index * 0.0002,
        total_seats=20 + index,
        non_smoking_status=_WEIGHTED_SAMPLING_NON_SMOKING_CYCLE[
            index % len(_WEIGHTED_SAMPLING_NON_SMOKING_CYCLE)
        ],
        card_payment_available=_WEIGHTED_SAMPLING_CARD_PAYMENT_CYCLE[
            index % len(_WEIGHTED_SAMPLING_CARD_PAYMENT_CYCLE)
        ],
        budget_average=_WEIGHTED_SAMPLING_BUDGET_CYCLE[
            index % len(_WEIGHTED_SAMPLING_BUDGET_CYCLE)
        ],
    )


_WEIGHTED_SAMPLING_CANDIDATES: tuple[NormalizedCandidate, ...] = tuple(
    _weighted_sampling_candidate(index) for index in range(_WEIGHTED_SAMPLING_POPULATION_SIZE)
)

_CANDIDATES: tuple[NormalizedCandidate, ...] = (
    *_WEIGHTED_SAMPLING_CANDIDATES,
    _DEFAULT_EXCLUDED_CANDIDATE,
)

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

# test-support-api.yaml v1.0.2 (adr/0023 decision 14 point 2): ZERO_PENDING_MATCH
# must supply a non-empty, non-excluded default population with no null
# cardPaymentAvailable/dinnerBudgetTier value, where at least one row matches
# cardPaymentOnly=true (confirmed true) and at least one row has
# dinnerBudgetTier=LOW, but no single row matches both -- so the UI-selectable
# pending combination cardPaymentOnly=true plus budgetTiers=[LOW] has an exact
# population match count of zero for every randomSeed, while each control
# remains independently meaningful (each alone matches at least one row).
_ZERO_PENDING_MATCH_CANDIDATES: tuple[NormalizedCandidate, ...] = (
    _synthetic_candidate(
        name="Synthetic zero-match card-only one",
        genre="和食",
        provider_page_url="https://example.invalid/acceptance-zero-match-card-one",
        latitude=0.0010,
        card_payment_available=True,
        budget_average=3500.0,  # MID: confirmed card-payment match, never budget LOW
    ),
    _synthetic_candidate(
        name="Synthetic zero-match card-only two",
        genre="和食",
        provider_page_url="https://example.invalid/acceptance-zero-match-card-two",
        latitude=0.0020,
        card_payment_available=True,
        budget_average=4500.0,  # HIGH: confirmed card-payment match, never budget LOW
    ),
    _synthetic_candidate(
        name="Synthetic zero-match budget-only one",
        genre="洋食",
        provider_page_url="https://example.invalid/acceptance-zero-match-budget-one",
        latitude=0.0030,
        card_payment_available=False,
        budget_average=1500.0,  # LOW: confirmed budget match, never card-payment match
    ),
    _synthetic_candidate(
        name="Synthetic zero-match budget-only two",
        genre="洋食",
        provider_page_url="https://example.invalid/acceptance-zero-match-budget-two",
        latitude=0.0040,
        card_payment_available=False,
        budget_average=3500.0,  # MID: confirmed non-match for both filters
    ),
)

# test-support-api.yaml v1.0.2 (adr/0023 decision 14 points 3-4):
# FALLBACK_PRESERVES_FILTERS must prove two things at once with a single
# synthetic population. (1) TDR-CS-10's boundary: with a combination of
# nonSmokingOnly/cardPaymentOnly/budgetTiers=[LOW] and includeIzakayaBar=false,
# the non-excluded population matches none of them (both non-excluded
# candidates below are confirmed nonSmokingStatus=NONE, which alone already
# fails nonSmokingOnly), so the server must fall back to the default-excluded
# genre to find the single candidate confirming all three -- while the three
# other default-excluded candidates, each a confirmed non-match for exactly
# one filter, prove the fallback does not silently admit them too.
# (2) decision 14 point 4: the sole non-excluded genre, offered as the only
# entry of availableGenres, has every member confirmed nonSmokingStatus=NONE,
# so selecting that explicit genre plus nonSmokingOnly=true deterministically
# empties the result without triggering the fallback (the genre filter alone
# already excludes every default-excluded/fallback-eligible candidate).
_FALLBACK_NON_EXCLUDED_GENRE = "うどん"
assert _FALLBACK_NON_EXCLUDED_GENRE not in DEFAULT_EXCLUDED_GENRES

_FALLBACK_PRESERVES_FILTERS_CANDIDATES: tuple[NormalizedCandidate, ...] = (
    _synthetic_candidate(
        name="Synthetic fallback non-excluded one",
        genre=_FALLBACK_NON_EXCLUDED_GENRE,
        provider_page_url="https://example.invalid/acceptance-fallback-non-excluded-one",
        latitude=0.0005,
        non_smoking_status="NONE",
        card_payment_available=True,
        budget_average=1500.0,
    ),
    _synthetic_candidate(
        name="Synthetic fallback non-excluded two",
        genre=_FALLBACK_NON_EXCLUDED_GENRE,
        provider_page_url="https://example.invalid/acceptance-fallback-non-excluded-two",
        latitude=0.0006,
        non_smoking_status="NONE",
        card_payment_available=False,
        budget_average=4500.0,
    ),
    _synthetic_candidate(
        name="Synthetic fallback all-match",
        genre=_DEFAULT_EXCLUDED_SYNTHETIC_GENRE,
        provider_page_url="https://example.invalid/acceptance-fallback-all-match",
        latitude=0.0010,
        non_smoking_status="FULL",
        card_payment_available=True,
        budget_average=1500.0,  # LOW: the only candidate confirming all three filters
    ),
    _synthetic_candidate(
        name="Synthetic fallback fails non-smoking",
        genre=_DEFAULT_EXCLUDED_SYNTHETIC_GENRE,
        provider_page_url="https://example.invalid/acceptance-fallback-fails-non-smoking",
        latitude=0.0015,
        non_smoking_status="NONE",  # confirmed non-match for nonSmokingOnly only
        card_payment_available=True,
        budget_average=1500.0,
    ),
    _synthetic_candidate(
        name="Synthetic fallback fails card payment",
        genre=_DEFAULT_EXCLUDED_SYNTHETIC_GENRE,
        provider_page_url="https://example.invalid/acceptance-fallback-fails-card-payment",
        latitude=0.0020,
        non_smoking_status="FULL",
        card_payment_available=False,  # confirmed non-match for cardPaymentOnly only
        budget_average=1500.0,
    ),
    _synthetic_candidate(
        name="Synthetic fallback fails budget",
        genre=_DEFAULT_EXCLUDED_SYNTHETIC_GENRE,
        provider_page_url="https://example.invalid/acceptance-fallback-fails-budget",
        latitude=0.0025,
        non_smoking_status="FULL",
        card_payment_available=True,
        budget_average=3500.0,  # MID: confirmed non-match for budgetTiers=[LOW] only
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

# test-support-api.yaml v1.1.0 (adr/0024 decision 1): GENRE_ORDER_BY_COUNT's
# default (non-excluded) population spans exactly 5 distinct genre values
# whose populationAttributes counts are strictly shaped so the
# count-descending presentation order, and its ascending-string-length
# tie-break, are both exercised deterministically:
#   - 和食 (2 chars): 6 members -- the strictly greatest count.
#   - 洋食 (2 chars): 4 members -- tied for next-greatest with イタリアン,
#     but shorter, so it must sort first under the tie-break.
#   - イタリアン (5 chars): 4 members -- tied with 洋食, but longer.
#   - 中華 (2 chars): 3 members -- distinct, smaller than the tied pair.
#   - エスニック (5 chars): 2 members -- distinct, the smallest.
# Plus a default-excluded genre (居酒屋) with 5 members -- its own count, not
# equal to any of 6/4/4/3/2 above -- so toggling includeIzakayaBar=true
# deterministically changes both the offered genre set and its order.
_GENRE_ORDER_BY_COUNT_COUNTS: tuple[tuple[str, int], ...] = (
    ("和食", 6),
    ("洋食", 4),
    ("イタリアン", 4),
    ("中華", 3),
    ("エスニック", 2),
)
_GENRE_ORDER_BY_COUNT_EXCLUDED_COUNT = 5


def _genre_order_by_count_candidates() -> tuple[NormalizedCandidate, ...]:
    candidates: list[NormalizedCandidate] = []
    latitude = 0.0010
    for genre, count in _GENRE_ORDER_BY_COUNT_COUNTS:
        for member_index in range(count):
            candidates.append(
                _synthetic_candidate(
                    name=f"合成{genre}店 {member_index:02d}",
                    genre=genre,
                    provider_page_url=(
                        f"https://example.invalid/acceptance-genre-order-{genre}-{member_index:02d}"
                    ),
                    latitude=latitude,
                )
            )
            latitude += 0.0002
    for member_index in range(_GENRE_ORDER_BY_COUNT_EXCLUDED_COUNT):
        candidates.append(
            _synthetic_candidate(
                name=f"合成居酒屋 order-{member_index:02d}",
                genre=_DEFAULT_EXCLUDED_SYNTHETIC_GENRE,
                provider_page_url=(
                    f"https://example.invalid/acceptance-genre-order-excluded-{member_index:02d}"
                ),
                latitude=latitude,
            )
        )
        latitude += 0.0002
    return tuple(candidates)


_GENRE_ORDER_BY_COUNT_CANDIDATES: tuple[NormalizedCandidate, ...] = (
    _genre_order_by_count_candidates()
)

# test-support-api.yaml v1.1.0 (adr/0024 decision 4, TDR-CS-14):
# SHOWN_POOL_PRIORITY's default (non-excluded) population has exactly 10
# lunch-eligible candidates with 10 distinct providerPageUrl values and
# distinct internal distances, comfortably below any real population size,
# so shownProviderPageUrls set-membership can be checked exhaustively
# (proposal.shownPoolPriority's three properties).
_SHOWN_POOL_PRIORITY_SIZE = 10


def _shown_pool_priority_candidate(index: int) -> NormalizedCandidate:
    return _synthetic_candidate(
        name=f"合成優先度食堂 {index:02d}号店",
        genre="和食",
        provider_page_url=f"https://example.invalid/acceptance-shown-pool-{index:02d}",
        latitude=0.0010 + index * 0.0003,
    )


_SHOWN_POOL_PRIORITY_CANDIDATES: tuple[NormalizedCandidate, ...] = tuple(
    _shown_pool_priority_candidate(index) for index in range(_SHOWN_POOL_PRIORITY_SIZE)
)

# test-support-api.yaml v1.3.0 (adr/0025 decision 3, distances recomputed
# under adr/0029 decision 2's detour factor): WALKING_TIME_LIMIT_EXCLUDES is
# the deterministic TDR-CS-15 Given. The eligible, non-excluded population is
# no larger than DISPLAY_CAP (mirroring CARD_PAYMENT_CAUTION_VISIBLE's
# approach, not NORMAL_WITH_WEIGHTED_SAMPLING's large-population one), so
# every member displays for every randomSeed. The fixed synthetic limit this
# mode is built against is exactly 12 minutes -- an arbitrary value chosen
# only for test determinism, not a claim about the real product's eventual
# offered walkingTimeMaxMinutes presets (see pipeline.WALKING_TIME_MAX_PRESET_
# MINUTES, which this mode's population does not need to share, since
# TDR-CS-15's own boundary assertions choose their own filter value directly
# rather than reading it from the presets), and this threshold itself is
# unchanged by adr/0029 -- only the straight-line distances that land each
# candidate on a chosen side of it needed recomputing, because
# pipeline.walking_time_minutes now multiplies distance by
# pipeline.WALKING_DETOUR_FACTOR before dividing by
# pipeline.WALKING_METERS_PER_MINUTE (ceil(distance * 1.3 / 80)), so the
# original 800m/950m/1100m no longer land in the same under/at/over bins
# (e.g. 950m now ceils to 16 minutes, not 12). Three members are placed at
# exactly-known distances via _latitude_degrees_for_meters, chosen the same
# way as before -- comfortably under, at, and comfortably over the 12-minute
# limit, each away from the neighboring minute's own boundary so
# floating-point rounding cannot push it into a neighboring minute: 600m
# (ceil(600*1.3/80) = 10 min, comfortably under 12), 710m (ceil(710*1.3/80)
# = 12 min, the boundary case -- 710m sits inside the (676.9m, 738.5m] range
# that ceils to exactly 12 minutes, with margin from both of that range's
# own edges), and 830m (ceil(830*1.3/80) = 14 min, comfortably over 12).
_WALKING_TIME_LIMIT_EXCLUDES_THRESHOLD_MINUTES = 12
_WALKING_TIME_LIMIT_EXCLUDES_CANDIDATES: tuple[NormalizedCandidate, ...] = (
    _synthetic_candidate(
        name="Synthetic walking-time under limit",
        genre="Synthetic Walking Test",
        provider_page_url="https://example.invalid/acceptance-walking-time-under",
        latitude=_latitude_degrees_for_meters(600.0),
    ),
    _synthetic_candidate(
        name="Synthetic walking-time at limit",
        genre="Synthetic Walking Test",
        provider_page_url="https://example.invalid/acceptance-walking-time-boundary",
        latitude=_latitude_degrees_for_meters(710.0),
    ),
    _synthetic_candidate(
        name="Synthetic walking-time over limit",
        genre="Synthetic Walking Test",
        provider_page_url="https://example.invalid/acceptance-walking-time-over",
        latitude=_latitude_degrees_for_meters(830.0),
    ),
)

# test-support-api.yaml v1.3.0 (human decision 2026-08-23): RATE_LIMITED_
# AFTER_INITIAL_SUCCESS is the deterministic TDR-CS-16 Given. Its population
# is small and fixed (mirroring CARD_PAYMENT_CAUTION_VISIBLE) because only
# the *first* /candidate-proposals request under this mode runs the real
# pipeline against it (see propose_with_override) -- every later request
# under the same acceptance state fails with the fixed RATE_LIMITED outcome
# instead, regardless of this population.
_RATE_LIMITED_AFTER_INITIAL_SUCCESS_CANDIDATES: tuple[NormalizedCandidate, ...] = (
    _synthetic_candidate(
        name="Synthetic prior-display one",
        genre="Synthetic Retention Test",
        provider_page_url="https://example.invalid/acceptance-prior-display-one",
        latitude=0.0010,
    ),
    _synthetic_candidate(
        name="Synthetic prior-display two",
        genre="Synthetic Retention Test",
        provider_page_url="https://example.invalid/acceptance-prior-display-two",
        latitude=0.0020,
    ),
)


def _normal_with_weighted_sampling_source() -> tuple[tuple[NormalizedCandidate, ...], Origin]:
    return _origin_shifted(_CANDIDATES)


def _izakaya_bar_only_source() -> tuple[tuple[NormalizedCandidate, ...], Origin]:
    return _origin_shifted(_IZAKAYA_BAR_ONLY_CANDIDATES)


def _default_exclusion_visible_source() -> tuple[tuple[NormalizedCandidate, ...], Origin]:
    return _origin_shifted(_DEFAULT_EXCLUSION_VISIBLE_CANDIDATES)


def _card_payment_caution_visible_source() -> tuple[tuple[NormalizedCandidate, ...], Origin]:
    return _origin_shifted(_CARD_PAYMENT_CAUTION_VISIBLE_CANDIDATES)


def _zero_pending_match_source() -> tuple[tuple[NormalizedCandidate, ...], Origin]:
    return _origin_shifted(_ZERO_PENDING_MATCH_CANDIDATES)


def _fallback_preserves_filters_source() -> tuple[tuple[NormalizedCandidate, ...], Origin]:
    return _origin_shifted(_FALLBACK_PRESERVES_FILTERS_CANDIDATES)


def _genre_order_by_count_source() -> tuple[tuple[NormalizedCandidate, ...], Origin]:
    return _origin_shifted(_GENRE_ORDER_BY_COUNT_CANDIDATES)


def _shown_pool_priority_source() -> tuple[tuple[NormalizedCandidate, ...], Origin]:
    return _origin_shifted(_SHOWN_POOL_PRIORITY_CANDIDATES)


def _walking_time_limit_excludes_source() -> tuple[tuple[NormalizedCandidate, ...], Origin]:
    return _origin_shifted(_WALKING_TIME_LIMIT_EXCLUDES_CANDIDATES)


def _rate_limited_after_initial_success_source() -> tuple[tuple[NormalizedCandidate, ...], Origin]:
    return _origin_shifted(_RATE_LIMITED_AFTER_INITIAL_SUCCESS_CANDIDATES)


def propose_with_override(
    mode: AcceptanceCandidateProposalMode,
    filters: CandidateFilters,
    shown_provider_page_urls: Collection[str] = (),
) -> ProposalResult:
    """The deterministic (or seeded-random) synthetic outcome for ``mode``.

    ``filters`` and ``shown_provider_page_urls`` (adr/0024 decision 4) are
    passed straight through to ``propose_candidates`` for every mode that
    runs the real pipeline; both are otherwise unused, matching the fixed
    synthetic outcomes of ``NO_RESULTS``, ``PROVIDER_UNAVAILABLE``, and
    ``RATE_LIMITED``.
    """
    if mode is AcceptanceCandidateProposalMode.PROVIDER_UNAVAILABLE:
        raise AcceptanceProviderUnavailable
    if mode is AcceptanceCandidateProposalMode.RATE_LIMITED:
        raise AcceptanceRateLimited(_SYNTHETIC_RATE_LIMIT_RETRY_AFTER_SECONDS)
    if mode is AcceptanceCandidateProposalMode.RATE_LIMITED_AFTER_INITIAL_SUCCESS:
        # TDR-CS-16 (human decision 2026-08-23): the first
        # /candidate-proposals request under this mode succeeds through the
        # real pipeline; every later one under the same acceptance state
        # fails with the same synthetic rate limit RATE_LIMITED already
        # raises above. A second `set_mode` call was deliberately not used
        # for this two-phase shape (no precedent in this file for that
        # technique -- see this module's docstring); instead this mode
        # tracks its own call count in the cache, reset whenever a mode is
        # (re)selected (`set_mode`/`reset_mode`).
        call_count = cache.get(_CACHE_KEY_RATE_LIMITED_AFTER_INITIAL_SUCCESS_CALLS, 0) + 1
        cache.set(_CACHE_KEY_RATE_LIMITED_AFTER_INITIAL_SUCCESS_CALLS, call_count, timeout=None)
        if call_count == 1:
            return propose_candidates(
                filters,
                fetch_candidates=_rate_limited_after_initial_success_source,
                random_source=active_random_source(),
                shown_provider_page_urls=shown_provider_page_urls,
            )
        raise AcceptanceRateLimited(_SYNTHETIC_RATE_LIMIT_RETRY_AFTER_SECONDS)
    if mode is AcceptanceCandidateProposalMode.NO_RESULTS:
        return ProposalResult(
            candidates=(),
            izakaya_bar_fallback_applied=False,
            available_genres=(),
            search_origin=active_search_origin(),
        )
    if mode is AcceptanceCandidateProposalMode.WALKING_TIME_LIMIT_EXCLUDES:
        return propose_candidates(
            filters,
            fetch_candidates=_walking_time_limit_excludes_source,
            random_source=active_random_source(),
            shown_provider_page_urls=shown_provider_page_urls,
        )
    if mode is AcceptanceCandidateProposalMode.IZAKAYA_BAR_ONLY:
        return propose_candidates(
            filters,
            fetch_candidates=_izakaya_bar_only_source,
            random_source=active_random_source(),
            shown_provider_page_urls=shown_provider_page_urls,
        )
    if mode is AcceptanceCandidateProposalMode.DEFAULT_EXCLUSION_VISIBLE:
        return propose_candidates(
            filters,
            fetch_candidates=_default_exclusion_visible_source,
            random_source=active_random_source(),
            shown_provider_page_urls=shown_provider_page_urls,
        )
    if mode is AcceptanceCandidateProposalMode.CARD_PAYMENT_CAUTION_VISIBLE:
        return propose_candidates(
            filters,
            fetch_candidates=_card_payment_caution_visible_source,
            random_source=active_random_source(),
            shown_provider_page_urls=shown_provider_page_urls,
        )
    if mode is AcceptanceCandidateProposalMode.ZERO_PENDING_MATCH:
        return propose_candidates(
            filters,
            fetch_candidates=_zero_pending_match_source,
            random_source=active_random_source(),
            shown_provider_page_urls=shown_provider_page_urls,
        )
    if mode is AcceptanceCandidateProposalMode.FALLBACK_PRESERVES_FILTERS:
        return propose_candidates(
            filters,
            fetch_candidates=_fallback_preserves_filters_source,
            random_source=active_random_source(),
            shown_provider_page_urls=shown_provider_page_urls,
        )
    if mode is AcceptanceCandidateProposalMode.GENRE_ORDER_BY_COUNT:
        return propose_candidates(
            filters,
            fetch_candidates=_genre_order_by_count_source,
            random_source=active_random_source(),
            shown_provider_page_urls=shown_provider_page_urls,
        )
    if mode is AcceptanceCandidateProposalMode.SHOWN_POOL_PRIORITY:
        return propose_candidates(
            filters,
            fetch_candidates=_shown_pool_priority_source,
            random_source=active_random_source(),
            shown_provider_page_urls=shown_provider_page_urls,
        )

    return propose_candidates(
        filters,
        fetch_candidates=_normal_with_weighted_sampling_source,
        random_source=active_random_source(),
        shown_provider_page_urls=shown_provider_page_urls,
    )
