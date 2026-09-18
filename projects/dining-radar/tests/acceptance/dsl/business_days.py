"""Single shared place (2026-09-18 tester task, following on ADR-0060) every
TDR-GTH/TDR-CS Given-state builder that needs a candidate date goes through
to pick one gathering-scheduling-api.yaml will actually accept.

gathering-scheduling-api.yaml's createGathering/addCandidateDates reject a
CandidateDateInput.startAt whose date is a Saturday, a Sunday, or a date this
product's own bundled Japan public holiday data recognizes as a holiday, with
400 CANDIDATE_DATE_NOT_A_BUSINESS_DAY (ADR-0060 decision 1/2/4). That bundled
holiday data is maintained by a human at least once a year and this suite
never reads it -- reimplementing an approximation of Japan's public-holiday
calendar inside test code would silently drift from whatever the product
itself actually enforces on any given day (the same class of risk the
scenario this rule exists for is itself guarding against). This module
therefore never computes weekends/holidays itself; it only ever asks the
product, through its own public boundary, whether one candidate date is
accepted, and advances to the next candidate on an observed rejection.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta

MAX_BUSINESS_DAY_ADVANCES = 8


class BusinessDayNotFoundError(AssertionError):
    """Raised when no accepted candidate date was found within the bound.

    A real regression in the product's own business-day check (e.g. it
    started rejecting every date) must fail loudly and explicitly here,
    not retry forever or silently hand back an unresolved seed.
    """


def resolve_business_day_iso(
    seed_iso: str,
    probe_is_accepted: Callable[[str], bool],
    *,
    step_days: int,
    max_advances: int = MAX_BUSINESS_DAY_ADVANCES,
) -> str:
    """Starting at ``seed_iso``, calls ``probe_is_accepted(candidate_iso)`` --
    a caller-supplied check backed only by gathering-scheduling-api.yaml's own
    observable behavior -- advancing the candidate by ``step_days`` calendar
    days each time it reports the candidate rejected, until one is accepted.

    ``step_days=7`` holds the seed's own weekday fixed (for callers whose
    Given-state depends on which weekday a date falls on, e.g.
    test-support-api.yaml's GATHERING_OPEN_SHOP_WEEKDAY_MATCH per-weekday
    openShopCount); ``step_days=1`` does not (for callers that only need
    *some* accepted date, or that need relative order between several dates
    preserved -- a 1-day advance can only ever move a date later, never past
    another candidate date fewer than ``max_advances`` days ahead of it).
    Bounded rather than open-ended, per the same reasoning as this module's
    docstring: a real defect must fail fast and explain itself.
    """
    cursor = datetime.fromisoformat(seed_iso)
    for _ in range(max_advances):
        candidate_iso = cursor.isoformat()
        if probe_is_accepted(candidate_iso):
            return candidate_iso
        cursor = cursor + timedelta(days=step_days)
    raise BusinessDayNotFoundError(
        f"no candidate date accepted as a business day within {max_advances} "
        f"attempts starting from {seed_iso} (step={step_days} days) -- "
        f"gathering-scheduling-api.yaml's CANDIDATE_DATE_NOT_A_BUSINESS_DAY "
        f"rejected every one"
    )
