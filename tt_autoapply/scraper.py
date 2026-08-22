"""Listing extraction.

Selector resolution lives in `selectors.py`; this module walks the page with it.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING
from urllib.parse import urljoin

from .config import Config
from .labels import extract_pairs, map_pairs
from .models import Role
from .selectors import as_list, parse_selector

# Labels the site uses for the facts that decide a match.
ROLE_FIELD_ALIASES: dict[str, list[str]] = {
    "location": ["location", "where", "region"],
    "pay": ["payment", "pay", "fee", "rate", "salary"],
    "age": ["age", "playing age", "age range"],
    "gender": ["gender", "sex"],
    "ethnicity": ["ethnicity", "ethnic appearance", "appearance"],
    "deadline": ["deadline", "closing date", "closes", "apply by"],
    "posted": ["posted", "date posted", "published"],
    "category": ["job category", "category", "job type"],
    "shoot_date": ["shoot date", "shoot dates", "shooting dates", "dates"],
}

if TYPE_CHECKING:  # pragma: no cover - import only needed for type checking
    from playwright.sync_api import Locator, Page


def first_match(scope: "Page | Locator", candidates) -> str | None:
    """Return the text (or attribute) of the first candidate selector that hits."""
    for raw in as_list(candidates):
        css, attr = parse_selector(raw)
        try:
            locator = scope.locator(css).first
            if locator.count() == 0:
                continue
            value = locator.get_attribute(attr) if attr else locator.inner_text()
        except Exception:
            continue
        if value and value.strip():
            return value.strip()
    return None


def all_matches(scope: "Page | Locator", candidates) -> list[str]:
    """Return the texts of every element matching the first candidate that hits."""
    for raw in as_list(candidates):
        css, attr = parse_selector(raw)
        try:
            locator = scope.locator(css)
            count = locator.count()
            if count == 0:
                continue
            values = []
            for i in range(count):
                item = locator.nth(i)
                value = item.get_attribute(attr) if attr else item.inner_text()
                if value and value.strip():
                    values.append(value.strip())
            if values:
                return values
        except Exception:
            continue
    return []


def _listing_locator(page: "Page", cfg: Config) -> "Locator | None":
    for raw in as_list(cfg.get("selectors.listing_item")):
        css, _ = parse_selector(raw)
        try:
            locator = page.locator(css)
            if locator.count() > 0:
                return locator
        except Exception:
            continue
    return None


def scrape_listing_page(page: "Page", cfg: Config, url: str) -> list[Role]:
    """Scrape one page of the auditions index into shallow Role objects."""
    page.goto(url, wait_until="domcontentloaded")
    wait_for = cfg.get("selectors.listing_ready")
    if wait_for:
        for raw in as_list(wait_for):
            css, _ = parse_selector(raw)
            try:
                page.wait_for_selector(css, timeout=int(cfg.get("site.timeout_ms", 30000)))
                break
            except Exception:
                continue

    items = _listing_locator(page, cfg)
    if items is None:
        return []

    base = cfg.get("site.base_url", "")
    roles: list[Role] = []
    for i in range(items.count()):
        card = items.nth(i)
        title = first_match(card, cfg.get("selectors.title")) or ""
        href = first_match(card, cfg.get("selectors.link")) or ""
        if not title and not href:
            continue
        roles.append(
            Role(
                url=urljoin(base, href) if href else "",
                title=title,
                company=first_match(card, cfg.get("selectors.company")),
                location=first_match(card, cfg.get("selectors.location")),
                pay=first_match(card, cfg.get("selectors.pay")),
                deadline=first_match(card, cfg.get("selectors.deadline")),
                posted=first_match(card, cfg.get("selectors.posted")),
                description=first_match(card, cfg.get("selectors.summary")) or "",
                tags=all_matches(card, cfg.get("selectors.tags")),
            )
        )
    return roles


def _page_urls(cfg: Config) -> list[str]:
    base_url = cfg.listing_url
    mode = cfg.get("site.pagination.mode", "none")
    max_pages = int(cfg.get("site.pagination.max_pages", 1) or 1)
    if mode != "query" or max_pages <= 1:
        return [base_url]

    param = cfg.get("site.pagination.param", "page")
    urls = [base_url]
    joiner = "&" if "?" in base_url else "?"
    for n in range(2, max_pages + 1):
        urls.append(f"{base_url}{joiner}{param}={n}")
    return urls


def scrape_roles(page: "Page", cfg: Config) -> list[Role]:
    """Scrape every configured listing page, de-duplicated by role id."""
    delay = float(cfg.get("site.request_delay_seconds", 3.0) or 0)
    seen: dict[str, Role] = {}
    for index, url in enumerate(_page_urls(cfg)):
        if index:
            time.sleep(delay)
        for role in scrape_listing_page(page, cfg, url):
            seen.setdefault(role.id, role)
    return list(seen.values())


def enrich_role(page: "Page", cfg: Config, role: Role) -> Role:
    """Open a role's detail page and pull the full brief text.

    Without the full brief the matcher is guessing from a one-line teaser, so
    this runs for every candidate role before any matching decision.
    """
    if not role.url:
        return role

    page.goto(role.url, wait_until="domcontentloaded")
    detail = cfg.get("selectors.detail", {}) or {}

    description = first_match(page, detail.get("description"))
    if not description:
        # Fall back to the whole body: a noisy brief beats an empty one.
        try:
            description = page.locator("body").inner_text()
        except Exception:
            description = role.description

    # The site's own DETAILS panel beats anything parsed out of the prose.
    role.fields = map_pairs(extract_pairs(page), ROLE_FIELD_ALIASES)

    role.description = description or role.description
    role.company = first_match(page, detail.get("company")) or role.company
    role.location = (
        role.fields.get("location") or first_match(page, detail.get("location")) or role.location
    )
    role.pay = role.fields.get("pay") or first_match(page, detail.get("pay")) or role.pay
    role.deadline = (
        role.fields.get("deadline") or first_match(page, detail.get("deadline")) or role.deadline
    )
    role.posted = (
        role.fields.get("posted") or first_match(page, detail.get("posted")) or role.posted
    )
    if role.fields.get("category"):
        role.tags = sorted(set(role.tags) | {role.fields["category"]})
    extra_tags = all_matches(page, detail.get("tags"))
    if extra_tags:
        role.tags = sorted(set(role.tags) | set(extra_tags))
    return role
