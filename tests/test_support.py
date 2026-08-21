"""Tests for the plumbing: selector parsing, dedupe keys and application history."""

from datetime import datetime, timezone

import pytest

from tt_autoapply.coverletter import render
from tt_autoapply.models import ApplicationResult, MatchResult, Role
from tt_autoapply.selectors import as_list, parse_selector
from tt_autoapply.store import Store


def test_parse_selector_splits_attribute():
    assert parse_selector("h2 a@href") == ("h2 a", "href")
    assert parse_selector(".title") == (".title", None)


def test_parse_selector_leaves_attribute_selectors_alone():
    assert parse_selector("input[data-a@b]") == ("input[data-a@b]", None)


def test_as_list_accepts_string_or_list():
    assert as_list("a") == ["a"]
    assert as_list(["a", "b"]) == ["a", "b"]
    assert as_list(None) == []


def test_role_id_is_stable_and_url_keyed():
    a = Role(url="https://x.test/1", title="One")
    b = Role(url="https://x.test/1", title="One (updated title)")
    c = Role(url="https://x.test/2", title="One")
    assert a.id == b.id, "same listing must dedupe even if the title is edited"
    assert a.id != c.id


def test_role_without_url_still_gets_an_id():
    assert Role(url="", title="Inline brief", company="Acme").id


def test_store_blocks_reapplying(tmp_path):
    with Store(tmp_path / "test.db") as store:
        role = Role(url="https://x.test/1", title="Role")
        assert store.record_role(role) is True
        assert store.record_role(role) is False  # second sighting

        assert not store.has_applied(role.id)
        store.record_application(ApplicationResult(role.id, "applied", "submitted"))
        assert store.has_applied(role.id)


def test_dry_run_does_not_count_as_applied(tmp_path):
    with Store(tmp_path / "test.db") as store:
        role = Role(url="https://x.test/1", title="Role")
        store.record_role(role)
        store.record_application(ApplicationResult(role.id, "dry_run", "not submitted"))
        assert not store.has_applied(role.id)
        assert store.applications_today() == 0


def test_daily_counter_counts_only_submissions(tmp_path):
    with Store(tmp_path / "test.db") as store:
        for i in range(3):
            r = Role(url=f"https://x.test/{i}", title=f"Role {i}")
            store.record_role(r)
            store.record_application(ApplicationResult(r.id, "applied", "submitted"))
        assert store.applications_today() == 3


def test_match_and_history_round_trip(tmp_path):
    with Store(tmp_path / "test.db") as store:
        role = Role(url="https://x.test/1", title="Commercial")
        store.record_role(role)
        store.record_match(MatchResult(role.id, True, 0.8, ["good fit"], []))
        store.record_application(ApplicationResult(role.id, "applied", "submitted"))
        rows = store.history()
        assert len(rows) == 1
        assert rows[0]["title"] == "Commercial"
        assert rows[0]["status"] == "applied"


def test_cover_letter_uses_only_profile_facts():
    profile = {
        "name": "Test Performer",
        "email": "test@example.com",
        "phone": "07700 900000",
        "base": "London",
        "gender": "male",
        "playing_age": {"min": 18, "max": 25},
        "skills": ["guitar"],
        "accents": ["RP"],
        "credits": ["Lead — 'Short', dir. Someone (2025)"],
        "showreel": "https://example.com/reel",
        "spotlight_pin": "",
    }
    role = Role(url="https://x.test/1", title="Male Lead", company="Acme Casting")
    letter = render(role, profile)
    assert "Acme Casting" in letter
    assert "Male Lead" in letter
    assert "18-25" in letter
    assert "test@example.com" in letter


def test_cover_letter_survives_a_sparse_profile():
    profile = {"name": "Test", "email": "t@example.com", "playing_age": {"min": 18, "max": 25}}
    letter = render(Role(url="https://x.test/1", title="Role"), profile)
    assert "Test" in letter
