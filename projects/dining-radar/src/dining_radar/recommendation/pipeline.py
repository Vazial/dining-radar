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
(1) ``PROXIMITY``, ``CAPACITY_REFERENCE``, and ``AMENITY_REFERENCE`` rank
only candidates outside ``DEFAULT_EXCLUDED_GENRES`` (genres whose lunch
service cannot be confirmed from returned provider fields);
``IZAKAYA_BAR_INCLUDED`` is the only kind whose population also includes
that genre category, and it is explainable only when at least one such
candidate is present. When excluding that category leaves no candidate for
any of the other three kinds, they fall through to unbuildable and
``IZAKAYA_BAR_INCLUDED`` becomes the only (and therefore initial) concept,
built from the full population rather than a "no candidates" outcome
(TDR-CS-10). (2) Every concept's displayed ``candidates`` is capped to the
top 5 after ranking the full eligible population; this is a display cap
applied last, not a limit on what was ranked.

Per ADR-0016, ``GENRE_VARIETY`` was removed from ``ConceptKind``: real
production data showed it always converged to the same candidate set and
order as ``PROXIMITY`` once the nearest candidates already spanned distinct
genres, so it no longer described a distinct, explainable lens. This module
now builds at most four concept kinds, so ``reproposal_options`` (at most
three, excluding the displayed kind) can never drop one to fit
``reProposalOptions.maxItems: 3`` -- the capacity defect ADR-0015 introduced
by adding a fifth kind is resolved structurally rather than by reordering
``_PRIORITY_ORDER``. A same-lens "try again" request (resending the
displayed proposal's own ``kind`` as ``reproposalKind``) is not a new
``ConceptKind`` and is not built here: ``select_reproposal`` already looks
up any requested kind, including the currently displayed one, from the
concepts this module built for the fresh search, so no new ranking logic is
needed for it.

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
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import StrEnum


class ConceptKind(StrEnum):
    """Mirrors ``components.schemas.ConceptKind`` in the API contract."""

    PROXIMITY = "PROXIMITY"
    CAPACITY_REFERENCE = "CAPACITY_REFERENCE"
    AMENITY_REFERENCE = "AMENITY_REFERENCE"
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


@dataclass(frozen=True)
class Origin:
    """The private runtime search origin. Never serialized to the browser."""

    latitude: float
    longitude: float


@dataclass(frozen=True)
class NormalizedCandidate:
    """A Hot Pepper shop already normalized to this application's fields.

    ``amenity_score`` and the coordinates are internal ranking inputs; only
    the fields also present in ``components.schemas.Candidate`` are ever
    serialized to the browser (see ``dining_radar.web.serializers``).
    """

    name: str
    genre: str
    description: str | None
    regular_holiday: str | None
    total_seats: int | None
    access: str | None
    latitude: float
    longitude: float
    provider_page_url: str
    amenity_score: int = 0


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


_TITLES: dict[ConceptKind, str] = {
    ConceptKind.PROXIMITY: "近さを優先する",
    ConceptKind.CAPACITY_REFERENCE: "グループ利用に余裕がありそうな店を選ぶ",
    ConceptKind.AMENITY_REFERENCE: "個室・禁煙など設備を参考にする",
    ConceptKind.IZAKAYA_BAR_INCLUDED: "居酒屋・バーを含めて探す",
}

_RATIONALES: dict[ConceptKind, str] = {
    ConceptKind.PROXIMITY: "検索地点から近い順に候補をまとめています。",
    ConceptKind.CAPACITY_REFERENCE: (
        "総席数の参考値をもとに、グループでの利用しやすさを比較しやすい候補を"
        "まとめています。空席や着席人数を保証するものではありません。"
    ),
    ConceptKind.AMENITY_REFERENCE: (
        "個室や禁煙対応など、取得できた設備情報を参考に候補をまとめています。"
        "設備の詳細は店舗ページでご確認ください。"
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
# through the fall-through described in this module's docstring. With
# GENRE_VARIETY removed (adr/0016), this tuple has four members, so
# reproposal_options's up-to-three-excluding-the-displayed-kind result can
# never drop a kind to fit the contract's maxItems: 3 -- no reordering of
# this tuple is needed to keep that true.
_PRIORITY_ORDER: tuple[ConceptKind, ...] = (
    ConceptKind.PROXIMITY,
    ConceptKind.CAPACITY_REFERENCE,
    ConceptKind.AMENITY_REFERENCE,
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

    ``PROXIMITY``, ``CAPACITY_REFERENCE``, and ``AMENITY_REFERENCE`` rank
    only the first list. ``IZAKAYA_BAR_INCLUDED``
    is explainable only when the second list is non-empty.
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


def _build_capacity_reference(
    candidates: Sequence[NormalizedCandidate],
) -> Concept | None:
    if not any(candidate.total_seats is not None for candidate in candidates):
        return None
    ordered = sorted(
        candidates,
        key=lambda candidate: (
            candidate.total_seats is None,
            -(candidate.total_seats or 0),
        ),
    )
    return Concept(
        ConceptKind.CAPACITY_REFERENCE,
        _TITLES[ConceptKind.CAPACITY_REFERENCE],
        _RATIONALES[ConceptKind.CAPACITY_REFERENCE],
        tuple(ordered),
    )


def _build_amenity_reference(
    candidates: Sequence[NormalizedCandidate],
) -> Concept | None:
    if not any(candidate.amenity_score > 0 for candidate in candidates):
        return None
    ordered = sorted(candidates, key=lambda candidate: -candidate.amenity_score)
    return Concept(
        ConceptKind.AMENITY_REFERENCE,
        _TITLES[ConceptKind.AMENITY_REFERENCE],
        _RATIONALES[ConceptKind.AMENITY_REFERENCE],
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
        ConceptKind.CAPACITY_REFERENCE: lambda: _build_capacity_reference(default_population),
        ConceptKind.AMENITY_REFERENCE: lambda: _build_amenity_reference(default_population),
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
