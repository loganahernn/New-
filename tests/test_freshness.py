"""Only new posts should be applied to — not the back catalogue."""

from datetime import date, timedelta

import pytest

from tt_autoapply.matcher import evaluate, extract_posted_date, role_age_days
from tt_autoapply.models import ApplicationResult, Role
from tt_autoapply.store import Store

TODAY = date(2026, 8, 21)

PROFILE = {
    "name": "Test Performer",
    "gender": "male",
    "ethnicity": "White British",
    "playing_age": {"min": 18, "max": 25},
    "base": "London",
}

RULES = {
    "min_score": 0.6,
    "max_age_days": 14,
    "pay": {"paid_only": True},
    "location": {"allow_self_tape": True, "allowed": ["london"]},
}

FRESH_BRIEF = "Male actor, playing age 18-25. Paid £300/day. London shoot."


def role(**kwargs) -> Role:
    base = {"url": "https://example.com/1", "title": "Role", "description": FRESH_BRIEF}
    base.update(kwargs)
    return Role(**base)


@pytest.mark.parametrize(
    "text,expected_days_ago",
    [
        ("Posted 2 days ago", 2),
        ("3 hours ago", 0),
        ("just now", 0),
        ("Posted today", 0),
        ("Posted yesterday", 1),
        ("1 week ago", 7),
        ("2 weeks ago", 14),
        ("a month ago", 30),
        ("an hour ago", 0),
    ],
)
def test_extract_posted_date_relative(text, expected_days_ago):
    assert extract_posted_date(text, today=TODAY) == TODAY - timedelta(days=expected_days_ago)


def test_extract_posted_date_absolute():
    assert extract_posted_date("Posted on 12 August 2026", today=TODAY) == date(2026, 8, 12)
    assert extract_posted_date("no date here", today=TODAY) is None


def test_role_age_prefers_the_most_recent_signal():
    # A stale date buried in the brief must not age a listing we just found.
    r = role(posted="", description="Filming began 2 January 2020. " + FRESH_BRIEF)
    age = role_age_days(r, today=TODAY, first_seen=TODAY)
    assert age == 0


def test_role_age_falls_back_to_when_we_first_saw_it():
    r = role(posted="")  # board shows no dates at all
    assert role_age_days(r, today=TODAY, first_seen=TODAY - timedelta(days=30)) == 30
    assert role_age_days(r, today=TODAY, first_seen=None) is None


def test_fresh_post_is_applied_to():
    result = evaluate(
        role(posted="Posted 1 day ago", location="London"), PROFILE, RULES, today=TODAY
    )
    assert result.fits, result.blockers


def test_old_post_is_blocked():
    result = evaluate(
        role(posted="Posted 30 days ago", location="London"), PROFILE, RULES, today=TODAY
    )
    assert not result.fits
    assert any("older than" in b for b in result.blockers)


def test_old_post_blocked_via_first_seen_when_board_shows_no_date():
    result = evaluate(
        role(location="London"),
        PROFILE,
        RULES,
        today=TODAY,
        first_seen=TODAY - timedelta(days=45),
    )
    assert not result.fits
    assert any("older than" in b for b in result.blockers)


def test_undated_listing_is_not_blocked_by_default():
    """A board with no dates must not filter out everything."""
    result = evaluate(role(location="London"), PROFILE, RULES, today=TODAY)
    assert result.fits, result.blockers


def test_require_posted_date_blocks_undated_listings():
    rules = dict(RULES, require_posted_date=True)
    result = evaluate(role(location="London"), PROFILE, rules, today=TODAY)
    assert not result.fits
    assert any("no posted date" in b for b in result.blockers)


def test_max_age_zero_disables_the_filter():
    rules = dict(RULES, max_age_days=0)
    result = evaluate(
        role(posted="Posted 400 days ago", location="London"), PROFILE, rules, today=TODAY
    )
    assert result.fits, result.blockers


def test_newer_posts_score_higher():
    fresh = evaluate(role(posted="Posted today", location="London"), PROFILE, RULES, today=TODAY)
    older = evaluate(
        role(posted="Posted 10 days ago", location="London"), PROFILE, RULES, today=TODAY
    )
    assert fresh.score > older.score


# --- the baseline ----------------------------------------------------------


def test_store_is_empty_only_before_the_first_scan(tmp_path):
    with Store(tmp_path / "t.db") as store:
        assert store.is_empty()
        store.record_role(role())
        assert not store.is_empty()


def test_baselined_roles_stay_excluded_on_later_runs(tmp_path):
    """The bug this guards: baseline records first_seen=today, so without an
    explicit marker the whole backlog looks brand new on the very next run."""
    with Store(tmp_path / "t.db") as store:
        backlog = [Role(url=f"https://x.test/{i}", title=f"Old {i}") for i in range(3)]
        for r in backlog:
            store.record_role(r)
        store.record_baseline(r.id for r in backlog)

        for r in backlog:
            assert store.is_baseline(r.id)

        # A genuinely new listing arriving later is not baselined.
        fresh = Role(url="https://x.test/new", title="New")
        store.record_role(fresh)
        assert not store.is_baseline(fresh.id)


def test_first_seen_round_trips(tmp_path):
    with Store(tmp_path / "t.db") as store:
        r = role()
        store.record_role(r)
        assert store.first_seen(r.id) == date.today()
        assert store.first_seen("never-seen") is None


def test_first_seen_is_not_bumped_by_later_sightings(tmp_path):
    with Store(tmp_path / "t.db") as store:
        r = role()
        store.record_role(r)
        original = store.first_seen(r.id)
        store.record_role(r)
        assert store.first_seen(r.id) == original
