"""Selector discovery.

The tool can't know Talent Talks' markup ahead of time, and the markup will
change. `discover` opens the real page with your session, finds the repeated
blocks that look like listings, and prints selector candidates to paste into
`config.yaml`. It also dumps the raw HTML so you can check by hand.
"""

from __future__ import annotations

import json
from pathlib import Path

from typing import TYPE_CHECKING

from .config import Config

if TYPE_CHECKING:  # pragma: no cover - import only needed for type checking
    from playwright.sync_api import Page

# Groups sibling elements by tag + class signature and reports the repeated
# blocks that contain a link — i.e. the shape a listing card almost always has.
_FIND_REPEATS = """
() => {
  const groups = new Map();
  for (const el of document.querySelectorAll('body *')) {
    const classes = (el.className && typeof el.className === 'string')
      ? el.className.trim().split(/\\s+/).slice(0, 3).join('.')
      : '';
    if (!classes) continue;
    const key = el.tagName.toLowerCase() + '.' + classes;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(el);
  }
  const out = [];
  for (const [selector, els] of groups) {
    if (els.length < 3) continue;
    const withLink = els.filter(e => e.querySelector('a[href]'));
    if (withLink.length < 3) continue;
    const sample = withLink[0];
    out.push({
      selector,
      count: withLink.length,
      text: (sample.innerText || '').trim().slice(0, 220),
      headings: [...sample.querySelectorAll('h1,h2,h3,h4')]
        .map(h => h.tagName.toLowerCase() + (h.className ? '.' + h.className.trim().split(/\\s+/)[0] : ''))
        .slice(0, 4),
      links: [...sample.querySelectorAll('a[href]')]
        .map(a => ({ text: (a.innerText || '').trim().slice(0, 60), href: a.getAttribute('href') }))
        .slice(0, 4),
    });
  }
  return out.sort((a, b) => b.count - a.count).slice(0, 12);
}
"""

_FIND_FORMS = """
() => [...document.querySelectorAll('form')].map(form => ({
  action: form.getAttribute('action'),
  id: form.id || null,
  classes: form.className || null,
  fields: [...form.querySelectorAll('input, textarea, select')].map(f => ({
    tag: f.tagName.toLowerCase(),
    type: f.getAttribute('type'),
    name: f.getAttribute('name'),
    id: f.id || null,
    placeholder: f.getAttribute('placeholder'),
    required: f.hasAttribute('required'),
    label: (f.labels && f.labels[0] ? f.labels[0].innerText.trim().slice(0, 60) : null),
  })),
  buttons: [...form.querySelectorAll('button, input[type=submit]')].map(b => ({
    text: (b.innerText || b.value || '').trim().slice(0, 40),
    type: b.getAttribute('type'),
    id: b.id || null,
    classes: b.className || null,
  })),
}))
"""


def _dump(page: "Page", out_dir: Path, name: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{name}.html").write_text(page.content(), encoding="utf-8")
    try:
        page.screenshot(path=str(out_dir / f"{name}.png"), full_page=True)
    except Exception:
        pass


def discover(page: "Page", cfg: Config, url: str | None = None) -> dict:
    """Inspect a page and return selector candidates."""
    target = url or cfg.listing_url
    out_dir = cfg.resolve_path("discover.output_dir", "state/discover")

    page.goto(target, wait_until="domcontentloaded")
    page.wait_for_timeout(2000)  # let any client-side rendering settle

    name = "detail" if url else "listing"
    _dump(page, out_dir, name)

    report = {
        "url": target,
        "title": page.title(),
        "repeated_blocks": page.evaluate(_FIND_REPEATS),
        "forms": page.evaluate(_FIND_FORMS),
        "saved_html": str(out_dir / f"{name}.html"),
    }
    (out_dir / f"{name}-report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report


def print_report(report: dict) -> None:
    print(f"\nPage: {report['title']}\n{report['url']}")
    print(f"HTML saved to {report['saved_html']}\n")

    blocks = report.get("repeated_blocks") or []
    if blocks:
        print("Repeated blocks (likely listing cards) — paste one into selectors.listing_item:")
        for block in blocks:
            print(f"\n  {block['selector']}   x{block['count']}")
            if block.get("headings"):
                print(f"    headings: {', '.join(block['headings'])}")
            for link in block.get("links", []):
                print(f"    link: {link['text']!r} -> {link['href']}")
            preview = " ".join(block["text"].split())[:160]
            if preview:
                print(f"    text: {preview}")
    else:
        print("No repeated link-bearing blocks found.")
        print("The listings may be behind a login, or rendered after a delay.")
        print("Check the saved HTML/screenshot, and try `login` first.")

    forms = report.get("forms") or []
    if forms:
        print("\nForms on this page — use these for application.form.fields:")
        for form in forms:
            ident = form.get("id") or form.get("classes") or form.get("action") or "<form>"
            print(f"\n  form: {ident}")
            for field in form.get("fields", []):
                bits = [field["tag"]]
                if field.get("type"):
                    bits.append(f"type={field['type']}")
                if field.get("name"):
                    bits.append(f"name={field['name']}")
                if field.get("id"):
                    bits.append(f"id={field['id']}")
                if field.get("required"):
                    bits.append("required")
                label = field.get("label") or field.get("placeholder") or ""
                print(f"    {' '.join(bits)}  {label}")
            for button in form.get("buttons", []):
                print(f"    button: {button['text']!r} type={button.get('type')}")
    print()
