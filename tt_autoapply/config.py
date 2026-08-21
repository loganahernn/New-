"""Configuration loading.

Everything site-specific (URLs, CSS selectors, form field mapping) lives in
YAML rather than in code, so the tool survives a site redesign without a code
change — run `tt-autoapply discover` to regenerate selector candidates.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

DEFAULTS: dict[str, Any] = {
    "site": {
        "base_url": "https://www.talenttalks.co.uk",
        "auditions_path": "/auditions/",
        "pagination": {"mode": "none", "param": "page", "max_pages": 3},
        "request_delay_seconds": 3.0,
        "timeout_ms": 30000,
    },
    "browser": {
        "headless": True,
        "storage_state": "state/session.json",
        "user_agent": None,
        "slow_mo_ms": 0,
    },
    # 0 means no cap: apply to every brief that fits. The delay between
    # submissions stays — that's about not hammering the site, not about volume.
    "limits": {
        "max_applications_per_run": 0,
        "max_applications_per_day": 0,
        "seconds_between_applications": 45,
    },
    "matching": {
        "mode": "rules",  # rules | llm | rules+llm
        "min_score": 0.6,
        "llm_model": "claude-opus-5",
        "llm_effort": "low",
    },
    "application": {
        "mode": "form",  # form | email | manual
        "require_confirmation": False,
    },
    "storage": {"database": "state/applications.db"},
    "notify": {"console": True},
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _expand_env(value: Any) -> Any:
    """Expand ${VAR} references so secrets stay out of the YAML file."""
    if isinstance(value, str):
        return _ENV_PATTERN.sub(lambda m: os.environ.get(m.group(1), ""), value)
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    return value


class Config:
    """Thin wrapper over the merged config dict with dotted-path lookup."""

    def __init__(self, data: dict, path: Path | None = None):
        self.data = data
        self.path = path
        self.root = path.parent if path else Path.cwd()

    @classmethod
    def load(cls, path: str | Path) -> "Config":
        p = Path(path).expanduser()
        if not p.exists():
            raise FileNotFoundError(
                f"Config not found: {p}\n"
                "Copy config.example.yaml to config.yaml and edit it."
            )
        with p.open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        merged = _deep_merge(DEFAULTS, _expand_env(raw))
        return cls(merged, p.resolve())

    def get(self, dotted: str, default: Any = None) -> Any:
        node: Any = self.data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def resolve_path(self, dotted: str, default: str | None = None) -> Path:
        """Resolve a path from config relative to the config file's directory."""
        value = self.get(dotted, default)
        if value is None:
            raise KeyError(f"Missing path setting: {dotted}")
        p = Path(str(value)).expanduser()
        return p if p.is_absolute() else (self.root / p)

    @property
    def listing_url(self) -> str:
        base = str(self.get("site.base_url", "")).rstrip("/")
        path = str(self.get("site.auditions_path", "/"))
        if not path.startswith("/"):
            path = "/" + path
        return base + path

    def load_profile(self) -> dict:
        """Load the performer profile referenced by the config."""
        p = self.resolve_path("profile", "profile.yaml")
        if not p.exists():
            raise FileNotFoundError(
                f"Profile not found: {p}\n"
                "Copy profile.example.yaml to profile.yaml and fill it in."
            )
        with p.open("r", encoding="utf-8") as fh:
            return _expand_env(yaml.safe_load(fh) or {})
