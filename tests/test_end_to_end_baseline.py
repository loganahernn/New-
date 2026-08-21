"""End-to-end: the first run must not work through the back catalogue.

Serves a *mutable* copy of the fixture site so a listing can be added between
runs, which is the only way to prove "new posts only" actually holds.
"""

from __future__ import annotations

import functools
import http.server
import shutil
import socket
import threading
from pathlib import Path

import pytest
import yaml

from tt_autoapply.cli import _run_pipeline
from tt_autoapply.config import Config
from tt_autoapply.store import Store

FIXTURES = Path(__file__).parent / "fixtures" / "site"

NEW_LISTING = """
  <article class="audition">
    <h2><a href="/roles/newrole.html">Male Lead - New Commercial</a></h2>
    <span class="company">Fresh Casting</span>
    <span class="location">London</span>
    <span class="fee">£400 per day</span>
    <span class="posted">Posted today</span>
    <span class="deadline">Closes 30/12/2099</span>
    <p class="excerpt">Brand new posting.</p>
  </article>
"""

NEW_ROLE_PAGE = """<!doctype html>
<html><head><title>Male Lead - New Commercial</title></head><body>
<nav><a href="/logout">Log out</a></nav>
<article class="entry-content">
  <h1>Male Lead - New Commercial</h1>
  <span class="company">Fresh Casting</span>
  <span class="location">London</span>
  <span class="fee">£400 per day</span>
  <span class="posted">Posted today</span>
  <p>Seeking a male actor, playing age 18-25. All ethnicities welcome.
     Paid £400 per day. London shoot. Posted today.</p>
</article>
<button id="apply-btn" onclick="document.getElementById('apply-form').style.display='block'">Apply</button>
<form class="application-form" id="apply-form" style="display:none"
      onsubmit="event.preventDefault();document.body.insertAdjacentHTML('beforeend','<div id=confirmation class=alert-success>Application sent</div>');">
  <textarea id="cover_letter" name="message"></textarea>
  <input id="phone" name="phone" type="text">
  <button type="submit">Send application</button>
</form>
</body></html>
"""

PROFILE = {
    "name": "Test Performer",
    "email": "test@example.com",
    "phone": "07700 900000",
    "base": "London",
    "gender": "male",
    "ethnicity": "White British",
    "playing_age": {"min": 18, "max": 25},
}


@pytest.fixture
def site(tmp_path):
    """A writable copy of the fixture site, served over HTTP."""
    root = tmp_path / "site"
    shutil.copytree(FIXTURES, root)

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield root, f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def cfg(tmp_path, site, chromium_executable):
    root, url = site
    data = yaml.safe_load((FIXTURES / "config.yaml").read_text())
    data["site"]["base_url"] = url
    data["storage"]["database"] = str(tmp_path / "apps.db")
    data["browser"]["storage_state"] = str(tmp_path / "session.json")
    data["application"]["screenshot_dir"] = str(tmp_path / "shots")
    data["matching"]["max_age_days"] = 14
    if chromium_executable:
        data["browser"]["executable_path"] = chromium_executable

    (tmp_path / "profile.yaml").write_text(yaml.safe_dump(PROFILE))
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(data))
    return Config.load(path)


def _applied(cfg) -> list[str]:
    with Store(cfg.resolve_path("storage.database")) as store:
        return [r["title"] for r in store.history() if r["status"] == "applied"]


def add_new_listing(root: Path) -> None:
    index = root / "index.html"
    index.write_text(index.read_text().replace("</main>", NEW_LISTING + "</main>"))
    (root / "roles" / "newrole.html").write_text(NEW_ROLE_PAGE)


def test_first_run_baselines_and_only_new_posts_are_applied_to(cfg, site):
    root, _ = site

    # Run 1: the board already has a role this performer fits. Nothing is sent.
    assert _run_pipeline(cfg, do_apply=True, limit=None) == 0
    assert _applied(cfg) == [], "first run must not work the back catalogue"

    with Store(cfg.resolve_path("storage.database")) as store:
        assert not store.is_empty()

    # Run 2: same board, nothing new. Still nothing sent — this is the case a
    # naive "first seen today" check would get wrong.
    assert _run_pipeline(cfg, do_apply=True, limit=None) == 0
    assert _applied(cfg) == []

    # Run 3: a genuinely new listing appears. That one, and only that one, goes.
    add_new_listing(root)
    assert _run_pipeline(cfg, do_apply=True, limit=None) == 0
    assert _applied(cfg) == ["Male Lead - New Commercial"]


def test_include_existing_opts_back_into_the_backlog(cfg):
    assert _run_pipeline(cfg, do_apply=True, limit=None) == 0
    assert _applied(cfg) == []

    assert _run_pipeline(cfg, do_apply=True, limit=None, include_existing=True) == 0
    assert _applied(cfg) == ["Male Lead - TV Commercial"]
