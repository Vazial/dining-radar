"""No-server, no-browser regression check for the 2026-09-19 CI time-
dependent failure: TDR-GTH-57 failed in CI at 2026-09-18T15:07Z (JST
2026-09-19 00:07) with 'CANDIDATE_DATE_NOT_IN_FUTURE' != 'CANDIDATE_DATE_
NOT_A_BUSINESS_DAY' -- next_weekday_iso(5)'s seed was built from
datetime.now(UTC), which was still calendar day 2026-09-18 in UTC while
Japan (this product's own, single locale, no DST) had already turned over
to 2026-09-19. gathering_scheduling_browser.py/candidate_search_browser.py
now build every candidate-date seed from business_days.jst_now() instead
(see that module's own docstring for the full reproduction).

This file freezes jst_now (never a real network call, never the Playwright/
LiveServerTestCase machinery the rest of tests/acceptance needs) at the
exact CI instant that failed and at the instant one minute before Japan's
calendar day turns over, and checks that every pure, no-network seed
builder these two DSL modules expose still lands on a Japan calendar day
strictly after "today" in Japan -- the same property createGathering's own
CANDIDATE_DATE_NOT_IN_FUTURE check requires. Under the prior UTC-based
seed, the first instant's next_weekday_iso(5) seed would land on Japan's
*today* (2026-09-19), failing the assertion below the same way it failed in
CI -- this is a genuine regression check, not a tautology against the
already-fixed code.
"""

from __future__ import annotations

from datetime import datetime
from unittest import mock

from django.test import SimpleTestCase

from tests.acceptance.dsl import business_days
from tests.acceptance.dsl import candidate_search_browser as csb
from tests.acceptance.dsl import gathering_scheduling_browser as gsb

# The exact CI failure instant (JST 2026-09-19 00:07, just after Japan's
# calendar day turns over while UTC is still 2026-09-18) and one minute
# before that turnover (JST 2026-09-18 23:59, both calendar days still
# agree) -- the coordinator's own two named boundary instants.
_CI_FAILURE_INSTANT_UTC_ISO = "2026-09-18T15:07:00+00:00"
_JUST_BEFORE_TURNOVER_UTC_ISO = "2026-09-18T14:59:00+00:00"


class JstCalendarDayBoundaryTests(SimpleTestCase):
    """Every candidate-date seed builder must stay Japan-tomorrow-or-later
    across the UTC/JST calendar-day boundary, without ever calling the real
    product or opening a browser.
    """

    def _assert_seed_is_jst_tomorrow_or_later(
        self, seed_iso: str, frozen_now_utc: datetime, label: str
    ) -> None:
        seed = datetime.fromisoformat(seed_iso)
        today_jst = frozen_now_utc.astimezone(business_days.JST).date()
        seed_date_jst = seed.astimezone(business_days.JST).date()
        self.assertGreater(
            seed_date_jst,
            today_jst,
            f"{label}: seed {seed_iso} is Japan calendar day {seed_date_jst}, "
            f"not strictly after Japan 'today' {today_jst} (frozen now "
            f"{frozen_now_utc.isoformat()})",
        )

    def _check_all_seed_builders_at(self, frozen_now_utc_iso: str) -> None:
        frozen_now_utc = datetime.fromisoformat(frozen_now_utc_iso)
        frozen_now_jst = frozen_now_utc.astimezone(business_days.JST)
        with (
            mock.patch.object(business_days, "jst_now", return_value=frozen_now_jst),
            mock.patch.object(gsb, "jst_now", return_value=frozen_now_jst),
            mock.patch.object(csb, "jst_now", return_value=frozen_now_jst),
        ):
            # TDR-GTH-57's own Saturday seed.
            self._assert_seed_is_jst_tomorrow_or_later(
                gsb._next_weekday_seed_iso(5), frozen_now_utc, "TDR-GTH-57 Saturday seed"
            )
            # TDR-GTH-58's own holiday seed.
            self._assert_seed_is_jst_tomorrow_or_later(
                gsb.next_fixed_public_holiday_on_weekday_iso(),
                frozen_now_utc,
                "TDR-GTH-58 holiday seed",
            )
            # A normal Given-state date (days_from_now_iso's own seed, the
            # shape dozens of unrelated TDR-GTH scenarios depend on).
            self._assert_seed_is_jst_tomorrow_or_later(
                gsb._days_from_now_seed_iso(1), frozen_now_utc, "days_from_now_iso(1) seed"
            )
            # candidate_search_browser.py's own duplicate next_weekday_iso
            # (TDR-CS-17..23/Nav3's own Given-state pin).
            self._assert_seed_is_jst_tomorrow_or_later(
                csb.next_weekday_iso(0), frozen_now_utc, "candidate_search next_weekday_iso(0) seed"
            )

    def test_seeds_stay_tomorrow_or_later_at_the_ci_failure_instant(self) -> None:
        """JST has already turned over to a new calendar day while UTC has
        not (the exact CI reproduction, 2026-09-18T15:07Z = JST 2026-09-19
        00:07) -- every seed must still be Japan-tomorrow-or-later.
        """
        self._check_all_seed_builders_at(_CI_FAILURE_INSTANT_UTC_ISO)

    def test_seeds_stay_tomorrow_or_later_just_before_the_jst_turnover(self) -> None:
        """One minute before Japan's calendar day turns over (UTC and JST
        still agree on "today") -- the boundary case immediately preceding
        the CI failure instant above.
        """
        self._check_all_seed_builders_at(_JUST_BEFORE_TURNOVER_UTC_ISO)
