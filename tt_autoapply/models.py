"""Core data types shared across the scraper, matcher and applier."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Role:
    """A single audition/casting listing."""

    url: str
    title: str
    description: str = ""
    company: str | None = None
    location: str | None = None
    pay: str | None = None
    deadline: str | None = None
    posted: str | None = None
    tags: list[str] = field(default_factory=list)
    scraped_at: str = field(default_factory=_now)

    @property
    def id(self) -> str:
        """Stable identifier so a role is only ever applied to once.

        Keyed on the URL where possible, falling back to the title when a
        listing has no permalink (some briefs are inline-only).
        """
        basis = self.url.strip() or f"{self.title.strip()}|{self.company or ''}"
        return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]

    @property
    def searchable_text(self) -> str:
        """Everything a matcher should read, lowercased."""
        parts = [
            self.title,
            self.company or "",
            self.location or "",
            self.pay or "",
            self.deadline or "",
            " ".join(self.tags),
            self.description,
        ]
        return "\n".join(p for p in parts if p).lower()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["id"] = self.id
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Role":
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**known)


@dataclass
class MatchResult:
    """Why we did or didn't decide to apply to a role."""

    role_id: str
    fits: bool
    score: float
    reasons: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    source: str = "rules"  # "rules" | "llm" | "rules+llm"
    cover_letter: str = ""  # set when the LLM drafted one for this role

    def summary(self) -> str:
        verdict = "FIT" if self.fits else "SKIP"
        detail = "; ".join(self.blockers or self.reasons) or "no signals"
        return f"[{verdict} {self.score:.2f}] {detail}"


@dataclass
class ApplicationResult:
    """Outcome of an attempt to submit an application."""

    role_id: str
    status: str  # applied | dry_run | failed | skipped
    detail: str = ""
    cover_letter: str = ""
    submitted_at: str = field(default_factory=_now)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)
