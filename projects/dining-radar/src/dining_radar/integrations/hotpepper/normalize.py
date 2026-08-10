"""Provider-format normalization for the Hot Pepper Gourmet Web Service.

The exact raw shape here follows the publicly documented Hot Pepper Gourmet
API response fields available at implementation time. Per ADR-0002 decision
7, this repository never performs a credentialed live-provider test, so this
mapping is verified only against synthetic fixtures shaped like the
documented response (``tests/test_hotpepper_adapter.py``). Reconfirm the
exact field names against the current official documentation before public
operation, alongside the other provider-terms checks ``design.md`` already
requires -- ADR-0019 decision 9 specifically flags ``non_smoking``, ``card``,
and ``budget`` (all newly read by this module) as needing the same
reconfirmation ``genre`` has already received.

A 2026-08-10 field-survey correction found ``budget.average`` unreliable
across 64 real candidates (5 empty, several others free-form prose mixing
more than one labeled figure, e.g. "通常平均：3000円 / 宴会平均：3500円"),
even though it had originally been reported alongside the other ``budget``
subfields as 100%-populated. ``budget_average`` (the ``NormalizedCandidate``
field ``dinnerBudgetTier`` is derived from; adr/0019 decision 8) is therefore
read from ``budget.name`` instead -- the provider's own price-band text
(e.g. "3,001〜4,000円"), which that same survey found genuinely 100%
populated and never mixes more than one price figure.

Every field this module reads is provider-supplied reference data; nothing
here alters, invents, or guesses a fact the provider did not supply
(``design.md`` "provider境界").

Per ADR-0019 decision 6, ``access`` is no longer read: the map already shows
each candidate's location, so this application no longer carries the
provider's free-text address at all.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from dining_radar.recommendation.pipeline import NormalizedCandidate

from .errors import HotPepperResponseError

# Known negative markers shared by the non-smoking and (formerly) amenity
# classifications: an explicit "not available" value, as opposed to an
# unknown/unparseable one that must not be asserted as a fact (ADR-0015's
# "確認できないことを断定しない" principle, applied here per ADR-0019
# decision 9).
_KNOWN_NEGATIVE_MARKERS = frozenset({"", "無", "なし", "-", "ー", "無し"})


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


# Matches a yen figure immediately followed by "円" (e.g. the "4,000" in
# "3,001〜4,000円"), commas and all -- see ``_dinner_budget_yen_reference``.
_DINNER_BUDGET_YEN_PATTERN = re.compile(r"(\d[\d,]*)\s*円")


def _dinner_budget_yen_reference(budget: object) -> float | None:
    """A coarse dinner-budget yen figure for ``dinnerBudgetTier`` bucketing.

    Reads ``budget.name`` (the provider's own price-band text, e.g.
    "3,001〜4,000円") rather than ``budget.average``: a 2026-08-10
    field-survey correction found ``average`` empty for 5 of 64 real
    candidates and, for several of the remaining 59, free-form prose mixing
    more than one labeled figure (e.g. "通常平均：3000円 / 宴会平均：3500円"),
    which this module must not guess between -- whereas ``name`` was
    genuinely 100% populated and never mixes more than one figure. Returns
    the largest yen figure named in the text (a range's upper bound, or its
    only bound when only one is named), or ``None`` -- never a guess -- when
    ``budget`` is absent, not an object, or its ``name`` names no figure.
    """
    if not isinstance(budget, dict):
        return None
    name = _text_or_none(budget.get("name"))
    if name is None:
        return None
    figures = [
        float(match.replace(",", "")) for match in _DINNER_BUDGET_YEN_PATTERN.findall(name)
    ]
    return max(figures) if figures else None


def _float_or_raise(value: object, *, field: str) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as error:
        raise HotPepperResponseError(f"Shop {field} was not numeric.") from error


def _non_smoking_status(value: object) -> str | None:
    """Classify the provider's ``non_smoking`` text into FULL/PARTIAL/NONE/null.

    Per ADR-0019 decision 9: a value containing "全面禁煙" is FULL; a value
    containing "禁煙" without "全面" is PARTIAL; a known negative marker (no
    non-smoking seating mentioned at all) is NONE; anything else is left
    ``None`` rather than asserted as a fact this module cannot confirm.
    """
    text = _text_or_none(value)
    if text is None:
        return None
    if "全面禁煙" in text:
        return "FULL"
    if "禁煙" in text:
        return "PARTIAL"
    if text in _KNOWN_NEGATIVE_MARKERS:
        return "NONE"
    return None


def _card_payment_available(value: object) -> bool | None:
    """Classify the provider's ``card`` text into a plain boolean or null.

    Per ADR-0019 decision 9: a value containing "不可" is False; a value
    containing "可" (and not "不可") is True; anything else is left ``None``.
    "不可" is checked first because "利用不可" also contains "可".
    """
    text = _text_or_none(value)
    if text is None:
        return None
    if "不可" in text:
        return False
    if "可" in text:
        return True
    return None


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

    budget_average = _dinner_budget_yen_reference(shop.get("budget"))

    return NormalizedCandidate(
        name=name,
        genre=genre_name,
        description=_text_or_none(shop.get("catch")),
        regular_holiday=_text_or_none(shop.get("close")),
        total_seats=_int_or_none(shop.get("capacity")),
        non_smoking_status=_non_smoking_status(shop.get("non_smoking")),
        card_payment_available=_card_payment_available(shop.get("card")),
        budget_average=budget_average,
        latitude=latitude,
        longitude=longitude,
        provider_page_url=provider_page_url,
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
