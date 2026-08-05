"""Provider-format normalization for the Hot Pepper Gourmet Web Service.

The exact raw shape here follows the publicly documented Hot Pepper Gourmet
API response fields available at implementation time. Per ADR-0002 decision
7, this repository never performs a credentialed live-provider test, so this
mapping is verified only against synthetic fixtures shaped like the
documented response (``tests/test_hotpepper_adapter.py``). Reconfirm the
exact field names against the current official documentation before public
operation, alongside the other provider-terms checks ``design.md`` already
requires.

Every field this module reads is provider-supplied reference data; nothing
here alters, invents, or guesses a fact the provider did not supply
(``design.md`` "provider境界").
"""

from __future__ import annotations

from collections.abc import Sequence

from dining_radar.recommendation.pipeline import NormalizedCandidate

from .errors import HotPepperResponseError

# Fields whose provider value indicates an amenity is available. Treated as
# internal-only ranking input for AMENITY_REFERENCE; none of these raw values
# are ever included in a browser-facing Candidate (see
# ``dining_radar.web.serializers``).
_AMENITY_FIELDS = ("private_room", "non_smoking", "parking", "wifi", "barrier_free")
_AMENITY_UNAVAILABLE_MARKERS = frozenset({"", "無", "なし", "-", "ー", "無し"})


def _text_or_none(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _float_or_raise(value: object, *, field: str) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as error:
        raise HotPepperResponseError(f"Shop {field} was not numeric.") from error


def _amenity_available(value: object) -> bool:
    text = _text_or_none(value)
    return text is not None and text not in _AMENITY_UNAVAILABLE_MARKERS


def _amenity_score(shop: dict) -> int:
    return sum(1 for field in _AMENITY_FIELDS if _amenity_available(shop.get(field)))


def _normalize_shop(shop: dict) -> NormalizedCandidate:
    if not isinstance(shop, dict):
        raise HotPepperResponseError("Each provider shop entry must be an object.")

    name = _text_or_none(shop.get("name"))
    if name is None:
        raise HotPepperResponseError("Provider shop was missing a name.")

    genre = shop.get("genre")
    genre_name = _text_or_none(genre.get("name")) if isinstance(genre, dict) else None
    if genre_name is None:
        raise HotPepperResponseError("Provider shop was missing a genre.")

    urls = shop.get("urls")
    provider_page_url = _text_or_none(urls.get("pc")) if isinstance(urls, dict) else None
    if provider_page_url is None:
        raise HotPepperResponseError("Provider shop was missing its page URL.")

    latitude = _float_or_raise(shop.get("lat"), field="lat")
    longitude = _float_or_raise(shop.get("lng"), field="lng")

    return NormalizedCandidate(
        name=name,
        genre=genre_name,
        description=_text_or_none(shop.get("catch")),
        business_hours=_text_or_none(shop.get("open")),
        regular_holiday=_text_or_none(shop.get("close")),
        total_seats=_int_or_none(shop.get("capacity")),
        access=_text_or_none(shop.get("access")),
        latitude=latitude,
        longitude=longitude,
        provider_page_url=provider_page_url,
        amenity_score=_amenity_score(shop),
    )


def normalize_shops(raw_response: dict) -> list[NormalizedCandidate]:
    """Convert one Hot Pepper search response into normalized candidates."""
    results = raw_response.get("results") if isinstance(raw_response, dict) else None
    shops = results.get("shop") if isinstance(results, dict) else None
    if shops is None:
        raise HotPepperResponseError("Provider response was missing results.shop.")
    if not isinstance(shops, Sequence) or isinstance(shops, (str, bytes)):
        raise HotPepperResponseError("Provider response results.shop was not a list.")

    return [_normalize_shop(shop) for shop in shops]
