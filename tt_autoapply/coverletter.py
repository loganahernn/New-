"""What goes in the application text box.

Talent Talks sends your whole profile to the casting company automatically, so
the box is only for extra information. The default note is therefore short —
a full cover letter restating what's already in the profile just adds noise.

Some briefs do ask for specifics ("state your height", "tell us your
availability that week"). Those need a real answer, so they're detected and
flagged rather than answered with a bare "Available".
"""

from __future__ import annotations

import re
from pathlib import Path

from jinja2 import ChainableUndefined, Environment, TemplateError

from .models import Role

DEFAULT_NOTE = "Available"

# Phrasing that means the brief wants something specific written in the box.
_ASKS_FOR_INFO = [
    r"please (state|include|send|provide|confirm|specify|tell|let us know|attach)",
    r"\b(state|include|specify|confirm) your\b",
    r"\blet us know\b",
    r"\btell us\b",
    r"\bwe need to know\b",
    r"\bin your (application|message|note)\b",
    r"\bwhen applying,? please\b",
    r"\bapplicants? (should|must) (state|include|provide|confirm)\b",
    r"\bplease answer\b",
    r"\bquestions?:\s",
    r"\bwhy you\b",
    r"\bmust be able to (confirm|provide)\b",
]
_ASKS_PATTERN = re.compile("|".join(_ASKS_FOR_INFO), re.IGNORECASE)


class SilentUndefined(ChainableUndefined):
    """Missing profile fields render as empty instead of raising.

    Chainable so a partly-filled profile (`profile.playing_age.min` with no
    `playing_age`) degrades to a blank rather than killing the whole run — a
    half-populated note still beats a crashed batch.
    """

    def __str__(self) -> str:
        return ""


def _env() -> Environment:
    return Environment(undefined=SilentUndefined, trim_blocks=False, lstrip_blocks=False)


def brief_asks_for_details(role: Role) -> str | None:
    """The phrase showing a brief wants specific information, if any.

    Returns the matched phrase so the reason can be shown to the user, rather
    than a bare True that leaves them guessing what was spotted.
    """
    match = _ASKS_PATTERN.search(role.description or "")
    return match.group(0).strip() if match else None


def render(
    role: Role,
    profile: dict,
    template_path: Path | None = None,
    *,
    note: str = DEFAULT_NOTE,
) -> str:
    """Build the note for this role's application box.

    Without a template file this is just the configured note — deliberately.
    The casting company already receives the full profile.
    """
    if template_path and Path(template_path).exists():
        source = Path(template_path).read_text(encoding="utf-8")
        context = {"role": role, "profile": profile, "note": note}
        try:
            rendered = _env().from_string(source).render(**context).strip()
        except TemplateError:
            return note
        return rendered or note
    return note
