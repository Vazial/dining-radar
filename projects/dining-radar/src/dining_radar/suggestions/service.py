"""Mediates one fresh provider search with the pure ``recommendation`` pipeline.

Per ADR-0001 decision 2, ``suggestions`` mediates the provider search and the
pure ``recommendation`` pipeline. It performs no persistence: every call is a
fresh proposal (ADR-0008 decision 2, unchanged by adr/0023).

Per adr/0023 decision 4 / hand-off item 4, this module owns the default
non-deterministic random source for normal operation: when the caller does
not inject a ``random.Random``, a fresh, unseeded ``random.Random()`` (system
entropy) is created per call. Only ``dining_radar.suggestions.acceptance_state``
injects a seeded source, and only from ``contracts/test-support-api.yaml``'s
``randomSeed`` -- the public ``candidate-search-api.yaml`` carries no seed.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass

from dining_radar.recommendation.pipeline import (
    CandidateFilters,
    NormalizedCandidate,
    Origin,
    PopulationAttribute,
    build_proposal,
)

CandidateSource = Callable[[], tuple[Sequence[NormalizedCandidate], Origin]]


@dataclass(frozen=True)
class ProposalResult:
    """A complete replacement displayed-proposal, ready to serialize."""

    candidates: tuple[NormalizedCandidate, ...]
    izakaya_bar_fallback_applied: bool
    available_genres: tuple[str, ...]
    population_attributes: tuple[PopulationAttribute, ...] = ()
    shown_pool_exhausted: bool = False


def propose_candidates(
    filters: CandidateFilters,
    *,
    fetch_candidates: CandidateSource,
    random_source: random.Random | None = None,
    shown_provider_page_urls: Collection[str] = (),
) -> ProposalResult:
    """Perform one fresh search and select the displayed proposal.

    ``filters`` (adr/0023 decision 1) is the parsed ``CandidateFilters`` for
    this request -- the same shape for the initial request, "try again", and
    "change filters" alike. ``random_source`` defaults to a fresh, unseeded
    ``random.Random()`` per call (non-deterministic, matching production
    behavior); acceptance testing injects a seeded one.
    ``shown_provider_page_urls`` (adr/0024 decision 4) is the browser's
    current not-yet-shown/already-shown priority state for this request; it
    is forwarded to ``build_proposal`` and never persisted here or anywhere
    downstream beyond this one call.
    """
    candidates, origin = fetch_candidates()
    proposal = build_proposal(
        candidates,
        origin,
        filters,
        random_source=random_source or random.Random(),
        shown_provider_page_urls=shown_provider_page_urls,
    )
    return ProposalResult(
        candidates=proposal.candidates,
        izakaya_bar_fallback_applied=proposal.izakaya_bar_fallback_applied,
        available_genres=proposal.available_genres,
        population_attributes=proposal.population_attributes,
        shown_pool_exhausted=proposal.shown_pool_exhausted,
    )
