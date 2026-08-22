"""The specific rules asked for: a 21-year-old white male performer.

Age must actually fall inside the brief's range, gender must match, and a
brief casting a specific ethnicity must not be applied to.
"""

from datetime import date

import pytest

from tt_autoapply.matcher import evaluate, excludes_white
from tt_autoapply.models import Role

TODAY = date(2026, 8, 22)

ME = {
    "name": "Test Performer",
    "age": 21,
    "gender": "male",
    "ethnicity": "White British",
    "playing_age": {"min": 18, "max": 25},
    "base": "London",
}

RULES = {
    "min_score": 0.6,
    "max_age_days": 0,
    "age_mode": "contains_age",
    "ethnicity_filter": True,
    "pay": {"paid_only": True},
    "location": {"allow_self_tape": True, "allowed": ["london"]},
}


def role(description="Shooting in London.", **fields) -> Role:
    base = {"location": "London", "pay": "£300 Per Day", "gender": "Male"}
    base.update(fields)
    return Role(url="https://x.test/1", title="Role", description=description, fields=base)


def verdict(**kwargs):
    return evaluate(role(**kwargs), ME, RULES, today=TODAY)


# --- age 21 ----------------------------------------------------------------


@pytest.mark.parametrize("age_range", ["18-25", "18-30", "21-21", "20-22", "16-25", "18+"])
def test_applies_when_21_is_inside_the_range(age_range):
    result = verdict(age=age_range)
    assert result.fits, f"{age_range}: {result.blockers}"


@pytest.mark.parametrize("age_range", ["35-55", "25-35", "22-30", "30+", "Under 18"])
def test_skips_when_21_is_outside_the_range(age_range):
    result = verdict(age=age_range)
    assert not result.fits, f"{age_range} should have been skipped"
    assert any("you are 21" in b for b in result.blockers)


def test_edge_of_range_counts_as_inside():
    assert verdict(age="21-40").fits
    assert verdict(age="10-21").fits


def test_overlap_at_the_boundary_no_longer_slips_through():
    """25-35 overlaps a playing age of 18-25 at exactly 25 — but 21 isn't in it."""
    assert not verdict(age="25-35").fits


def test_a_brief_with_no_age_is_not_blocked_on_age():
    result = verdict()
    assert result.fits, result.blockers


# --- male ------------------------------------------------------------------


@pytest.mark.parametrize("gender", ["Male", "Male/Female", "Any"])
def test_applies_when_the_brief_wants_male(gender):
    assert verdict(age="18-25", gender=gender).fits


@pytest.mark.parametrize("gender", ["Female", "Woman"])
def test_skips_a_female_only_brief(gender):
    result = verdict(age="18-25", gender=gender)
    assert not result.fits
    assert any("female" in b.lower() for b in result.blockers)


# --- white -----------------------------------------------------------------


@pytest.mark.parametrize(
    "description",
    [
        "Seeking an East Asian male, London shoot.",
        "Casting a Black male lead for a short film.",
        "We need a South Asian actor for this role.",
        "Looking for an Asian male, 18-25.",
        "Middle Eastern male wanted.",
    ],
)
def test_skips_briefs_casting_another_ethnicity(description):
    result = evaluate(role(description=description, age="18-25"), ME, RULES, today=TODAY)
    assert not result.fits, f"should have skipped: {description}"
    assert any("specifies" in b for b in result.blockers)


@pytest.mark.parametrize(
    "description",
    [
        "This role is open to BAME performers only.",
        "We are casting from the global majority for this part.",
        "Seeking a person of colour for the lead.",
        "Non-white performers only for this character.",
    ],
)
def test_skips_briefs_that_exclude_white_performers(description):
    assert excludes_white(description)
    result = evaluate(role(description=description, age="18-25"), ME, RULES, today=TODAY)
    assert not result.fits
    assert any("ethnically diverse" in b for b in result.blockers)


@pytest.mark.parametrize(
    "description",
    [
        "All ethnicities welcome. Male, 18-25, London.",
        "Open to all ethnicities and backgrounds.",
        "Short film shooting in London, paid.",
        "A black comedy set in a London flat.",
        "Wardrobe is all black clothing.",
        "Seeking a White British male, 18-25.",
    ],
)
def test_still_applies_where_ethnicity_is_open_or_matches(description):
    result = evaluate(role(description=description, age="18-25"), ME, RULES, today=TODAY)
    assert result.fits, f"should have applied: {description} - {result.blockers}"


def test_bame_wording_inside_an_open_brief_does_not_block():
    """"Open to all ethnicities including BAME performers" is an invitation."""
    text = "Open to all ethnicities, including BAME performers. Male, 18-25."
    assert not excludes_white(text)
    assert evaluate(role(description=text, age="18-25"), ME, RULES, today=TODAY).fits


# --- the three together ----------------------------------------------------


def test_the_real_listing_from_the_board_is_applied_to():
    """"Guys and Girls Aged 18-25 ... Paid £100" — squarely a fit."""
    result = evaluate(
        role(
            description=(
                "We are looking for people aged 18-25 to take part in a 90 minute "
                "research interview in London, Camden. Paid £100."
            ),
            age="18-25",
            gender="Male/Female",
        ),
        ME,
        RULES,
        today=TODAY,
    )
    assert result.fits, result.blockers
