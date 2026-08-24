"""Pure candidate filtering, ordering, and distance-weighted random selection.

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
   active, this reduces to plain nearest-first. ``build_proposal`` applies
   this rule once, to the final selected candidates, immediately before
   display (decision 4 step 6), so the browser always sees the same fixed
   display order regardless of which candidates selection happened to draw.
3. **Distance-weighted selection with not-yet-shown priority**
   (``select_pool_and_sample`` / ``select_with_shown_priority``, adr/0024
   decisions 3-4, superseding adr/0023 decision 4 steps 4-5's fixed
   near-distance pool plus uniform draw): the filtered/fallback-applied
   population is first partitioned into "not-yet-shown" and "already-shown"
   using the caller-supplied ``shown_provider_page_urls`` (adr/0024 decision
   4 -- priority, never exclusion), then up to 5 candidates are drawn by
   distance-weighted random sampling (adr/0024 decision 3) that draws
   exclusively from the not-yet-shown partition while it has at least 5
   members, fills any remaining slots from the already-shown partition when
   the not-yet-shown partition is smaller, and draws from the full
   population without regard to ``shown_provider_page_urls`` when the
   not-yet-shown partition is empty (reported back as
   ``shown_pool_exhausted``). Per decision 4's "決定性としての要求", the
   exact distance value feeding the weighting is never returned to the
   browser (unchanged from the prior ``ConceptKind`` model's own
   non-disclosure of distance), and the random source itself is never seeded
   from anything the public API accepts -- only ``dining_radar.suggestions``
   may inject a seeded source, and only via
   ``contracts/test-support-api.yaml``. ``shown_provider_page_urls`` is
   likewise never persisted by this module or any caller beyond the current
   request's processing.
4. **The default izakaya/bar-genre exclusion fallback**
   (``apply_izakaya_bar_fallback``, decision 6, successor to ADR-0015 decision
   4 / ``IZAKAYA_BAR_INCLUDED``): when ``includeIzakayaBar`` is false and
   applying every filter leaves no candidate, the server recomputes with that
   one exclusion set aside and returns those candidates instead, flagging
   this in the response. No other filter is ever silently loosened.
5. **Search-origin disclosure and walking-time estimation**
   (``walking_time_minutes``, ``walking_time_band``, ``Proposal.search_origin``,
   adr/0025 decisions 1-3, superseding this module's former blanket
   non-disclosure of ``origin``/distance): the private search origin is now
   carried on ``Proposal`` for the browser to show as a map marker, and every
   displayed candidate carries an estimated one-way walking time in minutes,
   computed from ``origin`` and the candidate's own coordinates -- both are
   always computable server-side (unlike a provider-sourced field), so
   neither is ever "unavailable" the way ``totalSeats`` or
   ``nonSmokingStatus`` can be. ``walkingTimeMaxMinutes``
   (``CandidateFilters.walking_time_max_minutes``) is consequently a *hard*
   filter, not a soft one like ``nonSmokingOnly``/``cardPaymentOnly``/
   ``budgetTiers``: there is no unconfirmed walking time for it to preserve,
   so it is applied inside ``filter_candidates``/``apply_izakaya_bar_fallback``
   alongside the other explicit filters (never silently loosened by the
   izakaya/bar fallback, adr/0025 decision 3 amending TDR-CS-10) and never
   participates in ``order_confirmed_then_unconfirmed``'s
   confirmed/unconfirmed grouping. ``population_attributes`` also gains a
   coarse, bucketed ``walking_time_band`` per row (see its own docstring for
   why it is bucketed rather than exact) so the browser can predict a
   pending ``walkingTimeMaxMinutes`` selection's match count exactly as it
   already does for the other filters, without this module ever returning an
   exact distance value to the browser (that remains forbidden -- only the
   derived, rounded minute counts are public).

``build_proposal`` composes all five concerns into the one operation
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
from collections.abc import Collection, Sequence
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

# adr/0025 decision 2: meters-per-degree-of-latitude used to convert
# ``_distance``'s planar lat/lon approximation into meters. 111,320 m is the
# standard equirectangular-projection constant (the WGS84 mean meridional
# degree length, ~111.32 km) -- adequate for the short (a few kilometers at
# most) lunch-radius distances this application ever ranks or estimates a
# walking time for; it is not a geodesic (great-circle) calculation, matching
# ``_distance``'s own long-standing "locally consistent ordering, not
# geodesic precision" rationale below. Public (not a leading-underscore
# constant) because ``dining_radar.suggestions.acceptance_state`` needs the
# identical conversion to place synthetic candidates at a precise target
# walking-time distance for TDR-CS-15's deterministic Given, and duplicating
# the constant there would risk the two drifting apart.
METERS_PER_DEGREE_LATITUDE = 111_320.0

# adr/0025 decision 2: walking-speed convention used to turn a distance in
# meters into a whole-minute estimate. 80 meters/minute is the walking-speed
# figure Japan's real-estate fair-competition rules (不動産の表示に関する公正
# 競争規約施行規則) fix for "徒歩1分" figures in property listings -- a
# publicly documented convention, not a value this project measured itself,
# which is appropriate for a value ``adr/0025``'s own "検証の申告" context
# explicitly left to implementation discretion (straight-line estimate, not a
# road-network routing calculation). Public for the same
# cross-module-reuse reason as ``METERS_PER_DEGREE_LATITUDE`` above.
#
# adr/0029 decision 1: this stays a *separate* constant from the detour
# factor below rather than being folded into one lower effective speed. 80
# m/min is an external convention this project did not choose and does not
# own; ``WALKING_DETOUR_FACTOR`` is a value this project chose for a
# different reason (real streets are not straight lines). Keeping them
# distinct in code, not just in prose, means a future revisit of either one
# (a different real-estate speed figure, or a future move to road-network
# routing that would make the detour factor disappear entirely) never has to
# first disentangle which part of one merged number came from which source.
WALKING_METERS_PER_MINUTE = 80.0

# adr/0029 decision 2: a straight-line distance underestimates the actual
# distance someone walks, because real streets bend and a straight line
# rarely exists between two points. 1.3 sits inside both (a) the commonly
# cited range for urban detour ratios (roughly 1.2-1.4) and (b) the range
# implied by the human's own on-foot report against production
# (contexts/0029 §3): walking the innermost ring's 800m straight-line
# distance took 13-17 minutes, which back-computes to roughly 1.3-1.7. This
# project has not independently measured either range for its own service
# area -- the value is admittedly weakly justified (meta/adr/0059 decision
# 5's spirit) and is expected to be revisited from future real-world
# reports, which is exactly why it is kept as this one named, single-purpose
# constant rather than folded into ``WALKING_METERS_PER_MINUTE`` above or
# copied by numeric literal anywhere else.
WALKING_DETOUR_FACTOR = 1.3

# adr/0025 decision 3: the closed set of walking-time-maximum preset values
# this application offers, shared by ``walking_time_band`` (used to bucket
# ``PopulationAttribute.walkingTimeBand`) and, by cross-referenced
# duplication, candidate.js's own filter-option control
# (``CandidateFilters.walkingTimeMaxMinutes``'s description: the two must
# stay in exact agreement for the browser's local match-count prediction to
# be correct, which the API schema cannot enforce structurally). Arbitrary,
# implementation-owned round numbers spanning a plausible lunch-break walking
# range (10-30 minutes) -- unlike ``_DINNER_BUDGET_LOW_MAX_YEN`` or
# ``_CAPACITY_TIER_SMALL_MAX_SEATS`` elsewhere in this codebase, these are
# not derived from any field survey, because adr/0025 deliberately leaves
# the concrete preset values and count to implementation discretion.
WALKING_TIME_MAX_PRESET_MINUTES: tuple[int, ...] = (10, 15, 20, 30)


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
    # adr/0025 decision 3: a *hard* filter (see the module docstring's item
    # 5) -- ``None`` means no restriction, matching every other field's
    # "omit/false/empty means no restriction" convention, but unlike
    # ``non_smoking_only``/``card_payment_only``/``budget_tiers`` there is no
    # soft/unconfirmed treatment for this one: ``walking_time_minutes`` is
    # never unconfirmed, so a value here always excludes with certainty.
    walking_time_max_minutes: int | None = None


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

    ``walking_time_band`` (adr/0025 decision 3) is the sole deliberate
    exception to "no location attribute of any kind" this row otherwise
    holds to: it is **not** the row's exact ``walking_time_minutes`` value
    (that would let a reader re-identify a specific displayed candidate by
    value alone, even with no stated order -- exactly the re-identification
    risk ``adr/0022``'s identity-free guarantee exists to prevent). It is
    instead the smallest value in ``WALKING_TIME_MAX_PRESET_MINUTES`` this
    row's exact walking time does not exceed, or ``None`` when the row is
    farther than every preset -- a coarse bucket multiple candidates share,
    carrying no candidate-correspondence order. Unlike this dataclass's other
    ``None`` values, ``walking_time_band=None`` does **not** mean
    "unavailable" (walking time is always computable); it means only
    "farther than any currently offered maximum" (see its own computing
    function, ``walking_time_band``, for the full reasoning).
    """

    genre: str
    non_smoking_status: str | None
    card_payment_available: bool | None
    dinner_budget_tier: str | None
    default_excluded: bool
    walking_time_band: int | None


@dataclass(frozen=True)
class Proposal:
    """A complete replacement displayed-proposal, ready to serialize."""

    candidates: tuple[NormalizedCandidate, ...]
    izakaya_bar_fallback_applied: bool
    available_genres: tuple[str, ...]
    population_attributes: tuple[PopulationAttribute, ...]
    shown_pool_exhausted: bool
    # adr/0025 decision 1: the private search origin, now carried through so
    # the browser can show it as a map marker and derive walking-time rings
    # from it. Never rendered with more precision than this -- the exact
    # configured search *range*/radius is still never carried anywhere in
    # this response (adr/0025 decision 4/8, unchanged).
    search_origin: Origin


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
    """A small-scale planar approximation of the distance, in meters.

    Historically (before adr/0025) this returned a unitless degree-based
    value used only to *rank* nearby candidates, on the reasoning that the
    exact distance was never returned to the browser (ADR-0004/0005/0008),
    so geodesic precision was unnecessary -- only a locally consistent
    ordering was. adr/0025 decision 2 broke that premise: the browser now
    shows a derived walking-time estimate (see ``walking_time_minutes``),
    which needs a real-world unit. This still is not a geodesic
    (great-circle) calculation -- it is the same equirectangular planar
    approximation as before, now scaled into meters by
    ``METERS_PER_DEGREE_LATITUDE`` -- adequate for the short, sub-search-
    radius distances this application ever ranks or estimates, and it keeps
    every ranking/selection computation that depends only on relative order
    or scale-normalized ratios (``order_confirmed_then_unconfirmed``,
    ``_distance_weight``) unaffected by the unit change: multiplying every
    input by the same constant does not change which candidate is nearer,
    nor the ratio any distance-weighted computation actually uses. The exact
    value returned by this function is still never sent to the browser --
    only the coarser, derived ``walking_time_minutes``
    (whole-minute-rounded) and ``walking_time_band`` (further bucketed)
    values are (adr/0025 decision 3's `PopulationAttribute.walking_time_band`
    docstring explains why the latter is bucketed at all).
    """
    latitude_scale = math.cos(math.radians(origin.latitude))
    delta_latitude = candidate.latitude - origin.latitude
    delta_longitude = (candidate.longitude - origin.longitude) * latitude_scale
    degrees = math.hypot(delta_latitude, delta_longitude)
    return degrees * METERS_PER_DEGREE_LATITUDE


def walking_time_minutes(origin: Origin, candidate: NormalizedCandidate) -> int:
    """The public, per-candidate ``Candidate.walkingTimeMinutes`` estimate.

    Derived from ``_distance`` (meters), corrected by ``WALKING_DETOUR_FACTOR``
    for the fact that real streets are not straight lines (adr/0029 decision
    1), and then converted to minutes by ``WALKING_METERS_PER_MINUTE``
    (adr/0025 decision 2), rounded *up* to the next whole minute (never
    down) so the figure reads as a safe upper-bound "めやす" for someone
    planning a bounded lunch break, matching the real-estate convention
    ``WALKING_METERS_PER_MINUTE`` itself is drawn from. Always computable
    (never ``None``): both ``origin`` and ``candidate.latitude``/
    ``candidate.longitude`` are always known server-side, unlike a
    provider-sourced field that can be missing (adr/0025 decision 2's own
    "there is no 'not supplied' case" reasoning, restated on
    ``candidate-search-api.yaml``'s ``Candidate.walkingTimeMinutes``).

    This is the single function ``candidate-search-browser-interface.yaml``'s
    ``walkingRadiusRings`` (via ``PopulationAttribute.walking_time_band``),
    the per-card estimate above, and ``CandidateFilters.walking_time_max_minutes``
    (via ``filter_candidates``/``apply_izakaya_bar_fallback``) all funnel
    through -- adr/0029 decision 4 requires this so a detour-factor change
    can never update the displayed estimate/rings without also updating the
    hard filter, or vice versa. ``web/static/dining_radar/web/candidate.js``
    cannot share this Python function directly, so it keeps its own mirrored
    copy of both ``WALKING_METERS_PER_MINUTE`` and ``WALKING_DETOUR_FACTOR``
    for drawing the walking-radius rings -- see that file's own comment for
    the synchronization responsibility this creates.
    """
    return math.ceil(
        _distance(origin, candidate) * WALKING_DETOUR_FACTOR / WALKING_METERS_PER_MINUTE
    )


def walking_time_band(
    minutes: int, presets: Sequence[int] = WALKING_TIME_MAX_PRESET_MINUTES
) -> int | None:
    """The coarse ``PopulationAttribute.walkingTimeBand`` bucket for ``minutes``.

    The smallest ``presets`` value ``minutes`` does not exceed, or ``None``
    when ``minutes`` exceeds every preset (adr/0025 decision 3). Deliberately
    coarser than ``walking_time_minutes`` itself -- see
    ``PopulationAttribute.walking_time_band``'s own docstring for the
    re-identification risk this bucketing exists to avoid.
    """
    for preset in sorted(presets):
        if minutes <= preset:
            return preset
    return None


def population_attributes(
    candidates: Sequence[NormalizedCandidate],
    origin: Origin,
) -> list[PopulationAttribute]:
    """Identity-free filterable attributes for the whole deduplicated population.

    Computed before any filter is applied -- including the default
    izakaya/bar exclusion -- because the browser must be able to count the
    effect of *any* pending selection, including turning ``includeIzakayaBar``
    on. The result is canonically ordered by the six public filter values,
    never by provider order, distance, or display rank. This prevents an
    array index from becoming an implicit correspondence with a candidate or
    a private-location-derived ordering; the browser can only count set
    membership. ``origin`` (adr/0025 decision 3) is needed only to compute
    each row's coarse ``walking_time_band`` -- see ``PopulationAttribute``'s
    own docstring for why that value is a bucket rather than the exact
    ``walking_time_minutes`` figure.
    """
    attributes = [
        PopulationAttribute(
            genre=candidate.genre,
            non_smoking_status=candidate.non_smoking_status,
            card_payment_available=candidate.card_payment_available,
            dinner_budget_tier=dinner_budget_tier(candidate.budget_average),
            default_excluded=candidate.genre in DEFAULT_EXCLUDED_GENRES,
            walking_time_band=walking_time_band(walking_time_minutes(origin, candidate)),
        )
        for candidate in candidates
    ]

    # ADR-0022: the public sequence must have no provider/source, ranking,
    # distance, map, or candidate-correspondence meaning. Every key below is
    # itself part of PopulationAttribute's closed public shape (the coarse
    # walking_time_band included, adr/0025 decision 3), so this sort cannot
    # encode a private field by accident.
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
            attribute.walking_time_band is None,
            attribute.walking_time_band or 0,
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
    candidates: Sequence[NormalizedCandidate], filters: CandidateFilters, origin: Origin
) -> list[NormalizedCandidate]:
    """Apply every filter to the full population (adr/0023 decisions 1-3).

    ``genres`` and ``includeIzakayaBar`` (its default-exclusion inversion)
    are hard filters. ``nonSmokingOnly``, ``cardPaymentOnly``, and
    ``budgetTiers`` are soft filters (decision 2): each excludes only a
    candidate *confirmed* not to match; a candidate whose relevant field is
    unconfirmed (``None``) is never excluded by that filter.
    ``walkingTimeMaxMinutes`` (``filters.walking_time_max_minutes``,
    adr/0025 decision 3) is also a hard filter -- see the module docstring's
    item 5 for why it has no soft/unconfirmed case -- and needs ``origin`` to
    compute each candidate's walking time.
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

    if filters.walking_time_max_minutes is not None:
        maximum = filters.walking_time_max_minutes
        population = [
            candidate
            for candidate in population
            if walking_time_minutes(origin, candidate) <= maximum
        ]

    return list(population)


def apply_izakaya_bar_fallback(
    candidates: Sequence[NormalizedCandidate], filters: CandidateFilters, origin: Origin
) -> tuple[list[NormalizedCandidate], bool]:
    """Filter, falling back to include izakaya/bar genres if that leaves none.

    Returns ``(population, izakaya_bar_fallback_applied)``. Per adr/0023
    decision 6 (successor to TDR-CS-10 / ADR-0015 decision 4): when
    ``includeIzakayaBar`` is false and filtering with it false leaves no
    candidate, this recomputes with only that one exclusion set aside --
    every other filter the organizer explicitly chose (``genres``,
    ``nonSmokingOnly``, ``cardPaymentOnly``, ``budgetTiers``, and now
    ``walkingTimeMaxMinutes`` -- adr/0025 decision 3 amending TDR-CS-10) is
    applied unchanged and never automatically loosened.
    ``izakaya_bar_fallback_applied`` is true only when that retry actually
    produced a non-empty population; if it is still empty, the exclusion was
    not the (sole) cause of the empty result, so the flag stays false
    (matching the contract's own description).
    """
    population = filter_candidates(candidates, filters, origin)
    if population or filters.include_izakaya_bar:
        return population, False

    fallback_filters = CandidateFilters(
        genres=filters.genres,
        include_izakaya_bar=True,
        non_smoking_only=filters.non_smoking_only,
        card_payment_only=filters.card_payment_only,
        budget_tiers=filters.budget_tiers,
        walking_time_max_minutes=filters.walking_time_max_minutes,
    )
    fallback_population = filter_candidates(candidates, fallback_filters, origin)
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


def _selection_scale(distances: Sequence[float]) -> float:
    """A robust, always-positive scale for ``_distance_weight`` (adr/0024 decision 3).

    The median of the strictly positive input distances, or ``1.0`` when
    every distance is exactly ``0`` (a degenerate population entirely
    colocated with the search origin, for which every candidate's weight is
    equal regardless of scale -- ``1.0`` is an arbitrary but harmless choice
    in that case).
    """
    positive = sorted(distance for distance in distances if distance > 0)
    if not positive:
        return 1.0
    midpoint = len(positive) // 2
    if len(positive) % 2:
        return positive[midpoint]
    return (positive[midpoint - 1] + positive[midpoint]) / 2.0


def _distance_weight(distance: float, scale: float) -> float:
    """The distance-based selection weight (adr/0024 decision 3).

    ``w(d) = exp(-d / scale)`` is one of the contract's own non-binding
    example weight functions ("d0 は母集団の距離の中央値等から定める" -- d0
    determined from the population's own distance median or similar). It is
    monotonically non-increasing in ``d`` (P1: a candidate at least as close
    is never less likely to be drawn) and strictly positive for every
    finite, non-negative ``d`` (P2: no eligible candidate ever has a
    structurally zero selection probability). It is chosen over the
    contract's other example, ``1 / (1 + d)``, because that fixed-form
    reciprocal only differentiates meaningfully when ``d`` is on the order
    of ``1`` in whatever unit it happens to be measured in -- unless ``d``
    happens to land near that magnitude, ``1 / (1 + d)`` either collapses
    toward a uniform weight (``d << 1``) or toward ``1 / d`` (``d >> 1``),
    neither of which is an intentional choice tied to this population's own
    actual spread of distances. Scaling by ``scale`` (see
    ``_selection_scale``, computed per call from the population actually
    being drawn from) keeps the weight meaningfully differentiated at
    whatever numeric magnitude the input distances happen to be in, without
    this module hardcoding a unit assumption. This is also why ``_distance``'s
    adr/0025 unit change (degrees to meters, so a walking time can be
    derived from it) needed no change here: this function only ever reasons
    about the scale-normalized ratio ``d / scale``, never an absolute
    magnitude.
    """
    return math.exp(-distance / scale)


def select_pool_and_sample(
    population: Sequence[NormalizedCandidate],
    origin: Origin,
    *,
    random_source: random.Random,
    display_cap: int = DISPLAY_CAP,
) -> list[NormalizedCandidate]:
    """A distance-weighted, without-replacement sample of up to ``display_cap``.

    Replaces adr/0023 decision 4 steps 4-5's fixed near-distance pool
    (nearest ``min(population, 20)``) plus uniform draw with a single draw
    over the *entire* ``population`` argument, weighted by
    ``_distance_weight`` (adr/0024 decision 3) -- there is no pool concept
    left, so (unlike the retired implementation) this accepts an unordered
    population and computes distance itself.

    Uses the Efraimidis-Spirakis "A-ES" weighted-sampling-without-
    replacement algorithm: each candidate draws an independent uniform
    ``u`` in ``[0, 1)`` from ``random_source`` and receives a priority key
    ``u ** (1 / weight)``; the ``display_cap`` candidates with the largest
    keys are returned. This reproduces an exact weighted-without-replacement
    draw using only one uniform variate per candidate (no rejection
    sampling, no population-wide normalization pass), and its "largest key
    wins" structure is what gives both required properties directly: a
    strictly positive weight always yields a finite, well-defined key (P2),
    and for two candidates compared under the same random draw, the one
    with the greater-or-equal weight has a greater-or-equal expected key, so
    it is never less likely to be among the top ``display_cap`` (P1). See
    ``tests/test_recommendation.py`` for the multi-trial statistical
    verification of both properties.

    The returned list's own order is not meaningful -- the caller must
    re-apply ``order_confirmed_then_unconfirmed`` to it before display
    (decision 4 step 6).
    """
    if not population:
        return []
    distances = [_distance(origin, candidate) for candidate in population]
    scale = _selection_scale(distances)
    scored = []
    for candidate, distance in zip(population, distances):
        weight = _distance_weight(distance, scale)
        key = random_source.random() ** (1.0 / weight)
        scored.append((key, candidate))
    scored.sort(key=lambda scored_candidate: scored_candidate[0], reverse=True)
    return [candidate for _, candidate in scored[:display_cap]]


def partition_by_shown(
    population: Sequence[NormalizedCandidate], shown_provider_page_urls: Collection[str]
) -> tuple[list[NormalizedCandidate], list[NormalizedCandidate]]:
    """Split ``population`` into (not-yet-shown, already-shown) (adr/0024 decision 4).

    Membership is by exact ``provider_page_url`` match against
    ``shown_provider_page_urls``. This is priority information, not an
    exclusion filter: both returned lists remain part of the eligible
    population that ``select_with_shown_priority`` draws from.
    """
    shown = set(shown_provider_page_urls)
    unseen = [candidate for candidate in population if candidate.provider_page_url not in shown]
    seen = [candidate for candidate in population if candidate.provider_page_url in shown]
    return unseen, seen


def select_with_shown_priority(
    population: Sequence[NormalizedCandidate],
    origin: Origin,
    shown_provider_page_urls: Collection[str],
    *,
    random_source: random.Random,
    display_cap: int = DISPLAY_CAP,
) -> tuple[list[NormalizedCandidate], bool]:
    """Distance-weighted selection that prioritizes not-yet-shown candidates.

    Returns ``(selected, shown_pool_exhausted)`` (adr/0024 decision 4). Per
    ``candidate-search-browser-interface.yaml``'s ``proposal.shownPoolPriority``
    invariant, exactly one of three cases applies, using ``population`` split
    by ``partition_by_shown`` into not-yet-shown ("unseen") and already-shown
    ("seen"):

    1. ``len(unseen) >= display_cap``: every returned candidate is drawn from
       ``unseen`` only; ``shown_pool_exhausted`` is ``False``.
    2. ``0 < len(unseen) < display_cap``: every member of ``unseen`` is
       returned, and the remaining slots are drawn from ``seen``;
       ``shown_pool_exhausted`` is ``False``.
    3. ``unseen`` is empty: the draw falls back to the full ``population``
       without regard to ``shown_provider_page_urls``, and
       ``shown_pool_exhausted`` is ``True``.

    The returned list's own order is not meaningful, matching
    ``select_pool_and_sample`` (the caller must re-apply
    ``order_confirmed_then_unconfirmed`` before display).
    """
    unseen, seen = partition_by_shown(population, shown_provider_page_urls)

    if not unseen:
        selected = select_pool_and_sample(
            population, origin, random_source=random_source, display_cap=display_cap
        )
        return selected, True

    if len(unseen) >= display_cap:
        selected = select_pool_and_sample(
            unseen, origin, random_source=random_source, display_cap=display_cap
        )
        return selected, False

    remaining = display_cap - len(unseen)
    filler = select_pool_and_sample(
        seen, origin, random_source=random_source, display_cap=remaining
    )
    return list(unseen) + filler, False


def build_proposal(
    candidates: Sequence[NormalizedCandidate],
    origin: Origin,
    filters: CandidateFilters,
    *,
    random_source: random.Random,
    shown_provider_page_urls: Collection[str] = (),
) -> Proposal:
    """The complete adr/0023/adr/0024/adr/0025 decision pipeline for one request.

    Composes deduplication, ``available_genres`` (decision 9, computed from
    the deduplicated population before any other filter),
    ``apply_izakaya_bar_fallback`` (decisions 1-3 and 6, now also carrying
    ``walkingTimeMaxMinutes`` -- adr/0025 decision 3),
    ``select_with_shown_priority`` (adr/0024 decisions 3-4, superseding
    adr/0023 decision 4 steps 4-5), then re-orders the selected candidates
    for display via ``order_confirmed_then_unconfirmed`` (decision 4 step 6).
    ``origin`` is also carried straight through onto ``Proposal.search_origin``
    (adr/0025 decision 1) for the browser's map marker.
    """
    deduped = _dedupe(candidates)
    genres = available_genres(deduped, filters.include_izakaya_bar)
    population, izakaya_bar_fallback_applied = apply_izakaya_bar_fallback(deduped, filters, origin)
    selected, shown_pool_exhausted = select_with_shown_priority(
        population,
        origin,
        shown_provider_page_urls,
        random_source=random_source,
    )
    display = order_confirmed_then_unconfirmed(selected, origin, filters)
    return Proposal(
        candidates=tuple(display),
        izakaya_bar_fallback_applied=izakaya_bar_fallback_applied,
        available_genres=tuple(genres),
        population_attributes=tuple(population_attributes(deduped, origin)),
        shown_pool_exhausted=shown_pool_exhausted,
        search_origin=origin,
    )
