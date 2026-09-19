"""Wires the Hot Pepper adapter into a ``suggestions`` candidate source.

This is the only place outside ``dining_radar.integrations`` itself that may
import it (``web`` must go through ``suggestions``; see
``tests/test_structure.py``).
"""

from __future__ import annotations

from dining_radar.integrations.hotpepper.client import fetch_shops
from dining_radar.integrations.hotpepper.config import HotPepperConfig
from dining_radar.integrations.hotpepper.errors import (
    HotPepperConfigurationError,
    ProviderUnavailableError,
)
from dining_radar.integrations.hotpepper.normalize import normalize_shops
from dining_radar.recommendation.pipeline import NormalizedCandidate, Origin

from .errors import CandidateSourceUnavailableError


def _origin_from_config(config: HotPepperConfig) -> Origin:
    return Origin(config.origin_latitude, config.origin_longitude)


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
    return candidates, _origin_from_config(config)


def configured_search_origin() -> Origin | None:
    """The private runtime search origin alone -- reads ``HOTPEPPER_SEARCH_
    LATITUDE``/``_LONGITUDE`` the same way ``fetch_real_candidates`` does
    (``_origin_from_config``, shared so the two can never disagree), but
    performs no ``fetch_shops`` call and no network request: a caller that
    only needs the configured origin (never a shop search) must not pay for
    one real provider search per read. ``None`` when the private runtime
    search configuration itself is missing or invalid.
    """
    try:
        config = HotPepperConfig.from_env()
    except HotPepperConfigurationError:
        return None
    return _origin_from_config(config)
