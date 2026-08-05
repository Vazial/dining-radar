"""Mediates one fresh provider search with the deterministic recommendation.

Per ADR-0001 decision 2, ``suggestions`` mediates the provider search and the
pure ``recommendation`` pipeline. It performs no persistence: every call is a
fresh proposal (ADR-0008 decision 2).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from dining_radar.recommendation.pipeline import (
    Concept,
    ConceptKind,
    NormalizedCandidate,
    Origin,
    ReproposalOption,
    build_concepts,
    select_initial,
    select_reproposal,
)
from dining_radar.recommendation.pipeline import (
    reproposal_options as _reproposal_options,
)

CandidateSource = Callable[[], tuple[Sequence[NormalizedCandidate], Origin]]


@dataclass(frozen=True)
class ProposalResult:
    """A complete replacement displayed-proposal, ready to serialize."""

    proposal: Concept | None
    reproposal_options: list[ReproposalOption]


def propose_candidates(
    reproposal_kind: str | None, *, fetch_candidates: CandidateSource
) -> ProposalResult:
    """Perform one fresh search and select the displayed proposal.

    ``reproposal_kind`` is ``None`` for the initial empty request and a raw
    ``ConceptKind`` value string for a re-proposal. An unknown enum literal or
    an unavailable lens both raise ``ReproposalKindUnavailableError`` /
    ``ValueError`` for the caller to translate into the contract's single
    ``400 PROPOSAL_REPROPOSAL_KIND_INVALID`` response.
    """
    # Validate the requested lens before any fallible provider call: a
    # malformed request is a client error regardless of provider health.
    parsed_kind = ConceptKind(reproposal_kind) if reproposal_kind is not None else None

    candidates, origin = fetch_candidates()
    concepts = build_concepts(candidates, origin)

    if parsed_kind is None:
        initial = select_initial(concepts)
        if initial is None:
            return ProposalResult(None, [])
        return ProposalResult(initial, _reproposal_options(concepts, initial.kind))

    if not concepts:
        return ProposalResult(None, [])

    selected = select_reproposal(concepts, parsed_kind)
    return ProposalResult(selected, _reproposal_options(concepts, selected.kind))
