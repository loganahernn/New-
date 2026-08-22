"""Guided first-time setup.

One command that walks the whole thing: log in, read the listing page, read one
role page, and write a single file to send back for the config to be filled in.

The point is that nobody has to know which command comes next, or find a role
URL by hand — the URL is picked out of the listing page we just read.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urljoin

if TYPE_CHECKING:  # pragma: no cover - import only needed for type checking
    from playwright.sync_api import Page

    from .config import Config

# Links in a listing card that are navigation rather than a role.
_NOT_A_ROLE = (
    "login", "logout", "register", "signup", "sign-up", "account", "profile",
    "contact", "about", "privacy", "terms", "cookie", "search", "#", "mailto:",
    "facebook", "twitter", "instagram", "linkedin", "tiktok",
)


def pick_detail_url(listing_report: dict, base_url: str) -> str | None:
    """Choose a role page from what the listing scan found.

    Saves the user hunting for an audition URL to paste. Prefers links from the
    block with the most repeats, since that's the one that looks like the
    listing grid.
    """
    for block in listing_report.get("repeated_blocks") or []:
        for link in block.get("links") or []:
            href = (link.get("href") or "").strip()
            if not href:
                continue
            lowered = href.lower()
            if any(bad in lowered for bad in _NOT_A_ROLE):
                continue
            return urljoin(base_url, href)
    return None


def build_summary(listing_report: dict, detail_report: dict | None) -> str:
    """One self-contained text file describing both pages."""
    lines = [
        "tt-autoapply discover results",
        "=" * 60,
        "",
        "Send this whole file back to get config.yaml filled in.",
        "It contains only page structure - no passwords, no personal details.",
        "",
        "-" * 60,
        "LISTING PAGE",
        "-" * 60,
        json.dumps(listing_report, indent=2)[:60000],
        "",
    ]
    if detail_report:
        lines += [
            "-" * 60,
            "ROLE PAGE (for mapping the application form)",
            "-" * 60,
            json.dumps(detail_report, indent=2)[:60000],
            "",
        ]
    else:
        lines += [
            "-" * 60,
            "ROLE PAGE",
            "-" * 60,
            "Could not identify a role page from the listing.",
            "",
        ]
    return "\n".join(lines)


def write_summary(cfg: "Config", summary: str) -> Path:
    out_dir = cfg.resolve_path("discover.output_dir", "state/discover")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "SEND-ME-THIS.txt"
    path.write_text(summary, encoding="utf-8")
    return path


def find_listing_blocks(report: dict) -> int:
    return len(report.get("repeated_blocks") or [])


def import_profile_if_found(cfg: "Config", page: "Page") -> tuple[str | None, list[str]]:
    """Find the logged-in user's profile page and pull their details in.

    Best-effort: a failure here must not derail setup, since the listing scan
    is the part that actually matters.
    """
    from .profile_import import (
        find_profile_url,
        merge_profile,
        missing_fields,
        scrape_profile,
        write_profile,
    )
    import yaml

    url = cfg.get("site.profile_url") or find_profile_url(page, cfg.get("site.base_url", ""))
    if not url:
        return None, []

    try:
        imported = scrape_profile(page, url)
    except Exception:
        return url, []
    if not imported:
        return url, []

    path = cfg.resolve_path("profile", "profile.yaml")
    existing = {}
    if path.exists():
        existing = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    merged, changes = merge_profile(existing, imported)
    write_profile(path, merged)

    gaps = missing_fields(merged)
    if gaps:
        changes = changes + [f"(still blank, fill in by hand: {', '.join(gaps)})"]
    return url, changes


def run(cfg: "Config", *, page: "Page", discover_fn) -> tuple[Path, dict, dict | None]:
    """Scan the listing page, then a role page found within it."""
    print("\nReading the auditions page...")
    listing = discover_fn(page, cfg)
    found = find_listing_blocks(listing)
    if found:
        print(f"  found {found} repeated block(s) that look like listings")
    else:
        print("  found nothing that looks like a listing")

    detail = None
    detail_url = pick_detail_url(listing, cfg.get("site.base_url", ""))
    if detail_url:
        print(f"\nReading one role page to map the application form:\n  {detail_url}")
        try:
            detail = discover_fn(page, cfg, url=detail_url)
        except Exception as exc:
            print(f"  couldn't open it: {exc}")
    else:
        print("\nNo role link found on the listing page, skipping the form scan.")

    print("\nLooking for your profile page...")
    try:
        profile_url, changes = import_profile_if_found(cfg, page)
    except Exception as exc:
        profile_url, changes = None, []
        print(f"  skipped: {exc}")
    if profile_url and changes:
        print(f"  read your details from {profile_url}")
        for change in changes[:12]:
            print(f"    {change}")
    elif profile_url:
        print(f"  found {profile_url} but couldn't read fields from it")
    else:
        print("  couldn't find a profile link - fill in profile.yaml by hand")

    path = write_summary(cfg, build_summary(listing, detail))
    return path, listing, detail
