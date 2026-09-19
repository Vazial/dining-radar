"""This product's own bundled Japan public holiday data (ADR-0060 decision 2).

**Why this module exists at all**: ``ADR-0035`` decision 6 declared "この製品
は国民の祝日、不定期の休業、特定日単位の営業判定は行わない" for the one place
this product used to touch holiday-adjacent judgment -- matching a shop's own
``regularHoliday`` free-text weekday closure. ``ADR-0060`` decisions 1/2/4
introduce a *second*, unrelated place -- whether a candidate-date calendar
day may be selected at all -- where this product now does judge whether a day
is a Japan public holiday. Decision 2's own text is explicit that this does
**not** reopen decision 6's scope: ``dining_radar.recommendation.pipeline``'s
``regularHoliday`` weekday matching is untouched by this module, and this
module is never imported there.

**Data shape (developer discretion, ADR-0060 decision 2's own delegation)**:
bundled with this product, never fetched from an external service at request
time, and confined to a fixed ``[MIN_YEAR, MAX_YEAR]`` range -- a date outside
that range is always treated as "not a holiday" (decision 2: "同梱データが
カバーする年の範囲を超える日付は「祝日でない」として扱う ... 過検出ではなく
過小検出になることは ... 安全な既定値"). The holiday dates themselves are
computed once, at import time, from Japan's own published national-holiday
rules (a fixed-date table, the "ハッピーマンデー" nth-Monday rule, the
astronomical vernal/autumnal equinox approximation the Cabinet Office's own
announcements track, plus the 振替休日/国民の休日 substitution rules) rather
than transcribed one date at a time by hand -- the *rules themselves* are the
stable, rarely-changing "static data" ADR-0060 decision 2 asked for (a law
change that alters one of these rules, e.g. 2019's one-off Emperor
enthronement holidays or the 2020/2021 Olympic-driven single-year house
moves, is exactly why ``MIN_YEAR``/``MAX_YEAR`` below deliberately excise
those anomalous years rather than attempt to special-case them here).

**Operational update process (decision 2: "年1回以上人間が手で更新する")**:
once a year (or whenever a law change is announced), a human re-verifies
``MAX_YEAR`` below still covers at least one year past "today", extends it
forward, and spot-checks a handful of the newly-covered year's dates against
the Cabinet Office's own official announcement
(https://www8.cao.go.jp/chosei/shukujitsu/gaiyou.html) before committing the
new value -- this module raises no alarm on its own if that lapses, short of
the safety-net unit test that asserts ``MAX_YEAR`` still covers "today +366
days" (``HolidayRangeCoversAtLeastOneYearAheadTests`` in
``tests/test_gathering.py``).
"""

from __future__ import annotations

from datetime import date, timedelta

# See this module's own docstring for the update process. MIN_YEAR
# deliberately starts after the 2019 (Emperor enthronement, one-off extra
# holidays) and 2020/2021 (Tokyo Olympics, one-off single-year house moves
# for Marine/Sports/Mountain day) anomaly years -- this module implements
# only the *ordinary* rule set below, which those three years do not follow.
MIN_YEAR = 2022
MAX_YEAR = 2036


def _nth_monday(year: int, month: int, nth: int) -> date:
    """The date of the ``nth`` Monday of ``year``/``month`` (1-indexed).

    Backs every "ハッピーマンデー" holiday (成人の日/海の日/敬老の日/
    スポーツの日) below.
    """
    first_of_month = date(year, month, 1)
    # date.weekday(): Monday == 0 ... Sunday == 6.
    days_until_first_monday = (0 - first_of_month.weekday()) % 7
    first_monday = 1 + days_until_first_monday
    return date(year, month, first_monday + 7 * (nth - 1))


def _vernal_equinox(year: int) -> date:
    """春分の日. The commonly-published astronomical approximation, valid
    across this module's own ``[MIN_YEAR, MAX_YEAR]`` range (the formula
    itself holds from 1980 through 2099)."""
    day = int(20.8431 + 0.242194 * (year - 1980)) - (year - 1980) // 4
    return date(year, 3, day)


def _autumnal_equinox(year: int) -> date:
    """秋分の日. Same approximation family as ``_vernal_equinox`` above."""
    day = int(23.2488 + 0.242194 * (year - 1980)) - (year - 1980) // 4
    return date(year, 9, day)


def _fixed_and_happy_monday_holidays(year: int) -> dict[date, str]:
    """Every named national holiday whose date this year's law fixes directly
    (a fixed month/day, an nth-Monday rule, or an equinox), before either
    substitution rule below is applied."""
    return {
        date(year, 1, 1): "元日",
        _nth_monday(year, 1, 2): "成人の日",
        date(year, 2, 11): "建国記念の日",
        date(year, 2, 23): "天皇誕生日",
        _vernal_equinox(year): "春分の日",
        date(year, 4, 29): "昭和の日",
        date(year, 5, 3): "憲法記念日",
        date(year, 5, 4): "みどりの日",
        date(year, 5, 5): "こどもの日",
        _nth_monday(year, 7, 3): "海の日",
        date(year, 8, 11): "山の日",
        _nth_monday(year, 9, 3): "敬老の日",
        _autumnal_equinox(year): "秋分の日",
        _nth_monday(year, 10, 2): "スポーツの日",
        date(year, 11, 3): "文化の日",
        date(year, 11, 23): "勤労感謝の日",
    }


def _with_citizens_holidays(base: dict[date, str]) -> dict[date, str]:
    """国民の休日: a day that is not itself a named holiday, but falls exactly
    between two days that are (most commonly the "敬老の日"/"秋分の日" gap
    some years produce, "シルバーウィーク"), is itself a holiday."""
    extra: dict[date, str] = {}
    for day in base:
        gap = day + timedelta(days=1)
        day_after_gap = day + timedelta(days=2)
        if gap not in base and day_after_gap in base:
            extra[gap] = "国民の休日"
    combined = dict(base)
    combined.update(extra)
    return combined


def _with_substitute_holidays(designated: dict[date, str]) -> dict[date, str]:
    """振替休日: any designated holiday (including a 国民の休日 from above)
    that falls on a Sunday moves to the nearest following day that is not
    itself already a designated holiday."""
    combined = dict(designated)
    for day in designated:
        if day.weekday() == 6:  # Sunday
            candidate = day + timedelta(days=1)
            while candidate in combined:
                candidate += timedelta(days=1)
            combined[candidate] = "振替休日"
    return combined


def _year_holidays(year: int) -> dict[date, str]:
    base = _fixed_and_happy_monday_holidays(year)
    with_citizens = _with_citizens_holidays(base)
    return _with_substitute_holidays(with_citizens)


# Materialized once, at import time, for every year this module bundles --
# "同梱データ" (decision 2): no per-request/per-call recomputation, and no
# external service is ever consulted to produce or refresh it.
_HOLIDAYS_BY_YEAR: dict[int, dict[date, str]] = {
    year: _year_holidays(year) for year in range(MIN_YEAR, MAX_YEAR + 1)
}


def is_public_holiday(day: date) -> bool:
    """Whether ``day`` is a Japan public holiday per this module's own bundled
    data. Always ``False`` outside ``[MIN_YEAR, MAX_YEAR]`` (decision 2)."""
    if not (MIN_YEAR <= day.year <= MAX_YEAR):
        return False
    return day in _HOLIDAYS_BY_YEAR[day.year]


def is_weekend(day: date) -> bool:
    """Saturday or Sunday, independent of ``is_public_holiday`` (ADR-0060
    decision 1/2: a day may be a weekday holiday, or a non-holiday weekend --
    the two conditions are checked independently everywhere this module is
    used)."""
    return day.weekday() >= 5


def is_business_day(day: date) -> bool:
    """Neither a weekend nor a Japan public holiday (ADR-0060 decision 4's
    ``CANDIDATE_DATE_NOT_A_BUSINESS_DAY`` rejection condition, and the
    calendar day-cell ``disabledState`` this module also backs)."""
    return not is_weekend(day) and not is_public_holiday(day)


def all_holiday_isos() -> list[str]:
    """Every bundled holiday date, ascending, as ``YYYY-MM-DD`` strings.

    Consumed by ``dining_radar.gathering.views`` to embed this exact data
    into the candidate-date calendar screens' own rendered HTML (via
    Django's ``json_script`` template filter) so the client-side
    ``data-holiday``/``disabledState`` calendar behavior and the server's
    authoritative ``CANDIDATE_DATE_NOT_A_BUSINESS_DAY`` rejection are always
    reading the identical dataset (ADR-0060: "同じデータを使う") -- this
    product never re-implements the holiday-computation rules a second time
    in JavaScript, and never fetches this data from an external service.
    """
    every_day = {day for year_holidays in _HOLIDAYS_BY_YEAR.values() for day in year_holidays}
    return [day.isoformat() for day in sorted(every_day)]
