"""Wires the Hot Pepper adapter into a ``suggestions`` candidate source.

This is the only place outside ``dining_radar.integrations`` itself that may
import it (``web`` must go through ``suggestions``; see
``tests/test_structure.py``).
"""

from __future__ import annotations

from dining_radar.integrations.hotpepper.client import fetch_shops
from dining_radar.integrations.hotpepper.config import HotPepperConfig
from dining_radar.integrations.hotpepper.errors import ProviderUnavailableError
from dining_radar.integrations.hotpepper.normalize import normalize_shops
from dining_radar.recommendation.pipeline import NormalizedCandidate, Origin

from .errors import CandidateSourceUnavailableError


def fetch_real_candidates() -> tuple[list[NormalizedCandidate], Origin]:
    """One fresh Hot Pepper search, normalized for the recommendation pipeline.

    Raises ``CandidateSourceUnavailableError`` for any configuration,
    communication, or response failure so callers never need to know about
    the concrete provider adapter's exception types.
    """
    try:
        config = HotPepperConfig.from_env()
        raw_response = fetch_shops(config)
        candidates = normalize_shops(raw_response)
    except ProviderUnavailableError as error:
        raise CandidateSourceUnavailableError(str(error)) from error
    return candidates, Origin(config.origin_latitude, config.origin_longitude)
