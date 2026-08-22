"""Guided-setup helpers and the Chromium launch fallback."""

import pytest

from tt_autoapply.browser import (
    BrowserMissing,
    find_system_browser,
    launch_attempts,
    launch_chromium,
)
from tt_autoapply.wizard import build_summary, find_listing_blocks, pick_detail_url

BASE = "https://www.talenttalks.co.uk"


def report(*links, blocks=1):
    return {
        "repeated_blocks": [
            {"selector": "article.audition", "count": 12,
             "links": [{"text": "x", "href": h} for h in links]}
        ] * blocks
    }


def test_pick_detail_url_resolves_relative_links():
    got = pick_detail_url(report("/auditions/male-lead/"), BASE)
    assert got == "https://www.talenttalks.co.uk/auditions/male-lead/"


def test_pick_detail_url_skips_navigation_links():
    got = pick_detail_url(
        report("/login", "https://facebook.com/x", "#", "/auditions/real-role/"), BASE
    )
    assert got == "https://www.talenttalks.co.uk/auditions/real-role/"


def test_pick_detail_url_handles_absolute_links():
    got = pick_detail_url(report(f"{BASE}/auditions/abc/"), BASE)
    assert got == f"{BASE}/auditions/abc/"


def test_pick_detail_url_returns_none_when_nothing_usable():
    assert pick_detail_url(report("/login", "mailto:a@b.com"), BASE) is None
    assert pick_detail_url({}, BASE) is None
    assert pick_detail_url({"repeated_blocks": [{"links": []}]}, BASE) is None


def test_find_listing_blocks_counts():
    assert find_listing_blocks({"repeated_blocks": [1, 2]}) == 2
    assert find_listing_blocks({}) == 0


def test_build_summary_contains_both_pages():
    text = build_summary({"url": "listing-page"}, {"url": "role-page"})
    assert "listing-page" in text
    assert "role-page" in text
    assert "LISTING PAGE" in text


def test_build_summary_survives_a_missing_detail_page():
    text = build_summary({"url": "listing-page"}, None)
    assert "listing-page" in text
    assert "Could not identify a role page" in text


# --- the failure the user actually hit -------------------------------------


class _FakeChromium:
    """Mimics a Playwright install that only works via `accepts`."""

    def __init__(self, accepts=None):
        self.accepts = accepts or (lambda kwargs: False)
        self.attempts: list[dict] = []

    def launch(self, **kwargs):
        self.attempts.append(kwargs)
        if self.accepts(kwargs):
            return "browser"
        raise RuntimeError(
            "Executable doesn't exist at .../chromium_headless_shell-1234/chrome-headless-shell"
        )


class _FakePlaywright:
    def __init__(self, chromium):
        self.chromium = chromium


def test_headless_launch_falls_back_to_the_full_chromium_build():
    chromium = _FakeChromium(lambda k: k.get("channel") == "chromium")
    assert launch_chromium(_FakePlaywright(chromium), headless=True) == "browser"
    assert chromium.attempts[1]["channel"] == "chromium"


def test_falls_back_to_installed_chrome_when_no_chromium_ships_for_the_os():
    """macOS 12: Playwright publishes no Chromium build, so drive real Chrome."""
    chromium = _FakeChromium(lambda k: k.get("channel") == "chrome")
    got = launch_chromium(_FakePlaywright(chromium), headless=True, _system_browser=None)
    assert got == "browser"
    assert [a.get("channel") for a in chromium.attempts] == [None, "chromium", "chrome"]


def test_falls_back_to_a_system_browser_path_last():
    chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    chromium = _FakeChromium(lambda k: k.get("executable_path") == chrome)
    got = launch_chromium(
        _FakePlaywright(chromium), headless=True, _system_browser=chrome
    )
    assert got == "browser"
    assert chromium.attempts[-1]["executable_path"] == chrome


def test_an_explicit_executable_path_is_never_second_guessed():
    attempts = launch_attempts({"executable_path": "/my/browser", "headless": True}, "/other")
    assert attempts == [{"executable_path": "/my/browser", "headless": True}]


def test_launch_failure_explains_both_fixes():
    chromium = _FakeChromium()
    with pytest.raises(BrowserMissing) as exc:
        launch_chromium(_FakePlaywright(chromium), headless=True, _system_browser=None)
    message = str(exc.value)
    assert "playwright install chromium" in message
    assert "google.com/chrome" in message


def test_headed_launch_skips_the_headless_only_workaround():
    attempts = launch_attempts({"headless": False}, None)
    assert all(a.get("channel") != "chromium" for a in attempts)


def test_find_system_browser_picks_the_first_that_exists(tmp_path):
    missing = str(tmp_path / "nope")
    present = tmp_path / "chrome"
    present.write_text("")
    assert find_system_browser([missing, str(present)]) == str(present)
    assert find_system_browser([missing]) is None
