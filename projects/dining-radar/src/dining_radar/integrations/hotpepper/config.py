"""Private runtime search configuration for the Hot Pepper adapter.

Per ADR-0002 and ADR-0005 decision 7, the search origin, its range, and the
provider API key are server-only runtime configuration. None of these values,
nor any realistic example of them, may be committed to this public
repository (``ARCHITECTURE.md`` "非公開データの扱い").
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from .errors import HotPepperConfigurationError

DEFAULT_BASE_URL = "https://webservice.recruit.co.jp/hotpepper/gourmet/v1/"
DEFAULT_SEARCH_RANGE = "3"


@dataclass(frozen=True)
class HotPepperConfig:
    """Everything the adapter needs for one search request.

    ``search_range`` is the Hot Pepper API's own ``range`` parameter (an
    opaque provider-defined band, not a public API concept); this product no
    longer exposes a range choice to the browser (ADR-0005 decision 4).
    """

    api_key: str
    origin_latitude: float
    origin_longitude: float
    search_range: str
    base_url: str

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> HotPepperConfig:
        env = environ if environ is not None else os.environ
        api_key = env.get("HOTPEPPER_API_KEY", "").strip()
        latitude_raw = env.get("HOTPEPPER_SEARCH_LATITUDE", "").strip()
        longitude_raw = env.get("HOTPEPPER_SEARCH_LONGITUDE", "").strip()
        search_range = env.get("HOTPEPPER_SEARCH_RANGE", "").strip() or DEFAULT_SEARCH_RANGE
        base_url = env.get("HOTPEPPER_API_BASE_URL", "").strip() or DEFAULT_BASE_URL

        missing = [
            name
            for name, value in (
                ("HOTPEPPER_API_KEY", api_key),
                ("HOTPEPPER_SEARCH_LATITUDE", latitude_raw),
                ("HOTPEPPER_SEARCH_LONGITUDE", longitude_raw),
            )
            if not value
        ]
        if missing:
            raise HotPepperConfigurationError(
                "Missing private runtime search configuration: " + ", ".join(missing)
            )

        try:
            latitude = float(latitude_raw)
            longitude = float(longitude_raw)
        except ValueError as error:
            raise HotPepperConfigurationError(
                "HOTPEPPER_SEARCH_LATITUDE and HOTPEPPER_SEARCH_LONGITUDE must be numeric."
            ) from error

        if not base_url.startswith("https://"):
            raise HotPepperConfigurationError("HOTPEPPER_API_BASE_URL must use HTTPS.")

        return cls(
            api_key=api_key,
            origin_latitude=latitude,
            origin_longitude=longitude,
            search_range=search_range,
            base_url=base_url,
        )
