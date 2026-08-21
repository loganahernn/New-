"""End-to-end test against a local fake casting site.

Proves the real chain — scrape the listing, open each brief, match it against
the profile, fill the apply form — works with actual selectors and an actual
browser, without touching Talent Talks.

Skipped automatically when Playwright's browser isn't installed.
"""

from __future__ import annotations

import functools
import os
import http.server
import socket
import threading
from pathlib import Path

import pytest
import yaml

from tt_autoapply.applier import apply_via_form
from tt_autoapply.config import Config
from tt_autoapply.coverletter import render as render_cover_letter
from tt_autoapply.matcher import evaluate
from tt_autoapply.scraper import enrich_role, scrape_roles

FIXTURES = Path(__file__).parent / "fixtures" / "site"

PROFILE = {
    "name": "Test Performer",
    "email": "test@example.com",
    "phone": "07700 900000",
    "base": "London",
    "gender": "male",
    "ethnicity": "White British",
    "playing_age": {"min": 18, "max": 25},
    "skills": ["guitar"],
    "accents": ["RP"],
    "credits": [],
}


@pytest.fixture(scope="module")
def site_url():
    """Serve the fixture site on a random free port."""
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(FIXTURES))
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture(scope="module")
def browser_page():
    playwright = pytest.importorskip("playwright.sync_api")
    pw = playwright.sync_playwright().start()

    # Try Playwright's own resolution first, then any Chromium already on the
    # box (CI images often ship one that doesn't match the pinned build).
    attempts: list[dict] = [{}]
    for root in (os.environ.get("PLAYWRIGHT_BROWSERS_PATH"), "/opt/pw-browsers"):
        if not root:
            continue
        for found in sorted(Path(root).glob("chromium-*/chrome-linux/chrome")):
            attempts.append({"executable_path": str(found)})

    browser = None
    for kwargs in attempts:
        try:
            browser = pw.chromium.launch(headless=True, **kwargs)
            break
        except Exception:
            continue
    if browser is None:
        pw.stop()
        pytest.skip("no Chromium available - run: playwright install chromium")

    context = browser.new_context()
    page = context.new_page()
    try:
        yield page
    finally:
        context.close()
        browser.close()
        pw.stop()


@pytest.fixture
def cfg(tmp_path, site_url) -> Config:
    data = yaml.safe_load((FIXTURES / "config.yaml").read_text())
    data["site"]["base_url"] = site_url
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(data))
    return Config.load(path)


def test_full_pipeline(browser_page, cfg):
    roles = scrape_roles(browser_page, cfg)
    titles = sorted(r.title for r in roles)
    assert titles == [
        "Female Lead - Feature Film",
        "Male Lead - TV Commercial",
        "Unpaid Student Short",
    ], f"scraper did not read the listing cards: {titles}"

    rules = cfg.get("matching")
    decisions = {}
    for role in roles:
        enrich_role(browser_page, cfg, role)
        decisions[role.title] = evaluate(role, PROFILE, rules)

    fitting = decisions["Male Lead - TV Commercial"]
    assert fitting.fits, fitting.blockers

    wrong_gender = decisions["Female Lead - Feature Film"]
    assert not wrong_gender.fits
    assert any("female" in b for b in wrong_gender.blockers)

    unpaid = decisions["Unpaid Student Short"]
    assert not unpaid.fits
    assert any("unpaid" in b.lower() for b in unpaid.blockers)


def test_dry_run_fills_the_form_but_does_not_submit(browser_page, cfg):
    role = next(r for r in scrape_roles(browser_page, cfg) if "Male Lead" in r.title)
    enrich_role(browser_page, cfg, role)
    letter = render_cover_letter(role, PROFILE)

    result = apply_via_form(browser_page, cfg, role, PROFILE, letter, dry_run=True)
    assert result.status == "dry_run"

    # The form is genuinely populated — the submit click is what's withheld.
    assert PROFILE["name"] in browser_page.locator("#cover_letter").input_value()
    assert browser_page.locator("#phone").input_value() == PROFILE["phone"]
    assert browser_page.locator("#confirmation").count() == 0


def test_live_apply_submits_and_confirms(browser_page, cfg):
    role = next(r for r in scrape_roles(browser_page, cfg) if "Male Lead" in r.title)
    enrich_role(browser_page, cfg, role)
    letter = render_cover_letter(role, PROFILE)

    result = apply_via_form(browser_page, cfg, role, PROFILE, letter, dry_run=False)
    assert result.status == "applied", result.detail
    assert browser_page.locator("#confirmation").count() == 1


def test_import_profile_from_a_real_page(browser_page, site_url, tmp_path):
    """Reads the performer's own profile page rather than making them retype it."""
    from tt_autoapply.profile_import import merge_profile, scrape_profile, write_profile

    imported = scrape_profile(browser_page, f"{site_url}/profile.html")

    assert imported["name"] == "Test Performer"
    assert imported["playing_age"] == {"min": 18, "max": 25}
    assert imported["gender"] == "Male"
    assert imported["ethnicity"] == "White British"
    assert imported["height_cm"] == 180
    assert imported["base"] == "London"
    assert imported["accents"] == ["RP", "Cockney"]
    assert "Guitar" in imported["skills"]
    assert imported["email"] == "test@example.com"
    assert len(imported["credits"]) == 2

    # And it lands in a usable profile.yaml without losing hand-entered fields.
    path = tmp_path / "profile.yaml"
    path.write_text("phone: '07700 900000'\n")
    existing = yaml.safe_load(path.read_text())
    merged, changes = merge_profile(existing, imported)
    write_profile(path, merged)

    saved = yaml.safe_load(path.read_text())
    assert saved["phone"] == "07700 900000"
    assert saved["playing_age"] == {"min": 18, "max": 25}
    assert changes
