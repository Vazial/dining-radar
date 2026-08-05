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
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum


class ConceptKind(StrEnum):
    """Mirrors ``components.schemas.ConceptKind`` in the API contract."""

    PROXIMITY = "PROXIMITY"
    CAPACITY_REFERENCE = "CAPACITY_REFERENCE"
    GENRE_VARIETY = "GENRE_VARIETY"
    AMENITY_REFERENCE = "AMENITY_REFERENCE"


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
    business_hours: str | None
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
    ConceptKind.GENRE_VARIETY: "いつもと違うジャンルを試す",
    ConceptKind.AMENITY_REFERENCE: "個室・禁煙など設備を参考にする",
}

_RATIONALES: dict[ConceptKind, str] = {
    ConceptKind.PROXIMITY: "検索地点から近い順に候補をまとめています。",
    ConceptKind.CAPACITY_REFERENCE: (
        "総席数の参考値をもとに、グループでの利用しやすさを比較しやすい候補を"
        "まとめています。空席や着席人数を保証するものではありません。"
    ),
    ConceptKind.GENRE_VARIETY: (
        "複数のジャンルを横断して比較できるよう、ジャンルが偏らないように候補をまとめています。"
    ),
    ConceptKind.AMENITY_REFERENCE: (
        "個室や禁煙対応など、取得できた設備情報を参考に候補をまとめています。"
        "設備の詳細は店舗ページでご確認ください。"
    ),
}

# Fixed, deterministic priority order for the initial displayed concept and
# for the order concepts are offered as re-proposal lenses (ADR-0004 decision
# 1: "初期のコンセプト生成と順位付けは...決定的なルールだけで行う").
_PRIORITY_ORDER: tuple[ConceptKind, ...] = (
    ConceptKind.PROXIMITY,
    ConceptKind.CAPACITY_REFERENCE,
    ConceptKind.GENRE_VARIETY,
    ConceptKind.AMENITY_REFERENCE,
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


def _interleave_by_genre(
    candidates: Sequence[NormalizedCandidate],
) -> list[NormalizedCandidate]:
    """Round-robin across genres so early positions cover distinct genres."""
    groups: dict[str, list[NormalizedCandidate]] = {}
    genre_order: list[str] = []
    for candidate in candidates:
        if candidate.genre not in groups:
            groups[candidate.genre] = []
            genre_order.append(candidate.genre)
        groups[candidate.genre].append(candidate)

    interleaved: list[NormalizedCandidate] = []
    remaining = sum(len(bucket) for bucket in groups.values())
    while remaining:
        for genre in genre_order:
            bucket = groups[genre]
            if bucket:
                interleaved.append(bucket.pop(0))
                remaining -= 1
    return interleaved


def _build_genre_variety(
    candidates: Sequence[NormalizedCandidate],
) -> Concept | None:
    distinct_genres = {candidate.genre for candidate in candidates}
    if len(distinct_genres) < 2:
        return None
    ordered = _interleave_by_genre(candidates)
    return Concept(
        ConceptKind.GENRE_VARIETY,
        _TITLES[ConceptKind.GENRE_VARIETY],
        _RATIONALES[ConceptKind.GENRE_VARIETY],
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


def build_concepts(candidates: Sequence[NormalizedCandidate], origin: Origin) -> list[Concept]:
    """Every concept explainable from the current candidates, in priority order."""
    deduped = _dedupe(candidates)
    builders = {
        ConceptKind.PROXIMITY: lambda: _build_proximity(deduped, origin),
        ConceptKind.CAPACITY_REFERENCE: lambda: _build_capacity_reference(deduped),
        ConceptKind.GENRE_VARIETY: lambda: _build_genre_variety(deduped),
        ConceptKind.AMENITY_REFERENCE: lambda: _build_amenity_reference(deduped),
    }
    concepts = (builders[kind]() for kind in _PRIORITY_ORDER)
    return [concept for concept in concepts if concept is not None]


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
