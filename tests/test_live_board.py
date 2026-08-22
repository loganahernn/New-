"""Against the actual listings on the board, and the signed-out trap.

Titles here are real ones read off talenttalks.co.uk/auditions/.
"""

from datetime import date

import pytest

from tt_autoapply.applier import href_is_rejected
from tt_autoapply.matcher import evaluate, extract_deadline
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


def listing(title, description="", **fields) -> Role:
    return Role(
        url="https://www.talenttalks.co.uk/audition/44413/",
        title=title,
        description=description or title,
        fields=fields,
    )


def fits(role) -> bool:
    return evaluate(role, ME, RULES, today=TODAY).fits


# --- the deadline field the board actually uses ----------------------------


def test_apply_before_is_parsed_as_a_deadline():
    """<p class="job-date">Apply Before 25/08/2026</p> — UK day-first."""
    assert extract_deadline("Apply Before 25/08/2026") == date(2026, 8, 25)


def test_a_closed_listing_is_skipped():
    role = listing("Paid role in London", age="18-25", gender="Male",
                   deadline="Apply Before 01/01/2026")
    assert not fits(role)


def test_an_open_listing_is_not_skipped_on_its_deadline():
    role = listing("Paid role in London. £100.", age="18-25", gender="Male",
                   location="London", pay="£100", deadline="Apply Before 25/08/2026")
    assert fits(role)


# --- the real listings on the board ----------------------------------------


def test_applies_to_the_18_to_25_research_interview():
    """"Guys and Girls Aged 18-25 ... Paid £100" — the obvious yes."""
    role = listing(
        "Guys and Girls Aged 18-25 on Tuesday 25th August. Paid £100 for 60 Minute "
        "Research Interview",
        "We are looking for people aged 18-25 to take part in a 90 minute research "
        "interview in London, Camden. Paid £100.",
        age="18-25", gender="Male/Female", location="London", pay="£100",
        deadline="Apply Before 25/08/2026",
    )
    assert fits(role), evaluate(role, ME, RULES, today=TODAY).blockers


def test_skips_the_child_actor_role():
    role = listing(
        "White Child Actor With Or Who Can Do A Northern American Accent Wanted For "
        "A Short Film Shoot",
        age="8-12", gender="Male", location="London", pay="£200",
    )
    assert not fits(role)


def test_skips_the_45_to_55_female_role():
    role = listing(
        "TV Drama : White Female aged 45-55 required for HMU test 25th August in "
        "Tottenham Hale. Paid FAA Rates",
        age="45-55", gender="Female", location="London", pay="£100",
    )
    assert not fits(role)


def test_skips_the_non_white_female_role():
    """Fails on two counts — gender and an ethnicity requirement."""
    role = listing(
        "Non-White Female aged 20-30 wanted for Social/Online Shoot",
        age="20-30", gender="Female", location="London", pay="£150",
    )
    result = evaluate(role, ME, RULES, today=TODAY)
    assert not result.fits
    assert len(result.blockers) >= 2


def test_skips_the_swimsuit_role_for_women():
    role = listing(
        "Females aged 20-30 happy to wear swimsuit on the beach required for social "
        "content shoot",
        age="20-30", gender="Female", location="Brighton", pay="£200",
    )
    assert not fits(role)


def test_applies_to_the_gen_z_fast_food_shoot():
    role = listing(
        "ACTORS ONLY: Gen-Z Types Wanted For A Fast Food Chain Shoot - Friday 28th August",
        "Casting Gen-Z types, 18-25, for a fast food chain commercial in London. Paid.",
        age="18-25", gender="Male/Female", location="London", pay="£300",
        deadline="Apply Before 28/08/2026",
    )
    assert fits(role), evaluate(role, ME, RULES, today=TODAY).blockers


def test_supporting_artist_role_spanning_20_to_45_is_applied_to():
    """21 sits inside 20-45, so this one counts."""
    role = listing(
        "Supporting artists aged 20-45 required for cosmetic brand commercial",
        age="20-45", gender="Male/Female", location="East London", pay="£120",
    )
    assert fits(role)


# --- the signed-out trap ---------------------------------------------------


@pytest.mark.parametrize(
    "href",
    ["member/login/", "/member/login/", "https://www.talenttalks.co.uk/member/login/",
     "sign-up/", "/client/register/"],
)
def test_an_apply_button_pointing_at_login_is_refused(href):
    """Signed out, the site shows the same button but links it to login."""
    reject = ["member/login", "/login", "sign-up", "register"]
    assert href_is_rejected(href, reject)


@pytest.mark.parametrize("href", ["/audition/44413/apply/", "/apply/44413/", None, ""])
def test_a_genuine_apply_link_is_allowed(href):
    reject = ["member/login", "/login", "sign-up", "register"]
    assert href_is_rejected(href, reject) is None


def test_no_reject_list_means_no_check():
    assert href_is_rejected("member/login/", []) is None


# --- the site's own "Already Applied" marker -------------------------------


def test_already_applied_roles_are_recorded_and_skipped(tmp_path):
    """The board marks cards you've applied to — including by hand."""
    from tt_autoapply.models import ApplicationResult
    from tt_autoapply.store import Store

    role = Role(
        url="https://www.talenttalks.co.uk/audition/44410/",
        title="ACTORS ONLY: Gen-Z Types Wanted For A Fast Food Chain Shoot",
        already_applied=True,
    )
    with Store(tmp_path / "t.db") as store:
        store.record_role(role)
        assert not store.has_applied(role.id)

        # What the pipeline does on seeing the marker.
        store.record_application(
            ApplicationResult(role.id, "applied", "already applied (per the site)")
        )
        assert store.has_applied(role.id), "must never be applied to again"


def test_roles_without_the_marker_stay_eligible():
    role = Role(url="https://x.test/1", title="Role")
    assert role.already_applied is False


def test_the_real_apply_url_is_not_mistaken_for_a_login_link():
    """Signed in the button goes to /audition/44413/apply/ — that must pass."""
    reject = ["member/login", "/login", "sign-up", "register"]
    assert href_is_rejected("/audition/44413/apply/", reject) is None
