"""Pure candidate filtering, ordering, and randomized pool selection.

Per ADR-0001 decision 3 and ``ARCHITECTURE.md``, this module has no Django,
HTTP, ORM, or Hot Pepper-specific dependency. It only filters, orders, and
selects among already-normalized candidates. Provider communication lives in
``dining_radar.integrations.hotpepper``; request/response wiring lives in
``dining_radar.web`` and ``dining_radar.suggestions``.

Per adr/0023, the prior ``ConceptKind`` lens model (``PROXIMITY``,
``GENRE_FOCUS``, ``NON_SMOKING_REFERENCE``, ``IZAKAYA_BAR_INCLUDED``) is
retired. adr/0023 decision 0 found every surviving lens decomposed into
either a filter (``GENRE_FOCUS``'s narrowing, ``IZAKAYA_BAR_INCLUDED``'s
default-exclusion inversion) or a sort (``PROXIMITY``'s and
``NON_SMOKING_REFERENCE``'s distance ordering). This module replaces that
model with two operations plus one product decision the human made
explicitly:

1. **Filtering** (``filter_candidates``, adr/0023 decisions 1-3): ``genres``,
   ``includeIzakayaBar``, ``nonSmokingOnly``, ``cardPaymentOnly``, and
   ``budgetTiers`` are applied to the full retrieved, normalized, deduplicated
   population -- never to a display-truncated subset. ``nonSmokingOnly``,
   ``cardPaymentOnly``, and ``budgetTiers`` are *soft* filters (decision 2,
   human judgment): they exclude only a candidate confirmed not to match, and
   never a candidate whose relevant field is unconfirmed (``None``). This
   mirrors ADR-0015's "確認できないことを断定しない" principle, applied here
   to filtering rather than only to display.
2. **Ordering** (``order_confirmed_then_unconfirmed``, decision 4 steps 2-3
   and 6): candidates confirmed to match every *active* nullable filter
   (``nonSmokingOnly``, ``cardPaymentOnly``, ``budgetTiers``) are placed
   before every candidate unconfirmed for at least one of them; within each
   group, candidates are ordered nearest-first. When no nullable filter is
   active, this reduces to plain nearest-first. This same ordering rule is
   applied twice: once to the filtered population before pool selection, and
   again to the final sampled candidates immediately before display (decision
   4 step 6), so the browser always sees the same fixed display order
   regardless of the random sample drawn.
3. **Randomized pool selection** (``select_pool_and_sample``, decision 4
   steps 4-5): the nearest ``min(population, pool_size)`` candidates (a
   non-binding recommended ``pool_size`` of 20) form a pool, and up to 5
   candidates are drawn from it at random via an injected ``random.Random``
   source. Per decision 4's "決定性としての要求", the exact distance value
   feeding this ordering is never returned to the browser (unchanged from the
   prior ``ConceptKind`` model's own non-disclosure of distance), and the
   random source itself is never seeded from anything the public API
   accepts -- only ``dining_radar.suggestions`` may inject a seeded source,
   and only via ``contracts/test-support-api.yaml``.
4. **The default izakaya/bar-genre exclusion fallback**
   (``apply_izakaya_bar_fallback``, decision 6, successor to ADR-0015 decision
   4 / ``IZAKAYA_BAR_INCLUDED``): when ``includeIzakayaBar`` is false and
   applying every filter leaves no candidate, the server recomputes with that
   one exclusion set aside and returns those candidates instead, flagging
   this in the response. No other filter is ever silently loosened.

``build_proposal`` composes all four steps into the one operation
``dining_radar.suggestions.service`` calls per request.

Total seats (``capacityTier``), non-smoking reference display, and
credit-card acceptance display remain card-display-only concerns owned by
``dining_radar.web.serializers`` (ADR-0019). ``dinner_budget_tier`` is the one
derived value this module also needs, because ``budgetTiers`` filtering and
ordering must reason about the same coarse tier the card displays -- so it is
defined here (the single source of truth for the threshold mapping) and
reused, not duplicated, by ``dining_radar.web.serializers``.
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from dataclasses import dataclass, field

# Genres whose Hot Pepper `lunch` response field cannot confirm lunch service
# for an individual shop (adr/0015 decision 2-3: the field only ever reports
# "available" for a search already restricted to lunch, and free-text `open`
# hours are not machine-judgeable). Excluded from the eligible population
# unless `includeIzakayaBar` is true (adr/0023 decision 1, successor to
# ADR-0015's IZAKAYA_BAR_INCLUDED concept). This exclusion reflects
# unconfirmed lunch status, not a confirmed absence of lunch service (no
# rationale here may claim the latter).
#
# Confirmed members come from one real-data review sample and are not yet a
# complete Hot Pepper genre-taxonomy audit; genre-string matching (rather
# than a genre code) is also a provisional choice. Both must be reconfirmed
# against current official documentation before public operation (adr/0015
# decision 3), mirroring the same reconfirmation duty
# ``integrations/hotpepper/normalize.py`` already documents for its own
# field-name assumptions.
DEFAULT_EXCLUDED_GENRES = frozenset({"居酒屋", "ダイニングバー・バル"})

# Non-binding recommended pool size (adr/0023 decision 4 step 4): the nearest
# min(population, this) candidates form the pool up to 5 are randomly sampled
# from. Kept as a module constant so callers needn't hardcode it, but
# `build_proposal`/`select_pool_and_sample` both accept an override.
DEFAULT_POOL_SIZE = 20

# Display cap: the maximum number of candidates ever returned to the browser
# (adr/0023 decision 4 step 5). Unchanged in value from the prior
# ConceptKind model's own display cap (ADR-0015 decision 1), but now also the
# random sample size rather than a plain ranking truncation.
DISPLAY_CAP = 5

# adr/0023 decision 10 / adr/0019 decisions 4 and 8: coarse dinner-price-range
# reference derived from the provider's dinner-oriented budget figure.
# Provisional thresholds from a one-time field survey (64 candidates, roughly
# balanced 18/30/16 split). Never used to infer or imply a lunch price. This
# is the single place these thresholds are defined; `filter_candidates` and
# `dining_radar.web.serializers.serialize_candidate` both read
# `dinner_budget_tier` rather than duplicating the thresholds.
_DINNER_BUDGET_LOW_MAX_YEN = 2000
_DINNER_BUDGET_MID_MAX_YEN = 4000


def dinner_budget_tier(budget_average: float | None) -> str | None:
    """The coarse LOW/MID/HIGH dinner-budget tier for a raw yen figure.

    ``None`` when ``budget_average`` is ``None`` -- never a guess (adr/0023
    decision 2's "確認できないことを断定しない" principle applies here too:
    an unconfirmed budget figure must never be coerced into a tier).
    """
    if budget_average is None:
        return None
    if budget_average <= _DINNER_BUDGET_LOW_MAX_YEN:
        return "LOW"
    if budget_average <= _DINNER_BUDGET_MID_MAX_YEN:
        return "MID"
    return "HIGH"


@dataclass(frozen=True)
class Origin:
    """The private runtime search origin. Never serialized to the browser."""

    latitude: float
    longitude: float


@dataclass(frozen=True)
class NormalizedCandidate:
    """A Hot Pepper shop already normalized to this application's fields.

    ``total_seats``, ``non_smoking_status``, ``card_payment_available``, and
    ``budget_average`` are all serialized to the browser (directly, or -- for
    ``budget_average`` -- via ``dinner_budget_tier``); ``budget_average``
    itself is never returned raw (only its coarse tier is). The coordinates
    are an internal ranking input; only the fields also present in
    ``components.schemas.Candidate`` are ever serialized to the browser (see
    ``dining_radar.web.serializers``).
    """

    name: str
    genre: str
    description: str | None
    regular_holiday: str | None
    total_seats: int | None
    non_smoking_status: str | None
    card_payment_available: bool | None
    budget_average: float | None
    latitude: float
    longitude: float
    provider_page_url: str


@dataclass(frozen=True)
class CandidateFilters:
    """Mirrors ``components.schemas.CandidateFilters`` in the API contract.

    Every field defaults to "no restriction" (an empty tuple or ``False``),
    matching the contract's "omit, or send {}, for no restriction" rule for
    the initial request. ``budget_tiers`` holds raw ``LOW``/``MID``/``HIGH``
    strings, mirroring the wire enum exactly.
    """

    genres: tuple[str, ...] = field(default_factory=tuple)
    include_izakaya_bar: bool = False
    non_smoking_only: bool = False
    card_payment_only: bool = False
    budget_tiers: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PopulationAttribute:
    """One candidate's filterable attributes, stripped of all identity.

    Carries no name, no provider page URL, and -- critically -- no
    coordinates, so the sequence of these can be sent to the browser without
    disclosing anything about the private search origin beyond what the
    displayed candidates already disclose (ADR-0005/ADR-0008). It exists so
    the browser can count how many candidates a *pending* filter selection
    would match, before the organizer commits it, without issuing a provider
    request per keystroke and without this application caching provider
    responses (a policy ADR-0018 leaves unopened).

    ``default_excluded`` mirrors ``DEFAULT_EXCLUDED_GENRES`` membership so the
    browser can also count the effect of toggling ``includeIzakayaBar``.
    """

    genre: str
    non_smoking_status: str | None
    card_payment_available: bool | None
    dinner_budget_tier: str | None
    default_excluded: bool


@dataclass(frozen=True)
class Proposal:
    """A complete replacement displayed-proposal, ready to serialize."""

    candidates: tuple[NormalizedCandidate, ...]
    izakaya_bar_fallback_applied: bool
    available_genres: tuple[str, ...]
    population_attributes: tuple[PopulationAttribute, ...]


def _dedupe(candidates: Sequence[NormalizedCandidate]) -> list[NormalizedCandidate]:
    """Distinct shops by provider page, preserving provider order.

    TDR-CS-01 requires "初期の候補に同じ店舗は重複して示されない".
    """
    seen: set[str] = set()
    deduped: list[NormalizedCandidate] = []
    for candidate in candidates:
        if candidate.provider_page_url in seen:
            continue
        seen.add(candidate.provider_page_url)
        deduped.append(candidate)
    return deduped


def _distance(origin: Origin, candidate: NormalizedCandidate) -> float:
    """A small-scale planar approximation used only to rank nearby candidates.

    The exact distance is never returned to the browser (ADR-0004/0005/0008,
    unchanged by adr/0023), so geodesic precision is unnecessary; a locally
    consistent ordering is sufficient.
    """
    latitude_scale = math.cos(math.radians(origin.latitude))
    delta_latitude = candidate.latitude - origin.latitude
    delta_longitude = (candidate.longitude - origin.longitude) * latitude_scale
    return math.hypot(delta_latitude, delta_longitude)


def population_attributes(
    candidates: Sequence[NormalizedCandidate],
) -> list[PopulationAttribute]:
    """Identity-free filterable attributes for the whole deduplicated population.

    Computed before any filter is applied -- including the default
    izakaya/bar exclusion -- because the browser must be able to count the
    effect of *any* pending selection, including turning ``includeIzakayaBar``
    on. The result is canonically ordered by the five public filter values,
    never by provider order, distance, or display rank. This prevents an
    array index from becoming an implicit correspondence with a candidate or
    a private-location-derived ordering; the browser can only count set
    membership.
    """
    attributes = [
        PopulationAttribute(
            genre=candidate.genre,
            non_smoking_status=candidate.non_smoking_status,
            card_payment_available=candidate.card_payment_available,
            dinner_budget_tier=dinner_budget_tier(candidate.budget_average),
            default_excluded=candidate.genre in DEFAULT_EXCLUDED_GENRES,
        )
        for candidate in candidates
    ]

    # ADR-0022: the public sequence must have no provider/source, ranking,
    # distance, map, or candidate-correspondence meaning. Every key below is
    # itself part of PopulationAttribute's closed public shape, so this sort
    # cannot encode a private field by accident.
    return sorted(
        attributes,
        key=lambda attribute: (
            attribute.genre,
            attribute.non_smoking_status is None,
            attribute.non_smoking_status or "",
            attribute.card_payment_available is None,
            attribute.card_payment_available is True,
            attribute.dinner_budget_tier is None,
            attribute.dinner_budget_tier or "",
        ),
    )


def available_genres(
    candidates: Sequence[NormalizedCandidate], include_izakaya_bar: bool
) -> list[str]:
    """Distinct genre labels for the response's ``availableGenres`` (decision 9).

    Computed from the population given only ``include_izakaya_bar`` -- never
    narrowed by ``genres`` or any other filter -- so the browser's offered
    genre choices never shrink as the organizer narrows (adr/0023 decision
    9). Returned in a fixed, deterministic (sorted) order: the contract
    requires only that the filter panel's options match this order one-to-
    one, not any particular ordering rule.
    """
    population = (
        candidates
        if include_izakaya_bar
        else [
            candidate for candidate in candidates if candidate.genre not in DEFAULT_EXCLUDED_GENRES
        ]
    )
    return sorted({candidate.genre for candidate in population})


def filter_candidates(
    candidates: Sequence[NormalizedCandidate], filters: CandidateFilters
) -> list[NormalizedCandidate]:
    """Apply every filter to the full population (adr/0023 decisions 1-3).

    ``genres`` and ``includeIzakayaBar`` (its default-exclusion inversion)
    are hard filters. ``nonSmokingOnly``, ``cardPaymentOnly``, and
    ``budgetTiers`` are soft filters (decision 2): each excludes only a
    candidate *confirmed* not to match; a candidate whose relevant field is
    unconfirmed (``None``) is never excluded by that filter.
    """
    population: Sequence[NormalizedCandidate] = candidates

    if not filters.include_izakaya_bar:
        population = [
            candidate for candidate in population if candidate.genre not in DEFAULT_EXCLUDED_GENRES
        ]

    if filters.genres:
        requested_genres = set(filters.genres)
        population = [candidate for candidate in population if candidate.genre in requested_genres]

    if filters.non_smoking_only:
        population = [
            candidate for candidate in population if candidate.non_smoking_status != "NONE"
        ]

    if filters.card_payment_only:
        population = [
            candidate for candidate in population if candidate.card_payment_available is not False
        ]

    if filters.budget_tiers:
        requested_tiers = set(filters.budget_tiers)
        population = [
            candidate
            for candidate in population
            if (tier := dinner_budget_tier(candidate.budget_average)) is None
            or tier in requested_tiers
        ]

    return list(population)


def apply_izakaya_bar_fallback(
    candidates: Sequence[NormalizedCandidate], filters: CandidateFilters
) -> tuple[list[NormalizedCandidate], bool]:
    """Filter, falling back to include izakaya/bar genres if that leaves none.

    Returns ``(population, izakaya_bar_fallback_applied)``. Per adr/0023
    decision 6 (successor to TDR-CS-10 / ADR-0015 decision 4): when
    ``includeIzakayaBar`` is false and filtering with it false leaves no
    candidate, this recomputes with only that one exclusion set aside --
    every other filter the organizer explicitly chose (``genres``,
    ``nonSmokingOnly``, ``cardPaymentOnly``, ``budgetTiers``) is applied
    unchanged and never automatically loosened. ``izakaya_bar_fallback_applied``
    is true only when that retry actually produced a non-empty population;
    if it is still empty, the exclusion was not the (sole) cause of the empty
    result, so the flag stays false (matching the contract's own
    description).
    """
    population = filter_candidates(candidates, filters)
    if population or filters.include_izakaya_bar:
        return population, False

    fallback_filters = CandidateFilters(
        genres=filters.genres,
        include_izakaya_bar=True,
        non_smoking_only=filters.non_smoking_only,
        card_payment_only=filters.card_payment_only,
        budget_tiers=filters.budget_tiers,
    )
    fallback_population = filter_candidates(candidates, fallback_filters)
    return fallback_population, bool(fallback_population)


def _is_unconfirmed_for_active_filters(
    candidate: NormalizedCandidate, filters: CandidateFilters
) -> bool:
    if filters.non_smoking_only and candidate.non_smoking_status is None:
        return True
    if filters.card_payment_only and candidate.card_payment_available is None:
        return True
    if filters.budget_tiers and dinner_budget_tier(candidate.budget_average) is None:
        return True
    return False


def order_confirmed_then_unconfirmed(
    candidates: Sequence[NormalizedCandidate], origin: Origin, filters: CandidateFilters
) -> list[NormalizedCandidate]:
    """Confirmed-match candidates first, then unconfirmed; each nearest-first.

    Per adr/0023 decision 4 steps 2-3 and 6 / TDR-CS-13: when at least one of
    ``nonSmokingOnly``, ``cardPaymentOnly``, or ``budgetTiers`` is active,
    every candidate unconfirmed for at least one of those active filters is
    placed after every candidate confirmed for all of them; within each
    group, candidates are ordered nearest-first. When none of those filters
    is active, this reduces to plain nearest-first over the whole input.
    """
    any_nullable_filter_active = bool(
        filters.non_smoking_only or filters.card_payment_only or filters.budget_tiers
    )
    if not any_nullable_filter_active:
        return sorted(candidates, key=lambda candidate: _distance(origin, candidate))

    confirmed = [
        candidate
        for candidate in candidates
        if not _is_unconfirmed_for_active_filters(candidate, filters)
    ]
    unconfirmed = [
        candidate
        for candidate in candidates
        if _is_unconfirmed_for_active_filters(candidate, filters)
    ]
    confirmed.sort(key=lambda candidate: _distance(origin, candidate))
    unconfirmed.sort(key=lambda candidate: _distance(origin, candidate))
    return confirmed + unconfirmed


def select_pool_and_sample(
    ordered_population: Sequence[NormalizedCandidate],
    *,
    random_source: random.Random,
    pool_size: int = DEFAULT_POOL_SIZE,
    display_cap: int = DISPLAY_CAP,
) -> list[NormalizedCandidate]:
    """A random up-to-``display_cap`` sample from the nearest ``pool_size`` (decision 4 steps 4-5).

    ``ordered_population`` must already be ordered nearest-first (optionally
    confirmed-before-unconfirmed) by ``order_confirmed_then_unconfirmed``,
    since the pool is defined as its nearest prefix. The returned list's own
    order is not meaningful -- the caller must re-apply
    ``order_confirmed_then_unconfirmed`` to it before display (decision 4
    step 6).
    """
    pool = ordered_population[: min(len(ordered_population), pool_size)]
    sample_size = min(display_cap, len(pool))
    return random_source.sample(list(pool), sample_size)


def build_proposal(
    candidates: Sequence[NormalizedCandidate],
    origin: Origin,
    filters: CandidateFilters,
    *,
    random_source: random.Random,
    pool_size: int = DEFAULT_POOL_SIZE,
) -> Proposal:
    """The complete adr/0023 decision 1-9 pipeline for one request.

    Composes deduplication, ``available_genres`` (decision 9, computed from
    the deduplicated population before any other filter),
    ``apply_izakaya_bar_fallback`` (decisions 1-3 and 6),
    ``order_confirmed_then_unconfirmed`` (decision 4 steps 2-3), and
    ``select_pool_and_sample`` (decision 4 steps 4-5), then re-orders the
    sample for display (decision 4 step 6).
    """
    deduped = _dedupe(candidates)
    genres = available_genres(deduped, filters.include_izakaya_bar)
    population, izakaya_bar_fallback_applied = apply_izakaya_bar_fallback(deduped, filters)
    ordered = order_confirmed_then_unconfirmed(population, origin, filters)
    sampled = select_pool_and_sample(ordered, random_source=random_source, pool_size=pool_size)
    display = order_confirmed_then_unconfirmed(sampled, origin, filters)
    return Proposal(
        candidates=tuple(display),
        izakaya_bar_fallback_applied=izakaya_bar_fallback_applied,
        available_genres=tuple(genres),
        population_attributes=tuple(population_attributes(deduped)),
    )
