"""The DETAILS panel decides matches, so it's parsed rather than guessed at.

Values here are taken from a real Talent Talks audition page.
"""

from datetime import date

import pytest

from tt_autoapply.coverletter import brief_asks_for_details
from tt_autoapply.labels import is_empty_value, map_pairs, normalise_label
from tt_autoapply.matcher import evaluate, parse_age_field, parse_gender_field
from tt_autoapply.models import Role
from tt_autoapply.scraper import ROLE_FIELD_ALIASES

# Exactly as the site renders it.
REAL_PAIRS = [
    ("LOCATION:", "London"),
    ("PAYMENT:", "£300 Per Day"),
    ("JOB CATEGORY:", "Short Film Shoot"),
    ("AGE:", "35-55"),
    ("GENDER:", "Male"),
    ("SHOOT DATE:", "18/09/2026"),
    ("POSTED:", "N/A"),
    ("DEADLINE", "18/09/2026"),
]

PROFILE = {
    "name": "Test Performer",
    "gender": "male",
    "ethnicity": "White British",
    "playing_age": {"min": 18, "max": 25},
    "base": "London",
}

RULES = {
    "min_score": 0.6,
    "max_age_days": 0,
    "pay": {"paid_only": True},
    "location": {"allow_self_tape": True, "allowed": ["london"]},
}

TODAY = date(2026, 8, 22)


def test_real_details_panel_maps_cleanly():
    got = map_pairs(REAL_PAIRS, ROLE_FIELD_ALIASES)
    assert got["location"] == "London"
    assert got["pay"] == "£300 Per Day"
    assert got["age"] == "35-55"
    assert got["gender"] == "Male"
    assert got["deadline"] == "18/09/2026"
    assert got["category"] == "Short Film Shoot"


def test_posted_na_is_treated_as_absent():
    """POSTED: N/A is common here — it must not parse as a date."""
    assert is_empty_value("N/A")
    assert "posted" not in map_pairs(REAL_PAIRS, ROLE_FIELD_ALIASES)


def test_labels_compare_regardless_of_styling():
    assert normalise_label("SHOOT DATE:") == normalise_label("Shoot Date")


@pytest.mark.parametrize(
    "value,expected",
    [
        ("35-55", (35, 55)),
        ("18-25", (18, 25)),
        ("18 to 25", (18, 25)),
        ("35+", (35, 99)),
        ("Under 18", (0, 18)),
        ("21", (21, 21)),
        ("Any", None),
        ("", None),
    ],
)
def test_parse_age_field(value, expected):
    assert parse_age_field(value) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        ("Male", {"male"}),
        ("Female", {"female"}),
        ("Male/Female", {"male", "female"}),
        ("Any", {"any"}),
        ("", set()),
    ],
)
def test_parse_gender_field(value, expected):
    assert parse_gender_field(value) == expected


def test_female_field_never_reads_as_male():
    assert "male" not in parse_gender_field("Female")


# --- end to end through the matcher ----------------------------------------


def role_with(**fields) -> Role:
    return Role(
        url="https://www.talenttalks.co.uk/audition/44413/",
        title="Short Film Shoot",
        description="A short film shooting in London.",
        fields=fields,
    )


def test_the_real_role_is_rejected_on_age():
    """AGE: 35-55 against a playing age of 18-25 — this must not be applied to."""
    result = evaluate(
        role_with(location="London", pay="£300 Per Day", age="35-55", gender="Male"),
        PROFILE,
        RULES,
        today=TODAY,
    )
    assert not result.fits
    assert any("35-55" in b for b in result.blockers)


def test_the_same_role_in_range_is_accepted():
    result = evaluate(
        role_with(location="London", pay="£300 Per Day", age="18-25", gender="Male"),
        PROFILE,
        RULES,
        today=TODAY,
    )
    assert result.fits, result.blockers


def test_the_labelled_field_beats_a_stray_number_in_the_prose():
    """AGE says 18-25; the body mentions "aged 40-50" for a different part."""
    role = role_with(location="London", pay="£300 Per Day", age="18-25", gender="Male")
    role.description = "Also casting a father figure, playing age 40-50, separately."
    assert evaluate(role, PROFILE, RULES, today=TODAY).fits


def test_deadline_field_is_read_in_uk_format():
    role = role_with(location="London", pay="£300", age="18-25", gender="Male",
                     deadline="18/09/2026")
    result = evaluate(role, PROFILE, RULES, today=TODAY)
    assert any("2026-09-18" in r for r in result.reasons)


def test_a_passed_deadline_from_the_field_blocks():
    role = role_with(location="London", pay="£300", age="18-25", gender="Male",
                     deadline="18/09/2025")
    result = evaluate(role, PROFILE, RULES, today=TODAY)
    assert not result.fits


# --- briefs that want more than "Available" --------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Please state your height and availability.",
        "Let us know why you are right for this role.",
        "When applying, please confirm you can drive.",
        "In your application include your Spotlight link.",
        "Tell us about your improv experience.",
    ],
)
def test_briefs_asking_for_specifics_are_detected(text):
    assert brief_asks_for_details(Role(url="u", title="t", description=text))


@pytest.mark.parametrize(
    "text",
    [
        "Short film shooting in London. Paid £300 per day.",
        "We are looking for people aged 18-25 for a research interview.",
        "",
    ],
)
def test_ordinary_briefs_are_not_flagged(text):
    assert brief_asks_for_details(Role(url="u", title="t", description=text)) is None
