"""Cover-letter rendering.

A Jinja2 template gets the role and your profile, so notes reference the actual
production rather than reading as an obvious mailshot. If the LLM matcher is
enabled it writes the note instead and this is the fallback.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import ChainableUndefined, Environment, TemplateError

from .models import Role


class SilentUndefined(ChainableUndefined):
    """Missing profile fields render as empty instead of raising.

    Chainable so a partly-filled profile (`profile.playing_age.min` with no
    `playing_age`) degrades to a blank rather than killing the whole run — a
    half-populated note still beats a crashed batch.
    """

    def __str__(self) -> str:
        return ""

DEFAULT_TEMPLATE = """Dear {{ role.company or 'Casting Team' }},

I'd like to be considered for {{ role.title }}.

I'm {{ profile.name }}, a {{ profile.gender }} performer with a playing age of \
{{ profile.playing_age.min }}-{{ profile.playing_age.max }}, based in {{ profile.base }}.\
{% if profile.skills %} Relevant skills: {{ profile.skills | join(', ') }}.{% endif %}
{% if profile.credits %}
Recent credits:
{% for credit in profile.credits[:3] %}  - {{ credit }}
{% endfor %}{% endif %}
My Spotlight/showreel links and full CV are attached to my profile.

Thank you for your time,
{{ profile.name }}
{{ profile.email }}{% if profile.phone %} | {{ profile.phone }}{% endif %}
"""


def _env() -> Environment:
    return Environment(undefined=SilentUndefined, trim_blocks=False, lstrip_blocks=False)


def render(role: Role, profile: dict, template_path: Path | None = None) -> str:
    """Render the cover letter for a role.

    Falls back to the built-in template if the configured one is missing or
    references a field your profile doesn't define — a missing note shouldn't
    stop an otherwise good application.
    """
    source = DEFAULT_TEMPLATE
    if template_path and Path(template_path).exists():
        source = Path(template_path).read_text(encoding="utf-8")

    context = {"role": role, "profile": profile}
    try:
        return _env().from_string(source).render(**context).strip()
    except TemplateError:
        if source is DEFAULT_TEMPLATE:
            raise
        return _env().from_string(DEFAULT_TEMPLATE).render(**context).strip()
