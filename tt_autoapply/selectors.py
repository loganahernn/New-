"""Selector helpers.

Deliberately free of any Playwright import so the parsing logic can be tested
without a browser installed.

Every selector setting in the config is a *list of candidates*: the first one
that matches wins, which means a site redesign usually costs one extra line of
YAML rather than a code change. A selector may end with `@attr` to read an
attribute instead of the element text, e.g. `h2 a@href`.
"""

from __future__ import annotations


def parse_selector(raw: str) -> tuple[str, str | None]:
    """Split `div.x a@href` into ("div.x a", "href")."""
    if "@" in raw:
        css, _, attr = raw.rpartition("@")
        # Guard against attribute selectors like [data-x@y] — only treat a
        # trailing @attr as an attribute read when the css part is non-empty.
        if css and not attr.endswith("]"):
            return css.strip(), attr.strip()
    return raw.strip(), None


def as_list(value) -> list[str]:
    """Normalise a config value that may be a single string or a list."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value]
