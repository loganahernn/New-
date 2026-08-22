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


class BrowserMissing(RuntimeError):
    """Playwright has no usable Chromium installed."""


# Browsers already on the machine that Playwright can drive. Used when its own
# Chromium download isn't available — notably on macOS 12, which recent
# Playwright versions publish no Chromium build for at all.
SYSTEM_BROWSERS = [
    # macOS
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    # Linux
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/microsoft-edge",
    # Windows
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]


def find_system_browser(candidates: list[str] | None = None) -> str | None:
    """First Chrome-family browser already installed, if any."""
    for path in candidates if candidates is not None else SYSTEM_BROWSERS:
        if Path(path).exists():
            return path
    return None


def launch_attempts(kwargs: dict, system_browser: str | None) -> list[dict]:
    """Ordered launch options to try, most-preferred first.

    Two separate failure modes to survive:

    * The `chrome-headless-shell` download is missing or lagging behind the
      main Chromium build, which only breaks *headless* launches —
      `channel="chromium"` runs the full build headlessly instead.
    * Playwright ships no Chromium at all for this OS (macOS 12), where the
      only way forward is a browser the user already has.
    """
    if kwargs.get("executable_path"):
        return [kwargs]  # explicitly configured: respect it, don't second-guess

    attempts = [kwargs]
    if kwargs.get("headless", True):
        attempts.append({**kwargs, "channel": "chromium"})
    attempts.append({**kwargs, "channel": "chrome"})
    if system_browser:
        attempts.append({**kwargs, "executable_path": system_browser})
    return attempts


def launch_chromium(pw, **kwargs) -> "Browser":
    """Launch a Chrome-family browser, falling back through what's available."""
    system_browser = kwargs.pop("_system_browser", None)
    if system_browser is None and not kwargs.get("executable_path"):
        system_browser = find_system_browser()

    last_error: Exception | None = None
    for attempt in launch_attempts(kwargs, system_browser):
        try:
            return pw.chromium.launch(**attempt)
        except Exception as exc:
            last_error = exc

    raise BrowserMissing(
        "Couldn't start a browser.\n\n"
        "First try installing Playwright's own:\n"
        "    ./.venv/bin/python -m playwright install chromium\n\n"
        "If that says your OS isn't supported (macOS 12 and older), install\n"
        "Google Chrome from https://www.google.com/chrome/ and run again —\n"
        "the tool will drive that instead.\n\n"
        f"Original error: {last_error}"
    ) from last_error


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
    # e.g. "chrome" to drive an installed Google Chrome rather than a download.
    channel = cfg.get("browser.channel")
    if channel:
        launch_kwargs["channel"] = str(channel)

    with sync_playwright() as pw:
        browser: Browser = launch_chromium(pw, **launch_kwargs)
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
        browser = launch_chromium(pw, headless=False)
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
