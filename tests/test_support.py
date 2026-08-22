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


def test_note_defaults_to_available():
    """The site attaches the full profile, so the box only needs a short note."""
    role = Role(url="https://x.test/1", title="Male Lead", company="Acme Casting")
    assert render(role, {"name": "Test"}) == "Available"


def test_note_is_configurable():
    role = Role(url="https://x.test/1", title="Role")
    assert render(role, {}, note="Available - happy to self-tape") == (
        "Available - happy to self-tape"
    )


def test_a_template_can_still_be_used(tmp_path):
    template = tmp_path / "note.j2"
    template.write_text("{{ note }} for {{ role.title }}")
    role = Role(url="https://x.test/1", title="Male Lead")
    assert render(role, {}, template) == "Available for Male Lead"


def test_a_broken_template_falls_back_to_the_note(tmp_path):
    template = tmp_path / "note.j2"
    template.write_text("{% for %}")  # invalid Jinja
    assert render(Role(url="https://x.test/1", title="Role"), {}, template) == "Available"


# --- "apply to everything I fit" semantics ---------------------------------


def test_zero_limit_means_no_cap():
    from tt_autoapply.cli import _within_limit

    # 0 / None / negative all mean uncapped.
    for limit in (0, None, -1):
        assert _within_limit(0, limit)
        assert _within_limit(9999, limit)

    # A positive number still caps.
    assert _within_limit(4, 5)
    assert not _within_limit(5, 5)


def test_seen_but_not_applied_role_is_rechecked(tmp_path):
    """A role skipped mid-run must not be lost just because we recorded it."""
    with Store(tmp_path / "test.db") as store:
        role = Role(url="https://x.test/1", title="Role")
        store.record_role(role)          # first run saw it...
        store.record_role(role)          # ...and a later run sees it again
        assert not store.has_applied(role.id), "still eligible to apply"


def test_rejected_lookup_only_fires_for_non_fitting_roles(tmp_path):
    with Store(tmp_path / "test.db") as store:
        good = Role(url="https://x.test/1", title="Fits")
        bad = Role(url="https://x.test/2", title="Does not fit")
        store.record_role(good)
        store.record_role(bad)
        store.record_match(MatchResult(good.id, True, 0.9, ["fits"], []))
        store.record_match(MatchResult(bad.id, False, 0.2, [], ["wrong age"]))

        assert store.was_rejected(bad.id)
        assert not store.was_rejected(good.id)
        assert not store.was_rejected("never-seen")
