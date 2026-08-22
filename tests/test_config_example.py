"""The shipped config must stay usable, not drift back into placeholders."""

from pathlib import Path

import pytest
import yaml

from tt_autoapply.config import Config

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "config.example.yaml"


@pytest.fixture
def cfg(tmp_path):
    """Load the shipped example the way a real run would."""
    target = tmp_path / "config.yaml"
    target.write_text(EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "profile.yaml").write_text(
        (ROOT / "profile.example.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    return Config.load(target)


def test_example_config_parses():
    assert yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))


def test_listing_url_is_the_real_auditions_page(cfg):
    assert cfg.listing_url == "https://www.talenttalks.co.uk/auditions/"


def test_listing_selectors_are_the_real_ones(cfg):
    """These came off the live site — a regression to guesses should fail here."""
    assert "div.white.job.media" in cfg.get("selectors.listing_item")
    assert "a[href^='/audition/']@href" in cfg.get("selectors.link")


def test_link_selector_excludes_the_share_links():
    """Cards carry a Twitter share link; a bare a@href would grab it."""
    from tt_autoapply.selectors import parse_selector

    css, attr = parse_selector("a[href^='/audition/']@href")
    assert attr == "href"
    assert css == "a[href^='/audition/']"


def test_apply_form_is_mapped_to_the_real_flow(cfg):
    """Apply is a button leading to a page with one text box and Submit."""
    assert cfg.get("application.mode") == "form"
    triggers = " ".join(cfg.get("application.form.trigger"))
    assert "Apply for this job" in triggers
    selectors = " ".join(
        " ".join(f["selector"]) for f in cfg.get("application.form.fields")
    )
    assert "textarea" in selectors


def test_the_note_is_short_by_default(cfg):
    """The site sends the full profile already; the box is for extras only."""
    assert cfg.get("application.note") == "Available"
    assert cfg.get("application.flag_when_brief_asks") is True


def test_profile_example_loads_and_is_complete_enough_to_match(cfg):
    from tt_autoapply.profile_import import missing_fields

    profile = cfg.load_profile()
    assert profile["playing_age"] == {"min": 18, "max": 25}
    assert profile["gender"] == "male"
    # Only the personal contact details should still need filling in.
    assert set(missing_fields(profile)) <= {"name", "email"}
