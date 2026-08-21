"""Shared browser resolution for the end-to-end tests.

CI images and dev machines often carry a Chromium that doesn't match the build
Playwright pins, so try Playwright's own resolution first and fall back to any
Chromium already on disk.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest


def _candidate_executables() -> list[str]:
    found: list[str] = []
    for root in (os.environ.get("PLAYWRIGHT_BROWSERS_PATH"), "/opt/pw-browsers"):
        if not root:
            continue
        for pattern in ("chromium-*/chrome-linux/chrome", "chromium-*/chrome-mac/*/Chromium"):
            found.extend(str(p) for p in sorted(Path(root).glob(pattern)))
    return found


@pytest.fixture(scope="session")
def chromium_executable() -> str | None:
    """An executable_path that actually launches, or None for the default."""
    playwright = pytest.importorskip("playwright.sync_api")
    pw = playwright.sync_playwright().start()
    try:
        for executable in [None, *_candidate_executables()]:
            kwargs = {"executable_path": executable} if executable else {}
            try:
                browser = pw.chromium.launch(headless=True, **kwargs)
            except Exception:
                continue
            browser.close()
            return executable
        pytest.skip("no Chromium available - run: playwright install chromium")
    finally:
        pw.stop()
