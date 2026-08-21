"""Playwright session management.

Login is done once, interactively, in a visible browser — you type your own
credentials and clear any captcha/2FA yourself. The resulting cookies are saved
to a storage-state file and reused by later headless runs, so the tool never
handles or stores your password.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Iterator

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

from .config import Config


class SessionExpired(RuntimeError):
    """Raised when the saved cookies no longer authenticate us."""


@contextlib.contextmanager
def browser_context(cfg: Config, *, headless: bool | None = None) -> Iterator[BrowserContext]:
    """Yield a browser context, loading saved cookies when they exist."""
    state_path = cfg.resolve_path("browser.storage_state")
    if headless is None:
        headless = bool(cfg.get("browser.headless", True))

    launch_kwargs: dict = {
        "headless": headless,
        "slow_mo": int(cfg.get("browser.slow_mo_ms", 0) or 0),
    }
    # Point at a specific Chrome/Chromium when Playwright's own download isn't
    # the one you want to drive (system Chrome, a CI image's browser).
    executable = cfg.get("browser.executable_path")
    if executable:
        launch_kwargs["executable_path"] = str(Path(str(executable)).expanduser())

    with sync_playwright() as pw:
        browser: Browser = pw.chromium.launch(**launch_kwargs)
        kwargs: dict = {}
        if state_path.exists():
            kwargs["storage_state"] = str(state_path)
        ua = cfg.get("browser.user_agent")
        if ua:
            kwargs["user_agent"] = ua

        context = browser.new_context(**kwargs)
        context.set_default_timeout(int(cfg.get("site.timeout_ms", 30000)))
        try:
            yield context
        finally:
            context.close()
            browser.close()


def save_state(context: BrowserContext, cfg: Config) -> Path:
    state_path = cfg.resolve_path("browser.storage_state")
    state_path.parent.mkdir(parents=True, exist_ok=True)
    context.storage_state(path=str(state_path))
    return state_path


def interactive_login(cfg: Config) -> Path:
    """Open a visible browser, wait for you to log in, then save the session."""
    login_url = cfg.get("site.login_url") or cfg.listing_url
    state_path = cfg.resolve_path("browser.storage_state")
    state_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(login_url, wait_until="domcontentloaded")
        print(
            "\nA browser window is open.\n"
            "  1. Log in to Talent Talks as you normally would.\n"
            "  2. Navigate to the auditions page so the session is fully established.\n"
            "  3. Come back here and press Enter.\n"
        )
        input("Press Enter once you are logged in... ")
        context.storage_state(path=str(state_path))
        context.close()
        browser.close()

    print(f"Session saved to {state_path}")
    return state_path


def is_logged_in(page: Page, cfg: Config) -> bool:
    """Best-effort auth check using the configured logged-in marker."""
    markers = cfg.get("selectors.logged_in_marker") or []
    if isinstance(markers, str):
        markers = [markers]
    if not markers:
        return True  # nothing configured to check against
    for selector in markers:
        try:
            if page.locator(selector).count() > 0:
                return True
        except Exception:
            continue
    return False
