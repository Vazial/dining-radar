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

**2026-09-19 CI time-dependent-failure fix**: the contract's own "today or
earlier is rejected" (CANDIDATE_DATE_NOT_IN_FUTURE) is evaluated by this
product against Japan calendar days -- this is a Japan-only product (product-
brief.md), and the contract's "startAt's date, time excluded" wording is
naturally read against that same locale, not against whichever timezone the
acceptance suite's own process happens to run in. A seed built from
``datetime.now(UTC)`` disagrees with the product about which calendar day
"today" is for exactly the 9 UTC hours (15:00-24:00) that are already
tomorrow in Japan (JST = UTC+9, no DST) -- reproduced in CI at
2026-09-18T15:07Z (JST 2026-09-19 00:07): next_weekday_iso(5)'s "next
Saturday" landed on the UTC calendar day 2026-09-19, which was JST's *today*,
not tomorrow, so createGathering rejected it with CANDIDATE_DATE_NOT_IN_
FUTURE before ever reaching the weekend check TDR-GTH-57 meant to exercise.
``jst_now`` below is the single clock every date-seed builder in this
suite's two DSL files goes through -- monkeypatch this one function (not
``datetime.now`` itself, and never this module's own already-timezone-aware
``resolve_business_day_iso`` above, which only ever advances whatever
tz-aware seed it is given) to fix "now" for a deterministic check.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

MAX_BUSINESS_DAY_ADVANCES = 8

# product-brief.md: this product has no locale/timezone setting -- it is a
# single-region (Japan) product, and settings_base.TIME_ZONE is "Asia/Tokyo"
# (fixed +09:00, no DST, confirmed in activeContext.md's own deploy-target
# realization notes). CandidateDateInput.startAt's "today or earlier"/
# "weekend or Japan public holiday" checks are both evaluated against that
# same Japan calendar day, not the acceptance suite process's own local time
# or UTC.
JST = ZoneInfo("Asia/Tokyo")


def jst_now() -> datetime:
    """The current moment as a Japan-local aware ``datetime`` -- the single
    clock every candidate-date seed in tests/acceptance is built from. A
    caller needing a fixed "now" for a deterministic, non-server check
    (this module's own docstring above) monkeypatches this function, e.g.
    ``unittest.mock.patch("tests.acceptance.dsl.business_days.jst_now", ...)``
    or, from the sibling DSL modules that import it by name, patches their
    own module-level reference instead (``patch.object(gathering_scheduling_
    browser, "jst_now", ...)``).
    """
    return datetime.now(JST)


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
