"""Pure candidate-concept selection and ranking.

Per ADR-0001 decision 3 and ``ARCHITECTURE.md``, this module has no Django,
HTTP, ORM, or Hot Pepper-specific dependency. It only reorders and selects
among already-normalized candidates. Provider communication lives in
``dining_radar.integrations.hotpepper``; request/response wiring lives in
``dining_radar.web`` and ``dining_radar.suggestions``.

Per ADR-0004 decision 1 and the ``kind`` field description in
``contracts/candidate-search-api.yaml``, the server "returns only kinds it
can explain from the current normalized provider data": a concept kind is
omitted entirely when the current candidate set cannot support the rule that
explains it (for example, no candidate has a total-seat reference).

Per ADR-0015, two further product rules apply to every concept built here:
(1) ``PROXIMITY``, ``GENRE_FOCUS``, and ``NON_SMOKING_REFERENCE`` rank only
candidates outside ``DEFAULT_EXCLUDED_GENRES`` (genres whose lunch service
cannot be confirmed from returned provider fields); ``IZAKAYA_BAR_INCLUDED``
is the only kind whose population also includes that genre category, and it
is explainable only when at least one such candidate is present. When
excluding that category leaves no candidate for any of the other three
kinds, they fall through to unbuildable and ``IZAKAYA_BAR_INCLUDED`` becomes
the only (and therefore initial) concept, built from the full population
rather than a "no candidates" outcome (TDR-CS-10). (2) Every concept's
displayed ``candidates`` is capped to the top 5 after ranking the full
eligible population; this is a display cap applied last, not a limit on what
was ranked.

Per ADR-0016, ``GENRE_VARIETY`` was removed from ``ConceptKind``: real
production data showed it always converged to the same candidate set and
order as ``PROXIMITY`` once the nearest candidates already spanned distinct
genres, so it no longer described a distinct, explainable lens. A same-lens
"try again" request (resending the displayed proposal's own ``kind`` as
``reproposalKind``) is not a new ``ConceptKind`` and is not built here:
``select_reproposal`` already looks up any requested kind, including the
currently displayed one, from the concepts this module built for the fresh
search, so no new ranking logic is needed for it.

Per ADR-0017, a third real-data review found the display cap alone
(ADR-0015) had structurally disabled the repeat-demotion mechanism ADR-0008
decision 2 originally specified for the browser: once every response is
truncated to exactly the display cap, the browser never holds an unseen
candidate to promote on a later re-proposal. Repeat demotion therefore moves
here, server-side: ``build_concepts`` now accepts
``previously_shown_provider_page_urls`` -- the exact ``providerPageUrl``
values a re-proposal request echoes back from what this server most
recently returned to the same browser (ADR-0017 decision 1) -- and, for
every concept, stably demotes matching candidates to the end of that
concept's ranked order before applying the ``_DISPLAY_CAP`` (ADR-0017
decision 2). This is a demotion, not an exclusion: a previously-shown
candidate is never dropped by this step, only reordered, and it may still
appear in the capped, displayed set once no unseen candidate remains ahead
of it. The caller (``dining_radar.suggestions.service``) receives this list
as a plain data argument and never stores, logs, or traces it (ADR-0017
decision 3 Must).

Per ADR-0017 decision 7, ``businessHours`` is no longer part of this
application's candidate model: it was the single largest contributor to
mobile card height and the browser never had a way to use it to confirm
lunch service (the provider's ``open`` field is free text and its ``lunch``
field only ever reports "available" for an already lunch-filtered search).
``NormalizedCandidate`` therefore carries no ``business_hours`` field; the
provider page link (``provider_page_url``) remains the authoritative source
for hours.

Per ADR-0019, a field survey of the same live candidates found
``CAPACITY_REFERENCE`` (sorting by exact seat count) and
``AMENITY_REFERENCE`` (a combined score over ``private_room``,
``non_smoking``, ``parking``, ``wifi``, ``barrier_free``) weak or unwanted as
comparison lenses -- the organizer found sorting by exact seat count added
no value, and every ``AMENITY_REFERENCE`` constituent field other than
``non_smoking`` was sparse or unusable in real data. Both are removed.
``ConceptKind`` gains two replacements, keeping the total at four so
``reProposalOptions.maxItems: 3`` (three, always the total minus the one
displayed) remains satisfied without change (decision 1):

* ``GENRE_FOCUS`` ranks by proximity only the candidates sharing the single
  most common genre in the default (non-excluded-genre) population, and is
  explainable only when that population spans at least two distinct genres.
  Because the rule always narrows the population rather than merely
  reordering it, ``GENRE_FOCUS``'s candidate set is -- whenever it is
  offered -- a strict subset of ``PROXIMITY``'s own candidate set, so it
  cannot reproduce the exact-match degeneracy that led to
  ``GENRE_VARIETY``'s removal (ADR-0016). Its ``title``/``rationale`` are
  generated per response and name the genre selected; this stays
  deterministic for a given candidate set (ADR-0004 decision 1's
  "explainable, deterministic" requirement is about reproducibility, not
  about being a compile-time constant).
* ``NON_SMOKING_REFERENCE`` ranks primarily by each candidate's
  ``non_smoking_status`` (full non-smoking, then partial, then none, then
  unconfirmed), then by proximity, and is explainable only when the
  population spans at least two distinct non-smoking references. It
  replaces ``AMENITY_REFERENCE``.

Total seats (``capacityTier``), dinner-price banding (``dinnerBudgetTier``),
and credit-card acceptance (``cardPaymentAvailable``) are card-display-only
derived values (ADR-0019 decisions 4, 5, and 8): they never participate in
ranking and are never a ``ConceptKind``. ``NormalizedCandidate`` still
carries the raw ``total_seats`` and ``budget_average`` values so
``dining_radar.web.serializers`` can derive the coarse card labels, and it
carries ``card_payment_available`` as a plain pass-through boolean; none of
the three is read anywhere in this module. ``non_smoking_status`` is the one
exception: it both drives ``NON_SMOKING_REFERENCE`` ranking here and is
serialized to the browser unchanged (ADR-0019 decision 3 changes the prior
"none of these raw values are ever included in a browser-facing Candidate"
assumption, which held only for the retired ``amenity_score``).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import StrEnum


class ConceptKind(StrEnum):
    """Mirrors ``components.schemas.ConceptKind`` in the API contract."""

    PROXIMITY = "PROXIMITY"
    GENRE_FOCUS = "GENRE_FOCUS"
    NON_SMOKING_REFERENCE = "NON_SMOKING_REFERENCE"
    IZAKAYA_BAR_INCLUDED = "IZAKAYA_BAR_INCLUDED"


# Genres whose Hot Pepper `lunch` response field cannot confirm lunch service
# for an individual shop (adr/0015 decision 2-3: the field only ever reports
# "available" for a search already restricted to lunch, and free-text `open`
# hours are not machine-judgeable). These are excluded from the default
# candidate population of every concept except IZAKAYA_BAR_INCLUDED. This
# exclusion reflects unconfirmed lunch status, not a confirmed absence of
# lunch service (no rationale here may claim the latter).
#
# Confirmed members come from one real-data review sample and are not yet a
# complete Hot Pepper genre-taxonomy audit; genre-string matching (rather
# than a genre code) is also a provisional choice. Both must be reconfirmed
# against current official documentation before public operation (adr/0015
# decision 3, design.md "後続スライスへの条件"), mirroring the same
# reconfirmation duty ``integrations/hotpepper/normalize.py`` already
# documents for its own field-name assumptions.
DEFAULT_EXCLUDED_GENRES = frozenset({"居酒屋", "ダイニングバー・バル"})

# Display cap applied after ranking the full eligible population
# (adr/0015 decision 1). It bounds only what is serialized to the browser.
_DISPLAY_CAP = 5

# Non-smoking rank used only for NON_SMOKING_REFERENCE's primary sort key
# (adr/0019 decision 3: full non-smoking, then partial, then none, then
# unconfirmed). Not a display value -- the browser-visible label is derived
# independently by dining_radar.web.serializers from the same raw enum
# string this module ranks by.
_NON_SMOKING_RANK: dict[str | None, int] = {"FULL": 0, "PARTIAL": 1, "NONE": 2}
_NON_SMOKING_RANK_UNCONFIRMED = 3


@dataclass(frozen=True)
class Origin:
    """The private runtime search origin. Never serialized to the browser."""

    latitude: float
    longitude: float


@dataclass(frozen=True)
class NormalizedCandidate:
    """A Hot Pepper shop already normalized to this application's fields.

    ``non_smoking_status`` is both a ranking input (``NON_SMOKING_REFERENCE``)
    and a value serialized to the browser unchanged. ``total_seats``,
    ``budget_average``, and ``card_payment_available`` are never read by this
    module's ranking logic; they exist only so
    ``dining_radar.web.serializers`` can derive ``capacityTier``,
    ``dinnerBudgetTier``, and pass through ``cardPaymentAvailable`` (ADR-0019
    decisions 4, 5, 8). The coordinates are an internal ranking input; only
    the fields also present in ``components.schemas.Candidate`` are ever
    serialized to the browser (see ``dining_radar.web.serializers``).
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
class Concept:
    kind: ConceptKind
    title: str
    rationale: str
    candidates: tuple[NormalizedCandidate, ...]


@dataclass(frozen=True)
class ReproposalOption:
    kind: ConceptKind
    title: str
    rationale: str


class ReproposalKindUnavailableError(Exception):
    """The requested lens cannot currently be explained from the candidates."""


# GENRE_FOCUS has no static title/rationale: both are generated per response
# from the genre it selected (see _build_genre_focus).
_TITLES: dict[ConceptKind, str] = {
    ConceptKind.PROXIMITY: "近さを優先する",
    ConceptKind.NON_SMOKING_REFERENCE: "禁煙対応を参考にする",
    ConceptKind.IZAKAYA_BAR_INCLUDED: "居酒屋・バーを含めて探す",
}

_RATIONALES: dict[ConceptKind, str] = {
    ConceptKind.PROXIMITY: "検索地点から近い順に候補をまとめています。",
    ConceptKind.NON_SMOKING_REFERENCE: (
        "禁煙対応の区分（全面禁煙・一部禁煙・禁煙席なし）を優先し、次に検索地点から近い順に"
        "候補をまとめています。禁煙区分は店舗からの参考情報です。詳細は店舗ページでご確認ください。"
    ),
    ConceptKind.IZAKAYA_BAR_INCLUDED: (
        "居酒屋やバーなど、取得できた情報だけではランチ営業の実施を確認できない候補も含めて、"
        "検索地点から近い順に候補をまとめています。含めた店舗が実際にランチ営業しているとは"
        "限らないため、営業時間は店舗ページでご確認ください。"
    ),
}

# Fixed, deterministic priority order for the initial displayed concept and
# for the order concepts are offered as re-proposal lenses (ADR-0004 decision
# 1: "初期のコンセプト生成と順位付けは...決定的なルールだけで行う").
# IZAKAYA_BAR_INCLUDED is placed last as a non-binding preference (adr/0015
# decision 4): the organizer should normally reach it only by choosing it as
# a re-proposal lens, and it is selected as the initial/only concept solely
# through the fall-through described in this module's docstring. This tuple
# has four members (adr/0019 decision 1: GENRE_FOCUS and NON_SMOKING_REFERENCE
# replace CAPACITY_REFERENCE and AMENITY_REFERENCE one-for-one, keeping the
# total at four), so reproposal_options's up-to-three-excluding-the-
# displayed-kind result can never drop a kind to fit the contract's
# maxItems: 3 -- no reordering of this tuple is needed to keep that true.
_PRIORITY_ORDER: tuple[ConceptKind, ...] = (
    ConceptKind.PROXIMITY,
    ConceptKind.GENRE_FOCUS,
    ConceptKind.NON_SMOKING_REFERENCE,
    ConceptKind.IZAKAYA_BAR_INCLUDED,
)


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


def _split_default_population(
    candidates: Sequence[NormalizedCandidate],
) -> tuple[list[NormalizedCandidate], list[NormalizedCandidate]]:
    """Default-eligible candidates and the default-excluded subset (adr/0015).

    ``PROXIMITY``, ``GENRE_FOCUS``, and ``NON_SMOKING_REFERENCE`` rank only
    the first list. ``IZAKAYA_BAR_INCLUDED`` is explainable only when the
    second list is non-empty.
    """
    default: list[NormalizedCandidate] = []
    excluded: list[NormalizedCandidate] = []
    for candidate in candidates:
        (excluded if candidate.genre in DEFAULT_EXCLUDED_GENRES else default).append(candidate)
    return default, excluded


def _distance(origin: Origin, candidate: NormalizedCandidate) -> float:
    """A small-scale planar approximation used only to rank nearby candidates.

    The exact distance is never returned to the browser (ADR-0004/0005/0008),
    so geodesic precision is unnecessary; a locally consistent ordering is
    sufficient.
    """
    latitude_scale = math.cos(math.radians(origin.latitude))
    delta_latitude = candidate.latitude - origin.latitude
    delta_longitude = (candidate.longitude - origin.longitude) * latitude_scale
    return math.hypot(delta_latitude, delta_longitude)


def _build_proximity(candidates: Sequence[NormalizedCandidate], origin: Origin) -> Concept | None:
    if not candidates:
        return None
    ordered = sorted(candidates, key=lambda candidate: _distance(origin, candidate))
    return Concept(
        ConceptKind.PROXIMITY,
        _TITLES[ConceptKind.PROXIMITY],
        _RATIONALES[ConceptKind.PROXIMITY],
        tuple(ordered),
    )


def _build_genre_focus(candidates: Sequence[NormalizedCandidate], origin: Origin) -> Concept | None:
    """Rank by proximity only the single most common genre (adr/0019 decision 2).

    Explainable only when the population spans at least two distinct
    genres -- otherwise "the most common genre" is the whole population and
    this lens would be indistinguishable from PROXIMITY. When it does apply,
    the narrowing to one genre makes the resulting candidate set a strict
    subset of PROXIMITY's own candidate set by construction, which is what
    keeps this lens from reproducing GENRE_VARIETY's exact-match degeneracy
    (adr/0016).
    """
    if not candidates:
        return None
    genre_counts: dict[str, int] = {}
    for candidate in candidates:
        genre_counts[candidate.genre] = genre_counts.get(candidate.genre, 0) + 1
    if len(genre_counts) < 2:
        return None

    ordered_by_distance = sorted(candidates, key=lambda candidate: _distance(origin, candidate))
    max_count = max(genre_counts.values())
    most_common_genres = {genre for genre, count in genre_counts.items() if count == max_count}
    # Deterministic tiebreak (developer discretion, adr/0019 decision 2's
    # non-binding algorithm note): prefer the genre of whichever tied genre's
    # candidate is nearest the search origin.
    selected_genre = next(
        candidate.genre
        for candidate in ordered_by_distance
        if candidate.genre in most_common_genres
    )
    filtered = [candidate for candidate in ordered_by_distance if candidate.genre == selected_genre]
    title = f"「{selected_genre}」を中心に探す"
    rationale = (
        f"候補の中で最も件数が多い「{selected_genre}」というジャンルに絞り込み、"
        "検索地点から近い順に候補をまとめています。"
    )
    return Concept(ConceptKind.GENRE_FOCUS, title, rationale, tuple(filtered))


def _non_smoking_rank(status: str | None) -> int:
    return _NON_SMOKING_RANK.get(status, _NON_SMOKING_RANK_UNCONFIRMED)


def _build_non_smoking_reference(
    candidates: Sequence[NormalizedCandidate], origin: Origin
) -> Concept | None:
    """Rank primarily by non-smoking reference, then proximity (adr/0019 decision 3).

    Explainable only when the population spans at least two distinct
    ``non_smoking_status`` values (including the unconfirmed/``None`` bucket
    as its own distinct value) -- otherwise the primary sort key is constant
    across every candidate and this lens would offer no comparison the
    organizer could not already see from PROXIMITY.
    """
    if not candidates:
        return None
    if len({candidate.non_smoking_status for candidate in candidates}) < 2:
        return None
    ordered = sorted(
        candidates,
        key=lambda candidate: (
            _non_smoking_rank(candidate.non_smoking_status),
            _distance(origin, candidate),
        ),
    )
    return Concept(
        ConceptKind.NON_SMOKING_REFERENCE,
        _TITLES[ConceptKind.NON_SMOKING_REFERENCE],
        _RATIONALES[ConceptKind.NON_SMOKING_REFERENCE],
        tuple(ordered),
    )


def _build_izakaya_bar_included(
    deduped: Sequence[NormalizedCandidate],
    excluded_population: Sequence[NormalizedCandidate],
    origin: Origin,
) -> Concept | None:
    """The only kind ranking the full population, including excluded genres.

    Explainable only when ``excluded_population`` is non-empty (adr/0015
    decision 2): otherwise this lens would rank exactly the same candidates
    as the default population already covers, with nothing distinct to
    offer. Ranking uses the same proximity rule as ``PROXIMITY`` over the
    full (excluded-inclusive) population, applied to the deduplicated set so
    the fall-through in ``build_concepts`` can rely on it as the sole
    surviving concept when every default-population concept is unbuildable
    (TDR-CS-10).
    """
    if not excluded_population:
        return None
    ordered = sorted(deduped, key=lambda candidate: _distance(origin, candidate))
    return Concept(
        ConceptKind.IZAKAYA_BAR_INCLUDED,
        _TITLES[ConceptKind.IZAKAYA_BAR_INCLUDED],
        _RATIONALES[ConceptKind.IZAKAYA_BAR_INCLUDED],
        tuple(ordered),
    )


def _demote_repeated(
    concept: Concept, previously_shown_provider_page_urls: frozenset[str]
) -> Concept:
    """Stably move already-shown candidates behind unseen ones (adr/0017 decision 2).

    This is a demotion, not an exclusion: every candidate in ``concept``
    stays in the returned candidates, only reordered. Unseen candidates keep
    their relative ranked order and precede every demoted one, which also
    keeps its relative ranked order among the other demoted candidates
    (mirroring the browser-side algorithm ADR-0008 decision 2 specified
    before ADR-0017 moved it server-side). Must run after ranking and before
    ``_cap_display`` so demotion can only ever change which candidates the
    cap keeps, never how they were ranked.
    """
    if not previously_shown_provider_page_urls:
        return concept
    unseen = [
        candidate
        for candidate in concept.candidates
        if candidate.provider_page_url not in previously_shown_provider_page_urls
    ]
    seen = [
        candidate
        for candidate in concept.candidates
        if candidate.provider_page_url in previously_shown_provider_page_urls
    ]
    return replace(concept, candidates=tuple(unseen + seen))


def _cap_display(concept: Concept) -> Concept:
    """Top-``_DISPLAY_CAP`` candidates after ranking (adr/0015 decision 1).

    Every ``_build_*`` function above already ranks its full eligible
    population; this must run last so the cap never influences ranking.
    """
    if len(concept.candidates) <= _DISPLAY_CAP:
        return concept
    return replace(concept, candidates=concept.candidates[:_DISPLAY_CAP])


def build_concepts(
    candidates: Sequence[NormalizedCandidate],
    origin: Origin,
    previously_shown_provider_page_urls: Sequence[str] = (),
) -> list[Concept]:
    """Every concept explainable from the current candidates, in priority order.

    ``previously_shown_provider_page_urls`` (adr/0017 decision 1) is empty
    for the initial request and, for a re-proposal, the exact
    ``providerPageUrl`` values this server most recently returned to the
    same browser. When non-empty, every concept's ranked candidates are
    stably demoted (``_demote_repeated``) before the display cap is applied;
    when empty, ranking and the cap are unaffected, matching the initial
    request and the pre-adr/0017 behavior exactly.
    """
    deduped = _dedupe(candidates)
    default_population, excluded_population = _split_default_population(deduped)
    builders = {
        ConceptKind.PROXIMITY: lambda: _build_proximity(default_population, origin),
        ConceptKind.GENRE_FOCUS: lambda: _build_genre_focus(default_population, origin),
        ConceptKind.NON_SMOKING_REFERENCE: lambda: _build_non_smoking_reference(
            default_population, origin
        ),
        ConceptKind.IZAKAYA_BAR_INCLUDED: lambda: _build_izakaya_bar_included(
            deduped, excluded_population, origin
        ),
    }
    previously_shown = frozenset(previously_shown_provider_page_urls)
    concepts = (builders[kind]() for kind in _PRIORITY_ORDER)
    return [
        _cap_display(_demote_repeated(concept, previously_shown))
        for concept in concepts
        if concept is not None
    ]


def select_initial(concepts: Sequence[Concept]) -> Concept | None:
    """The first buildable concept in the fixed deterministic priority order."""
    return concepts[0] if concepts else None


def reproposal_options(
    concepts: Sequence[Concept], displayed_kind: ConceptKind | None
) -> list[ReproposalOption]:
    """Up to three lenses other than the currently displayed one."""
    offered = [concept for concept in concepts if concept.kind != displayed_kind]
    return [
        ReproposalOption(concept.kind, concept.title, concept.rationale) for concept in offered[:3]
    ]


def select_reproposal(concepts: Sequence[Concept], requested_kind: ConceptKind) -> Concept:
    """The buildable concept for ``requested_kind``.

    Raises ``ReproposalKindUnavailableError`` when the current candidates
    cannot explain that lens. The server holds no memory of what was
    previously displayed (ADR-0008), so availability depends only on the
    current candidate set.
    """
    for concept in concepts:
        if concept.kind == requested_kind:
            return concept
    raise ReproposalKindUnavailableError(requested_kind)
