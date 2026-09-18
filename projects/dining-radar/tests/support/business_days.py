"""The single, shared "N-th business day from now" fixture-date builder.

ADR-0060 decision 4 (``CANDIDATE_DATE_NOT_A_BUSINESS_DAY``) rejects a
candidate date whose calendar day is not a business day per
``dining_radar.gathering.holidays.is_business_day`` (neither a weekend nor a
Japan public holiday). Several test modules build a gathering's candidate
date from "now" as a Given fixture and need that date to always be a valid,
future, distinct business day *regardless of which real-world calendar date
this suite happens to run on* -- a raw ``timezone.now() + timedelta(days=N)``
call site (this module's own reason for existing: it replaces the small,
independently-written ``timedelta(days=N)``/``weekday()``-based helpers that
used to live one-per-module in ``tests/test_candidate_search.py`` and
``tests/ui_invariants/test_render_invariants.py``, and consolidates the
counting logic ``tests/test_gathering.py`` already had for the same reason
into one place, per the round that discovered the two former call sites
would fail whenever "today" rolled onto a weekend/holiday, e.g. 2026-09-18's
"tomorrow" landing on 2026-09-19 (Saturday) or 2026-09-21 (敬老の日)) can
silently land on a non-business day and be rejected with a 400 depending on
what day the suite happens to run.

Counting forward by business days only (skipping the exact same
weekend/holiday dates the rejection rule itself excludes), rather than a raw
calendar-day offset, has two properties every call site below relies on:

- it is strictly increasing in ``n`` (two different ``n`` arguments can
  never collide on the same date, unlike a raw weekend-crossing calendar
  offset could -- e.g. "+1 day" landing on a Saturday and "+2 days" landing
  on the same following Monday once both are pushed off the weekend), and
- the result is always both in the future and a business day, for any real
  calendar date this suite happens to run on, without hardcoding any
  holiday date here (the holiday data itself lives only in
  ``dining_radar.gathering.holidays``, this module's single source of
  truth for "is this day usable").
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from django.utils import timezone

from dining_radar.gathering import holidays


def nth_business_day(n: int = 1, *, from_date: date | None = None) -> date:
    """The ``n``-th business day (``holidays.is_business_day`` true) counting
    forward from ``from_date`` (local "today" if omitted, never included
    itself). ``n=1`` is the next business day after today.
    """
    if n < 1:
        raise ValueError("n must be >= 1")
    current = from_date if from_date is not None else timezone.localtime(timezone.now()).date()
    remaining = n
    while remaining > 0:
        current += timedelta(days=1)
        if holidays.is_business_day(current):
            remaining -= 1
    return current


def nth_business_datetime(n: int = 1, *, hour: int = 12, minute: int = 0) -> datetime:
    """An aware ``datetime`` at local ``hour:minute`` on ``nth_business_day(n)``."""
    target = nth_business_day(n)
    naive_at_time = datetime(target.year, target.month, target.day, hour, minute, 0)
    return timezone.make_aware(naive_at_time)


def nth_business_day_iso(n: int = 1, *, hour: int = 12, minute: int = 0) -> str:
    """``nth_business_day(n)`` as an RFC3339 string, at the fixed +09:00
    offset ``settings_base.TIME_ZONE = "Asia/Tokyo"`` always has (no DST)."""
    target = nth_business_day(n)
    return f"{target.isoformat()}T{hour:02d}:{minute:02d}:00+09:00"


def next_business_weekday_iso(
    weekday: int, *, min_days_ahead: int = 1, hour: int = 12, minute: int = 0
) -> str:
    """The next date >= ``min_days_ahead`` days from now whose ``weekday()``
    matches ``weekday`` (``datetime.date.weekday()``'s convention: 0=Monday
    ... 6=Sunday) *and* is not a Japan public holiday.

    For fixtures that need one specific day-of-week on purpose (e.g. a
    synthetic candidate population keyed by weekday, or a check whose intent
    is "this being a Monday matters") rather than merely "any business day"
    -- the "first business day satisfying the condition" reading ADR-0060
    decision 4 calls for when a weekday is pinned for another reason. Only
    ever called with a weekday that is itself a weekday (0-4); pinning a
    weekend day here would defeat ``is_business_day`` and is not this
    function's purpose (see the dedicated, intentionally-not-business-day
    Saturday/Sunday/holiday fixture builders test_gathering.py itself still
    owns for negative-path ``CANDIDATE_DATE_NOT_A_BUSINESS_DAY`` tests).

    If the target date is a public holiday, skips a whole week forward
    (keeps the requested weekday exact) rather than picking an adjacent day.
    """
    base_date = (timezone.localtime(timezone.now()) + timedelta(days=min_days_ahead)).date()
    delta = (weekday - base_date.weekday()) % 7
    target_date = base_date + timedelta(days=delta)
    while holidays.is_public_holiday(target_date):
        target_date += timedelta(days=7)
    return f"{target_date.isoformat()}T{hour:02d}:{minute:02d}:00+09:00"
