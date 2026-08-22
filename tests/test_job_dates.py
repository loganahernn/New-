"""Only jobs that haven't happened yet.

Listings write the date without a year ("Tuesday 25th August"), so the year is
inferred as the occurrence nearest today.
"""

from datetime import date

import pytest

from tt_autoapply.matcher import (
    evaluate,
    extract_event_dates,
    job_date,
    parse_day_month,
)
from tt_autoapply.models import Role

TODAY = date(2026, 8, 22)

ME = {
    "name": "Test", "age": 21, "gender": "male", "ethnicity": "White British",
    "playing_age": {"min": 18, "max": 25}, "base": "London",
}
RULES = {
    "min_score": 0.6, "max_age_days": 0, "age_mode": "contains_age",
    "require_future_date": True,
    "pay": {"paid_only": True},
    "location": {"allow_self_tape": True, "allowed": ["london"]},
}


def role(title="Paid role in London", **fields) -> Role:
    base = {"age": "18-25", "gender": "Male", "location": "London", "pay": "£100"}
    base.update(fields)
    return Role(url="https://x.test/1", title=title, description=title, fields=base)


# --- inferring the year ----------------------------------------------------


def test_a_date_just_ahead_is_this_year():
    assert parse_day_month(25, 8, TODAY) == date(2026, 8, 25)


def test_a_date_just_behind_is_this_year_not_next():
    """20th August with today 22nd August means it has been and gone."""
    assert parse_day_month(20, 8, TODAY) == date(2026, 8, 20)


def test_january_from_december_rolls_forward():
    december = date(2026, 12, 28)
    assert parse_day_month(4, 1, december) == date(2027, 1, 4)


def test_december_from_january_rolls_back():
    january = date(2026, 1, 4)
    assert parse_day_month(28, 12, january) == date(2025, 12, 28)


def test_an_impossible_date_is_ignored():
    assert parse_day_month(30, 2, TODAY) is None


# --- pulling dates out of real listing titles ------------------------------


def test_reads_the_date_from_a_real_title():
    title = "Guys and Girls Aged 18-25 on Tuesday 25th August. Paid £100"
    assert extract_event_dates(title, today=TODAY) == [date(2026, 8, 25)]


def test_reads_a_slash_date():
    assert extract_event_dates("Shoot date 18/09/2026", today=TODAY) == [date(2026, 9, 18)]


def test_a_multi_day_job_uses_its_last_day():
    """"Fitting Tuesday 25th and Filming Wednesday 26th August" — over on the 26th."""
    got = job_date(
        role(shoot_date="Fitting 25th August and Filming 26th August"), today=TODAY
    )
    assert got == date(2026, 8, 26)


def test_the_shoot_date_field_wins_over_the_title():
    got = job_date(
        role("Shoot on 20th August", shoot_date="18/09/2026"), today=TODAY
    )
    assert got == date(2026, 9, 18)


def test_the_body_text_is_not_scanned_for_job_dates():
    """Briefs mention other dates in passing; only the field and title count."""
    r = role("Paid role in London")
    r.description = "The company was founded on 3rd January and films often."
    assert job_date(r, today=TODAY) is None


# --- the filter ------------------------------------------------------------


def test_a_job_later_today_still_counts():
    assert evaluate(role(shoot_date="22/08/2026"), ME, RULES, today=TODAY).fits


def test_a_job_tomorrow_counts():
    assert evaluate(role(shoot_date="23/08/2026"), ME, RULES, today=TODAY).fits


def test_a_job_next_month_counts():
    assert evaluate(role(shoot_date="18/09/2026"), ME, RULES, today=TODAY).fits


@pytest.mark.parametrize("shoot", ["21/08/2026", "20/08/2026", "01/07/2026"])
def test_a_job_that_has_already_happened_is_skipped(shoot):
    result = evaluate(role(shoot_date=shoot), ME, RULES, today=TODAY)
    assert not result.fits
    assert any("already gone" in b for b in result.blockers)


def test_a_past_date_in_the_title_is_caught():
    result = evaluate(
        role("Extras wanted for shoot on Thursday 20th August. Paid"),
        ME, RULES, today=TODAY,
    )
    assert not result.fits
    assert any("already gone" in b for b in result.blockers)


def test_a_job_with_no_date_is_not_blocked():
    """No date stated is not evidence the job has passed."""
    assert evaluate(role("Paid role in London"), ME, RULES, today=TODAY).fits


def test_the_filter_can_be_turned_off():
    rules = dict(RULES, require_future_date=False)
    assert evaluate(role(shoot_date="01/07/2026"), ME, RULES, today=TODAY).fits is False
    assert evaluate(role(shoot_date="01/07/2026"), ME, rules, today=TODAY).fits


def test_the_real_upcoming_listing_still_passes():
    result = evaluate(
        role(
            "Guys and Girls Aged 18-25 on Tuesday 25th August. Paid £100 for 60 "
            "Minute Research Interview",
            deadline="Apply Before 25/08/2026",
            gender="Male/Female",
        ),
        ME, RULES, today=TODAY,
    )
    assert result.fits, result.blockers
