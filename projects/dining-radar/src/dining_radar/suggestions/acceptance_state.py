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
genre exclusion and 5-candidate display cap, and the adr/0017 server-side
repeat demotion). ``NO_RESULTS``, ``PROVIDER_UNAVAILABLE``, ``RATE_LIMITED``,
and ``INVALID_REPROPOSAL_KIND`` return a fixed synthetic outcome directly,
without calling the pipeline.
"""

from __future__ import annotations

from collections.abc import Sequence
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
    non_smoking_status: str | None = None,
    card_payment_available: bool | None = None,
    budget_average: float | None = None,
) -> NormalizedCandidate:
    """A deterministic, clearly fictional synthetic shop.

    Per adr/0017 decision 7, ``NormalizedCandidate`` no longer carries a
    business-hours field, so none is supplied here. Per adr/0019 decision 6,
    it no longer carries ``access`` either.
    """
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

# A default-excluded-genre candidate (adr/0015). Its latitude (0.0008) is the
# nearest of every NORMAL_WITH_REPEAT candidate, so it always survives
# IZAKAYA_BAR_INCLUDED's 5-item display cap: this is what lets (a) the
# initial default proposal exclude it, (b) IZAKAYA_BAR_INCLUDED be offered as
# a re-proposal option, and (c) selecting that lens include it (TDR-CS-09),
# all from this one NORMAL_WITH_REPEAT mode.
_DEFAULT_EXCLUDED_CANDIDATE = _synthetic_candidate(
    name="合成居酒屋 一号店",
    genre=_DEFAULT_EXCLUDED_SYNTHETIC_GENRE,
    provider_page_url="https://example.invalid/acceptance-shop-izakaya",
    latitude=0.0008,
    total_seats=25,
)

# adr/0017 decision 5 / test-support-api.yaml v0.5.0: NORMAL_WITH_REPEAT must
# supply, for at least one concept, more candidates than the adr/0015
# 5-item display cap, so a request naming every candidate most recently
# returned via previouslyShownProviderPageUrls deterministically has at
# least one unseen candidate left to promote. The six default-population
# (non-excluded-genre) candidates below give PROXIMITY exactly that: ranked
# by latitude (this module's proximity approximation with longitude fixed at
# 0.0, see pipeline._distance), the nearest five (shop A-E) are the initial
# display and the sixth (shop F) is always the unseen "new" candidate once
# the initial five are echoed back as previouslyShownProviderPageUrls.
#
# Unlike the pre-adr/0017 shape (two disjoint candidate sets switched by
# whether the request carried a reproposalKind, modeling "each request is an
# independent fresh search" per the now-superseded ADR-0008 decision 2),
# this mode returns the exact same candidate population regardless of the
# request's reproposalKind: demotion is now driven only by the request's
# previouslyShownProviderPageUrls (adr/0017 decision 2), so an
# unconditionally-different response would no longer distinguish a working
# demotion mechanism from a canned one that ignores the request.
#
# adr/0019: this population also carries the four new candidate-level
# reference values.
#
# * Genre: all six default-population candidates carry distinct genres, so
#   GENRE_FOCUS's "at least two distinct genres" explainability condition
#   holds and its most-common-genre tiebreak (developer discretion, adr/0019
#   decision 2) falls to the nearest-shop rule -- shop A (和食, the nearest).
# * Non-smoking: every default-population candidate deliberately shares the
#   same non_smoking_status (None, i.e. unconfirmed), so NON_SMOKING_REFERENCE
#   stays unbuildable here -- this replaces the prior AMENITY_REFERENCE
#   exclusion (both existed to make TDR-CS-07's "request an unavailable lens"
#   scenario deterministic) and does not contradict GENRE_FOCUS's own
#   distinct-genre requirement, since the two fields are independent.
# * Card payment: shops A-E (the initial five displayed) mix True/False/None
#   so TDR-CS-12's presence/absence contrast is observable in the very first
#   response, not only after a re-proposal.
# * Dinner budget: shops A-E also mix a non-null figure with an explicit
#   `None` (no provider budget data) for the same reason.
_CANDIDATES: tuple[NormalizedCandidate, ...] = (
    _synthetic_candidate(
        name="合成食堂 一号店",
        genre="和食",
        provider_page_url="https://example.invalid/acceptance-shop-a",
        latitude=0.0010,
        total_seats=30,
        card_payment_available=True,
        budget_average=2500.0,
    ),
    _synthetic_candidate(
        name="合成食堂 二号店",
        genre="洋食",
        provider_page_url="https://example.invalid/acceptance-shop-b",
        latitude=0.0012,
        total_seats=20,
        card_payment_available=False,
        budget_average=None,
    ),
    _synthetic_candidate(
        name="合成食堂 三号店",
        genre="中華",
        provider_page_url="https://example.invalid/acceptance-shop-c",
        latitude=0.0014,
        total_seats=45,
        card_payment_available=None,
        budget_average=1500.0,
    ),
    _synthetic_candidate(
        name="合成食堂 四号店",
        genre="韓国料理",
        provider_page_url="https://example.invalid/acceptance-shop-d",
        latitude=0.0016,
        total_seats=15,
        card_payment_available=True,
        budget_average=None,
    ),
    _synthetic_candidate(
        name="合成食堂 五号店",
        genre="エスニック",
        provider_page_url="https://example.invalid/acceptance-shop-e",
        latitude=0.0018,
        total_seats=50,
        card_payment_available=False,
        budget_average=5000.0,
    ),
    _synthetic_candidate(
        name="合成食堂 六号店",
        genre="カフェ・スイーツ",
        provider_page_url="https://example.invalid/acceptance-shop-f",
        latitude=0.0020,
        total_seats=10,
        card_payment_available=None,
        budget_average=3500.0,
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


def _normal_with_repeat_source() -> tuple[tuple[NormalizedCandidate, ...], Origin]:
    return _CANDIDATES, _ORIGIN


def _izakaya_bar_only_source() -> tuple[tuple[NormalizedCandidate, ...], Origin]:
    return _IZAKAYA_BAR_ONLY_CANDIDATES, _ORIGIN


def propose_with_override(
    mode: AcceptanceCandidateProposalMode,
    reproposal_kind: str | None,
    previously_shown_provider_page_urls: Sequence[str] = (),
) -> ProposalResult:
    """The deterministic synthetic outcome for the currently selected mode.

    ``previously_shown_provider_page_urls`` (adr/0017 decision 1) is passed
    straight through to ``propose_candidates`` for the two modes that run
    the real pipeline; it is otherwise unused, matching the other modes'
    fixed synthetic outcomes.
    """
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
            fetch_candidates=_izakaya_bar_only_source,
            previously_shown_provider_page_urls=previously_shown_provider_page_urls,
        )

    return propose_candidates(
        reproposal_kind,
        fetch_candidates=_normal_with_repeat_source,
        previously_shown_provider_page_urls=previously_shown_provider_page_urls,
    )
