"""Reading label/value pairs out of a page.

Talent Talks states the things that decide a match — AGE, GENDER, LOCATION,
PAYMENT, DEADLINE — as labelled fields in a DETAILS panel. Reading those
directly is far more reliable than regexing the prose, so this is the primary
source and the text scan in `matcher` is the fallback.

The same extraction serves the profile importer, which faces the same shapes.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - import only needed for type checking
    from playwright.sync_api import Page

# Covers the four layouts these pages use: definition lists, two-column tables,
# a bold "LABEL:" element with its value in the next element, and a single
# element containing "Label: value".
EXTRACT_PAIRS_JS = """
() => {
  const clean = (s) => (s || '').replace(/\\s+/g, ' ').trim();
  const pairs = [];
  const add = (k, v) => { if (k && v) pairs.push([clean(k), clean(v)]); };

  for (const dl of document.querySelectorAll('dl')) {
    const dts = [...dl.querySelectorAll('dt')];
    const dds = [...dl.querySelectorAll('dd')];
    dts.forEach((dt, i) => { if (dds[i]) add(dt.innerText, dds[i].innerText); });
  }

  for (const row of document.querySelectorAll('tr')) {
    const cells = [...row.querySelectorAll('th, td')];
    if (cells.length === 2) add(cells[0].innerText, cells[1].innerText);
  }

  // "LOCATION:" in one element, "London" in the next.
  for (const el of document.querySelectorAll('*')) {
    if (el.children.length) continue;
    const text = clean(el.innerText);
    if (!text.endsWith(':') || text.length > 40) continue;
    let sib = el.nextElementSibling;
    while (sib && !clean(sib.innerText)) sib = sib.nextElementSibling;
    if (sib) add(text.slice(0, -1), sib.innerText);
  }

  // "Playing age: 18-25" in a single element.
  for (const el of document.querySelectorAll('li, p, span, div, td')) {
    if (el.children.length) continue;
    const text = clean(el.innerText);
    const m = text.match(/^([A-Za-z][A-Za-z /'-]{2,30}):\\s*(.+)$/);
    if (m && m[2].length < 400) add(m[1], m[2]);
  }

  return pairs;
}
"""

# Values that mean "not stated" and should be treated as absent.
_EMPTY_VALUES = {"n/a", "na", "-", "--", "none", "not stated", "tbc", "tba", ""}


def normalise_label(label: str) -> str:
    """"SHOOT DATE:" -> "shoot date", so labels compare regardless of styling."""
    return re.sub(r"[^a-z ]", " ", (label or "").lower()).strip()


def is_empty_value(value: str) -> bool:
    return (value or "").strip().lower() in _EMPTY_VALUES


def extract_pairs(page: "Page") -> list[tuple[str, str]]:
    """Every label/value pair on the page, in document order."""
    try:
        raw = page.evaluate(EXTRACT_PAIRS_JS)
    except Exception:
        return []
    return [(str(k), str(v)) for k, v in raw if k and v]


def build_lookup(aliases: dict[str, list[str]]) -> dict[str, str]:
    """Turn {field: [labels]} into {normalised label: field}."""
    return {
        normalise_label(alias): field
        for field, labels in aliases.items()
        for alias in labels
    }


def map_pairs(pairs, aliases: dict[str, list[str]]) -> dict[str, str]:
    """Map label/value pairs onto field names, first occurrence winning.

    First wins because these pages repeat key facts lower down (a footer, a
    related-jobs block) and the panel at the top is the authoritative one.
    """
    lookup = build_lookup(aliases)
    found: dict[str, str] = {}
    for label, value in pairs:
        field = lookup.get(normalise_label(label))
        if not field or field in found or is_empty_value(value):
            continue
        found[field] = value.strip()
    return found
