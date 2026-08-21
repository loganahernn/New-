"""Optional LLM brief matching.

Rules catch the mechanical filters (age, gender, pay, travel). A lot of casting
briefs are free text though — "must be comfortable with heights", "northern
accent essential", "playing a junior doctor" — and that's what this is for.

Requires `pip install 'tt-autoapply[llm]'` and an Anthropic API key. If the SDK
or key is missing, the caller falls back to rules-only matching.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from .models import MatchResult, Role

MODEL = "claude-opus-5"

_SCHEMA = {
    "type": "object",
    "properties": {
        "fits": {
            "type": "boolean",
            "description": "True only if the performer plausibly meets every stated requirement.",
        },
        "confidence": {
            "type": "number",
            "description": "0.0-1.0 confidence in the fits verdict.",
        },
        "reasons": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Short bullets on why the performer does or doesn't fit.",
        },
        "concerns": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Requirements that are unmet, unclear, or a stretch.",
        },
        "cover_letter": {
            "type": "string",
            "description": (
                "A short, specific application note in the performer's voice. "
                "Empty string if fits is false."
            ),
        },
    },
    "required": ["fits", "confidence", "reasons", "concerns", "cover_letter"],
    "additionalProperties": False,
}

SYSTEM = """You screen casting briefs for a single performer and decide whether they should apply.

Be strict. A performer applying to roles they clearly don't fit wastes a casting director's
time and damages the performer's reputation. Set `fits` to false when the brief states a
requirement the performer does not meet (playing age, gender, ethnicity where specified as a
character requirement, accent, a hard skill like horse riding or a driving licence, union
status, or a location they cannot reach).

Do not invent credits, skills, or experience the performer's profile does not list. The cover
letter must only reference things in their profile, be under 150 words, and name something
specific from the brief so it does not read as a form letter."""


@dataclass
class LLMVerdict:
    fits: bool
    confidence: float
    reasons: list[str]
    concerns: list[str]
    cover_letter: str


class LLMUnavailable(RuntimeError):
    """The anthropic SDK or an API key is not available."""


def _client():
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - depends on install extras
        raise LLMUnavailable(
            "anthropic SDK not installed - run: pip install 'tt-autoapply[llm]'"
        ) from exc
    try:
        return anthropic.Anthropic()
    except Exception as exc:  # missing credentials
        raise LLMUnavailable(f"could not initialise Anthropic client: {exc}") from exc


def _prompt(role: Role, profile: dict) -> str:
    return (
        "PERFORMER PROFILE (the only facts you may use about them):\n"
        f"{json.dumps(profile, indent=2, default=str)}\n\n"
        "CASTING BRIEF:\n"
        f"Title: {role.title}\n"
        f"Company: {role.company or 'not stated'}\n"
        f"Location: {role.location or 'not stated'}\n"
        f"Pay: {role.pay or 'not stated'}\n"
        f"Deadline: {role.deadline or 'not stated'}\n"
        f"URL: {role.url}\n\n"
        f"{role.description[:12000]}\n\n"
        "Decide whether this performer should apply, and if so draft their application note."
    )


def assess(role: Role, profile: dict, *, model: str = MODEL, effort: str = "low") -> LLMVerdict:
    """Ask Claude whether the performer fits the brief. Raises LLMUnavailable."""
    client = _client()
    response = client.beta.messages.create(
        model=model,
        max_tokens=16000,
        system=SYSTEM,
        messages=[{"role": "user", "content": _prompt(role, profile)}],
        thinking={"type": "adaptive"},
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": _SCHEMA}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )

    if getattr(response, "stop_reason", None) == "refusal":
        raise LLMUnavailable("model declined to assess this brief")

    text = next((b.text for b in response.content if b.type == "text"), None)
    if not text:
        raise LLMUnavailable("no text block in response")

    data = json.loads(text)
    return LLMVerdict(
        fits=bool(data["fits"]),
        confidence=float(data["confidence"]),
        reasons=list(data["reasons"]),
        concerns=list(data["concerns"]),
        cover_letter=str(data["cover_letter"]),
    )


def combine(rules_result: MatchResult, verdict: LLMVerdict) -> MatchResult:
    """Both must agree before we apply — the LLM can veto, never override a blocker."""
    return MatchResult(
        role_id=rules_result.role_id,
        fits=rules_result.fits and verdict.fits,
        score=round((rules_result.score + verdict.confidence) / 2, 3),
        reasons=rules_result.reasons + [f"llm: {r}" for r in verdict.reasons],
        blockers=rules_result.blockers + [f"llm: {c}" for c in verdict.concerns if not verdict.fits],
        source="rules+llm",
    )
