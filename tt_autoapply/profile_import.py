"""Build profile.yaml from your existing Talent Talks profile.

You've already typed your playing age, height, accents and credits into their
site. Retyping them into a YAML file is both tedious and a chance to introduce a
mismatch between what casting sees and what the matcher believes.

This reads your own profile page with your saved session and maps whatever it
finds onto the profile schema. The label→field mapping is heuristic (their
markup isn't knowable from here), so it prints exactly what it found and what it
couldn't fill, and never silently discards a value you'd already set.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:  # pragma: no cover - import only needed for type checking
    from playwright.sync_api import Page

# Pulls label/value pairs out of the shapes profile pages actually use:
# definition lists, two-column tables, and label/value div pairs.
_EXTRACT_PAIRS = """
() => {
  const pairs = [];
  const clean = (s) => (s || '').replace(/\\s+/g, ' ').trim();

  for (const dl of document.querySelectorAll('dl')) {
    const dts = [...dl.querySelectorAll('dt')];
    const dds = [...dl.querySelectorAll('dd')];
    dts.forEach((dt, i) => {
      if (dds[i]) pairs.push([clean(dt.innerText), clean(dds[i].innerText)]);
    });
  }

  for (const row of document.querySelectorAll('tr')) {
    const cells = [...row.querySelectorAll('th, td')];
    if (cells.length === 2) {
      pairs.push([clean(cells[0].innerText), clean(cells[1].innerText)]);
    }
  }

  for (const el of document.querySelectorAll('[class*="label"], [class*="field"]')) {
    const value = el.nextElementSibling;
    if (value && !value.querySelector('*')) {
      pairs.push([clean(el.innerText), clean(value.innerText)]);
    }
  }

  // "Playing age: 18-25" style lines anywhere on the page.
  for (const el of document.querySelectorAll('li, p, span, div')) {
    if (el.children.length) continue;
    const text = clean(el.innerText);
    const m = text.match(/^([A-Za-z][A-Za-z /'-]{2,30}):\\s*(.+)$/);
    if (m && m[2].length < 400) pairs.push([m[1], m[2]]);
  }

  return pairs.filter(([k, v]) => k && v);
}
"""

_CREDIT_SELECTORS = """
() => {
  const clean = (s) => (s || '').replace(/\\s+/g, ' ').trim();
  const out = [];
  for (const el of document.querySelectorAll(
      '[class*="credit"] li, [class*="credit"] tr, [class*="experience"] li')) {
    const text = clean(el.innerText);
    if (text && text.length < 200) out.push(text);
  }
  return out;
}
"""

# Profile field <- the labels a casting site might use for it.
_LABEL_MAP: dict[str, list[str]] = {
    "name": ["name", "full name", "performer name", "stage name"],
    "email": ["email", "e-mail", "email address"],
    "phone": ["phone", "telephone", "mobile", "contact number"],
    "base": ["base", "based", "location", "based in", "home town", "region"],
    "gender": ["gender", "sex", "casting gender"],
    "ethnicity": ["ethnicity", "ethnic appearance", "appearance", "playing ethnicity"],
    "playing_age": ["playing age", "playing age range", "age range", "casting age"],
    "age": ["age", "actual age", "real age"],
    "height_cm": ["height"],
    "hair": ["hair", "hair colour", "hair color"],
    "eyes": ["eyes", "eye colour", "eye color"],
    "accents": ["accents", "accent", "dialects"],
    "skills": ["skills", "special skills", "other skills", "abilities", "sports"],
    "training": ["training", "education", "drama school"],
    "union": ["union", "equity", "membership"],
    "spotlight_pin": ["spotlight", "spotlight pin", "spotlight number"],
    "showreel": ["showreel", "show reel", "reel", "video"],
}

_LIST_FIELDS = {"accents", "skills"}


# Where a logged-in user's own details live. Ordered: the earlier the pattern,
# the more likely that link is the profile rather than a settings page.
_PROFILE_HINTS = [
    "my-profile", "myprofile", "my-account", "myaccount", "my-details",
    "profile", "account", "dashboard", "my-cv", "portfolio",
]
_NOT_PROFILE = ("logout", "signout", "sign-out", "login", "register", "password")

_FIND_ACCOUNT_LINKS = """
() => [...document.querySelectorAll('a[href]')].map(a => ({
  text: (a.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 60),
  href: a.getAttribute('href') || '',
})).filter(l => l.href)
"""


def pick_profile_link(links: list[dict], base_url: str) -> str | None:
    """Choose the logged-in user's own profile page from a page's links.

    Saves the user finding and pasting their profile URL. Scored rather than
    first-match so "My Profile" beats a generic "Account settings" link.
    """
    best: tuple[int, str] | None = None
    for link in links:
        href = (link.get("href") or "").strip()
        text = (link.get("text") or "").lower()
        if not href:
            continue
        haystack = f"{href.lower()} {text}"
        if any(bad in haystack for bad in _NOT_PROFILE):
            continue
        for rank, hint in enumerate(_PROFILE_HINTS):
            if hint in haystack.replace(" ", "-"):
                if best is None or rank < best[0]:
                    best = (rank, urljoin(base_url, href))
                break
    return best[1] if best else None


def find_profile_url(page: "Page", base_url: str) -> str | None:
    """Look for the user's own profile link on whatever page is open."""
    try:
        links = page.evaluate(_FIND_ACCOUNT_LINKS)
    except Exception:
        return None
    return pick_profile_link(links, base_url)


def normalise_label(label: str) -> str:
    return re.sub(r"[^a-z ]", "", (label or "").lower()).strip()


def parse_playing_age(value: str) -> dict | None:
    """"18 - 25" / "18 to 25" / "18-25 years" -> {"min": 18, "max": 25}."""
    m = re.search(r"(\d{1,2})\s*(?:-|–|—|to)\s*(\d{1,2})", value or "")
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        if lo <= hi <= 99:
            return {"min": lo, "max": hi}
    m = re.search(r"\b(\d{1,2})\b", value or "")
    if m:
        age = int(m.group(1))
        return {"min": age, "max": age}
    return None


def parse_height_cm(value: str) -> int | None:
    """Accepts 180cm, 1.80m, 5'11" and returns centimetres."""
    text = (value or "").lower()

    m = re.search(r"(\d{2,3})\s*cm", text)
    if m:
        return int(m.group(1))

    m = re.search(r"(\d)\s*[.,]\s*(\d{1,2})\s*m\b", text)
    if m:
        return round(float(f"{m.group(1)}.{m.group(2).ljust(2, '0')}") * 100)

    m = re.search(r"(\d)\s*(?:'|ft|feet)\s*(\d{1,2})?", text)
    if m:
        feet = int(m.group(1))
        inches = int(m.group(2)) if m.group(2) else 0
        return round(feet * 30.48 + inches * 2.54)

    m = re.search(r"^\s*(\d{3})\s*$", text)
    return int(m.group(1)) if m else None


def parse_list(value: str) -> list[str]:
    """Split a comma/newline/bullet separated field into clean entries."""
    parts = re.split(r"[,;\n•·|]+", value or "")
    seen: list[str] = []
    for part in parts:
        cleaned = part.strip(" \t-–—")
        if cleaned and cleaned.lower() not in {p.lower() for p in seen}:
            seen.append(cleaned)
    return seen


def map_pairs(pairs: list[tuple[str, str]]) -> dict:
    """Map scraped label/value pairs onto the profile schema."""
    lookup: dict[str, str] = {}
    for label, value in _LABEL_MAP.items():
        for alias in value:
            lookup[alias] = label

    found: dict = {}
    for raw_label, raw_value in pairs:
        field = lookup.get(normalise_label(raw_label))
        if not field or not raw_value:
            continue
        # First occurrence wins — page headers are more reliable than footers.
        if field in found:
            continue

        if field == "playing_age":
            parsed = parse_playing_age(raw_value)
            if parsed:
                found[field] = parsed
        elif field == "height_cm":
            parsed = parse_height_cm(raw_value)
            if parsed:
                found[field] = parsed
        elif field == "age":
            m = re.search(r"\b(\d{1,2})\b", raw_value)
            if m:
                found[field] = int(m.group(1))
        elif field in _LIST_FIELDS:
            parsed_list = parse_list(raw_value)
            if parsed_list:
                found[field] = parsed_list
        else:
            found[field] = raw_value.strip()

    return found


def _is_empty(value) -> bool:
    return value is None or value == "" or value == [] or value == {}


def merge_profile(existing: dict, imported: dict) -> tuple[dict, list[str]]:
    """Merge imported values over an existing profile.

    Imported values win where present — that's the point of importing — but an
    empty import never blanks out something you'd already filled in. Returns the
    merged profile and a human-readable list of what changed.
    """
    merged = dict(existing or {})
    changes: list[str] = []

    for key, new_value in (imported or {}).items():
        if _is_empty(new_value):
            continue
        old_value = merged.get(key)
        if _is_empty(old_value):
            changes.append(f"{key}: (unset) -> {new_value}")
        elif old_value != new_value:
            changes.append(f"{key}: {old_value} -> {new_value}")
        else:
            continue
        merged[key] = new_value

    return merged, changes


def missing_fields(profile: dict) -> list[str]:
    """Fields the matcher and cover letters rely on that are still blank."""
    required = ["name", "email", "base", "gender", "ethnicity", "playing_age"]
    return [f for f in required if _is_empty(profile.get(f))]


def scrape_profile(page: "Page", url: str) -> dict:
    """Read the performer's own profile page into profile fields."""
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_timeout(1500)

    pairs = [(str(a), str(b)) for a, b in page.evaluate(_EXTRACT_PAIRS)]
    imported = map_pairs(pairs)

    credits = [c for c in page.evaluate(_CREDIT_SELECTORS) if c]
    if credits:
        imported["credits"] = credits[:20]

    return imported


def write_profile(path: Path, profile: dict) -> Path | None:
    """Write the profile, backing up any existing file first."""
    path = Path(path)
    backup = None
    if path.exists():
        backup = path.with_suffix(path.suffix + ".bak")
        backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(profile, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    return backup
