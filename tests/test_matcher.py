from datetime import date

import pytest

from tt_autoapply.matcher import (
    evaluate,
    extract_age_range,
    extract_amounts,
    extract_deadline,
    extract_ethnicities,
    extract_genders,
    is_self_tape,
    is_unpaid,
    normalise_ethnicity,
)
from tt_autoapply.models import Role

PROFILE = {
    "name": "Test Performer",
    "gender": "male",
    "ethnicity": "White British",
    "playing_age": {"min": 18, "max": 25},
    "base": "London",
    "skills": ["full clean driving licence", "guitar"],
}

RULES = {
    "min_score": 0.6,
    "exclude_nudity": True,
    "ethnicity_filter": True,
    "pay": {"paid_only": True},
    "location": {"allow_self_tape": True, "allowed": ["london", "south east"]},
    "keyword_boosts": {"commercial": 0.15},
}

TODAY = date(2026, 8, 21)


def role(**kwargs) -> Role:
    base = {"url": "https://example.com/1", "title": "Role", "description": ""}
    base.update(kwargs)
    return Role(**base)


# --- extraction ------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Playing age 18-25", (18, 25)),
        ("Aged 20 to 30, London based", (20, 30)),
        ("Male, playing age: 21", (21, 21)),
        ("Looking for someone in their 30s", (30, 39)),
        ("25 - 35 years old", (25, 35)),
        ("No age given here", None),
    ],
)
def test_extract_age_range(text, expected):
    assert extract_age_range(text.lower()) == expected


def test_female_does_not_read_as_male():
    assert extract_genders("Seeking a female lead") == {"female"}
    assert "male" not in extract_genders("Seeking a female lead")


def test_male_and_any_gender():
    assert extract_genders("Male actor, 20s") == {"male"}
    assert "any" in extract_genders("Any gender, playing age 18-25")


def test_unpaid_detection():
    assert is_unpaid("Unpaid, expenses only")
    assert is_unpaid("This is a profit share production")
    assert not is_unpaid("Paid: £150 per day")


def test_extract_amounts_sorted_desc():
    assert extract_amounts("£150 per day, total £1,200") == [1200.0, 150.0]


def test_self_tape_detection():
    assert is_self_tape("Self-tape auditions only")
    assert not is_self_tape("In person casting in Soho")


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Deadline: 2026-09-30", date(2026, 9, 30)),
        ("Closes 30/09/2026", date(2026, 9, 30)),
        ("Applications close 30th September 2026", date(2026, 9, 30)),
        ("No date at all", None),
    ],
)
def test_extract_deadline(text, expected):
    assert extract_deadline(text) == expected


def test_normalise_ethnicity():
    assert normalise_ethnicity("White British") == "white"
    assert normalise_ethnicity("Black Caribbean") == "black"
    assert normalise_ethnicity("Prefer not to say") is None


def test_ethnicity_only_read_next_to_a_casting_word():
    assert extract_ethnicities("black male, playing age 20-30") == {"black"}
    assert extract_ethnicities("male lead, black") == {"black"}
    # Incidental uses must not be read as a casting requirement.
    assert extract_ethnicities("a black comedy about four friends") == set()
    assert extract_ethnicities("wardrobe: all black clothing") == set()
    # An open brief is not a requirement either.
    assert extract_ethnicities("all ethnicities welcome, black or white") == set()


# --- evaluate --------------------------------------------------------------


def test_good_match_is_applied_to():
    result = evaluate(
        role(
            title="Male lead, TV commercial",
            location="London",
            pay="£350 per day",
            description="Seeking a male actor, playing age 18-25. Paid commercial. London shoot.",
        ),
        PROFILE,
        RULES,
        today=TODAY,
    )
    assert result.fits
    assert result.score >= 0.6


def test_wrong_playing_age_blocks():
    result = evaluate(
        role(description="Male, playing age 45-60, London."),
        PROFILE,
        RULES,
        today=TODAY,
    )
    assert not result.fits
    assert any("playing age" in b for b in result.blockers)


def test_wrong_gender_blocks():
    result = evaluate(
        role(description="Seeking a female actress, playing age 18-25, London. Paid."),
        PROFILE,
        RULES,
        today=TODAY,
    )
    assert not result.fits
    assert any("casting female" in b for b in result.blockers)


def test_mismatched_ethnicity_blocks():
    result = evaluate(
        role(description="Black male actor, playing age 18-25, London. Paid £200/day."),
        PROFILE,
        RULES,
        today=TODAY,
    )
    assert not result.fits
    assert any("specifies black" in b for b in result.blockers)


def test_open_ethnicity_brief_does_not_block():
    result = evaluate(
        role(
            location="London",
            pay="£200 per day",
            description=(
                "All ethnicities welcome. Male, playing age 18-25. Paid commercial in London."
            ),
        ),
        PROFILE,
        RULES,
        today=TODAY,
    )
    assert result.fits


def test_unpaid_blocks_when_paid_only():
    result = evaluate(
        role(description="Male, 18-25, London. Unpaid, expenses only."),
        PROFILE,
        RULES,
        today=TODAY,
    )
    assert not result.fits
    assert any("unpaid" in b for b in result.blockers)


def test_out_of_area_blocks_but_self_tape_saves_it():
    away = role(location="Glasgow", description="Male, 18-25. Paid. In person casting.")
    assert not evaluate(away, PROFILE, RULES, today=TODAY).fits

    tape = role(
        location="Glasgow",
        pay="£300",
        description="Male, playing age 18-25. Paid. Self-tape audition.",
    )
    assert evaluate(tape, PROFILE, RULES, today=TODAY).fits


def test_passed_deadline_blocks():
    result = evaluate(
        role(
            location="London",
            deadline="Closes 01/01/2026",
            description="Male, 18-25, London. Paid £200.",
        ),
        PROFILE,
        RULES,
        today=TODAY,
    )
    assert not result.fits
    assert any("deadline passed" in b for b in result.blockers)


def test_nudity_blocks():
    result = evaluate(
        role(location="London", description="Male, 18-25, London. Paid. Involves nudity."),
        PROFILE,
        RULES,
        today=TODAY,
    )
    assert not result.fits


def test_excluded_keyword_blocks():
    rules = dict(RULES, exclude_keywords=["student film"])
    result = evaluate(
        role(location="London", description="Student film, male 18-25, London, paid."),
        PROFILE,
        rules,
        today=TODAY,
    )
    assert not result.fits


def test_below_threshold_is_reported_not_silently_dropped():
    rules = dict(RULES, min_score=0.99)
    result = evaluate(
        role(location="London", description="Male, 18-25, London, paid £200."),
        PROFILE,
        rules,
        today=TODAY,
    )
    assert not result.fits
    assert any("below threshold" in b for b in result.blockers)
